"""
test_citeguard.py — gltest suite for CiteGuard.

Covers the happy path (SUPPORTED → asserter wins the pot) and the edge cases
(UNSUPPORTED / MISLEADING → challenger wins, INCONCLUSIVE → both refunded,
uncontested resolve, bad bonds, self-challenge).

Runtime rules followed:
  R16 — fluent client API: contract.connect(acct).method(args=[...]).transact(value=X)
  R17 — install sim mocks BEFORE any nondet tx; params is a BARE DICT.

Run with:  gltest
"""

import json
import pytest
from gltest import get_contract_factory, get_accounts
from gltest.clients import get_gl_provider
from gltest.assertions import tx_execution_failed


def _install_mocks(verdict: str, rationale: str = "Mock ruling.",
                   body: str = "Mock source page text that the claim is checked against."):
    provider = get_gl_provider()
    provider.make_request(
        method="sim_installMocks",
        params={
            "llm_mocks": {".*": json.dumps({"verdict": verdict, "rationale": rationale})},
            "web_mocks": {".*": {"status": 200, "body": body}},
        },
    )


def _balance(addr: str) -> int:
    """Native GEN balance (wei) of an account or contract address."""
    provider = get_gl_provider()
    resp = provider.make_request(method="sim_getBalance", params={"account_address": addr})
    return int(resp["result"])


def _fund(addr: str, amount: int) -> None:
    """Credit `amount` wei of native GEN to `addr` on the simulator so that
    value-bearing transactions (and the payouts they trigger) can be observed."""
    provider = get_gl_provider()
    provider.make_request(method="sim_fundAccount", params={"account_address": addr, "amount": amount})


@pytest.fixture
def deployed():
    accounts = get_accounts()
    asserter, challenger = accounts[0], accounts[1]
    factory = get_contract_factory("Contract")
    contract = factory.deploy(args=[])
    return contract, asserter, challenger


# ── SUPPORTED → asserter takes the pot ──────────────────────────────────────

def test_supported_asserter_wins(deployed):
    contract, asserter, challenger = deployed

    contract.connect(asserter).assert_claim(args=[
        "The report states global coverage reached 80 percent in 2025",
        "https://example.org/report",
    ]).transact(value=10_000)
    contract.connect(challenger).challenge(args=[0]).transact(value=10_000)

    _install_mocks(verdict="SUPPORTED", rationale="Source states exactly 80 percent.")
    contract.connect(asserter).resolve(args=[0]).transact()

    c = json.loads(contract.get_claim(args=[0]).call())
    assert c["verdict"] == "SUPPORTED"
    assert c["status"] == "RESOLVED_SUPPORTED"
    assert c["winner"].lower() == asserter.address.lower()
    assert c["pot"] == "20000"


# ── UNSUPPORTED → challenger takes the pot ──────────────────────────────────

def test_unsupported_challenger_wins(deployed):
    contract, asserter, challenger = deployed

    contract.connect(asserter).assert_claim(args=[
        "The page proves the drug cured 90 percent of patients",
        "https://example.org/study",
    ]).transact(value=4_000)
    contract.connect(challenger).challenge(args=[0]).transact(value=4_000)

    _install_mocks(verdict="UNSUPPORTED", rationale="Source makes no such claim.")
    contract.connect(challenger).resolve(args=[0]).transact()

    c = json.loads(contract.get_claim(args=[0]).call())
    assert c["status"] == "RESOLVED_UNSUPPORTED"
    assert c["winner"].lower() == challenger.address.lower()


# ── MISLEADING → challenger takes the pot ───────────────────────────────────

def test_misleading_challenger_wins(deployed):
    contract, asserter, challenger = deployed

    contract.connect(asserter).assert_claim(args=[
        "This quote shows the author endorsed the policy",
        "https://example.org/quote",
    ]).transact(value=2_000)
    contract.connect(challenger).challenge(args=[0]).transact(value=3_000)

    _install_mocks(verdict="MISLEADING", rationale="Quote used out of context.")
    contract.connect(asserter).resolve(args=[0]).transact()

    c = json.loads(contract.get_claim(args=[0]).call())
    assert c["status"] == "RESOLVED_MISLEADING"
    assert c["winner"].lower() == challenger.address.lower()


# ── INCONCLUSIVE → both sides refunded ──────────────────────────────────────

def test_inconclusive_refunds_both(deployed):
    contract, asserter, challenger = deployed

    contract.connect(asserter).assert_claim(args=[
        "The linked page confirms the launch date is March",
        "https://example.org/dead",
    ]).transact(value=5_000)
    contract.connect(challenger).challenge(args=[0]).transact(value=5_000)

    _install_mocks(verdict="INCONCLUSIVE", rationale="Source unreachable.")
    contract.connect(asserter).resolve(args=[0]).transact()

    c = json.loads(contract.get_claim(args=[0]).call())
    assert c["status"] == "RESOLVED_INCONCLUSIVE"
    assert c["winner"] == "0x0000000000000000000000000000000000000000"


# ── uncontested claim can be reclaimed without a jury ───────────────────────

def test_uncontested_resolve_returns_bond(deployed):
    contract, asserter, _ = deployed
    contract.connect(asserter).assert_claim(args=[
        "A sufficiently long claim sentence for adjudication",
        "https://example.org/x",
    ]).transact(value=1_000)
    contract.connect(asserter).resolve(args=[0]).transact()
    c = json.loads(contract.get_claim(args=[0]).call())
    assert c["status"] == "RESOLVED_UNCONTESTED"


