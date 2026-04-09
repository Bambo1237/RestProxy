import fastapi
from fastapi import FastAPI, HTTPException, Request, Response, Depends
import httpx
from contextlib import asynccontextmanager

from dotenv import load_dotenv

from dependencies import resolve_endpoint
from tools import load_yaml, filter_headers

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.endpoints = load_yaml()
    yield

app = fastapi.FastAPI(lifespan=lifespan)


@app.get("/proxy/{env}/{path:path}")
async def proxy_get(endpoints: dict = Depends(resolve_endpoint)):

    target_url = endpoints["target_url"]

    headers = endpoints["headers"]

    async with httpx.AsyncClient(timeout=endpoints.get("timeout")) as client:
        try:
            response = await client.get(target_url, headers=headers)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=520, detail=str(e))

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=filter_headers(response.headers),
        media_type=response.headers.get("content-type"),
    )

@app.post("/proxy/{env}/{path:path}")
async def proxy_post(request: Request, endpoints: dict = Depends(resolve_endpoint)):

    target_url = endpoints["target_url"]
    headers = endpoints["headers"]

    body = await request.body()

    async with httpx.AsyncClient(timeout=endpoints.get("timeout")) as client:
        try:
            response = await client.post(target_url, headers=headers, content=body)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=520, detail=str(e))

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=filter_headers(response.headers),
        media_type=response.headers.get("content-type"),
    )