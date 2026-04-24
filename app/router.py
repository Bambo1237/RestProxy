import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from .cache import build_cache_key, get_cached, set_cached
from .dependencies import resolve_endpoint
from .middleware import filter_headers
from .retry import fetchWithRetry

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("REDIS_URL", "redis://localhost:6379"),
    strategy="moving-window",
)

router = APIRouter()


@router.get("/proxy/{env}/{path:path}")
@limiter.limit("15/second;150/minute;1500/hour")
async def proxy_get(request: Request, endpoints: dict = Depends(resolve_endpoint)):
    client: httpx.AsyncClient = request.app.state.http_client
    redis = request.app.state.redis
    cache_ttl: int | None = endpoints.get("cache_ttl")
    bypass_cache = request.headers.get("cache-control") == "no-cache"

    if cache_ttl is not None and not bypass_cache:
        cache_key = build_cache_key(
            request.path_params["env"],
            request.path_params["path"],
            request.url.query,
        )
        cached = await get_cached(redis, cache_key)
        if cached:
            return Response(
                content=cached["content"],
                status_code=cached["status"],
                headers={**cached["headers"], "x-cache": "HIT"},
                media_type=cached["headers"].get("content-type"),
            )
    else:
        cache_key = None

    try:
        response = await fetchWithRetry(
            client=client,
            method="GET",
            url=endpoints["target_url"],
            headers=endpoints["headers"],
            timeout=endpoints["timeout"],
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Connect timeout")
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="Read timeout")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=520, detail=str(e))

    filtered = filter_headers(response.headers)

    if cache_ttl is not None and cache_key is not None:
        await set_cached(redis, cache_key, response.status_code, filtered, response.content, cache_ttl)

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={**filtered, "x-cache": "MISS"},
        media_type=response.headers.get("content-type"),
    )


@router.post("/proxy/{env}/{path:path}")
@limiter.limit("5/second;100/minute;1000/hour")
async def proxy_post(request: Request, endpoints: dict = Depends(resolve_endpoint)):
    client: httpx.AsyncClient = request.app.state.http_client
    body = await request.body()

    try:
        response = await client.post(
            endpoints["target_url"],
            headers=endpoints["headers"],
            content=body,
            timeout=endpoints["timeout"],
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=520, detail=str(e))

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=filter_headers(response.headers),
        media_type=response.headers.get("content-type"),
    )
