"""marketerloop - the CLI is the product.

Clone the repo, add your keys, run templates, work the approval queue in your
terminal. No platform, no hosted anything: your keys, your data, your SQLite
file. A thin localhost board may come later - the queue is the truth either way."""
import argparse, json, os, shlex, subprocess, sys, tempfile

from dotenv import load_dotenv

load_dotenv()  # .env in the repo root, never committed

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config
from .approvals import approve, edit, reject
from .connectors import get_connector, list_connectors
from .connectors.base import InputItem
from .db import DB
from .runner import run_template
from .templates_loader import get_template, list_templates

# force_terminal only via env override: real users are on a tty; the override
# exists so captured output (docs, demos) keeps Unicode boxes and color.
console = Console(force_terminal=os.environ.get("MARKETERLOOP_FORCE_TTY") == "1")
ACCENT = "dark_orange"
WARM = "wheat1"

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "templates",
                      "meeting-to-content", "evals", "fixtures", "sample_transcript.txt")

def db() -> DB:
    return DB(config.DB_PATH)

def _status_color(s: str) -> str:
    return {"pending": "yellow", "approved": "green", "edited": "cyan",
            "rejected": "red", "awaiting_approval": "yellow",
            "done": "green", "failed": "red", "running": "blue"}.get(s, "white")

def _short(i: str) -> str:
    return i.split("_", 1)[-1][:8]

# ---------------- commands ----------------

def cmd_templates(args):
    if args.what == "list":
        t = Table(title="templates", title_style=ACCENT, border_style=WARM)
        for col in ("id", "version", "trigger", "description"):
            t.add_column(col, overflow="fold")
        for tpl in list_templates():
            t.add_row(tpl.id, tpl.version, str(tpl.spec.get("trigger")),
                      tpl.spec.get("description", "").split("\n")[0])
        console.print(t)
    else:
        tpl = get_template(args.template_id)
        console.print(Panel(
            f"[bold]{tpl.spec['name']}[/] v{tpl.version}\n\n{tpl.spec['description']}\n\n"
            f"DAG: " + " -> ".join(s["id"] for s in tpl.spec["dag"]) +
            f"\nApproval: {', '.join(tpl.formats)} (required: {tpl.spec['approval']['required']})"
            f"\nBudgets: {json.dumps(tpl.budgets)}",
            title=tpl.id, border_style=ACCENT))

def cmd_connectors(args):
    t = Table(title="connectors", title_style=ACCENT, border_style=WARM)
    for col in ("name", "tier", "status", "key", "configured"):
        t.add_column(col)
    for c in list_connectors():
        conf = "[green]yes[/]" if c.configured() else "[dim]no[/]"
        t.add_row(c.name, c.tier, c.status, c.requires_key or "-", conf)
    console.print(t)
    console.print("[dim]A connector with no key simply isn't configured. Keys live in .env[/]")

def cmd_inputs(args):
    conn = get_connector(args.connector)
    if not conn.configured():
        console.print(f"[red]{conn.name} is not configured[/] - needs {conn.requires_key}")
        raise SystemExit(1)
    t = Table(title=f"{conn.name}: recent inputs", title_style=ACCENT, border_style=WARM)
    t.add_column("id"); t.add_column("title", overflow="fold"); t.add_column("when")
    for i in conn.list_inputs(limit=args.limit):
        t.add_row(i["external_id"], i["title"], str(i.get("occurred_at") or ""))
    console.print(t)

def cmd_run(args):
    tpl = get_template(args.template)
    if args.sample:
        item = InputItem(external_id="sample", title="Growth sync (sample)",
                         text=open(SAMPLE).read())
        connector = "manual"
    elif args.text:
        item = InputItem(external_id="adhoc", title=args.title or "Pasted notes",
                         text=args.text)
        connector = "manual"
    elif args.file:
        item = InputItem(external_id=os.path.basename(args.file),
                         title=args.title or os.path.basename(args.file),
                         text=open(args.file).read())
        connector = "manual"
    elif args.stdin:
        item = InputItem(external_id="stdin", title=args.title or "Pasted notes",
                         text=sys.stdin.read())
        connector = "manual"
    elif args.connector and args.external_id:
        conn = get_connector(args.connector)
        if not conn.configured():
            console.print(f"[red]{conn.name} is not configured[/] - needs {conn.requires_key} in .env")
            raise SystemExit(1)
        item = conn.get_input(args.external_id)
        connector = conn.name
    else:
        console.print("[red]give me an input:[/] --sample, --file, --text, --stdin, "
                      "or --connector <name> --external-id <id>")
        raise SystemExit(2)

    with console.status(f"[{WARM}]running {tpl.id} on “{item.title}”...[/]"):
        run = run_template(db(), tpl, connector, item)
    color = _status_color(run["status"])
    console.print(Panel(
        f"run [bold]{run['id']}[/]\nstatus: [{color}]{run['status']}[/]\n"
        f"model: {run.get('model') or config.MODEL}\n"
        f"tokens: {run['tokens_in']} in / {run['tokens_out']} out"
        f"   cost: ${run['cost_usd']:.4f}\n\n"
        f"next: [bold]marketerloop queue[/] to review the drafts",
        title=f"[{ACCENT}]{tpl.id}[/]", border_style=ACCENT))
    if run["status"] == "failed":
        console.print(f"[red]error:[/] {run.get('error')}")

