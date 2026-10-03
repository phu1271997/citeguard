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
