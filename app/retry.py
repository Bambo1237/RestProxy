from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.ConnectTimeout)),
    reraise=True
)
async def fetchWithRetry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict = None,
    timeout: httpx.Timeout | float = 10.0,
    content: bytes = None
) -> httpx.Response:
    return await client.request(
        method=method,
        url=url,
        headers=headers,
        content=content,
        timeout=timeout
    )
