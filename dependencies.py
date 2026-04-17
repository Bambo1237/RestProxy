from fastapi import HTTPException, Request
from tools import filter_headers, build_timeout


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
        "timeout": build_timeout(endpoint.get("timeout", 10))
    }