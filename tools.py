import os
import yaml

OP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}

def filter_headers(headers) -> dict:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in OP_BY_HOP_HEADERS
    }

def load_yaml() -> dict:
    with open("endpoints.yml", "r") as stream:
        config = yaml.safe_load(stream)

    for _, endpoint in config.get("endpoints", {}).items():
        api_key_ref = endpoint.get("api_key","")
        resolved = os.getenv(api_key_ref)
        if resolved:
            endpoint["api_key"] = resolved

    return config