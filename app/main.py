import json
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, status, Query
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

from app.config import settings
from app.vector_store import VectorCacheManager
from app.normalizer import normalize_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.vector_cache = VectorCacheManager()
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


# Security Headers Middleware
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
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    # Multi-tenant header extraction (defaults to 'default')
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    is_stream = body.get("stream", False)
    client: httpx.AsyncClient = request.app.state.http_client
    vector_cache: VectorCacheManager = request.app.state.vector_cache

    messages = body.get("messages", [])
    raw_user_prompt = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            raw_user_prompt = msg.get("content", "")
            break

    cleaned_prompt = normalize_text(raw_user_prompt) if raw_user_prompt else ""

    # 1. Check Semantic Cache with Tenant Isolation
    if not is_stream and cleaned_prompt:
        cached_result = vector_cache.search_similar(
            query_text=cleaned_prompt,
            similarity_threshold=0.85,
            tenant_id=tenant_id
        )
        if cached_result:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=cached_result["cached_response"],
                headers={
                    "X-Cache": "HIT",
                    "X-Cache-Score": str(round(cached_result["score"], 4)),
                    "X-Tenant-ID": tenant_id
                }
            )

    # 2. Proxy to Upstream LLM Provider on Cache Miss
    try:
        if is_stream:
            req = client.build_request("POST", "/chat/completions", json=body)
            response = await client.send(req, stream=True)

            if response.status_code != 200:
                error_body = await response.aread()
                return JSONResponse(
                    status_code=response.status_code,
                    content=json.loads(error_body.decode())
                )

            async def sse_generator():
                async for chunk in response.aiter_bytes():
                    yield chunk
                await response.aclose()

            return StreamingResponse(
                sse_generator(),
                media_type="text/event-stream",
                headers={"X-Cache": "MISS", "X-Tenant-ID": tenant_id}
            )
        else:
            response = await client.post("/chat/completions", json=body)
            resp_data = response.json()

            if response.status_code == 200 and cleaned_prompt:
                vector_cache.store_cache(
                    prompt=cleaned_prompt,
                    response=resp_data,
                    tenant_id=tenant_id
                )

            return JSONResponse(
                status_code=response.status_code,
                content=resp_data,
                headers={"X-Cache": "MISS", "X-Tenant-ID": tenant_id}
            )

    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to connect to upstream LLM API provider."
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream LLM API request timed out."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Proxy error: {str(e)}"
        )


# Admin Invalidation Endpoint
@app.delete("/v1/cache")
async def invalidate_cache(
    request: Request,
    tenant_id: Optional[str] = Query(default=None, description="Tenant ID to purge"),
    purge_all: bool = Query(default=False, alias="all", description="Set to true to clear all cache")
):
    vector_cache: VectorCacheManager = request.app.state.vector_cache

    if not tenant_id and not purge_all:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specify either 'tenant_id' parameter or 'all=true' to invalidate cache."
        )

    res = vector_cache.delete_cache(tenant_id=tenant_id, purge_all=purge_all)
    
    if purge_all:
        return {"status": "success", "message": "Entire semantic cache purged successfully."}
    return {"status": "success", "message": f"Cache invalidated for tenant '{tenant_id}'."}