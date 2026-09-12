"""Execute a template DAG end to end. Every step writes append-only evidence:
what went in, which prompt/model versions produced what, tokens, cost, and the
human decisions afterwards. Budgets from template.yaml are enforced before any
LLM call; a blocked run is an event, not an exception."""
import hashlib, json

from . import llm
from .config import MODEL
from .db import DB, new_id, _now
from .templates_loader import Template

class BudgetExceeded(Exception):
    pass

def _budget_check(db: DB, tpl: Template):
    b = tpl.budgets
    weekly = b.get("weekly_llm_usd")
    if weekly is not None and db.budget_spend_7d(tpl.id) >= float(weekly):
        raise BudgetExceeded(f"weekly_llm_usd {weekly} reached for {tpl.id}")
    per_day = b.get("max_runs_per_day")
    if per_day is not None and db.runs_today(tpl.id) >= int(per_day):
        raise BudgetExceeded(f"max_runs_per_day {per_day} reached for {tpl.id}")

def run_template(db: DB, tpl: Template, connector_name: str, item) -> dict:
    """item: connectors.base.InputItem. Returns the created run record."""
    run_id = new_id("run")
    evidence = {
        "title": item.title, "text": item.text, "occurred_at": item.occurred_at,
        "source_url": item.source_url, "meta": item.meta,
    }
    db.insert("runs", {
        "id": run_id, "template": tpl.id, "template_version": tpl.version,
        "connector": connector_name, "trigger": tpl.spec.get("trigger", "manual"),
        "status": "queued", "input_title": item.title,
        "input_hash": hashlib.sha256(item.text.encode()).hexdigest()[:16],
        "evidence_json": json.dumps(evidence), "created_at": _now(),
    })
    db.event(run_id, "ingest", {"connector": connector_name, "chars": len(item.text)})
    prompt_versions, totals = {}, {"in": 0, "out": 0, "cost": 0.0, "models": set()}

    try:
        _budget_check(db, tpl)
        db.insert("budget_events", {"template": tpl.id, "at": _now(),
                                    "kind": "run", "amount_usd": 0,
                                    "detail_json": json.dumps({"run_id": run_id})})
        db.set_status(run_id, "running")

        # --- extract_ideas (llm)
        prompt, ver = tpl.prompt("extract_ideas")
        prompt_versions["extract_ideas"] = ver
        system = prompt.replace("{{source_title}}", item.title)
        res = llm.complete(system, f"TRANSCRIPT:\n{item.text}", json_mode=True)
        _bill(db, tpl.id, run_id, res, totals)
        raw = json.loads(res.text)
        ideas = raw.get("ideas", [])
        for idx, i in enumerate(ideas):
            db.insert("ideas", {
                "id": new_id("idea"), "run_id": run_id, "idx": idx,
                "timestamp_ref": i.get("timestamp"), "speaker": i.get("speaker"),
                "idea": i.get("idea", ""), "why_it_lands": i.get("why_it_lands"),
                "score": i.get("score"), "confidential": 1 if i.get("confidential") else 0,
            })
        db.event(run_id, "extract_ideas",
                 {"count": len(ideas), "prompt_version": ver, "model": res.model})

        # --- score (deterministic): keep order by score desc, drop empty
        ideas = sorted((i for i in ideas if i.get("idea")), key=lambda x: -(x.get("score") or 0))
        db.event(run_id, "score", {"kept": len(ideas)})

        # --- draft per format (llm), few-shot from accepted edits
        shareable = [i for i in ideas if not i.get("confidential")]
        for fmt in tpl.formats:
            dprompt, dver = tpl.prompt(fmt)
            prompt_versions[fmt] = dver
            examples = db.recent_edit_examples(fmt, limit=5)
            ex_text = "\n\n".join(
                f"BEFORE:\n{e['original_body']}\nAFTER (the marketer's edit - match this taste):\n{e['edited_body']}"
                for e in examples) or "(no edits yet - default to the style guide above)"
            system = (dprompt
                      .replace("{{source_title}}", item.title)
                      .replace("{{edit_examples}}", ex_text))
            user = json.dumps({"source_title": item.title, "ideas": shareable,
                               "edit_examples": [
                                   {"before": e["original_body"], "after": e["edited_body"]}
                                   for e in examples]})
            res = llm.complete(system, user)
            _bill(db, tpl.id, run_id, res, totals)
            db.insert("drafts", {
                "id": new_id("drft"), "run_id": run_id, "format": fmt,
                "title": item.title, "body": res.text.strip(),
                "prompt_version": dver, "model": res.model,
                "fewshot_count": len(examples), "created_at": _now(),
            })
            db.event(run_id, f"draft:{fmt}",
                     {"prompt_version": dver, "model": res.model,
                      "fewshot_count": len(examples)})

        db.execute("UPDATE runs SET model=?, prompt_versions_json=?, tokens_in=?, "
                   "tokens_out=?, cost_usd=? WHERE id=?",
                   (", ".join(sorted(totals["models"])) or MODEL,
                    json.dumps(prompt_versions), totals["in"],
                    totals["out"], totals["cost"], run_id))
        db.set_status(run_id, "awaiting_approval")
    except BudgetExceeded as e:
        db.set_status(run_id, "failed")
        db.event(run_id, "budget_exceeded", {"reason": str(e)})
        db.execute("UPDATE runs SET error=? WHERE id=?", (str(e), run_id))
    except Exception as e:  # surface, don't swallow: a failed run is evidence too
        db.set_status(run_id, "failed")
        db.event(run_id, "error", {"message": str(e)})
        db.execute("UPDATE runs SET error=? WHERE id=?", (str(e), run_id))
    return db.one("SELECT * FROM runs WHERE id=?", (run_id,))

def _bill(db: DB, template_id: str, run_id: str, res, totals):
    totals["models"].add(res.model)
    totals["in"] += res.tokens_in
    totals["out"] += res.tokens_out
    totals["cost"] += res.cost_usd
    db.insert("budget_events", {
        "template": template_id, "at": _now(), "kind": "llm_call",
        "amount_usd": res.cost_usd,
        "detail_json": json.dumps({"run_id": run_id, "model": res.model}),
    })
