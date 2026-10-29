import test from "node:test";
import assert from "node:assert/strict";
import { MoneyloverClient } from "../src/moneyloverClient.js";

// Mock fetch: capture the /transaction/add payload, and answer
// /transaction/list with a category object that maps a wallet-specific
// id to a global id (the shape the live API returns).
let lastAddPayload = null;
const calls = [];
globalThis.fetch = async (url, opts = {}) => {
  calls.push(url);
  const body = opts.body ? JSON.parse(opts.body) : {};
  if (url.endsWith("/transaction/list")) {
    return {
      ok: true,
      text: async () => JSON.stringify({
        error: 0,
        data: {
          transactions: [{
            category: {
              _id: "B2A73776CBD34CDA80C12C643C15900E",
              metadata: "shopping0",
              categories: ["b591c7bfcd4d407c928d51985d2540f7"],
            },
          }],
        },
      }),
    };
  }
  if (url.endsWith("/transaction/add")) {
    lastAddPayload = body;
    return {
      ok: true,
      text: async () => JSON.stringify({ error: 0, msg: "transaction_add_success", data: { _id: "test-id", ...body } }),
    };
  }
  return { ok: true, text: async () => JSON.stringify({ error: 0, data: {} }) };
};

test("add_transaction translates a wallet-specific category id to the global id", async () => {
  const client = new MoneyloverClient("test-token");
  const data = await client.addTransaction({
    walletId: "wallet-1",
    categoryId: "b591c7bfcd4d407c928d51985d2540f7",
    amount: "27000",
    note: "test",
    date: "2026-10-29",
  });
  assert.equal(data._id, "test-id");
  assert.equal(lastAddPayload.category, "B2A73776CBD34CDA80C12C643C15900E");
  assert.equal(typeof lastAddPayload.amount, "number");
  assert.equal(lastAddPayload.amount, 27000);
});

test("add_transaction keeps an already-global category id as-is", async () => {
  const client = new MoneyloverClient("test-token");
  await client.addTransaction({
    walletId: "wallet-1",
    categoryId: "B2A73776CBD34CDA80C12C643C15900E",
    amount: 86500,
    note: "test2",
    date: "2026-10-29",
  });
  assert.equal(lastAddPayload.category, "B2A73776CBD34CDA80C12C643C15900E");
  assert.equal(lastAddPayload.amount, 86500);
});
