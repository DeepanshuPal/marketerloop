# marketerloop

Marketer-in-the-loop agentic workflows. Open source, BYOK, and every output waits for a human before it goes anywhere.

A workflow turns a source signal into drafts, then puts every external write behind review. Accepted edits become few-shot examples for later drafts. The runtime and catalog live here. This is the parent project, not the name of one template.

```bash
git clone https://github.com/DeepanshuPal/marketerloop
cd marketerloop
pip install -e .
cp .env.example .env

marketerloop run meeting-to-content --sample
marketerloop queue
marketerloop show <draft-id>
marketerloop edit <draft-id>
```

## The shared runtime

The common path is deliberately small and inspectable:

```
source -> normalize evidence -> qualify/extract -> draft -> approval queue -> outcome
```

- Templates are folders with a readable `template.yaml`, versioned prompts and offline evals.
- Runs, source evidence, prompt/model versions, costs, decisions, edit diffs and outcomes are append-only in local SQLite.
- API keys stay in environment variables. Mock mode runs CI and the sample without keys or cost.
- Budgets fail closed before model calls.
- Nothing posts, sends or touches a social account automatically.

There is no visual builder and no hosted account. Clone it, bring your own keys, and keep your data in your own SQLite file.

## Workflow catalog

Templates that fit the shared runner stay as folders. Specialized workflows ship as focused repos while their interfaces settle, but they are catalog entries under Marketerloop, not separate product bets.

| workflow | status | what it does |
|---|---|---|
| [`meeting-to-content`](templates/meeting-to-content) | native template | Transcript or notes -> timestamped ideas -> LinkedIn post, X thread and newsletter blurb -> approval queue. Confidential lines are flagged and excluded. |
| [`fresh-intent-reply-queue`](https://github.com/DeepanshuPal/fresh-intent-reply-queue) | standalone workflow | Reddit RSS + HN intent signals -> ICP match -> scored reply drafts -> human approval. |
| [`linkedin-visitor-conversion`](https://github.com/DeepanshuPal/linkedin-visitor-conversion) | standalone workflow | Manual LinkedIn visitor/follower CSV -> ICP qualification -> connection-note drafts -> human approval and export. |
| `citation-queue` ([spec](docs/specs/citation-queue.md)) | spec, not built | [am-i-cited](https://github.com/DeepanshuPal/am-i-cited) citation feed -> durable cited threads -> participation drafts -> human approval. The durable-signal companion to fresh intent. |

All three share the same operating rules: local state, BYOK models, append-only run evidence, explicit budgets, and no external write without human approval. As their contracts stabilize, they can move behind the common runner without breaking their focused CLIs.

## Native template contract

```
templates/meeting-to-content/
  template.yaml
  prompts/*.v1.md
  evals/
  README.md
```

`template.yaml` declares inputs, connector scopes, trigger, DAG, approval gates, budgets and state. The runner reads that contract. There is no hidden workflow behavior.

The meeting-to-content template accepts a transcript through manual paste, a file or stdin, or from Granola. It extracts timestamped ideas, excludes confidential material, and drafts three formats: LinkedIn post, X thread and newsletter blurb. Every draft stops in the queue.

## Connectors

| connector | status | cost |
|---|---|---|
| manual paste/file/stdin | live and verified | free |
| Granola | implemented against the public API docs; live account path not verified | Business-plan API key required |
| Firecrawl | interface stub | free tier exists |
| Spider Cloud | interface stub | free tier exists |
| Browserbase | interface stub | paid |
| Exa | interface stub | paid |

A missing connector key means “not configured”, not a broken run. Stubs are labelled as stubs so the architecture is visible without pretending unfinished integrations work.

## Models and keys

One OpenRouter key can route all model calls, or use OpenAI or Anthropic directly.

| env var | purpose |
|---|---|
| `OPENROUTER_API_KEY` | recommended model router |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | direct provider keys |
| `GRANOLA_API_KEY` | Granola Business API |
| `MOCK_LLM=1` | deterministic local mode used by CI and evals |

The default model is configurable with `MARKETERLOOP_MODEL`. Limits are declared in the template (`weekly_llm_usd`, `max_runs_per_day`) and checked before calls.

## Verification

```bash
pip install -e ".[dev]"
MOCK_LLM=1 pytest -q
MOCK_LLM=1 python templates/meeting-to-content/evals/eval.py
MOCK_LLM=1 marketerloop run meeting-to-content --sample
marketerloop queue
```

The suite covers the pipeline, approval state, template loading and CLI. The offline eval checks extraction, evidence coverage, confidentiality exclusions and all three draft formats. Granola still needs a real Business-plan key for a true live connector test; the README will not call that verified until it is.

## Develop

```bash
marketerloop templates list
marketerloop connectors
marketerloop runs
marketerloop budgets
```

Python 3.11+ is recommended; mock mode works on 3.10. MIT licensed.
