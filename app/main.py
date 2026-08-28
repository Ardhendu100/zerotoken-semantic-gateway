import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Shared HTTPX client with connection pooling for low-latency proxying
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

    is_stream = body.get("stream", False)
    client: httpx.AsyncClient = request.app.state.http_client

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
                media_type="text/event-stream"
            )
        else:
            response = await client.post("/chat/completions", json=body)
            return JSONResponse(
                status_code=response.status_code,
                content=response.json()
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