def cmd_runs(args):
    t = Table(title="runs", title_style=ACCENT, border_style=WARM)
    for col in ("id", "template", "connector", "input", "status", "cost", "created"):
        t.add_column(col, overflow="fold")
    for r in db().q("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (args.limit,)):
        t.add_row(_short(r["id"]), r["template"], r["connector"],
                  (r["input_title"] or "")[:28],
                  f"[{_status_color(r['status'])}]{r['status']}[/]",
                  f"${r['cost_usd']:.4f}", r["created_at"][:16])
    console.print(t)

def cmd_run_show(args):
    d = db()
    r = d.one("SELECT * FROM runs WHERE id=?", (args.run_id,)) or \
        d.one("SELECT * FROM runs WHERE id LIKE ?", (f"%{args.run_id}%",))
    if not r:
        console.print(f"[red]no run matching {args.run_id}[/]"); raise SystemExit(1)
    ideas = d.q("SELECT * FROM ideas WHERE run_id=? ORDER BY idx", (r["id"],))
    drafts = d.q("SELECT * FROM drafts WHERE run_id=?", (r["id"],))
    events = d.q("SELECT * FROM run_events WHERE run_id=? ORDER BY id", (r["id"],))
    console.print(Panel(
        f"[bold]{r['input_title']}[/]\ntemplate: {r['template']} v{r['template_version']}\n"
        f"connector: {r['connector']}   status: [{_status_color(r['status'])}]{r['status']}[/]\n"
        f"model: {r.get('model')}   prompts: {r.get('prompt_versions_json')}\n"
        f"tokens: {r['tokens_in']}/{r['tokens_out']}   cost: ${r['cost_usd']:.4f}\n"
        f"evidence sha: {r['input_hash']}",
        title=f"[{ACCENT}]run {_short(r['id'])}[/]", border_style=ACCENT))
    if ideas:
        t = Table(title="ideas (timestamped evidence)", title_style=WARM, border_style=WARM)
        t.add_column("ts"); t.add_column("speaker"); t.add_column("score")
        t.add_column("idea", overflow="fold"); t.add_column("conf")
        for i in ideas:
            t.add_row(i["timestamp_ref"] or "", i["speaker"] or "",
                      f"{i['score']:.2f}", i["idea"][:90],
                      "[red]yes[/]" if i["confidential"] else "")
        console.print(t)
    if drafts:
        t = Table(title="drafts", title_style=WARM, border_style=WARM)
        t.add_column("id"); t.add_column("format"); t.add_column("status"); t.add_column("few-shot")
        for dr in drafts:
            t.add_row(_short(dr["id"]), dr["format"],
                      f"[{_status_color(dr['status'])}]{dr['status']}[/]", str(dr["fewshot_count"]))
        console.print(t)
    console.print("[dim]events: " + " -> ".join(e["event"] for e in events) + "[/]")

def _find_draft(d: DB, draft_id: str):
    return d.one("SELECT * FROM drafts WHERE id=?", (draft_id,)) or \
        d.one("SELECT * FROM drafts WHERE id LIKE ?", (f"%{draft_id}%",))

def cmd_queue(args):
    rows = db().q(
        "SELECT d.*, r.input_title FROM drafts d JOIN runs r ON r.id=d.run_id "
        + ("" if args.all else "WHERE d.status='pending' ")
        + "ORDER BY d.created_at DESC LIMIT ?", (args.limit,))
    if not rows:
        console.print(f"[{WARM}]queue is empty - run something:[/] marketerloop run meeting-to-content --sample")
        return
    t = Table(title="approval queue" + ("" if args.all else " (pending)"),
              title_style=ACCENT, border_style=WARM)
    t.add_column("id"); t.add_column("format"); t.add_column("from")
    t.add_column("status"); t.add_column("preview", overflow="fold")
    for r in rows:
        t.add_row(_short(r["id"]), r["format"], (r["input_title"] or "")[:24],
                  f"[{_status_color(r['status'])}]{r['status']}[/]",
                  r["body"].replace("\n", " ")[:60])
    console.print(t)
    console.print("[dim]marketerloop show <id> · approve <id> · edit <id> · reject <id>[/]")

def cmd_show(args):
    dr = _find_draft(db(), args.draft_id)
    if not dr:
        console.print(f"[red]no draft matching {args.draft_id}[/]"); raise SystemExit(1)
    console.print(Panel(dr["body"],
        title=f"[{ACCENT}]{dr['format']}[/] · [{_status_color(dr['status'])}]{dr['status']}[/] · {_short(dr['id'])}",
        subtitle=f"prompt {dr['prompt_version']} · {dr['model']} · {dr['title']}",
        border_style=ACCENT))

def cmd_approve(args):
    d = db(); dr = _find_draft(d, args.draft_id)
    if not dr:
        console.print(f"[red]no draft matching {args.draft_id}[/]"); raise SystemExit(1)
    approve(d, dr["id"])
    console.print(f"[green]approved[/] {_short(dr['id'])} ({dr['format']}) - "
                  f"record where you post it: [bold]marketerloop outcome-add {_short(dr['id'])} --platform <p> --url <u>[/]")

def cmd_reject(args):
    d = db(); dr = _find_draft(d, args.draft_id)
    if not dr:
        console.print(f"[red]no draft matching {args.draft_id}[/]"); raise SystemExit(1)
    reject(d, dr["id"], reason=args.reason)
    console.print(f"[red]rejected[/] {_short(dr['id'])} ({dr['format']})"
                  + (f" - {args.reason}" if args.reason else ""))

def cmd_edit(args):
    d = db(); dr = _find_draft(d, args.draft_id)
    if not dr:
        console.print(f"[red]no draft matching {args.draft_id}[/]"); raise SystemExit(1)
    if args.file:
        final = open(args.file).read()
    else:
        editor = os.environ.get("MARKETERLOOP_EDITOR") or os.environ.get("EDITOR") or "vi"
        fd, path = tempfile.mkstemp(suffix=".md", prefix="marketerloop-")
        with os.fdopen(fd, "w") as tf:
            tf.write(dr["body"])
        console.print(f"[dim]opening {editor} - save and quit to keep your edit[/]")
        subprocess.call(shlex.split(editor) + [path])
        final = open(path).read()
        os.unlink(path)
    if final.strip() == dr["body"].strip():
        console.print("[yellow]no changes[/] - draft untouched")
        return
    result = edit(d, dr["id"], final)
    added = sum(1 for l in result["diff"].splitlines() if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in result["diff"].splitlines() if l.startswith("-") and not l.startswith("---"))
    console.print(f"[cyan]edit saved[/] {_short(dr['id'])}: +{added}/-{removed} lines. "
                  f"This before/after pair now few-shots every future {dr['format']} draft.")

def cmd_edits(args):
    rows = db().q("SELECT * FROM edit_examples ORDER BY created_at DESC LIMIT ?", (args.limit,))
    if not rows:
        console.print(f"[{WARM}]no edits yet[/] - edit a draft and the loop starts learning")
        return
    for e in rows:
        console.print(Panel(e["diff"],
            title=f"[cyan]{e['format']}[/] · {e['id'][-8:]} · {e['created_at'][:16]}",
            border_style="cyan"))

def cmd_outcomes(args):
    rows = db().q("SELECT * FROM outcomes ORDER BY created_at DESC LIMIT ?", (args.limit,))
    t = Table(title="outcomes", title_style=ACCENT, border_style=WARM)
    t.add_column("id"); t.add_column("draft"); t.add_column("platform")
    t.add_column("url", overflow="fold"); t.add_column("posted"); t.add_column("removed")
    for r in rows:
        t.add_row(_short(r["id"]), _short(r["draft_id"]), r["platform"] or "",
                  r["url"] or "", (r["posted_at"] or "")[:16],
                  "[red]yes[/]" if r["removed"] else "no")
    console.print(t)

def cmd_outcome_add(args):
    d = db(); dr = _find_draft(d, args.draft_id)
    if not dr:
        console.print(f"[red]no draft matching {args.draft_id}[/]"); raise SystemExit(1)
    from .db import new_id, _now
    d.insert("outcomes", {"id": new_id("out"), "draft_id": dr["id"],
                          "platform": args.platform, "url": args.url,
                          "posted_at": args.posted_at or _now(),
                          "metrics_json": None, "removed": 0,
                          "last_checked_at": None, "created_at": _now()})
    console.print(f"[green]outcome recorded[/] for {_short(dr['id'])} - "
                  f"removal checks now have something to watch")

def cmd_budgets(args):
    t = Table(title="budgets (7-day window)", title_style=ACCENT, border_style=WARM)
    t.add_column("template"); t.add_column("weekly cap"); t.add_column("spent 7d")
    t.add_column("runs today"); t.add_column("daily cap")
    for tpl in list_templates():
        b = tpl.budgets
        t.add_row(tpl.id, f"${float(b.get('weekly_llm_usd', 0)):.2f}",
                  f"${db().budget_spend_7d(tpl.id):.4f}",
                  str(db().runs_today(tpl.id)), str(b.get("max_runs_per_day", "-")))
    console.print(t)

def cmd_config(args):
    t = Table(title="config", title_style=ACCENT, border_style=WARM)
    t.add_column("setting"); t.add_column("value")
    t.add_row("db", config.DB_PATH)
    t.add_row("model", config.MODEL)
    t.add_row("mock mode", "[yellow]on[/]" if config.MOCK_LLM else "off")
    for key in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "GRANOLA_API_KEY", "FIRECRAWL_API_KEY", "SPIDER_API_KEY",
                "BROWSERBASE_API_KEY", "EXA_API_KEY"):
        set_it = bool(os.environ.get(key))
        t.add_row(key, "[green]set[/]" if set_it else "[dim]not set[/]")
    console.print(t)
    console.print("[dim]values never print. edit .env to change anything here[/]")

