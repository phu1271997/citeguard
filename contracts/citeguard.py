# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
CiteGuard - a two-sided market that checks a claim against its OWN cited source.

WHY GENLAYER (dies-without-it):
    The disputed question is subjective and evidence-bound: "Does the source a
    claim cites actually back up that claim?" An asserter posts a factual claim
    together with the URL they cite as support, and stakes a bond. A challenger
    who thinks the citation is bogus stakes an equal bond against it. At
    resolution the contract OPENS the cited page on-chain (gl.nondet.web.render)
    and a validator jury reads it and rules whether the source SUPPORTS,
    FAILS TO SUPPORT, or is MISLEADINGLY cited for the claim
    (gl.nondet.exec_prompt). The winning side takes the pot. No oracle and no
    human fact-checker: a normal contract cannot fetch a page and reason about
    whether it substantiates a sentence.

MARKET DESIGN (what makes this different from an escrow):
    This is ADVERSARIAL and two-sided. The asserter is not a buyer and the
    challenger is not a worker - they are opposing bettors. The jury does not
    decide "was a job done", it decides "is this citation honest", and the loser
    funds the winner. That turns citation quality into a priced, contestable
    market.

FLOW:
    asserter  -> assert_claim(claim, source_url)   [stakes bond A]
    challenger-> challenge(claim_id)               [stakes bond B >= A]
    anyone    -> resolve(claim_id)  ...contract reads source_url + LLM rules...
      SUPPORTED   -> asserter takes the whole pot
      UNSUPPORTED -> challenger takes the whole pot
      MISLEADING  -> challenger takes the whole pot (cite is technically there
                     but used out of context / to mean something it does not)
      INCONCLUSIVE-> both bonds refunded (source unreachable / unreadable)
    An UNCHALLENGED claim can be resolved too; with no opponent the asserter
    simply reclaims their own bond regardless of verdict.

CONSENSUS DESIGN (Axis 2 - the critical part):
    Validators agree on the VERDICT, not on JSON bytes. Each validator
    independently fetches source_url, runs its own LLM, and endorses the leader
    only when its own verdict matches. A real SUPPORTED-vs-UNSUPPORTED split
    fails consensus; differently-worded rationales do not.
