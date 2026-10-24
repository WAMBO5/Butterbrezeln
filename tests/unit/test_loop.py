from app.agents.factory import make_agent
from app.compliance.ledger import Ledger
from app.config.settings import load_settings
from app.llm import AgentOutputError, BudgetExceeded
from app.models import Issue, Review
from app.pipeline.loop import LoopSpec, run_verified

FAKE = load_settings({}, fake_llm=True)
PRODUCER = make_agent(name="producer", description="d", instruction="i", output_schema=Review, tier="judgment",
                      effort="low", settings=FAKE)
VERIFIER = make_agent(name="verifier", description="d", instruction="i", output_schema=Review, tier="fast",
                      effort="low", settings=FAKE)
GOOD = Review(verdict="pass", issues=[])
BAD = Review(verdict="retry", issues=[])  # the gate below rejects verdict "retry"
ISSUE = Issue(type="missed", target_id="x", reason="r", evidence=[], proposed=None)


class Script:
    """A fake `call`: scripted outputs per agent, and the prompts each agent received."""

    def __init__(self, producer, verifier):
        self.outputs = {"producer": list(producer), "verifier": list(verifier)}
        self.prompts = {"producer": [], "verifier": []}

    async def __call__(self, spec, prompt):
        self.prompts[spec.name].append(prompt)
        out = self.outputs[spec.name].pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def gate(payload, out):
    return [] if out.verdict == "pass" else [Issue(type="gate", target_id="g", reason="bad", evidence=[], proposed=None)]


def loop(verifier=VERIFIER, retries=2):
    return LoopSpec(name="t", producer=PRODUCER, output_schema=Review,
                    build_prompt=lambda payload, feedback: f"p:{[i.type for i in feedback]}", gate=gate,
                    verifier=verifier, build_review_prompt=(lambda payload, out: "review") if verifier else None,
                    max_retries=retries)


async def test_pass_first_try():
    script = Script([GOOD], [GOOD])
    res = await run_verified(loop(), {}, script, None)
    assert res.resolved and res.output == GOOD and len(res.attempts) == 1 and res.open_issues == []


async def test_gate_failure_then_pass(tmp_path):
    script = Script([BAD, GOOD], [GOOD])
    led = Ledger(tmp_path)
    res = await run_verified(loop(), {}, script, led)
    assert res.resolved and len(res.attempts) == 2
    assert script.prompts["producer"] == ["p:[]", "p:['gate']"] and len(script.prompts["verifier"]) == 1
    assert [r.kind for r in led.records()] == ["gate", "gate", "review", "loop_result"]


async def test_verifier_retries_until_give_up():
    retry = Review(verdict="retry", issues=[ISSUE])
    script = Script([GOOD, GOOD, GOOD], [retry, retry, retry])
    res = await run_verified(loop(), {}, script, None)
    assert len(res.attempts) == 3 and not res.resolved and res.open_issues == [ISSUE] and res.output == GOOD


async def test_producer_always_fails():
    script = Script([AgentOutputError("producer", "bad json")] * 3, [])
    res = await run_verified(loop(), {}, script, None)
    assert res.output is None and len(res.attempts) == 3 and res.open_issues[0].type == "schema"


async def test_verifier_error_keeps_output():
    script = Script([GOOD], [AgentOutputError("verifier", "boom")])
    res = await run_verified(loop(), {}, script, None)
    assert res.output == GOOD and not res.resolved and res.open_issues[0].type == "verifier_error"


async def test_no_verifier_resolves_on_gate():
    res = await run_verified(loop(verifier=None), {}, Script([GOOD], []), None)
    assert res.resolved and len(res.attempts) == 1


async def test_budget_stops_retrying():
    script = Script([BudgetExceeded("producer", "budget")] * 3, [])
    res = await run_verified(loop(), {}, script, None)
    assert len(res.attempts) == 1 and res.open_issues[0].type == "budget"
