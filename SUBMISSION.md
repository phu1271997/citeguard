# GENLAYER PROJECT EXPLORER — SUBMISSION (CiteGuard)
**Project:** CiteGuard · **Network:** studionet · **Status: READY TO SUBMIT**

Everything below is live: contract deployed, frontend on Vercel (Home + Explorer routes), and real
jury-resolved disputes already on-chain for a reviewer to inspect without a wallet.

---

# FIELDS TO PASTE INTO THE PORTAL EXPLORER FORM

## Project name
```
CiteGuard
```

## Primary category
```
Dispute Resolution
```
Two parties stake opposite sides of one question — "does the cited source actually back this claim?" —
and a GenLayer validator jury resolves it, loser funds winner. Adversarial adjudication is the product.

## Category tag 1
```
Evidence Assessment
```
The ruling is made on the live cited page the contract fetches itself: `gl.nondet.web.render(source_url)`
in `_judge`, feeding the LLM. The jury reads the source and rules SUPPORTED / UNSUPPORTED / MISLEADING.

## Category tag 2
```
Escrow Claims
```
`assert_claim` and `challenge` lock opposing bonds, and `resolve` conditionally releases the pot to the
winner (or refunds both) — "conditional fund locking and resolution of escrow disputes." This is the
secondary mechanic under the same Primary as tag 1.

**Rejected:** `Jury Selection` (jury is GenLayer validators, not app-selected). Earlier drafts used
`Fact Checking` / `Content Verification` — those are **not** in the taxonomy and have been removed.

> Tags above are taken strictly from `~GEN_RULES/tag_taxonomy_specification.md` (Primary →
> sub-tags only within that Primary). Honest note: both of my current projects are genuinely
> **Dispute Resolution** at core; I did not mis-tag them into other Primaries just to spread the
> catalog. The closest cross-Primary fit for CiteGuard is **AI & Agents → Source Verification** if
> you prefer to diversify — flagged for you to decide at submit time.

## One-liner (176 chars)
```
Stake a factual claim with the source you cite; anyone can stake against it, and a GenLayer AI jury reads that source on-chain and rules whether it backs the claim. Loser pays.
```

## Description (982 chars)
```
A two-sided market that checks a claim against its own cited source, settled on-chain by a GenLayer AI jury.

An asserter posts a factual claim plus the one URL they cite as backing it, and stakes a bond. Anyone who thinks the citation is bogus stakes an equal-or-greater bond against it. At settlement the contract fetches the cited page via gl.nondet.web.render and each validator's LLM rules SUPPORTED, UNSUPPORTED, MISLEADING, or INCONCLUSIVE — judging only against that source. SUPPORTED pays the pot to the asserter; UNSUPPORTED or MISLEADING pays the challenger; INCONCLUSIVE refunds both.

For journalists, researchers, and moderators pricing whether a citation is honest.

Consensus is on the verdict's meaning, not byte-identical JSON: each validator independently re-fetches and re-judges, agreeing only if its verdict matches the leader's. A normal contract cannot fetch a page and reason about whether it substantiates a sentence — that is why CiteGuard needs GenLayer.
```

## How to try it

**Prerequisites**
- MetaMask installed (the app auto-adds & switches to GenLayer Studio Network on Connect — chain `61999` / `0xf22f`).
- Wallet funded with GEN on **studionet**. Empty wallet → banner links to **Studio → Accounts**. `~30,000` wei is enough.
- No wallet needed to browse: open **/explorer** and the ledger loads read-only.

**Step 1 — Browse the Explorer.** Open the live URL → **Explorer**. Real resolved disputes: one **SUPPORTED** (asserter won the pot) and one **UNSUPPORTED** (challenger won), each with the AI rationale, the pot, and the winner. Filters: All / Open / Disputed / Supported / Failed.

**Step 2 — Connect MetaMask** (Home route). Approve connection + the network switch. Fund if balance is 0.

**Step 3 — Assert a claim.** One checkable sentence + the source URL you cite + an assertion bond in wei (e.g. `10000`). Sign in MetaMask.

**Step 4 — Challenge (second account).** Switch MetaMask accounts (the asserter cannot challenge their own claim). Click **Stake against it** and stake at least the assertion bond.

**Step 5 — Resolve.** Click **Resolve with the jury**. Wait ~15–20s — the contract fetches the cited source and the validator jury runs its LLMs. The claim flips to SUPPORTED / UNSUPPORTED / MISLEADING / INCONCLUSIVE; the pot pays the winner (or refunds both) on-chain.

**If something goes wrong:**
- "insufficient funds" — wallet empty on studionet; fund from Studio → Accounts.
- Wrong-chain RPC error — click Reconnect.
- Point the UI at another CiteGuard instance by appending `?address=0x…` to either route.

## Expected verification outcome (479 chars)
```
Open /explorer with no wallet: the ledger shows a SUPPORTED claim (pot paid to the asserter) and an UNSUPPORTED claim (pot paid to the challenger), each with a one-sentence AI rationale citing the fetched source. Both are real validator-jury output — open the contract link, find the resolve tx on explorer-studio.genlayer.com, and it shows GENVM RESULT: SUCCESS with CONSENSUS Accepted. Asserting + challenging + resolving a fresh claim writes a new verdict on-chain in ~15-20s.
```

## Contract link
```
https://explorer-studio.genlayer.com/address/0x8FECC1a61C71c400167d3AfAcc09e154cAbaf319
```
- **Network:** studionet
- **Status:** Preview (Studio deploy = Preview per Explorer rules)
- **Address:** `0x8FECC1a61C71c400167d3AfAcc09e154cAbaf319`
- **Deploy tx:** `0x4960328c705a5c07e0a5dfcaa031e04168dae2831c02383114890b4100ca13b5`

## Website
```
https://citeguard-one.vercel.app
```
Explorer route: `https://citeguard-one.vercel.app/explorer`

## GitHub
```
https://github.com/phu1271997/citeguard
```

## Community links (optional)
Leave blank, or add your Discord / X / Telegram.

---

## SEEDED ON-CHAIN DEMO (already live)
| Claim | Statement | Cited source | Verdict | Winner |
|---|---|---|---|---|
| #0 | "page reserves the domain for documentation examples" | https://example.com | **SUPPORTED** | asserter |
| #1 | "page states GenLayer mainnet launched in 2020" | https://example.com | **UNSUPPORTED** | challenger |

Reproduce: `source ~/.genlayer/env.sh && node scripts/seed.mjs` (asserter = `GENLAYER_PRIVATE_KEY`, challenger = `GENLAYER_PRIVATE_KEY_2`).

## PRE-SUBMISSION CHECKLIST
- [x] Core decision runs via `gl.nondet.*` inside the contract (not off-chain AI)
- [x] Contract deployed on studionet, writes finalize (`Result: SUCCESS`)
- [x] Consensus checks the **verdict**, not JSON schema (`validator_fn` in `_judge`)
- [x] Frontend signs real txs + reads real state; Home + `/explorer` routes
- [x] Explorer shows real resolved cases with no wallet connected
- [x] `GENLAYER_CONTRACT_ADDRESS` baked into `frontend/app.js` on the live deploy
- [x] One-liner ≤180 (176) · Description ≤1000 (982) · Verification ≤500 (479)
- [x] Website + GitHub present
- [ ] Logo attached (PNG/JPEG/WebP, 128–2048 px square, < 2 MB) — optional, ask if you want one generated
- [ ] Demo video recorded
