# Spec: citation-queue (next template, not built)

Status: **spec only**. No code exists for this template. This document is the
contract a first implementation must satisfy before it joins the catalog.

## The bet

[fresh-intent-reply-queue](https://github.com/DeepanshuPal/fresh-intent-reply-queue)
answers *fresh* intent: someone asked a buying question on Reddit or HN an
hour ago. Its known weakness is the other half of the surface: the threads
the answer engines already cite when a buyer asks ChatGPT, Gemini or
Perplexity the same question. Those citations are **durable** - a thread an
engine cites today it will probably keep citing for months - and a helpful,
human reply inside one of them pays out on every future answer that quotes
the thread. Fresh intent is a race; durable citations are real estate.

The data source already exists: [am-i-cited](https://github.com/DeepanshuPal/am-i-cited)
asks the answer engines the buying questions in a niche, parses the links
they cite, and tracks share of voice per domain over weekly re-samples. This
template turns that citation feed into a work queue.

Known limit, priced in: a durable-citations-only queue drains in roughly six
weeks for a niche - the cited set turns over slowly by definition. That is
why this is a *companion* template, not a replacement: fresh-intent keeps
volume, citation-queue keeps compounding value. The merged design is fresh +
durable signals in one catalog, ranked by citation value where that data
exists.

## Pipeline (shared runner contract)

```
source -> normalize evidence -> qualify/extract -> draft -> approval queue -> outcome
```

1. **Source.** An am-i-cited run export (JSON): the buying questions asked,
   the engines sampled, and for each answer the cited URLs with rank and
   sample date. v0 reads the export file; the direct connector is a later
   adapter behind the same `template.yaml` connector scope.
2. **Normalize evidence.** Each cited URL becomes an item: canonical URL,
   surface type (reddit thread / HN thread / blog / forum / docs page), which
   questions cite it, which engines cite it, first-seen and last-seen sample
   dates. Dedupe on canonical URL across samples so a durable citation is one
   queue item with a citation history, not a weekly duplicate.
3. **Qualify.** Score 0-100 on two axes, BYOK LLM with the ICP blurb:
   - *citation value* - how many buying questions and engines cite this URL,
     weighted by how durable it has proven across samples;
   - *participability* - can a human still add value here? Open Reddit/HN
     thread: yes. Archived thread, closed forum, a competitor's own docs: no.
   Threads fetchable for context go through the existing
   Exa / Firecrawl connector stubs rather than a new scraping path.
4. **Draft.** A value-first contribution in the operator's voice for that
   specific thread: answer the original question properly, mention the
   product only where it genuinely helps. Few-shot from prior approved edits,
   same learning loop as the other templates.
5. **Approval queue.** Unchanged and non-negotiable: every draft waits for a
   human. The operator posts from their own account. Nothing in this template
   ever posts, votes, or touches a social account.
6. **Outcome.** Posted permalinks are recorded and watched for removal
   (72h, same best-effort RSS re-read as fresh-intent). The next am-i-cited
   re-sample closes the loop: did share of voice move, and is the thread we
   contributed to still cited?

## Why the human gate matters more here, not less

Reddit's rules on automated posting do not bend because the thread is old -
if anything, drive-by promotional comments on high-traffic cited threads are
the fastest way to get a domain's citations *removed*. The approval step is
the compliance layer, same as in fresh-intent, and the helpful:promotional
guardrail ratio carries over unchanged.

## Template contract sketch

```yaml
name: citation-queue
version: 0.1.0
inputs:
  - kind: file
    format: am-i-cited export JSON
connectors:
  - am_i_cited_export   # v0: file import
  - exa                 # stub: thread/page context fetch
  - firecrawl           # stub: thread/page context fetch
trigger: manual (weekly, after each am-i-cited re-sample)
dag: [normalize, qualify, draft, approval]
approval_gates:
  - every draft            # human approval before anything leaves
  - promo_ratio_guardrail  # carried over from fresh-intent-reply-queue
budgets:
  weekly_llm_usd: 1.00     # qualification + drafting on a weekly cited set is small
  max_runs_per_day: 1
state: sqlite, append-only runs/edits/outcomes, as all templates
```

## Cost shape

Weekly cadence on a niche-scale cited set (tens to low hundreds of URLs):
one qualification call per new or re-surfaced URL, one draft call per
approved-for-drafting item. On free OpenRouter models: $0. On cheap paid
models: cents per week. The expensive input (the LLM sampling in am-i-cited)
is already paid for by that tool's own budget.

## Open questions for v0

- Exact am-i-cited export schema version this consumes (pin one; the export
  is the interface).
- Whether qualification fetches thread bodies in v0 or qualifies on
  title+question context only (cheaper; fetching is the upgrade).
- How citation value should decay for URLs that drop out of the cited set
  between samples.

## What done looks like for v0

A folder in `templates/` that passes the native template contract: readable
`template.yaml`, versioned prompts, offline evals over a fixture export, mock
mode with no keys, and a README that says verified vs stubbed honestly -
same bar as meeting-to-content.
