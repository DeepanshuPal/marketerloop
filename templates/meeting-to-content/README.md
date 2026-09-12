# Template: meeting-to-content

Turn a meeting transcript into three ready-to-post drafts - a LinkedIn post, an
X thread, and a newsletter blurb - with a human approving every word.

## How it runs

```
transcript (paste/upload or Granola)
  -> ingest            (deterministic, evidence stored once)
  -> extract_ideas     (LLM, prompts/extract_ideas.v1.md -> timestamped JSON)
  -> score             (deterministic rank)
  -> draft x3 formats  (LLM, prompts/draft_*.v1.md, few-shot from your edits)
  -> approval queue    (approve / edit / reject - nothing posts itself)
```

## The two rules this template never breaks

1. **Every claim traces to a timestamp.** Extraction cites [MM:SS] and speaker;
   an idea without one is rejected by the prompt contract and the eval.
2. **Confidential stays out of drafts.** Lines flagged off-the-record are
   recorded as evidence, never drafted from. The eval asserts this.

## Your edits are the moat

Approve a draft and it counts as accepted taste. Edit one and the before/after
pair is stored in `edit_examples` and injected as few-shot context into the
next draft of the same format. Ten edits in, the drafts sound like you wrote
them on a good day.

## Inputs

| input | cost | notes |
|---|---|---|
| manual paste/upload | free | works with any meeting tool's export |
| Granola | Granola Business plan | real public API connector; pick a note, run |

## Evals

```
MOCK_LLM=1 python evals/eval.py
```

Covers extraction shape, coverage of load-bearing moments, confidentiality
flagging, the full pipeline (3 pending drafts), and evidence recording. CI runs
it on every push with no keys.
