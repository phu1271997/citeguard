// deploy.mjs — deploy CiteGuard to GenLayer studionet with genlayer-js.
//
// Usage:
//   source ~/.genlayer/env.sh        # exports GENLAYER_PRIVATE_KEY (funded)
//   npm install
//   node scripts/deploy.mjs
//
// Reads contracts/citeguard.py, deploys it, prints the address, and writes it
// to .env as GENLAYER_CONTRACT_ADDRESS so `node scripts/build.mjs` can bake it
// into the frontend.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createClient, createAccount } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const code = readFileSync(join(root, "contracts", "citeguard.py"), "utf8");

let pk = process.env.GENLAYER_PRIVATE_KEY;
if (!pk) {
  console.error("GENLAYER_PRIVATE_KEY not set. Run: source ~/.genlayer/env.sh");
  process.exit(1);
}
if (!pk.startsWith("0x")) pk = "0x" + pk;

const account = createAccount(pk);
const client = createClient({ chain: studionet, account });
console.log("Deployer:", account.address);

const txHash = await client.deployContract({ code, args: [], leaderOnly: false });
console.log("Deploy tx:", txHash);

const receipt = await client.waitForTransactionReceipt({ hash: txHash, status: "FINALIZED" });
const address = receipt.contractAddress || receipt.data?.contract_address;
if (!address) {
  console.error("No contract address in receipt:", JSON.stringify(receipt, null, 2));
  process.exit(1);
}
console.log("Contract address:", address);

const envPath = join(root, ".env");
let env = existsSync(envPath) ? readFileSync(envPath, "utf8") : "";
if (/GENLAYER_CONTRACT_ADDRESS\s*=.*/.test(env)) {
  env = env.replace(/GENLAYER_CONTRACT_ADDRESS\s*=.*/, `GENLAYER_CONTRACT_ADDRESS=${address}`);
} else {
  env += (env && !env.endsWith("\n") ? "\n" : "") + `GENLAYER_CONTRACT_ADDRESS=${address}\n`;
}
writeFileSync(envPath, env);
console.log("Wrote GENLAYER_CONTRACT_ADDRESS to .env");
