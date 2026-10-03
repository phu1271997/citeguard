// build.mjs — bake the deployed contract address into frontend/index.html.
// Vercel runs this as the build command; it also runs locally after deploy.mjs.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

let contractAddress = process.env.GENLAYER_CONTRACT_ADDRESS;
if (!contractAddress) {
  const envPath = join(root, ".env");
  if (existsSync(envPath)) {
    const m = readFileSync(envPath, "utf8").match(/GENLAYER_CONTRACT_ADDRESS\s*=\s*(.*)/);
    if (m) contractAddress = m[1].trim();
  }
}
if (!contractAddress) {
  console.warn("No GENLAYER_CONTRACT_ADDRESS found; leaving placeholder in index.html");
  process.exit(0);
}

const appPath = join(root, "frontend", "app.js");
let app = readFileSync(appPath, "utf8");
app = app.replace(/const INJECTED = "[^"]*"/, `const INJECTED = "${contractAddress}"`);
writeFileSync(appPath, app);
console.log(`Injected contract address into app.js: ${contractAddress}`);
