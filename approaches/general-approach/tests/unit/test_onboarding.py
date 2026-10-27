from pathlib import Path

import pytest

from app.gates.market_gate import market_claims, market_gate
from app.markets.onboarding import SourceDoc, read_source
from app.models import MarketProfile, MarketRule, RegulationVersion, SourceRef

SAMPLE = Path("app/markets/samples/market_d_source.md")
VERSIONS = [RegulationVersion(regulation=r, title=r, role="base", version_label="1", status="", file_name="", sha256="")
            for r in ("UN R48", "UN R148", "UN R10")]
SOURCE = SourceDoc(document_id="note", text="Market D applies UN Regulation No. 48 as a mandatory rule.", sample=False)


def profile(rules, outside=(), illustrative=False):
    return MarketProfile(market_id="market_d", name="Market D", illustrative=illustrative, rules=rules,
                         outside_corpus=list(outside))


def rule(reg="UN R48", quote="applies UN Regulation No. 48", doc="note"):
    return MarketRule(regulation=reg, status="mandatory", version_role="base",
                      source_ref=SourceRef(document_id=doc, quote=quote) if quote is not None else None)


def test_gate_accepts_cited_rule():
    assert market_gate([SOURCE], VERSIONS, profile([rule()])) == []


def test_gate_rejects_uncited_and_unfound_quotes():
    assert [i.type for i in market_gate([SOURCE], VERSIONS, profile([rule(quote=None)]))] == ["uncited"]
    assert [i.type for i in market_gate([SOURCE], VERSIONS, profile([rule(quote="applies R99")]))] == ["quote_not_found"]
    assert [i.type for i in market_gate([SOURCE], VERSIONS, profile([rule(reg="UN R999")]))] == ["unknown_regulation"]
    outside = SourceRef(document_id="note", quote="a rule nobody wrote")
    assert [i.type for i in market_gate([SOURCE], VERSIONS, profile([rule()], [outside]))] == ["quote_not_found"]


def test_sample_source_forces_illustrative():
    sample = read_source(SAMPLE)
    assert sample.sample and sample.document_id == "market_d_source"
    p = profile([rule(quote="applies UN Regulation No. 48", doc="market_d_source")])
    assert [i.type for i in market_gate([sample], VERSIONS, p)] == ["not_illustrative"]


def test_claims_carry_context():
    claims = market_claims([SOURCE], profile([rule()]))
    assert len(claims) == 1 and "Market D applies" in claims[0].cited_text


@pytest.mark.integration
@pytest.mark.skipif(not Path("industrial-ai-hackathon/regulations/index.json").exists(), reason="challenge data missing")
def test_cli_onboards_sample(monkeypatch, tmp_path, capsys):
    from app.cli import main
    from app.markets.profiles import load_market_profiles

    monkeypatch.setenv("CERTIVITY_DATA_DIR", str(tmp_path))
    assert main(["--fake-llm", "markets", "add", "Market D", "--source", str(SAMPLE)]) == 0
    written = list((tmp_path / "markets").glob("*.yaml"))
    assert [p.name for p in written] == ["market_d.yaml"]
    [p] = load_market_profiles([tmp_path / "markets"], ["UN R48", "UN R148", "UN R10"])
    assert p.illustrative and {r.regulation for r in p.rules} == {"UN R48", "UN R148", "UN R10"} and p.outside_corpus
