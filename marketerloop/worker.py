"""Always-on loop for templates that declare a schedule (template.yaml ->
schedule.interval_minutes + a connector with poll: true). meeting-to-content
is manual-trigger, so the worker idles until template 2 (fresh intent queue)
lands. Run: python -m marketerloop.worker [--once]

GitHub Actions is deliberately not this scheduler: scheduled workflows are
delayed/dropped under load and auto-disabled after 60 days of repo inactivity."""
import argparse, sys, time

from . import config
from .db import DB
from .connectors import get_connector
from .templates_loader import list_templates
from .runner import run_template

def tick(db: DB) -> int:
    created = 0
    for tpl in list_templates():
        sched = tpl.spec.get("schedule") or {}
        interval = sched.get("interval_minutes")
        if not interval:
            continue
        last = db.one("SELECT value FROM settings WHERE key=?",
                      (f"schedule_last_run:{tpl.id}",))
        # v0 policy: run every interval; settings table stores the last fire.
        for inp in tpl.spec.get("inputs", []):
            if not (inp.get("poll")):
                continue
            conn = get_connector(inp["connector"])
            if not conn.configured():
                continue
            for stub in conn.list_inputs(limit=10):
                if db.one("SELECT id FROM runs WHERE template=? AND input_hash IS NOT NULL "
                          "AND json_extract(evidence_json,'$.meta.external_id')=?",
                          (tpl.id, stub["external_id"])):
                    continue
                item = conn.get_input(stub["external_id"])
                item.meta["external_id"] = stub["external_id"]
                run_template(db, tpl, conn.name, item)
                created += 1
        db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,datetime('now'))",
                   (f"schedule_last_run:{tpl.id}",))
    return created

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=300,
                    help="fallback loop sleep seconds between ticks")
    args = ap.parse_args()
    db = DB(config.DB_PATH)
    while True:
        n = tick(db)
        print(f"[worker] tick complete, {n} new run(s)", flush=True)
        if args.once:
            return
        time.sleep(args.interval)

if __name__ == "__main__":
    sys.exit(main())
