import json
import base64
import os
from redis.asyncio import Redis

CACHE_ALLOWED_STATUS: set[int] = {
    int(s.strip())
    for s in os.getenv("CACHE_ALLOWED_STATUS", "200").split(",")
    if s.strip().isdigit()
}


def build_cache_key(env: str, path: str, query_string: str) -> str:
    sorted_qs = "&".join(sorted(query_string.split("&"))) if query_string else ""
    return f"proxy:cache:{env}:{path}:{sorted_qs}"


async def get_cached(redis: Redis, key: str) -> dict | None:
    data = await redis.get(key)
    if data is None:
        return None
    entry = json.loads(data)
    entry["content"] = base64.b64decode(entry["content"])
    return entry


async def set_cached(redis: Redis, key: str, status: int, headers: dict, content: bytes, ttl: int):
    if status not in CACHE_ALLOWED_STATUS:
        return
    payload = json.dumps({
        "status": status,
        "headers": headers,
        "content": base64.b64encode(content).decode(),
    })
    await redis.setex(key, ttl, payload)
