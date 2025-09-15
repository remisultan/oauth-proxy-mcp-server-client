import json
from pathlib import Path

import httpx
from urllib.parse import urlencode
from starlette.responses import JSONResponse, RedirectResponse
from starlette.status import HTTP_400_BAD_REQUEST

CREDENTIALS_FILE = Path.home() / ".mcp_server" / "client_credentials.json"

def save_credentials(data: dict):
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CREDENTIALS_FILE.open("w") as f:
        json.dump(data, f, indent=2)

def load_credentials() -> dict:
    if CREDENTIALS_FILE.exists():
        with CREDENTIALS_FILE.open("r") as f:
            return json.load(f)
    return {}

def register(mcp, settings, token_verifier):
    @mcp.custom_route("/register", methods=["POST"])
    async def register_client(request):
        """Dynamic Client Registration (RFC 7591) with auto-persistence."""
        try:
            data = load_credentials()
            if not data:
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
                    del data['registration_access_token']
                    del data['registration_client_uri']
                    # Save full registration data to disk
                    save_credentials(data)

            # Update token verifier in memory
            token_verifier.client_id = data["client_id"]
            token_verifier.client_secret = data["client_secret"]

            del data['client_secret']
            return JSONResponse(content=data)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=400)

    @mcp.custom_route("/authorize", methods=["GET"])
    async def authorize(request):
        """Redirect client to Gravitee AM authorization endpoint."""
        params = dict(request.query_params)
        authorize_url = f"{settings.gravitee_am_url}/oauth/authorize?{urlencode(params)}"
        return RedirectResponse(authorize_url)

    @mcp.custom_route("/token", methods=["POST"])
    async def token_proxy(request):
        """Proxy token exchange to Gravitee AM, adding client_secret if client_id matches."""
        try:
            body_bytes = await request.body()
            body_str = body_bytes.decode()

            # Parse body into key-value pairs
            form_dict = dict(item.split("=", 1) for item in body_str.split("&") if "=" in item)

            # Conditionally add client_secret
            if form_dict.get("client_id") == token_verifier.client_id:
                form_dict["client_secret"] = token_verifier.client_secret
            else:
                # Optionally remove any client_secret that might have been passed
                form_dict.pop("client_secret", None)

            # Re-encode body
            body_with_creds = "&".join(f"{k}={v}" for k, v in form_dict.items())

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.gravitee_am_url}/oauth/token",
                    content=body_with_creds,
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
            return JSONResponse({"error": str(e)}, status_code=400)
