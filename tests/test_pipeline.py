"""Pipeline: transcript -> ideas -> drafts -> human decisions -> learning.
Everything runs in MOCK_LLM mode: deterministic, no keys, no network."""
import json, os

from marketerloop.approvals import approve, edit, reject
from marketerloop.connectors.base import InputItem
from marketerloop.db import DB, new_id, _now
from marketerloop.runner import run_template
from marketerloop.templates_loader import get_template

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "templates",
                      "meeting-to-content", "evals", "fixtures", "sample_transcript.txt")

def _db(tmp_path):
    return DB(str(tmp_path / "t.db"))

def _run(db):
    tpl = get_template("meeting-to-content")
    return run_template(db, tpl, "manual",
                        InputItem(external_id="t", title="Growth sync",
                                  text=open(SAMPLE).read()))

def test_end_to_end(tmp_path):
    db = _db(tmp_path)
    run = _run(db)
    assert run["status"] == "awaiting_approval"
    ideas = db.q("SELECT * FROM ideas WHERE run_id=?", (run["id"],))
    assert len(ideas) >= 4
    assert all(i["timestamp_ref"] for i in ideas)          # every idea cites its line
    drafts = db.q("SELECT * FROM drafts WHERE run_id=?", (run["id"],))
    assert {d["format"] for d in drafts} == {"linkedin_post", "x_thread", "newsletter_blurb"}
    assert all(d["status"] == "pending" for d in drafts)
    # confidential meeting content never leaks into drafts
    for d in drafts:
        assert "Acme Corp" not in d["body"] and "pricing experiment" not in d["body"]
    # evidence: prompt versions + cost recorded
    assert json.loads(run["prompt_versions_json"])["extract_ideas"] == "v1"

def test_decisions_and_learning(tmp_path):
    db = _db(tmp_path)
    run = _run(db)
    drafts = db.q("SELECT * FROM drafts WHERE run_id=?", (run["id"],))
    by_fmt = {d["format"]: d for d in drafts}

    approve(db, by_fmt["x_thread"]["id"])
    reject(db, by_fmt["newsletter_blurb"]["id"], reason="too corporate")
    edit(db, by_fmt["linkedin_post"]["id"],
         by_fmt["linkedin_post"]["id"] and by_fmt["linkedin_post"]["body"] + "\n\n(PS: we ship Friday.)")

    assert db.one("SELECT status FROM drafts WHERE id=?", (by_fmt["x_thread"]["id"],))["status"] == "approved"
    assert db.one("SELECT status FROM drafts WHERE id=?", (by_fmt["newsletter_blurb"]["id"],))["status"] == "rejected"
    assert db.one("SELECT status FROM drafts WHERE id=?", (by_fmt["linkedin_post"]["id"],))["status"] == "edited"

    examples = db.q("SELECT * FROM edit_examples WHERE format='linkedin_post'")
    assert len(examples) == 1 and "(PS: we ship Friday.)" in examples[0]["edited_body"]

    # the next run's linkedin draft is few-shot on that edit
    run2 = _run(db)
    li = db.one("SELECT * FROM drafts WHERE run_id=? AND format='linkedin_post'", (run2["id"],))
    assert li["fewshot_count"] == 1

def test_budget_enforced(tmp_path):
    db = _db(tmp_path)
    db.insert("budget_events", {"template": "meeting-to-content", "at": _now(),
                                "kind": "llm_call", "amount_usd": 99.0,
                                "detail_json": "{}"})
    run = _run(db)
    assert run["status"] == "failed"
    assert "weekly_llm_usd" in (run["error"] or "")
