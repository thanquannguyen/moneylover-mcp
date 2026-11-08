# moneylover-mcp

[![License: MIT](https://img.shields.io/github/license/thanquannguyen/moneylover-mcp?style=flat-square)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/thanquannguyen/moneylover-mcp?style=flat-square)](https://github.com/thanquannguyen/moneylover-mcp/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/thanquannguyen/moneylover-mcp?style=flat-square)](https://github.com/thanquannguyen/moneylover-mcp/forks)
[![Last commit](https://img.shields.io/github/last-commit/thanquannguyen/moneylover-mcp?style=flat-square)](https://github.com/thanquannguyen/moneylover-mcp/commits/main)
[![Repo size](https://img.shields.io/github/repo-size/thanquannguyen/moneylover-mcp?style=flat-square)](https://github.com/thanquannguyen/moneylover-mcp)
![Top language](https://img.shields.io/github/languages/top/thanquannguyen/moneylover-mcp?style=flat-square)

An unofficial Model Context Protocol (MCP) server for MoneyLover, exposed over stdio for MCP-compatible clients.

MoneyLover provides no official public API. This server uses the unofficial web API employed by the MoneyLover web application. It may cease to function if that API changes.

## Contents

- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Tools](#tools)
- [Refreshing an expired token](#refreshing-an-expired-token)
- [Security](#security)
- [Development](#development)
- [Contributing](#contributing)
- [Releases](#releases)
- [License](#license)

## Requirements

- Node.js. The project does not pin a minimum version in `package.json`
  (no `engines` field).
- A MoneyLover account. No official public API is used; see [Security](#security).

## Features

- Wallet, category, and transaction retrieval.
- Transaction creation, with category identifiers resolved to the global form required by the transaction endpoint.
- Token caching with automatic refresh on expiry, when environment credentials are supplied.

## Quick start

```bash
npm install
npm start
```

```json
{
  "mcpServers": {
    "moneylover": {
      "command": "node",
      "args": ["/path/to/moneylover-mcp/src/server.js"],
      "env": {
        "EMAIL": "you@example.com",
        "PASSWORD": "your-password"
      }
    }
  }
}
```

A `token` argument to any tool overrides environment authentication.

Verify it works by calling `get_wallets` from your MCP client — it should
list your MoneyLover wallets. If calls fail with error 706, see
[Refreshing an expired token](#refreshing-an-expired-token).

## Tools

| Tool | Description |
| --- | --- |
| `login` | Authenticate and cache an access token. |
| `get_user_info` | Retrieve the authenticated user profile. |
| `get_wallets` | List wallets. |
| `get_categories` | List categories for a wallet. |
| `get_transactions` | List transactions for a wallet over a date range. |
| `add_transaction` | Create a transaction in a wallet. |

## Refreshing an expired token

The server only auto-refreshes on error 717 / `token_device_not_found`.
If calls start failing with error 706 (`Not authorized`), fetch a fresh
token with the standalone script (Python 3, standard library only; the
password is prompted with `getpass` and never stored):

```bash
python3 scripts/refresh_token.py --email you@example.com
```

It runs the same two-step login as the server, verifies the token with
`wallet/list`, and caches it at `~/.moneylover-mcp/<base64url(email)>.json`
(directory `0700`, file `0600`). Its tests are mocked and need no network:

```bash
python3 test/refresh_token.test.py
```

## Security

- Only MoneyLover hosts are contacted: `https://web.moneylover.me/api` and `https://oauth.moneylover.me/token`.
- Runtime dependencies are limited to `@modelcontextprotocol/sdk` and `zod`.
- Access tokens are cached as plaintext JSON in `~/.moneylover-mcp/<base64url(email)>.json` (directory `0700`, file `0600`). Delete that directory to revoke stored sessions.
- No `.env` file is loaded. Credentials are taken only from the host environment or explicit tool arguments.

## Development

```bash
npm test
```

## Contributing

Issues and pull requests are welcome. Please describe the problem or change
clearly, keep changes focused, and include test evidence where applicable.

## Releases

See [Releases](https://github.com/thanquannguyen/moneylover-mcp/releases)
for published versions. Current release: v0.1.0 (initial release).

## License

MIT. This project is not affiliated with, endorsed by, or connected to MoneyLover.
