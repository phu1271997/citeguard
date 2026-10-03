// seed.mjs — populate the deployed CiteGuard contract with real disputes so the
// Explorer has resolved cases to show. Signs with the funded keystore wallet.
//
//   source ~/.genlayer/env.sh
//   node scripts/seed.mjs
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createClient, createAccount } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
let address = process.env.GENLAYER_CONTRACT_ADDRESS;
if (!address && existsSync(join(root, ".env"))) {
  const m = readFileSync(join(root, ".env"), "utf8").match(/GENLAYER_CONTRACT_ADDRESS\s*=\s*(.*)/);
  if (m) address = m[1].trim();
}
let pk = process.env.GENLAYER_PRIVATE_KEY;
if (!pk) { console.error("GENLAYER_PRIVATE_KEY not set (source ~/.genlayer/env.sh)"); process.exit(1); }
if (!pk.startsWith("0x")) pk = "0x" + pk;

// Asserter = keystore wallet 1; challenger = wallet 2 if present, else same wallet.
let pk2 = process.env.GENLAYER_PRIVATE_KEY_2;
if (pk2 && !pk2.startsWith("0x")) pk2 = "0x" + pk2;

const asserter = createAccount(pk);
const challenger = createAccount(pk2 || pk);
const cA = createClient({ chain: studionet, account: asserter });
const cB = createClient({ chain: studionet, account: challenger });
console.log("Seeding", address, "\n  asserter:", asserter.address, "\n  challenger:", challenger.address);

async function waitSuccess(client, hash, label, tries = 40) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await client.getTransactionReceipt({ hash });
      if (r?.status === "success") { console.log(`  ✓ ${label}`); return true; }
      if (r?.status === "error" || r?.status === "reverted") { console.log(`  ✗ ${label}: ${r.status}`); return false; }
    } catch {}
    await new Promise((r) => setTimeout(r, 5000));
  }
  console.log(`  … ${label}: still pending after timeout`);
  return false;
}
async function write(client, fn, args, value, label) {
  const req = { address, functionName: fn, args };
  if (value !== undefined) req.value = BigInt(value);
  const hash = await client.writeContract(req);
  console.log(`  tx ${label}: ${hash}`);
  await waitSuccess(client, hash, label);
  return hash;
}

// Claim 0 — the cited page genuinely supports the claim => SUPPORTED (asserter wins).
await write(cA, "assert_claim",
  ["This page states the domain is reserved for use in illustrative examples in documents", "https://example.com"],
  12000, "assert #0 (expect SUPPORTED)");
// Claim 1 — the cited page does NOT support the claim => UNSUPPORTED (challenger wins).
await write(cA, "assert_claim",
  ["This page states that GenLayer mainnet launched in the year 2020", "https://example.com"],
  12000, "assert #1 (expect UNSUPPORTED)");

console.log("Challenging both…");
await write(cB, "challenge", [0], 12000, "challenge #0");
await write(cB, "challenge", [1], 12000, "challenge #1");

console.log("Resolving (nondet jury reads the cited source on-chain — slower)…");
await write(cA, "resolve", [0], undefined, "resolve #0");
await write(cA, "resolve", [1], undefined, "resolve #1");

const raw = await cA.readContract({ address, functionName: "list_claims", args: [] });
console.log("\nCurrent ledger:");
for (const c of JSON.parse(raw)) console.log(`  #${c.id} [${c.status}] verdict=${c.verdict || "-"} :: ${c.claim.slice(0, 48)}`);