def cmd_worker(args):
    from .worker import main as worker_main
    sys.argv = ["worker"] + (["--once"] if args.once else [])
    worker_main()

# ---------------- argparse ----------------

def main():
    p = argparse.ArgumentParser(
        prog="marketerloop",
        description="Marketer-in-the-loop agentic workflows. Templates as folders, BYOK, human approval on every word.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("templates"); sp.add_argument("what", choices=["list", "show"], nargs="?", default="list")
    sp.add_argument("template_id", nargs="?"); sp.set_defaults(f=cmd_templates)
    sp = sub.add_parser("connectors"); sp.set_defaults(f=cmd_connectors)
    sp = sub.add_parser("inputs"); sp.add_argument("connector"); sp.add_argument("--limit", type=int, default=10); sp.set_defaults(f=cmd_inputs)

    sp = sub.add_parser("run"); sp.add_argument("template")
    sp.add_argument("--sample", action="store_true"); sp.add_argument("--text")
    sp.add_argument("--file"); sp.add_argument("--stdin", action="store_true")
    sp.add_argument("--connector"); sp.add_argument("--external-id")
    sp.add_argument("--title"); sp.set_defaults(f=cmd_run)

    sp = sub.add_parser("runs"); sp.add_argument("--limit", type=int, default=10); sp.set_defaults(f=cmd_runs)
    sp = sub.add_parser("run-show"); sp.add_argument("run_id"); sp.set_defaults(f=cmd_run_show)

    sp = sub.add_parser("queue"); sp.add_argument("--all", action="store_true"); sp.add_argument("--limit", type=int, default=20); sp.set_defaults(f=cmd_queue)
    sp = sub.add_parser("show"); sp.add_argument("draft_id"); sp.set_defaults(f=cmd_show)
    sp = sub.add_parser("approve"); sp.add_argument("draft_id"); sp.set_defaults(f=cmd_approve)
    sp = sub.add_parser("reject"); sp.add_argument("draft_id"); sp.add_argument("--reason"); sp.set_defaults(f=cmd_reject)
    sp = sub.add_parser("edit"); sp.add_argument("draft_id"); sp.add_argument("--file"); sp.set_defaults(f=cmd_edit)
    sp = sub.add_parser("edits"); sp.add_argument("--limit", type=int, default=10); sp.set_defaults(f=cmd_edits)

    sp = sub.add_parser("outcomes"); sp.add_argument("--limit", type=int, default=20); sp.set_defaults(f=cmd_outcomes)
    sp = sub.add_parser("outcome-add"); sp.add_argument("draft_id")
    sp.add_argument("--platform", required=True); sp.add_argument("--url", required=True)
    sp.add_argument("--posted-at"); sp.set_defaults(f=cmd_outcome_add)

    sp = sub.add_parser("budgets"); sp.set_defaults(f=cmd_budgets)
    sp = sub.add_parser("config"); sp.set_defaults(f=cmd_config)
    sp = sub.add_parser("worker"); sp.add_argument("--once", action="store_true"); sp.set_defaults(f=cmd_worker)

    args = p.parse_args()
    if getattr(args, "what", None) == "show" and not getattr(args, "template_id", None):
        p.error("templates show needs a template id")
    args.f(args)

if __name__ == "__main__":
    main()