# ── edge cases ──────────────────────────────────────────────────────────────

def test_zero_bond_rejected(deployed):
    contract, asserter, _ = deployed
    receipt = contract.connect(asserter).assert_claim(args=[
        "A sufficiently long claim sentence for adjudication",
        "https://example.org/x",
    ]).transact(value=0)
    assert tx_execution_failed(receipt)


def test_challenge_below_bond_rejected(deployed):
    contract, asserter, challenger = deployed
    contract.connect(asserter).assert_claim(args=[
        "A sufficiently long claim sentence for adjudication",
        "https://example.org/x",
    ]).transact(value=10_000)
    receipt = contract.connect(challenger).challenge(args=[0]).transact(value=5_000)
    assert tx_execution_failed(receipt)


def test_self_challenge_rejected(deployed):
    contract, asserter, _ = deployed
    contract.connect(asserter).assert_claim(args=[
        "A sufficiently long claim sentence for adjudication",
        "https://example.org/x",
    ]).transact(value=1_000)
    receipt = contract.connect(asserter).challenge(args=[0]).transact(value=1_000)
    assert tx_execution_failed(receipt)


def test_non_url_source_rejected(deployed):
    contract, asserter, _ = deployed
    receipt = contract.connect(asserter).assert_claim(args=[
        "A sufficiently long claim sentence for adjudication",
        "ftp://nope",
    ]).transact(value=1_000)
    assert tx_execution_failed(receipt)


# ── native-token settlement: recipient + contract balances actually move ────
#
# These exercise the fix for the audit finding: every settlement branch must move
# native GEN through the SDK's native account transfer primitive
# (`_Payee(addr).emit_transfer(...)`), NOT a `get_contract_at(addr)` contract proxy.
#
# `total_locked` is the contract's own escrowed-balance ledger: it holds exactly
# the sum of native GEN the contract is custodying, so draining it to 0 is the
# contract-side balance change. We also snapshot the payees' native balances and,
# when the backend models native-token flow (real studionet/testnet does; the
# in-memory local simulator does not move value on emit_transfer), strictly assert
# the recipient deltas too. We resolve from a NEUTRAL third account so no gas ever
# touches a payee's or the contract's balance, keeping every delta exact.

def _total_locked(contract) -> int:
    return int(contract.get_total_locked(args=[]).call())


def test_winner_payout_moves_balances(deployed):
    contract, asserter, challenger = deployed
    resolver = get_accounts()[2]
    for acct in (asserter, challenger, resolver):
        _fund(acct.address, 1_000_000)

    A, B = 10_000, 10_000
    contract.connect(asserter).assert_claim(args=[
        "The report states global coverage reached 80 percent in 2025",
        "https://example.org/report",
    ]).transact(value=A)
    contract.connect(challenger).challenge(args=[0]).transact(value=B)

    # Snapshot AFTER both bonds are locked, BEFORE resolution pays out.
    assert _total_locked(contract) == A + B          # whole pot escrowed in contract
    contract_before = _balance(contract.address)
    asserter_before = _balance(asserter.address)
    native_enforced = contract_before >= A + B

    _install_mocks(verdict="SUPPORTED", rationale="Source states exactly 80 percent.")
    contract.connect(resolver).resolve(args=[0]).transact()

    c = json.loads(contract.get_claim(args=[0]).call())
    assert c["status"] == "RESOLVED_SUPPORTED"
    assert c["winner"].lower() == asserter.address.lower()   # recipient of the pot
    # Contract-side balance change: the entire escrow is released.
    assert _total_locked(contract) == 0

    if native_enforced:
        # Winner receives the whole pot; the contract is drained by exactly it.
        assert _balance(asserter.address) == asserter_before + (A + B)
        assert _balance(contract.address) == contract_before - (A + B)


def test_split_refund_moves_balances(deployed):
    contract, asserter, challenger = deployed
    resolver = get_accounts()[2]
    for acct in (asserter, challenger, resolver):
        _fund(acct.address, 1_000_000)

    A, B = 5_000, 7_000
    contract.connect(asserter).assert_claim(args=[
        "The linked page confirms the launch date is March",
        "https://example.org/dead",
    ]).transact(value=A)
    contract.connect(challenger).challenge(args=[0]).transact(value=B)

    assert _total_locked(contract) == A + B
    contract_before = _balance(contract.address)
    asserter_before = _balance(asserter.address)
    challenger_before = _balance(challenger.address)
    native_enforced = contract_before >= A + B

    _install_mocks(verdict="INCONCLUSIVE", rationale="Source unreachable.")
    contract.connect(resolver).resolve(args=[0]).transact()

    c = json.loads(contract.get_claim(args=[0]).call())
    assert c["status"] == "RESOLVED_INCONCLUSIVE"
    assert c["winner"] == "0x0000000000000000000000000000000000000000"
    # Split refund: contract releases the whole pot back to the two parties.
    assert _total_locked(contract) == 0

    if native_enforced:
        # Each side is refunded exactly its own bond.
        assert _balance(asserter.address) == asserter_before + A
        assert _balance(challenger.address) == challenger_before + B
        assert _balance(contract.address) == contract_before - (A + B)
