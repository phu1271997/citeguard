// Shared client logic for CiteGuard — used by both index.html (Home) and
// explorer.html (/explorer). Page-aware wiring.
import { createClient } from "https://esm.sh/genlayer-js@1.1.8";
import { studionet } from "https://esm.sh/genlayer-js@1.1.8/chains";

// Injected at build time by scripts/build.mjs from GENLAYER_CONTRACT_ADDRESS.
const INJECTED = "0x5b7b9846554B4312C61B47649623F54866ef239e";

const CHAIN = studionet;
const CHAIN_ID_HEX = "0x" + CHAIN.id.toString(16);
const RPC_URL = "https://studio.genlayer.com/api";
const EXPLORER = "https://explorer-studio.genlayer.com";

const $ = (id) => document.getElementById(id);
export const short = (a) => (a && a.length > 12 ? a.slice(0, 6) + "…" + a.slice(-4) : a || "");
export const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
export const fmt = (n) => { try { return BigInt(n).toLocaleString("en-US"); } catch { return n; } };
export const isZero = (a) => !a || /^0x0+$/.test(a);

let contractAddress = INJECTED;
const qp = new URLSearchParams(location.search).get("address");
if (qp && /^0x[0-9a-fA-F]{40}$/.test(qp)) contractAddress = qp;
else {
  const saved = localStorage.getItem("citeguard.address");
  if (saved && /^0x[0-9a-fA-F]{40}$/.test(saved)) contractAddress = saved;
}
export const getAddress = () => contractAddress;
export function setAddress(a) {
  contractAddress = a; localStorage.setItem("citeguard.address", a);
  if ($("explorerLink")) $("explorerLink").href = `${EXPLORER}/address/${a}`;
}
const hasAddress = () => /^0x[0-9a-fA-F]{40}$/.test(contractAddress);

let account = null, client = null;
const readClient = createClient({ chain: CHAIN });
export const getClient = () => client || readClient;

export function toast(msg, isErr = false, hold = false) {
  const t = $("toast"); if (!t) return;
  t.className = "toast" + (isErr ? " err" : "");
  t.innerHTML = (hold ? '<span class="spin"></span>' : "") + msg;
  t.style.display = "block";
  if (!hold) { clearTimeout(t._h); t._h = setTimeout(() => (t.style.display = "none"), 4800); }
}

async function ensureStudioChain() {
  if (!window.ethereum) throw new Error("MetaMask not detected");
  try {
    await window.ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_ID_HEX }] });
  } catch (err) {
    if (err.code === 4902 || err.code === -32603) {
      await window.ethereum.request({ method: "wallet_addEthereumChain", params: [{
        chainId: CHAIN_ID_HEX, chainName: "GenLayer Studio Network",
        nativeCurrency: { name: "GEN Token", symbol: "GEN", decimals: 18 },
        rpcUrls: [RPC_URL], blockExplorerUrls: [EXPLORER],
      }] });
    } else throw err;
  }
}

async function connect() {
  try {
    if (!window.ethereum) { toast("Install MetaMask — this dApp signs with MetaMask, not a burner key", true); return; }
    const accs = await window.ethereum.request({ method: "eth_requestAccounts" });
    if (!accs || !accs.length) throw new Error("No account selected");
    account = accs[0];
    await ensureStudioChain();
    client = createClient({ chain: CHAIN, account });
    paintWallet();
    toast("Wallet ready on studionet");
    await balanceHint();
    document.dispatchEvent(new CustomEvent("wallet:ready"));
  } catch (e) { toast("Connect failed: " + (e.shortMessage || e.message), true); }
}

function paintWallet() {
  if ($("walletInfo")) {
    $("walletInfo").textContent = account ? "Connected · " + short(account) : "Not connected";
    $("walletInfo").className = account ? "addr" : "net";
  }
  if ($("connectBtn")) $("connectBtn").textContent = account ? "Reconnect" : "Connect wallet";
}

async function balanceHint() {
  if (!$("fundHint") || !account) return;
  try {
    const bal = await window.ethereum.request({ method: "eth_getBalance", params: [account, "latest"] });
    const zero = !bal || bal === "0x0" || bal === "0x";
    $("fundHint").style.display = zero ? "block" : "none";
    if ($("fundAddr")) $("fundAddr").textContent = account;
  } catch {}
}
export const getAccount = () => account;

export function requireReady() {
  if (!client) { toast("Connect your wallet first", true); return false; }
  if (!hasAddress()) { toast("No valid contract address loaded", true); return false; }
  return true;
}

export async function listClaims() {
  if (!hasAddress()) throw new Error("No contract address set");
  const raw = await getClient().readContract({ address: contractAddress, functionName: "list_claims", args: [] });
  return JSON.parse(raw);
}
export async function totalLocked() {
  try { return await getClient().readContract({ address: contractAddress, functionName: "get_total_locked", args: [] }); }
  catch { return "0"; }
}

export async function send(fn, args, value, pending) {
  if (!requireReady()) return false;
  try {
    toast((pending || "Sending") + " — approve in MetaMask…", false, true);
    const req = { address: contractAddress, functionName: fn, args };
    if (value !== undefined) req.value = BigInt(value);
    const hash = await client.writeContract(req);
    toast("Waiting for the validator jury to finalize…", false, true);
    await client.waitForTransactionReceipt({ hash, status: "FINALIZED" });
    toast("Done — refreshing");
    return true;
  } catch (e) { toast("Action failed: " + (e.shortMessage || e.message), true); return false; }
}

export function initCommon() {
  if ($("connectBtn")) $("connectBtn").onclick = connect;
  if ($("explorerLink")) $("explorerLink").href = `${EXPLORER}/address/${contractAddress}`;
  paintWallet();
  if (window.ethereum && window.ethereum.on) {
    window.ethereum.on("accountsChanged", (a) => {
      account = a && a[0] ? a[0] : null;
      client = account ? createClient({ chain: CHAIN, account }) : null;
      paintWallet(); balanceHint();
      document.dispatchEvent(new CustomEvent("wallet:changed"));
    });
    window.ethereum.on("chainChanged", () => location.reload());
  }
}

export function stampFor(status) {
  if (status === "OPEN") return ["OPEN", "s-OPEN"];
  if (status === "CHALLENGED") return ["DISPUTED", "s-CHALLENGED"];
  if (status === "RESOLVED_SUPPORTED") return ["SUPPORTED", "s-SUPPORTED"];
  if (status === "RESOLVED_UNSUPPORTED") return ["UNSUPPORTED", "s-AGAINST"];
  if (status === "RESOLVED_MISLEADING") return ["MISLEADING", "s-AGAINST"];
  if (status === "RESOLVED_INCONCLUSIVE") return ["INCONCLUSIVE", "s-MUTE"];
  if (status === "RESOLVED_UNCONTESTED") return ["UNCONTESTED", "s-MUTE"];
  return [status, "s-MUTE"];
}
export { EXPLORER };
