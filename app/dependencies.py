import os
import yaml
import httpx
from fastapi import HTTPException, Request

from .middleware import filter_headers


def load_yaml() -> dict:
    with open("endpoints.yml", "r") as stream:
        config = yaml.safe_load(stream)

    for _, endpoint in config.get("endpoints", {}).items():
        api_key_ref = endpoint.get("api_key", "")
        resolved = os.getenv(api_key_ref)
        if resolved:
            endpoint["api_key"] = resolved

    return config


def build_timeout(timeout_config) -> httpx.Timeout:
    if isinstance(timeout_config, (int, float)):
        return httpx.Timeout(timeout_config)

    return httpx.Timeout(
        connect=timeout_config.get("connect", 5.0),
        read=timeout_config.get("read", 30.0),
        write=timeout_config.get("write", 15.0),
        pool=timeout_config.get("pool", 10),
    )


async def resolve_endpoint(env: str, path: str, request: Request):
    endpoints = request.app.state.endpoints.get("endpoints", {})

    if env not in endpoints:
        raise HTTPException(status_code=404, detail="Environment not found")

    endpoint = endpoints[env]
    auth_header = endpoint["auth_header"]
    api_key = endpoint["api_key"]
    auth_scheme = endpoint["auth_scheme"]

    if not endpoint.get("enable", True):
        raise HTTPException(status_code=403, detail="Environment is disabled")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Auth header were not provided")
    if not api_key:
        raise HTTPException(status_code=401, detail="Api key credentials were not provided")

    headers = filter_headers(request.headers)

    if auth_scheme:
        headers[auth_header] = f"{auth_scheme} {api_key}"
    else:
        headers[auth_header] = api_key

    return {
        "target_url": f"{endpoints[env]['url'].rstrip('/')}/{path}",
        "headers": headers,
        "timeout": build_timeout(endpoint.get("timeout", 10)),
        "cache_ttl": endpoint.get("cache_ttl"),
    }
