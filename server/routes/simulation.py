import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

SIMULATOR_URL = os.environ.get("SIMULATOR_URL", "http://localhost:8000")

router = APIRouter()


async def proxy_to_simulator(request: Request) -> JSONResponse:
    path = request.path_params["path"]
    url = f"{SIMULATOR_URL}/simulation/{path}"
    params = dict(request.query_params)
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    async with httpx.AsyncClient(trust_env=False, timeout=120.0) as client:
        response = await client.request(
            method=request.method,
            url=url,
            params=params,
            content=body,
            headers=headers,
        )

    return JSONResponse(content=response.json(), status_code=response.status_code)


router.add_api_route("/api/simulation/{path:path}", proxy_to_simulator, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
