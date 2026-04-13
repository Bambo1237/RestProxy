import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from tools import filter_headers

ALLOWED_CONTENT_TYPES = {
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
    "text/plain",
}

MAX_HEADER_NAME_LEN = 100
MAX_HEADER_VALUE_LEN = 8192
MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB

_VALID_HEADER_NAME = re.compile(r"^[a-zA-Z0-9\-_]+$")



class ProxyMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        error = self._validate_path(request)
        if error:
            return error

        error = self._validate_request_headers(request)
        if error:
            return error

        if request.method == "POST":
            error = self._validate_post(request)
            if error:
                return error

        response = await call_next(request)


        filtered_headers = filter_headers(response.headers)
        for key in list(response.headers.keys()):
            if key not in filtered_headers:
               del response.headers[key]

        return response

    def _validate_path(self, request: Request):
        path: str = request.scope.get("path", "")
        raw_path: str = request.scope.get("raw_path", b"").decode("latin-1")

        if "\x00" in path:
            return JSONResponse({"detail": "Invalid path: null byte"}, status_code=400)

        if "../" in path or "..\\" in path:
            return JSONResponse({"detail": "Invalid path: path traversal"}, status_code=400)

        raw_lower = raw_path.lower()
        if "%2e%2e" in raw_lower:
            return JSONResponse({"detail": "Invalid path: encoded traversal"}, status_code=400)

        if "%00" in raw_lower:
            return JSONResponse({"detail": "Invalid path: encoded null byte"}, status_code=400)

        return None

    def _validate_request_headers(self, request: Request):
        for name, value in request.headers.items():
            if len(name) > MAX_HEADER_NAME_LEN:
                return JSONResponse(
                    {"detail": f"Header name too long: {name[:50]}..."},
                    status_code=400,
                )
            if len(value) > MAX_HEADER_VALUE_LEN:
                return JSONResponse(
                    {"detail": f"Header value too long for: {name}"},
                    status_code=400,
                )
            if not _VALID_HEADER_NAME.match(name):
                return JSONResponse(
                    {"detail": f"Invalid characters in header name: {name[:50]}"},
                    status_code=400,
                )
        return None

    def _validate_post(self, request: Request):
        content_type = request.headers.get("content-type", "")
        base_type = content_type.split(";")[0].strip().lower()

        if base_type and base_type not in ALLOWED_CONTENT_TYPES:
            return JSONResponse(
                {"detail": f"Unsupported Content-Type: {base_type}"},
                status_code=415,
            )

        raw_length = request.headers.get("content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > MAX_BODY_SIZE:
                    return JSONResponse(
                        {"detail": "Request body too large"},
                        status_code=413,
                    )
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid Content-Length header"},
                    status_code=400,
                )

        return None
