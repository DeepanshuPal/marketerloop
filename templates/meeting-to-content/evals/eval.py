"""Deterministic eval for meeting-to-content. Runs with MOCK_LLM=1, no keys,
no network. CI gate: extraction cites timestamps, scores rank, confidential
lines are flagged, and no confidential text leaks into any draft."""
import json, os, sys

os.environ.setdefault("MOCK_LLM", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from marketerloop.connectors.base import InputItem
from marketerloop.db import DB
from marketerloop.llm import mock_extract_ideas
from marketerloop.runner import run_template
from marketerloop.templates_loader import get_template

HERE = os.path.dirname(__file__)

def main() -> int:
    transcript = open(os.path.join(HERE, "fixtures", "sample_transcript.txt")).read()
    expected = json.load(open(os.path.join(HERE, "expected_ideas.json")))

    # 1. extraction shape
    ideas = mock_extract_ideas(transcript)
    assert len(ideas) >= expected["min_ideas"], f"too few ideas: {len(ideas)}"
    import re
    for i in ideas:
        assert re.fullmatch(r"\d{2}:\d{2}", i["timestamp"]), f"bad timestamp: {i}"
        assert 0.0 <= i["score"] <= 1.0
    scores = [i["score"] for i in ideas]
    assert scores == sorted(scores, reverse=True), "ideas not ranked"

    # 2. coverage: the load-bearing moments survive extraction
    body = " ".join(i["idea"] for i in ideas)
    for options in expected["must_contain_any"]:
        assert any(o in body for o in options), f"missing any of {options}"

    # 3. confidentiality: flagged at extraction
    conf_text = " ".join(i["idea"] for i in ideas if i.get("confidential"))
    assert any(c in conf_text for c in expected["confidential_must_be_flagged"]), \
        "confidential line was not flagged"

    # 4. full pipeline: drafts exist, are pending, and leak nothing confidential
    db = DB(":memory:")
    tpl = get_template("meeting-to-content")
    run = run_template(db, tpl, "manual",
                       InputItem(external_id="fixture", title="Growth sync",
                                 text=transcript))
    assert run["status"] == "awaiting_approval", run["status"]
    drafts = db.q("SELECT * FROM drafts WHERE run_id=?", (run["id"],))
    assert len(drafts) == 3 and all(d["status"] == "pending" for d in drafts)
    for bad in expected["confidential_must_be_flagged"]:
        for d in drafts:
            assert bad not in d["body"], f"confidential text leaked into {d['format']}"

    # 5. evidence: prompt versions + cost recorded on the run
    assert run["prompt_versions_json"] and json.loads(run["prompt_versions_json"])
    print("eval: PASS (extraction, coverage, confidentiality, pipeline, evidence)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
