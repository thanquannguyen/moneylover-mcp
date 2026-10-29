# moneylover-mcp

An unofficial Model Context Protocol (MCP) server for MoneyLover, exposed over stdio for MCP-compatible clients.

MoneyLover provides no official public API. This server uses the unofficial web API employed by the MoneyLover web application. It may cease to function if that API changes.

## Features

- Wallet, category, and transaction retrieval.
- Transaction creation, with category identifiers resolved to the global form required by the transaction endpoint.
- Token caching with automatic refresh on expiry, when environment credentials are supplied.

## Tools

| Tool | Description |
| --- | --- |
| `login` | Authenticate and cache an access token. |
| `get_user_info` | Retrieve the authenticated user profile. |
| `get_wallets` | List wallets. |
| `get_categories` | List categories for a wallet. |
| `get_transactions` | List transactions for a wallet over a date range. |
| `add_transaction` | Create a transaction in a wallet. |

## Usage

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

## Security

- Only MoneyLover hosts are contacted: `https://web.moneylover.me/api` and `https://oauth.moneylover.me/token`.
- Runtime dependencies are limited to `@modelcontextprotocol/sdk` and `zod`.
- Access tokens are cached as plaintext JSON in `~/.moneylover-mcp/<base64url(email)>.json` (directory `0700`, file `0600`). Delete that directory to revoke stored sessions.
- No `.env` file is loaded. Credentials are taken only from the host environment or explicit tool arguments.

## Development

```bash
npm test
```

## License

MIT. This project is not affiliated with, endorsed by, or connected to MoneyLover.
