# Contributing

Marketerloop is a template runner. Two ways to contribute:

## Add a template

Copy `templates/meeting-to-content/` and edit:

- `template.yaml` - inputs, connector scopes, trigger, DAG, approval gates,
  budgets, state. This file is the contract; the runner reads it, nothing else.
- `prompts/*.v1.md` - versioned prompts. Bump the version in the filename when
  you change one; run records store the version that produced each draft.
- `evals/` - at least one fixture and one assertion. Evals must run with
  `MOCK_LLM=1` (deterministic, no keys) in CI.

No visual builder, no template JSON DSL. A template is a folder.

## Add a connector

Implement `marketerloop/connectors/base.py:Connector` (`name`, `configured()`,
`fetch()`), register it in `marketerloop/connectors/__init__.py`, and document
its env var in `.env.example`. A connector with no key must report
`configured() == False`, never crash.

## Rules

- Tests and evals pass with `MOCK_LLM=1` and no network.
- Never log or commit secrets. Keys come from env, full stop.
- Run records are append-only. If you need lifecycle state, write an event.
