from fastapi import FastAPI, HTTPException, Request, Response, Depends
import httpx
from contextlib import asynccontextmanager

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from dotenv import load_dotenv

from retry import fetchWithRetry
from dependencies import resolve_endpoint
from middleware import ProxyMiddleware, filter_headers
from tools import load_yaml

load_dotenv()

limiter = Limiter(
    key_func=get_remote_address,
    #storage_uri="redis://localhost:6379",
    strategy="moving-window"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.endpoints = load_yaml()
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    yield
    await app.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)
app.add_middleware(ProxyMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/proxy/{env}/{path:path}")
@limiter.limit("15/second;150/minute;1500/hour")
async def proxy_get(request: Request, endpoints: dict = Depends(resolve_endpoint)):

    client:  httpx.AsyncClient = request.app.state.http_client

    try:
        response = await fetchWithRetry(
            client=client,
            method="GET",
            url=endpoints["target_url"],
            headers=endpoints["headers"],
            timeout=endpoints["timeout"])

    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail="Connect timeout")
    except httpx.ReadTimeout as e:
        raise HTTPException(status_code=504, detail="Read timeout")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=520, detail=str(e))

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=filter_headers(response.headers),
        media_type=response.headers.get("content-type"),
    )

@app.post("/proxy/{env}/{path:path}")
@limiter.limit("5/second;100/minute;1000/hour")
async def proxy_post(request: Request, endpoints: dict = Depends(resolve_endpoint)):

    timeout = endpoints["timeout"]

    client: httpx.AsyncClient = request.app.state.http_client

    body = await request.body()

    try:
        response = await client.post(
            endpoints["target_url"],
            headers=endpoints["headers"],
            content=body,
            timeout=timeout)

    except httpx.HTTPError as e:
        raise HTTPException(status_code=520, detail=str(e))

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=filter_headers(response.headers),
        media_type=response.headers.get("content-type"),
    )