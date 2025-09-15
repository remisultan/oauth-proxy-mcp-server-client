import httpx
from urllib.parse import urlencode
from starlette.responses import JSONResponse, RedirectResponse
from starlette.status import HTTP_400_BAD_REQUEST


def register(mcp, settings, token_verifier):

    @mcp.custom_route("/register", methods=["POST"])
    async def register_client(request):
        """Dynamic Client Registration (RFC 7591)."""
        try:
            client_metadata = await request.json()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.gravitee_am_url}/oidc/register",
                    json=client_metadata,
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

                token_verifier.set_client_credentials(
                    client_id=data["client_id"],
                    client_secret=data["client_secret"],
                )
            return JSONResponse(content=data)
        except Exception as e:
            return {"error": str(e)}, 400

    @mcp.custom_route("/authorize", methods=["GET"])
    async def authorize(request):
        """Redirect client to Gravitee AM authorization endpoint."""
        params = dict(request.query_params)
        authorize_url = f"{settings.gravitee_am_url}/oauth/authorize?{urlencode(params)}"
        return RedirectResponse(authorize_url)

    @mcp.custom_route("/token", methods=["POST"])
    async def token_proxy(request):
        """Proxy token exchange to Gravitee AM."""
        try:
            body = await request.body()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.gravitee_am_url}/oauth/token",
                    content=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10,
                )
                resp.raise_for_status()
                return JSONResponse(content=resp.json())
        except httpx.HTTPStatusError as e:
            return JSONResponse(
                {"error": f"HTTP error: {e.response.status_code}", "details": e.response.text},
                status_code=e.response.status_code,
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTP_400_BAD_REQUEST)
