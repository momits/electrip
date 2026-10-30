#!/usr/bin/python3
"""Adds the tokens to requests of the agent, so the agent never sees them.

Runs as user keeper, which alone can read the tokens in /etc/electrip-secrets
and connect to the internet directly. Listens on 127.0.0.1:8080 and forwards
to fixed targets:

  /anthropic/v1/...                     -> https://api.anthropic.com/v1/...
  /github-api/repos/momits/electrip...  -> https://api.github.com/repos/momits/electrip...
  /github-git/...                       -> https://github.com/momits/electrip.git/...
"""

import base64
import http.client
import http.server
from urllib.parse import unquote

SECRETS = "/etc/electrip-secrets"
REPO = "/repos/momits/electrip"
DROP = {"host", "authorization", "x-api-key", "content-length", "connection",
        "keep-alive", "proxy-connection", "transfer-encoding", "te", "upgrade", "trailer"}


def token(name):
    with open(f"{SECRETS}/{name}") as f:
        return f.read().strip()


def route(path):
    """Returns host, upstream path and Authorization header, or None."""
    if ".." in unquote(path.split("?")[0]):
        return None
    if path.startswith("/anthropic/v1/"):
        return "api.anthropic.com", path[len("/anthropic"):], "Bearer " + token("claude")
    rest = path[len("/github-api"):]
    if path.startswith("/github-api/") and (rest == REPO or rest.startswith((REPO + "/", REPO + "?"))):
        return "api.github.com", rest, "Bearer " + token("github")
    if path.startswith("/github-git/"):
        basic = base64.b64encode(f"x-access-token:{token('github')}".encode()).decode()
        return "github.com", "/momits/electrip.git/" + path[len("/github-git/"):], "Basic " + basic
    return None


class Handler(http.server.BaseHTTPRequestHandler):
    def forward(self):
        try:
            target = route(self.path)
        except OSError:
            return self.send_error(503, "token missing")
        if target is None:
            return self.send_error(403, "path not allowed")
        if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
            return self.send_error(411, "chunked request bodies are not supported")
        host, path, auth = target
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))) or None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in DROP}
        headers["Authorization"] = auth
        try:
            upstream = http.client.HTTPSConnection(host, timeout=600)
            upstream.request(self.command, path, body=body, headers=headers)
            response = upstream.getresponse()
        except OSError as e:
            return self.send_error(502, f"{host}: {e}")
        self.log_request(response.status)
        self.send_response_only(response.status, response.reason)
        for k, v in response.getheaders():
            if k.lower() not in DROP:
                self.send_header(k, v)
        self.end_headers()
        while chunk := response.read1(65536):
            self.wfile.write(chunk)
            self.wfile.flush()

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = forward


http.server.ThreadingHTTPServer(("127.0.0.1", 8080), Handler).serve_forever()
