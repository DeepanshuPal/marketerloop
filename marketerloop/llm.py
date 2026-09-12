"""LLM access. BYOK via LiteLLM (one client, every provider; OpenRouter
recommended). MOCK_LLM=1 swaps in a deterministic local model so tests, evals
and CI run with no key, no network and no cost.

LiteLLM is imported lazily: mock mode never needs it installed."""
import hashlib, json, re

from . import config

class LLMResult:
    def __init__(self, text, tokens_in=0, tokens_out=0, cost_usd=0.0, model="mock"):
        self.text = text
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost_usd
        self.model = model

def complete(system: str, user: str, json_mode: bool = False) -> LLMResult:
    if config.MOCK_LLM or not config.llm_key_present():
        return _mock(system, user, json_mode)
    import litellm  # lazy: real runs only
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = litellm.completion(
        model=config.MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        **kwargs,
    )
    text = resp.choices[0].message.content
    usage = getattr(resp, "usage", None)
    try:
        cost = litellm.completion_cost(completion_response=resp) or 0.0
    except Exception:
        cost = 0.0
    return LLMResult(
        text=text,
        tokens_in=getattr(usage, "prompt_tokens", 0) if usage else 0,
        tokens_out=getattr(usage, "completion_tokens", 0) if usage else 0,
        cost_usd=float(cost),
        model=config.MODEL,
    )

# ---------------- deterministic mock ----------------
# Extractive, not generative: pulls real lines from the transcript so tests and
# evals assert stable facts. Draft output is assembled from those extractions.

_SIGNAL = ("we should", "decided", "launch", "metric", "customer",
           "insight", "surprised", "learned", "data shows", "the point is",
           "positioning", "convert", "retention", "retain", "headline", "story",
           "activation", "churn", "users who", "habit", "channel", "%")
_CONFIDENTIAL = ("confidential", "off the record", "do not share", "internal only",
                 "not public", "between us")

def _parse_turns(transcript: str):
    turns = []
    for line in transcript.splitlines():
        m = re.match(r"\s*\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s+([A-Za-z][A-Za-z .'-]{1,40}?):\s+(.*)", line)
        if m:
            turns.append({"ts": m.group(1), "speaker": m.group(2).strip(), "text": m.group(3).strip()})
        elif line.strip() and turns:
            turns[-1]["text"] += " " + line.strip()
    return turns

def mock_extract_ideas(transcript: str):
    turns = _parse_turns(transcript)
    ideas = []
    for t in turns:
        low = t["text"].lower()
        conf = any(w in low for w in _CONFIDENTIAL)
        hits = sum(1 for w in _SIGNAL if w in low)
        if conf:
            hits = max(hits, 2)  # confidential lines are always captured as evidence
        if hits or len(t["text"]) > 140:
            score = min(0.55 + 0.12 * hits + (0.08 if len(t["text"]) > 160 else 0), 0.97)
            ideas.append({
                "timestamp": t["ts"], "speaker": t["speaker"],
                "idea": t["text"][:280],
                "why_it_lands": f"Contains {hits} insight signal(s); said by {t['speaker']} at {t['ts']}.",
                "score": round(score, 2), "confidential": conf,
            })
    ideas.sort(key=lambda i: i["score"], reverse=True)
    return ideas[:8]

def _mock(system: str, user: str, json_mode: bool) -> LLMResult:
    if "EXTRACT_IDEAS" in system:
        transcript = user.split("TRANSCRIPT:", 1)[-1]
        ideas = mock_extract_ideas(transcript)
        return LLMResult(json.dumps({"ideas": ideas}),
                         tokens_in=len(user)//4, tokens_out=len(ideas)*60, model="mock")
    if "DRAFT" in system:
        fmt = re.search(r"FORMAT:\s*(\w+)", system)
        fmt = fmt.group(1) if fmt else "linkedin_post"
        try:
            payload = json.loads(user)
        except Exception:
            payload = {"ideas": [], "edit_examples": []}
        ideas = [i for i in payload.get("ideas", []) if not i.get("confidential")]
        body = _assemble_draft(fmt, ideas, payload.get("source_title", "a team meeting"))
        return LLMResult(body, tokens_in=len(user)//4, tokens_out=len(body)//4, model="mock")
    return LLMResult("mock response", model="mock")

def _assemble_draft(fmt: str, ideas: list, source_title: str) -> str:
    if not ideas:
        return "No shareable ideas found in this transcript."
    top = ideas[0]
    bullets = "\n".join(f"- {i['idea']}" for i in ideas[1:4])
    if fmt == "x_thread":
        parts = [f"1/ {top['idea']}"]
        for n, i in enumerate(ideas[1:4], start=2):
            parts.append(f"{n}/ {i['idea']}")
        parts.append(f"{len(parts)+1}/ From {source_title}. More where this came from.")
        return "\n\n".join(parts)
    if fmt == "newsletter_blurb":
        return (f"**From the room: {source_title}**\n\n"
                f"{top['idea']}\n\n"
                f"Also worth your scroll:\n{bullets}\n\n"
                f"(Drafted from your meeting notes - every claim above traces to a timestamped line.)")
    # linkedin_post
    return (f"{top['idea']}\n\n"
            f"That line came out of {source_title}. A few more that stuck:\n\n"
            f"{bullets}\n\n"
            f"Meetings are where the content already is. You just have to keep it.")
