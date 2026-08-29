import json
import time
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Depends, Request, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

from app.config import settings
from app.vector_store import VectorCacheManager
from app.normalizer import normalize_text
from app.guardrails import is_volatile_query, BudgetGuardrailManager
from app.db import init_db, log_metrics_async
from app.auth import get_tenant_id_from_key  # 👈 Added Auth Dependency Import

# Standard LLM Pricing per 1k tokens (Estimated GPT-4o class rate for savings calculation)
COST_PER_PROMPT_TOKEN = 0.005 / 1000
COST_PER_COMPLETION_TOKEN = 0.015 / 1000


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database
    init_db()
    app.state.vector_cache = VectorCacheManager()
    app.state.budget_manager = BudgetGuardrailManager(daily_token_limit=100000)
    app.state.http_client = httpx.AsyncClient(
        base_url=settings.UPSTREAM_BASE_URL,
        headers={"Authorization": f"Bearer {settings.UPSTREAM_API_KEY}"},
        timeout=httpx.Timeout(60.0, connect=5.0)
    )
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="ZeroToken Gateway",
    version="0.1.0",
    description="Sub-15ms Enterprise Multi-Tenant Semantic Cache Proxy",
    lifespan=lifespan
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ZeroToken Gateway"}


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request, 
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id_from_key)  # 👈 Automatically validates API Key and extracts tenant_id
):
    start_time = time.perf_counter()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    is_stream = body.get("stream", False)
    client: httpx.AsyncClient = request.app.state.http_client
    vector_cache: VectorCacheManager = request.app.state.vector_cache
    budget_manager: BudgetGuardrailManager = request.app.state.budget_manager

    # 1. Budget Guardrail Enforcement
    allowed, current_usage, max_limit = budget_manager.check_budget(tenant_id=tenant_id, estimated_tokens=100)
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "message": f"Daily token budget exceeded for tenant '{tenant_id}'. Used {current_usage}/{max_limit} tokens.",
                    "type": "budget_exceeded",
                    "code": 429
                }
            },
            headers={"X-Tenant-ID": tenant_id}
        )

    messages = body.get("messages", [])
    raw_user_prompt = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            raw_user_prompt = msg.get("content", "")
            break

    cleaned_prompt = normalize_text(raw_user_prompt) if raw_user_prompt else ""
    volatile = is_volatile_query(cleaned_prompt) if cleaned_prompt else False

    # 2. Check Semantic Cache
    if not is_stream and cleaned_prompt and not volatile:
        cached_result = vector_cache.search_similar(
            query_text=cleaned_prompt,
            similarity_threshold=0.85,
            tenant_id=tenant_id
        )
        if cached_result:
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Estimate saved tokens and costs
            est_prompt_tokens = len(cleaned_prompt.split()) * 2
            est_comp_tokens = 150
            cost_saved = (est_prompt_tokens * COST_PER_PROMPT_TOKEN) + (est_comp_tokens * COST_PER_COMPLETION_TOKEN)

            # Log metrics asynchronously in background
            background_tasks.add_task(
                log_metrics_async,
                tenant_id=tenant_id,
                cache_status="HIT",
                latency_ms=latency_ms,
                similarity_score=cached_result["score"],
                prompt_tokens=est_prompt_tokens,
                completion_tokens=est_comp_tokens,
                cost_saved_usd=cost_saved
            )

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=cached_result["cached_response"],
                headers={
                    "X-Cache": "HIT",
                    "X-Cache-Score": str(round(cached_result["score"], 4)),
                    "X-Tenant-ID": tenant_id
                }
            )

    # 3. Cache Miss / Volatile Query -> Upstream Proxy
    try:
        response = await client.post("/chat/completions", json=body)
        resp_data = response.json()
        latency_ms = (time.perf_counter() - start_time) * 1000

        cache_status = "BYPASS" if volatile else "MISS"
        usage = resp_data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        comp_tokens = usage.get("completion_tokens", 0)

        if response.status_code == 200:
            budget_manager.record_usage(tenant_id=tenant_id, actual_tokens=prompt_tokens + comp_tokens)
            if cleaned_prompt and not volatile:
                vector_cache.store_cache(
                    prompt=cleaned_prompt,
                    response=resp_data,
                    tenant_id=tenant_id
                )

        background_tasks.add_task(
            log_metrics_async,
            tenant_id=tenant_id,
            cache_status=cache_status,
            latency_ms=latency_ms,
            similarity_score=0.0,
            prompt_tokens=prompt_tokens,
            completion_tokens=comp_tokens,
            cost_saved_usd=0.0
        )

        return JSONResponse(
            status_code=response.status_code,
            content=resp_data,
            headers={"X-Cache": cache_status, "X-Tenant-ID": tenant_id}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Proxy error: {str(e)}"
        )


@app.delete("/v1/cache")
async def invalidate_cache(
    request: Request,
    tenant_id: str = Depends(get_tenant_id_from_key),  # 👈 Authenticated tenant
    purge_all: bool = Query(default=False, alias="all")
):
    vector_cache: VectorCacheManager = request.app.state.vector_cache
    if not tenant_id and not purge_all:
        raise HTTPException(status_code=400, detail="Specify 'tenant_id' or 'all=true'.")
    vector_cache.delete_cache(tenant_id=tenant_id, purge_all=purge_all)
    return {"status": "success", "message": f"Cache invalidated for tenant '{tenant_id}'."}