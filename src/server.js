#!/usr/bin/env node
// MoneyLover MCP server (unofficial).
// Stdio server for MCP hosts (Claude Desktop, Cursor, Muse, ...).
// It never loads a .env file on its own; credentials come only from the
// MCP host's environment or from an explicit tool argument.
//
// Token cache: ~/.moneylover-mcp/<base64url(email)>.json, directory 0700,
// file 0600, token stored as plaintext JSON. Delete that directory to
// revoke stored sessions.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { promises as fs } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { MoneyloverClient } from "./moneyloverClient.js";

const CACHE_DIR = join(homedir(), ".moneylover-mcp");

function cachePath(email) {
  return join(CACHE_DIR, Buffer.from(email, "utf8").toString("base64url") + ".json");
}

async function readCachedToken(email) {
  try {
    const data = JSON.parse(await fs.readFile(cachePath(email), "utf8"));
    return data.token || null;
  } catch {
    return null;
  }
}

async function writeCachedToken(email, token) {
  await fs.mkdir(CACHE_DIR, { recursive: true, mode: 0o700 });
  await fs.writeFile(cachePath(email), JSON.stringify({ token }), { mode: 0o600 });
}

function envCredentials() {
  const email = process.env.EMAIL;
  const password = process.env.PASSWORD;
  return email && password ? { email, password } : null;
}

async function resolveToken(explicitToken) {
  if (explicitToken) return explicitToken;
  if (process.env.MONEYLOVER_TOKEN) return process.env.MONEYLOVER_TOKEN;
  const creds = envCredentials();
  if (creds) {
    const cached = await readCachedToken(creds.email);
    if (cached) return cached;
    const token = await MoneyloverClient.getToken(creds.email, creds.password);
    await writeCachedToken(creds.email, token);
    return token;
  }
  if (process.env.EMAIL) {
    const cached = await readCachedToken(process.env.EMAIL);
    if (cached) return cached;
  }
  throw new Error("No token available: pass a token argument, set MONEYLOVER_TOKEN, or set EMAIL (+PASSWORD for login/refresh)");
}

async function runWithClient(explicitToken, fn) {
  let token = await resolveToken(explicitToken);
  try {
    return await fn(new MoneyloverClient(token));
  } catch (error) {
    const isExpired = error?.code === 717 || /token_device_not_found/i.test(error?.message || "");
    const creds = envCredentials();
    if (isExpired && creds) {
      token = await MoneyloverClient.getToken(creds.email, creds.password);
      await writeCachedToken(creds.email, token);
      return await fn(new MoneyloverClient(token));
    }
    throw error;
  }
}

const formatSuccess = (data) => ({
  content: [{ type: "text", text: JSON.stringify(data ?? {}, null, 2) }],
  structuredContent: data ?? {},
});
const formatError = (error) => ({
  content: [{ type: "text", text: `Error: ${error.message}` }],
  isError: true,
});

const tokenArgument = {
  token: z.string().optional().describe("JWT token returned by login, or derived from environment credentials"),
};

export function createMoneyloverServer() {
  const server = new McpServer({ name: "moneylover-mcp-server", version: "0.1.0" });

  server.registerTool("login", {
    title: "Login",
    description: "Authenticate using Money Lover credentials to retrieve a JWT token (cached locally).",
    inputSchema: {
      email: z.string().min(1),
      password: z.string().min(1),
    },
  }, async ({ email, password }) => {
    try {
      const token = await MoneyloverClient.getToken(email, password);
      await writeCachedToken(email, token);
      return formatSuccess({ ok: true, note: "Token cached locally; subsequent calls can omit the token when EMAIL is set." });
    } catch (error) {
      return formatError(error);
    }
  });

  server.registerTool("get_user_info", {
    title: "Get User Info",
    description: "Retrieve the Money Lover user profile associated with the token.",
    inputSchema: { ...tokenArgument },
  }, async ({ token }) => {
    try {
      return formatSuccess(await runWithClient(token, (c) => c.getUserInfo()));
    } catch (error) {
      return formatError(error);
    }
  });

  server.registerTool("get_wallets", {
    title: "Get Wallets",
    description: "List wallets available to the authenticated user.",
    inputSchema: { ...tokenArgument },
  }, async ({ token }) => {
    try {
      return formatSuccess(await runWithClient(token, (c) => c.getWallets()));
    } catch (error) {
      return formatError(error);
    }
  });

  server.registerTool("get_categories", {
    title: "Get Categories",
    description: "List categories for a wallet. Note: the ids returned here are wallet-specific; add_transaction translates them to global ids automatically.",
    inputSchema: { ...tokenArgument, walletId: z.string().min(1) },
  }, async ({ token, walletId }) => {
    try {
      return formatSuccess(await runWithClient(token, (c) => c.getCategories(walletId)));
    } catch (error) {
      return formatError(error);
    }
  });

  server.registerTool("get_transactions", {
    title: "Get Transactions",
    description: "Fetch transactions for a wallet between two dates (YYYY-MM-DD).",
    inputSchema: {
      ...tokenArgument,
      walletId: z.string().min(1),
      startDate: z.string().regex(/\d{4}-\d{2}-\d{2}/),
      endDate: z.string().regex(/\d{4}-\d{2}-\d{2}/),
    },
  }, async ({ token, walletId, startDate, endDate }) => {
    try {
      return formatSuccess(await runWithClient(token, (c) => c.getTransactions(walletId, startDate, endDate)));
    } catch (error) {
      return formatError(error);
    }
  });

  server.registerTool("add_transaction", {
    title: "Add Transaction",
    description: "Create a new transaction in a wallet. categoryId may be a wallet-specific id from get_categories or a global category id; it is translated to the global id the current API expects.",
    inputSchema: {
      ...tokenArgument,
      walletId: z.string().min(1).describe("Wallet identifier"),
      categoryId: z.string().min(1).describe("Category identifier (wallet-specific or global)"),
      amount: z.union([z.string(), z.number()]).describe("Transaction amount"),
      note: z.string().optional().describe("Optional transaction note"),
      date: z.string().regex(/\d{4}-\d{2}-\d{2}/).describe("Display date in YYYY-MM-DD format"),
      with: z.array(z.string()).optional().describe("Optional array of related parties"),
    },
  }, async ({ token, ...payload }) => {
    try {
      const data = await runWithClient(token, (c) => c.addTransaction({
        walletId: payload.walletId,
        categoryId: payload.categoryId,
        amount: payload.amount,
        note: payload.note,
        date: payload.date,
        with: payload.with,
      }));
      return formatSuccess(data ?? {});
    } catch (error) {
      return formatError(error);
    }
  });

  return server;
}

export async function startMoneyloverServer() {
  const server = createMoneyloverServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  return server;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await startMoneyloverServer();
}
