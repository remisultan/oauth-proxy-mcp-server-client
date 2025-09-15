import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


class CallbackHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to capture OAuth callback."""

    def __init__(self, request, client_address, server, callback_data):
        self.callback_data = callback_data
        super().__init__(request, client_address, server)

    def do_GET(self):
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        if "code" in query_params:
            self.callback_data["authorization_code"] = query_params["code"][0]
            self.callback_data["state"] = query_params.get("state", [None])[0]
            self._send_page("Authorization Successful", success=True)
        elif "error" in query_params:
            self.callback_data["error"] = query_params["error"][0]
            self._send_page(f"Authorization Failed: {self.callback_data['error']}", success=False)
        else:
            self.send_response(404)
            self.end_headers()

    def _send_page(self, message: str, success: bool):
        status = 200 if success else 400
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(
            f"""
            <html><body>
                <h1>{message}</h1>
                <p>You can close this window and return to the terminal.</p>
                <script>setTimeout(() => window.close(), 2000);</script>
            </body></html>
            """.encode()
        )

    def log_message(self, format, *args):
        pass  # Suppress default logging


class CallbackServer:
    """Simple local server to handle OAuth callbacks."""

    def __init__(self, port=3030):
        self.port = port
        self.server = None
        self.thread = None
        self.callback_data = {"authorization_code": None, "state": None, "error": None}

    def _handler(self):
        callback_data = self.callback_data

        class DataHandler(CallbackHandler):
            def __init__(self, req, addr, srv):
                super().__init__(req, addr, srv, callback_data)
        return DataHandler

    def start(self):
        self.server = HTTPServer(("localhost", self.port), self._handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"🖥️ Callback server running at http://localhost:{self.port}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

    def wait_for_callback(self, timeout=300):
        start = time.time()
        while time.time() - start < timeout:
            if self.callback_data["authorization_code"]:
                return self.callback_data["authorization_code"]
            if self.callback_data["error"]:
                raise Exception(f"OAuth error: {self.callback_data['error']}")
            time.sleep(0.1)
        raise TimeoutError("Timeout waiting for OAuth callback")

    def get_state(self):
        return self.callback_data["state"]