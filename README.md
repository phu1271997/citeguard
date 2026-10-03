# CiteGuard

**A two-sided market that checks a claim against its own cited source, settled by a GenLayer AI validator jury.**

Post a factual claim together with the one source you cite as backing it, and stake a bond.
Anyone who thinks the citation is bogus can stake against it. When it settles, the Intelligent
Contract opens the cited page **on-chain**, a GenLayer validator jury reads it and rules whether
the source really **SUPPORTS** the claim — or fails to, or is cited misleadingly — and the loser
funds the winner. No oracle, no human fact-checker.

- **Live app:** _TO BE FILLED AFTER VERCEL DEPLOY_
- **Contract (studionet):** `0x7b56b5042DE319E35f3C8c1bABb7c0d0B8e400c1`
- **Deploy tx:** `0x2fe53689564cc36a86876e9b1031fbf8cfea74af53840c103f8301aab46493cb`
- **Explorer:** https://explorer-studio.genlayer.com/address/0x7b56b5042DE319E35f3C8c1bABb7c0d0B8e400c1
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

## Project layout

```
contracts/citeguard.py    # the Intelligent Contract
frontend/index.html       # genlayer-js dApp (MetaMask signs; no key in the bundle)
tests/test_citeguard.py   # gltest: all four verdicts + edge cases (LLM/web mocked)
scripts/deploy.mjs        # deploy to studionet, writes address to .env
scripts/build.mjs         # bakes the address into the frontend (Vercel build step)
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
Connect MetaMask; the app auto-switches to the GenLayer Studio network. You can paste any deployed
CiteGuard address into the **Load** box to point the UI at another instance.

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

## One-line pitch

*CiteGuard dies without GenLayer because only an on-chain jury that can fetch the cited page and
reason about it can price whether a citation is honest — the loser funds the winner.*
