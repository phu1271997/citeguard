# CiteGuard

**A two-sided market that checks a claim against its own cited source, settled by a GenLayer AI validator jury.**

Post a factual claim together with the one source you cite as backing it, and stake a bond.
Anyone who thinks the citation is bogus can stake against it. When it settles, the Intelligent
Contract opens the cited page **on-chain**, a GenLayer validator jury reads it and rules whether
the source really **SUPPORTS** the claim — or fails to, or is cited misleadingly — and the loser
funds the winner. No oracle, no human fact-checker.

- **Live app:** https://citeguard-one.vercel.app
- **Source:** https://github.com/phu1271997/citeguard
- **Contract (studionet):** `0x8FECC1a61C71c400167d3AfAcc09e154cAbaf319`
- **Deploy tx:** `0x4960328c705a5c07e0a5dfcaa031e04168dae2831c02383114890b4100ca13b5`
- **Explorer:** https://explorer-studio.genlayer.com/address/0x8FECC1a61C71c400167d3AfAcc09e154cAbaf319
- **Network:** GenLayer **studionet** (via GenLayer Studio)

---

## Why this dies without GenLayer

The disputed question is subjective and evidence-bound: *"Does the source this claim cites
actually back up the claim?"* Pricing that requires **fetching the cited page** and **reading it
in natural language** to see whether it supports, omits, contradicts, or is twisted away from the
claim. A normal contract can do neither. CiteGuard puts both inside the contract via
`gl.nondet.web.render` (fetch the source on-chain) and `gl.nondet.exec_prompt` (the jury reads
it). Strip the AI + web read and the market cannot exist.

## What makes it more than an escrow: an adversarial two-sided market

The asserter is **not a buyer** and the challenger is **not a worker** — they are opposing
bettors. The jury does not decide "was a job done", it decides "is this citation honest", and the
**loser funds the winner**. That turns citation quality into a priced, contestable market.

## Consensus design (the part that matters)

Validators agree on the **verdict**, not on JSON bytes. In `_judge`, each validator independently
fetches the cited source, runs its own LLM, and endorses the leader **only when its own verdict
matches**. A real `SUPPORTED`-vs-`UNSUPPORTED` split fails consensus; differently-worded
rationales do not. Built on the docs-recommended `gl.vm.run_nondet` (sandboxed), with a fallback
to `run_nondet_unsafe` only on older Studio builds.

## Lifecycle

```
asserter  -> assert_claim(claim, source_url)   [stakes bond A]
challenger-> challenge(claim_id)               [stakes bond B >= A]
anyone    -> resolve(claim_id)   ...reads source_url + LLM verdict...
  SUPPORTED    -> asserter takes the whole pot
  UNSUPPORTED  -> challenger takes the whole pot
  MISLEADING   -> challenger takes the whole pot (cite exists but out of context)
  INCONCLUSIVE -> both bonds refunded (source unreachable / unreadable)
```
An **unchallenged** claim can be resolved too: with no opponent the asserter simply reclaims their
own bond via `RESOLVED_UNCONTESTED`.

### Edge cases handled explicitly
- Source fails to fetch / empty / unreadable → `INCONCLUSIVE`, both sides refunded.
- Challenge bond below the assertion bond → rejected (no cheap griefing).
- Asserter challenging their own claim → rejected.
- Zero bond, too-short claim, non-`http(s)` source → rejected.
- Resolving an already-resolved claim → rejected.
- Terminal state is written **before** any value transfer (re-entrancy safety).
- Payouts and refunds use the SDK's **native account transfer primitive**
  (`_Payee(addr).emit_transfer(...)`, an `gl.evm.contract_interface`), not a
  `get_contract_at(addr)` contract proxy — the correct path for sending native
  GEN to a wallet (EOA).

## Frontend routes

The dApp is split into dedicated views rather than one crammed page:

| Route | Purpose |
|---|---|
| `/` | **Assert & dispute** — connect wallet, stake a claim, challenge open claims, resolve disputed ones. Primary actions only. |
| `/explorer` | **Public ledger** — read-only, no wallet needed. Every dispute with its verdict, rationale, pot, who won, and filters (All / Open / Disputed / Supported / Failed). This is the transparency layer. |

## Seeded on-chain demo

The live contract already holds real, jury-resolved disputes so the Explorer is not empty:

- **Claim #0 — SUPPORTED** — claim that the cited page reserves the domain for documentation
  examples → the jury fetched `https://example.com`, confirmed it, and paid the pot to the asserter.
- **Claim #1 — UNSUPPORTED** — claim that the same page states GenLayer mainnet launched in 2020 →
  the jury found no such statement and paid the pot to the challenger.

Reproduce with `source ~/.genlayer/env.sh && node scripts/seed.mjs` (uses `GENLAYER_PRIVATE_KEY` as
asserter and `GENLAYER_PRIVATE_KEY_2` as challenger).

## Project layout

```
contracts/citeguard.py    # the Intelligent Contract
frontend/index.html       # Home route (assert + dispute)
frontend/explorer.html    # /explorer route (read-only ledger)
frontend/app.js           # shared genlayer-js client (MetaMask signs; no key in the bundle)
frontend/styles.css       # shared styles
tests/test_citeguard.py   # gltest: all four verdicts + edge cases (LLM/web mocked)
scripts/deploy.mjs        # deploy to studionet, writes address to .env
scripts/build.mjs         # bakes the address into frontend/app.js (Vercel build step)
scripts/seed.mjs          # populate real disputes for the Explorer demo
```

## Deploy to studionet (step by step)

1. Fund your deployer wallet with GEN from the Studio **Accounts** panel (studionet, **not** a
   testnet faucet).
2. Load the central keystore and deploy:
   ```bash
   source ~/.genlayer/env.sh      # exports GENLAYER_PRIVATE_KEY (funded)
   npm install
   npm run deploy                 # node scripts/deploy.mjs
   ```
   The script prints the contract address and writes `GENLAYER_CONTRACT_ADDRESS` into `.env`.
3. In the Studio **Run & Debug** view, confirm the deploy transaction shows **`Result: SUCCESS`**
   (not merely `Status: FINALIZED`).

## Run the frontend

```bash
npm run build     # bakes GENLAYER_CONTRACT_ADDRESS from .env into frontend/index.html
npm run dev       # serves frontend/ at http://localhost:8080
```
Connect MetaMask; the app auto-switches to the GenLayer Studio network. To point the UI at a
different CiteGuard instance, append `?address=0x…` to either route.

### Deploying the frontend (Vercel)
`vercel.json` runs `node scripts/build.mjs` as the build command and serves `frontend/`. Set the
`GENLAYER_CONTRACT_ADDRESS` environment variable in the Vercel project.

## Tests

```bash
source ~/.genlayer/env.sh
gltest                       # local simulator (fast)
gltest --network studionet   # against studionet
```
Non-deterministic transactions install LLM/web mocks first (`sim_installMocks`) so the jury
verdict is deterministic in tests.

Settlement is covered by `test_winner_payout_moves_balances` and
`test_split_refund_moves_balances`: they lock a pot, resolve from a neutral third
account, and assert the contract's escrowed-balance ledger (`total_locked`) drains
to 0 to the correct recipient. On a backend that models native-token flow
(studionet / testnet) they additionally assert the exact recipient and contract
native-balance deltas; the in-memory local simulator does not move value on
`emit_transfer`, so those strict deltas engage only off the local sim.

## One-line pitch

*CiteGuard dies without GenLayer because only an on-chain jury that can fetch the cited page and
reason about it can price whether a citation is honest — the loser funds the winner.*
