# marketerloop

Marketer-in-the-loop agentic workflows. Open source, BYOK, and every output
waits for a human before it goes anywhere.

A template turns a source (meeting notes today, intent signals next) into
drafts. You approve, edit, or reject every one - and **your edits become the
few-shot examples for the next draft**, so the tenth draft sounds like you
wrote it. That's the loop.

This is a CLI, not a platform. Clone it, add your keys, run it on your own
machine. Your keys, your data, your SQLite file.

```bash
git clone https://github.com/DeepanshuPal/marketerloop
cd marketerloop
pip install -e .            # or: pip install -r requirements.txt and use python -m marketerloop.cli
cp .env.example .env        # add one LLM key - or don't, mock mode works

marketerloop run meeting-to-content --sample
marketerloop queue
marketerloop show <draft-id>
marketerloop edit <draft-id>   # opens your $EDITOR; the diff teaches the loop
```

## How people use it

```
you                          marketerloop (your machine)
 |                                |
 |-- paste transcript ----------->|  marketerloop run meeting-to-content --file sync.txt
 |                                |     ingest -> extract_ideas -> score -> draft x3
 |                                |     (evidence, prompt versions, tokens, cost -> SQLite)
 |<-- 3 drafts in the queue ------|  marketerloop queue
 |-- approve / edit / reject ---->|  decisions + diffs stored append-only
 |                                |  accepted edits few-shot the next drafts
 |-- record where it posted ----->|  marketerloop outcome-add <id> --platform x --url ...
```

No hosted tier, no account, nothing phones home. `marketerloop worker` is the
always-on loop for templates that declare a schedule (none do yet) - and it is
deliberately not GitHub Actions, which delays or drops scheduled jobs under
load and disables them after 60 days of repo inactivity.

## Templates are folders

```
templates/meeting-to-content/
  template.yaml      inputs, connector scopes, trigger, DAG, approval gates, budgets, state
  prompts/*.v1.md    versioned prompts (the version lands on every draft it produced)
  evals/             fixtures + assertions, run in CI with no keys (MOCK_LLM=1)
  README.md
```

The runner reads `template.yaml` and nothing else. There is no visual builder
and no hidden behavior; a template you can read in one sitting is the point.
Shipped today:

| template | what it does |
|---|---|
| `meeting-to-content` | transcript/notes -> timestamped idea extraction -> LinkedIn post, X thread, newsletter blurb -> approval queue. Confidential lines are flagged and never drafted from. |

Coming next: `fresh-intent-reply-queue` (Reddit/HN signals -> matched to your
ICP -> reply drafts, same queue, same learning loop).

## Connectors

A connector normalizes a source into a timestamped transcript and gets out of
the way. No key = not configured, never an error.

| connector | status | cost |
|---|---|---|
| manual paste/upload | ✅ live | free - works with any meeting tool's export |
| Granola | ✅ live (built against the [public API docs](https://docs.granola.ai)) | needs a Granola **Business** plan key (Settings -> Connectors -> API keys) |
| Firecrawl | 🔜 stub | free tier exists |
| Spider Cloud | 🔜 stub | free tier exists |
| Browserbase | 🔜 stub | paid - logged-in capture |
| Exa | 🔜 stub | paid - quality pick for discovery |

Stubs are exactly that: registered interfaces with docs links, so the pattern
is visible and PRs have somewhere to land.

## BYOK

Bring your own keys; the tool is free, your usage is yours. One OpenRouter key
covers every model, or use provider keys directly.

| env var | what for |
|---|---|
| `OPENROUTER_API_KEY` | recommended: one key, any model (`MARKETERLOOP_MODEL`, default `openrouter/anthropic/claude-sonnet-4.5`) |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | direct provider instead |
| `GRANOLA_API_KEY` | Granola connector (Business plan) |
| `MOCK_LLM=1` | deterministic local mode, no key, no cost - how CI and evals run |

Budgets are enforced in `template.yaml` (`weekly_llm_usd`, `max_runs_per_day`).
A run that would exceed the cap fails loudly with a `budget_exceeded` event,
and `marketerloop budgets` shows the 7-day spend.

## The records are the product

Every run stores, append-only: the raw evidence (hash + text), which prompt
and model versions produced which draft, tokens and cost, every human
decision (approve / reject+reason / edit+diff), and outcomes - where approved
drafts got posted, their metrics, and whether they were later removed. SQL,
one file, yours: `./data/marketerloop.db`. Query it with anything.

## Develop

```bash
pip install -e ".[dev]"
MOCK_LLM=1 pytest -q
MOCK_LLM=1 python templates/meeting-to-content/evals/eval.py
```

Python 3.11+ recommended (3.10 works in mock mode; LiteLLM needs 3.11).
MIT licensed.
