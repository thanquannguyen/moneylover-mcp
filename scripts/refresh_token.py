#!/usr/bin/env python3
"""Refresh a MoneyLover access token and cache it for the MCP server.

Why this exists: the MCP server caches a token in
``~/.moneylover-mcp/<base64url(email)>.json`` and only auto-refreshes on
error 717 / ``token_device_not_found``. When the token expires with
error 706 (``Not authorized``), every MCP call fails until a fresh token
is fetched. This script fetches one, using the same two-step login the
server itself uses (see ``src/moneyloverClient.js`` ``getToken``):

1. ``POST https://web.moneylover.me/api/user/login-url``
   -> ``request_token`` + ``login_url`` (whose ``client`` query param is
   needed below).
2. ``POST https://oauth.moneylover.me/token`` with
   ``Authorization: Bearer <request_token>``, header ``Client: <client>``
   and form fields ``email`` / ``password`` -> ``access_token``.

The token is then verified with ``POST /api/wallet/list`` (``AuthJWT``)
and cached in the same format the server reads. The password is read
with :func:`getpass.getpass` (never echoed, never passed on the command
line, never written to disk or to the cache file) and is only sent to
``oauth.moneylover.me`` over HTTPS.

Usage::

    python3 scripts/refresh_token.py --email you@example.com
    # or: MONEYLOVER_EMAIL=you@example.com python3 scripts/refresh_token.py
    # password is prompted interactively; --password is intentionally
    # not supported.

Exit code 0 means a fresh token was cached and verified. On failure
nothing is cached and the error is printed without the token or the
password.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://web.moneylover.me/api"
LOGIN_URL = f"{BASE_URL}/user/login-url"
TOKEN_URL = "https://oauth.moneylover.me/token"

CACHE_DIR = Path.home() / ".moneylover-mcp"


def cache_path(email: str) -> Path:
    name = base64.urlsafe_b64encode(email.encode("utf-8")).rstrip(b"=").decode("ascii")
    return CACHE_DIR / f"{name}.json"


def _read_json(response) -> dict:
    text = response.read().decode("utf-8")
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"MoneyLover returned non-JSON: {exc}") from exc


# Cloudflare (error 1010) rejects the default urllib User-Agent, so
# send a browser-like one on every request.
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}


def _post_json(url: str, *, headers=None, data: bytes | None = None) -> dict:
    merged = dict(DEFAULT_HEADERS)
    merged.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=merged, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return _read_json(resp)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail[:300]}") from exc


def fetch_token(email: str, password: str) -> str:
    """Run the two-step login and return a fresh access token."""
    login_payload = _post_json(LOGIN_URL)
    request_token = (login_payload.get("data") or {}).get("request_token")
    login_url = (login_payload.get("data") or {}).get("login_url")
    if not request_token or not login_url:
        raise RuntimeError("login-url response has no request_token/login_url")
    client = urllib.parse.urlparse(login_url)
    client_param = urllib.parse.parse_qs(client.query).get("client", [""])[0]
    if not client_param:
        raise RuntimeError("login URL has no client parameter")

    form = urllib.parse.urlencode({"email": email, "password": password}).encode("utf-8")
    token_payload = _post_json(
        TOKEN_URL,
        headers={
            "Authorization": f"Bearer {request_token}",
            "Client": client_param,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=form,
    )
    access_token = token_payload.get("access_token")
    if not access_token:
        raise RuntimeError("token response has no access_token")
    return access_token


def verify_token(token: str) -> int:
    """Check the token against /api/wallet/list; return wallet count."""
    payload = _post_json(
        f"{BASE_URL}/wallet/list",
        headers={"Authorization": f"AuthJWT {token}"},
    )
    error = payload.get("error", payload.get("e", 0))
    if error:
        raise RuntimeError(f"wallet/list rejected the token: {payload.get('msg') or payload}")
    wallets = (payload.get("data") or {}).get("wallets")
    if wallets is None:
        wallets = payload.get("data") or []
    if not isinstance(wallets, list):
        raise RuntimeError("wallet/list returned an unexpected shape")
    return len(wallets)


def save_token(email: str, token: str) -> Path:
    path = cache_path(email)
    CACHE_DIR.mkdir(mode=0o700, exist_ok=True)
    os.chmod(CACHE_DIR, 0o700)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {"token": token, "updatedAt": datetime.now(timezone.utc).isoformat()},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=os.environ.get("MONEYLOVER_EMAIL"),
                        help="MoneyLover account email (or MONEYLOVER_EMAIL)")
    args = parser.parse_args(argv)
    email = (args.email or "").strip()
    if not email:
        parser.error("email is required: pass --email or set MONEYLOVER_EMAIL")
    password = getpass.getpass("MoneyLover password: ")
    if not password:
        print("error: empty password", file=sys.stderr)
        return 1
    try:
        token = fetch_token(email, password)
        count = verify_token(token)
        path = save_token(email, token)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Token cached and verified ({count} wallets): {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