"""

from genlayer import *
import json
import typing
from dataclasses import dataclass


ZERO_ADDR = Address(b"\x00" * 20)


@allow_storage
@dataclass
class Claim:
    asserter: Address
    challenger: Address         # ZERO until someone challenges
    claim: str                  # the factual sentence being asserted
    source_url: str             # the citation the asserter leans on
    assert_bond: bigint         # asserter's stake, in wei
    challenge_bond: bigint      # challenger's stake, in wei (0 if unchallenged)
    status: str                 # OPEN | CHALLENGED | RESOLVED_SUPPORTED |
                                #   RESOLVED_UNSUPPORTED | RESOLVED_MISLEADING |
                                #   RESOLVED_INCONCLUSIVE | RESOLVED_UNCONTESTED
    verdict: str                # SUPPORTED | UNSUPPORTED | MISLEADING | INCONCLUSIVE | ""
    rationale: str              # AI explanation of the ruling
    winner: Address             # who received the pot (ZERO if refunded/none)


class Contract(gl.Contract):
    claims: TreeMap[u256, Claim]
    next_id: bigint
    total_locked: bigint

    def __init__(self):
        self.next_id = bigint(0)
        self.total_locked = bigint(0)

    # -- helpers --------------------------------------------------------------

    def _require_claim(self, claim_id: u256) -> Claim:
        if claim_id not in self.claims:
            raise Exception("Claim does not exist")
        return self.claims[claim_id]

    def _addr_str(self, addr: Address) -> str:
        try:
            return addr.as_hex
        except Exception:
            return str(addr)

    # -- asserter posts a claim + the source they cite ------------------------

    @gl.public.write.payable
    def assert_claim(self, claim: str, source_url: str) -> u256:
        amount = gl.message.value
        if amount == 0:
            raise Exception("Assertion bond must be > 0")
        if len(claim.strip()) < 12:
            raise Exception("Claim too short to adjudicate")
        if len(source_url.strip()) == 0:
            raise Exception("A source URL is required")
        if not source_url.strip().lower().startswith(("http://", "https://")):
            raise Exception("source_url must be an http(s) URL")

        claim_id = u256(self.next_id)
        self.claims[claim_id] = Claim(
            asserter=gl.message.sender_address,
            challenger=ZERO_ADDR,
            claim=claim,
            source_url=source_url.strip(),
            assert_bond=bigint(amount),
            challenge_bond=bigint(0),
            status="OPEN",
            verdict="",
            rationale="",
            winner=ZERO_ADDR,
        )
        self.next_id = self.next_id + bigint(1)
        self.total_locked = self.total_locked + bigint(amount)
        return claim_id

    # -- challenger stakes against the citation -------------------------------

    @gl.public.write.payable
    def challenge(self, claim_id: u256) -> None:
        claim = self._require_claim(claim_id)
        if claim.status != "OPEN":
            raise Exception("Claim is not open to challenge")
        if gl.message.sender_address == claim.asserter:
            raise Exception("Asserter cannot challenge their own claim")
        amount = gl.message.value
        if amount < claim.assert_bond:
            raise Exception("Challenge bond must be at least the assertion bond")

        claim.challenger = gl.message.sender_address
        claim.challenge_bond = bigint(amount)
        claim.status = "CHALLENGED"
        self.total_locked = self.total_locked + bigint(amount)

    # -- permissionless resolution: read the cited source + AI verdict --------

    @gl.public.write
    def resolve(self, claim_id: u256) -> str:
        claim = self._require_claim(claim_id)
        if claim.status not in ("OPEN", "CHALLENGED"):
            raise Exception("Claim is already resolved")

        # Uncontested claims need no jury - nobody is betting against the
        # asserter, so they simply reclaim their own bond.
        if claim.status == "OPEN":
            claim.status = "RESOLVED_UNCONTESTED"
            claim.winner = claim.asserter
            amount = claim.assert_bond
            self.total_locked = self.total_locked - amount
            gl.get_contract_at(claim.asserter).emit_transfer(value=u256(amount))
            return claim.status

        # Read storage BEFORE the nondet block.
        claim_text = claim.claim
        source_url = claim.source_url

        verdict, rationale = self._judge(claim_text, source_url)
        claim.verdict = verdict
        claim.rationale = rationale

        pot = claim.assert_bond + claim.challenge_bond
        if verdict == "SUPPORTED":
            claim.status = "RESOLVED_SUPPORTED"
            claim.winner = claim.asserter
            self.total_locked = self.total_locked - pot
            gl.get_contract_at(claim.asserter).emit_transfer(value=u256(pot))
        elif verdict in ("UNSUPPORTED", "MISLEADING"):
            claim.status = "RESOLVED_UNSUPPORTED" if verdict == "UNSUPPORTED" else "RESOLVED_MISLEADING"
            claim.winner = claim.challenger
            self.total_locked = self.total_locked - pot
            gl.get_contract_at(claim.challenger).emit_transfer(value=u256(pot))
        else:  # INCONCLUSIVE - refund both sides their own bonds
            claim.status = "RESOLVED_INCONCLUSIVE"
            claim.winner = ZERO_ADDR
            self.total_locked = self.total_locked - pot
            gl.get_contract_at(claim.asserter).emit_transfer(value=u256(claim.assert_bond))
            gl.get_contract_at(claim.challenger).emit_transfer(value=u256(claim.challenge_bond))
        return claim.status

    # -------------------------------------------------------------------------
    # THE NON-DETERMINISTIC HEART - read the cited source + LLM judgement.
    # -------------------------------------------------------------------------

    def _judge(self, claim_text: str, source_url: str) -> tuple[str, str]:

        def leader_fn():
            try:
                page = gl.nondet.web.render(source_url, mode="text")
            except Exception as e:
                page = f"__FETCH_FAILED__: {e}"
            excerpt = page[:6000] if isinstance(page, str) else str(page)

            prompt = f"""You are an impartial citation auditor. Someone made a factual claim and
