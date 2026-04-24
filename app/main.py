import os
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis
from dotenv import load_dotenv
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .dependencies import load_yaml
from .middleware import ProxyMiddleware
from .router import limiter, router

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.endpoints = load_yaml()
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=False)
    yield
    await app.state.http_client.aclose()
    await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(ProxyMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(router)