cited ONE source as backing it. Judge the claim ONLY against that cited source,
not against your own outside knowledge.

THE CLAIM:
{claim_text}

CITED SOURCE URL: {source_url}
FETCHED SOURCE (text extract, may be truncated):
{excerpt}

Rule on how the source relates to the claim:
- SUPPORTED    : the source clearly states or directly backs the claim.
- UNSUPPORTED  : the source does not contain or back the claim (absent, or it
                 says something different / contradicts it).
- MISLEADING   : the words appear in the source but are used out of context or
                 twisted to mean something the source does not actually assert.
- INCONCLUSIVE : the source could not be fetched (look for __FETCH_FAILED__),
                 is empty, or is unreadable, so backing cannot be assessed.

Respond with ONLY a JSON object, no prose, no markdown:
{{"verdict": "SUPPORTED" | "UNSUPPORTED" | "MISLEADING" | "INCONCLUSIVE", "rationale": "<one or two sentences>"}}"""

            return gl.nondet.exec_prompt(prompt, response_format="json")

        valid = ("SUPPORTED", "UNSUPPORTED", "MISLEADING", "INCONCLUSIVE")

        def _extract(payload) -> str:
            try:
                data = json.loads(payload) if isinstance(payload, str) else payload
                v = str(data.get("verdict", "")).upper().strip()
                return v if v in valid else ""
            except Exception:
                return ""

        def validator_fn(leader_res: typing.Any) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            leader_verdict = _extract(leader_res.calldata)
            if leader_verdict == "":
                return False
            try:
                mine = leader_fn()
            except Exception:
                return False
            my_verdict = _extract(mine)
            # meaning-level consensus: match on VERDICT, ignore rationale wording.
            return my_verdict != "" and my_verdict == leader_verdict

        runner = getattr(gl.vm, "run_nondet", None) or gl.vm.run_nondet_unsafe
        result = runner(leader_fn, validator_fn)

        try:
            payload = result.calldata if isinstance(result, gl.vm.Return) else result
            data = json.loads(payload) if isinstance(payload, str) else payload
            verdict = str(data.get("verdict", "INCONCLUSIVE")).upper().strip()
            if verdict not in valid:
                verdict = "INCONCLUSIVE"
            rationale = str(data.get("rationale", ""))[:500]
        except Exception:
            verdict = "INCONCLUSIVE"
            rationale = "Could not parse a verdict; refunding both sides."
        return verdict, rationale

    # -- read-only views (for the frontend) -----------------------------------

    @gl.public.view
    def get_claim(self, claim_id: u256) -> str:
        return json.dumps(self._claim_dict(claim_id, self._require_claim(claim_id)))

    @gl.public.view
    def list_claims(self) -> str:
        out = []
        for cid in self.claims:
            out.append(self._claim_dict(cid, self.claims[cid]))
        return json.dumps(out)

    @gl.public.view
    def get_claim_count(self) -> int:
        return int(self.next_id)

    @gl.public.view
    def get_total_locked(self) -> str:
        return str(int(self.total_locked))

    def _claim_dict(self, claim_id: u256, c: Claim) -> dict:
        return {
            "id": int(claim_id),
            "asserter": self._addr_str(c.asserter),
            "challenger": self._addr_str(c.challenger),
            "claim": c.claim,
            "source_url": c.source_url,
            "assert_bond": str(int(c.assert_bond)),
            "challenge_bond": str(int(c.challenge_bond)),
            "pot": str(int(c.assert_bond + c.challenge_bond)),
            "status": c.status,
            "verdict": c.verdict,
            "rationale": c.rationale,
            "winner": self._addr_str(c.winner),
        }
