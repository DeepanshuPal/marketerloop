"""Granola connector - implemented against the public Granola API docs
(https://docs.granola.ai, OpenAPI 3.1, server https://public-api.granola.ai).

- Auth: HTTP Bearer API key (grn_...), created in the Granola desktop app under
  Settings -> Connectors -> API keys. Requires a Granola Business or Enterprise
  plan, so this connector is marked premium.
- GET /v1/notes                       list (cursor-paginated, limit 1-30)
- GET /v1/notes/{id}?include=transcript  note + inline transcript; when too
  large it returns 413 TRANSCRIPT_TOO_LARGE -> page GET /v1/notes/{id}/transcript
- Transcript items: {speaker:{name?,label?,attribution?}, text, start_time,
  end_time} with ISO datetimes; we rebase to [MM:SS] offsets from the first
  item so drafts cite meeting-relative timestamps.

Untested against a live workspace (needs a Business-plan key); the request
shapes below mirror the published OpenAPI spec field-for-field.
"""
import os
from datetime import datetime, timezone

import httpx

from .base import Connector, InputItem, NotConfigured

BASE = os.environ.get("GRANOLA_API_BASE", "https://public-api.granola.ai")

class GranolaConnector(Connector):
    name = "granola"
    label = "Granola"
    requires_key = "GRANOLA_API_KEY"
    tier = "premium"   # API keys require a Granola Business plan
    status = "live"

    def configured(self) -> bool:
        return bool(os.environ.get("GRANOLA_API_KEY"))

    def _client(self) -> httpx.Client:
        key = os.environ.get("GRANOLA_API_KEY")
        if not key:
            raise NotConfigured(
                "Granola connector needs GRANOLA_API_KEY (Granola Business plan: "
                "desktop app -> Settings -> Connectors -> API keys).")
        return httpx.Client(
            base_url=BASE,
            headers={"Authorization": f"Bearer {key}"},
            timeout=30.0,
        )

    def _check(self, r: httpx.Response) -> httpx.Response:
        if r.status_code == 401:
            raise NotConfigured("Granola rejected the API key (401). Check GRANOLA_API_KEY.")
        if r.status_code == 413:
            return r  # caller falls back to the paged transcript endpoint
        r.raise_for_status()
        return r

    def list_inputs(self, limit: int = 25) -> list[dict]:
        with self._client() as c:
            out, cursor = [], None
            while len(out) < limit:
                params = {"limit": min(30, limit - len(out))}
                if cursor:
                    params["cursor"] = cursor
                r = self._check(c.get("/v1/notes", params=params))
                data = r.json()
                notes = data.get("notes", [])
                for n in notes:
                    out.append({
                        "external_id": n["id"],
                        "title": n.get("title") or "Untitled meeting",
                        "occurred_at": n.get("created_at"),
                        "source_url": n.get("web_url"),
                    })
                if not data.get("has_more") or not data.get("cursor") or not notes:
                    break
                cursor = data["cursor"]
            return out

    def get_input(self, external_id: str) -> InputItem:
        with self._client() as c:
            r = self._check(c.get(f"/v1/notes/{external_id}",
                                  params={"include": "transcript"}))
            if r.status_code == 413:
                items = self._paged_transcript(c, external_id)
                note = self._check(c.get(f"/v1/notes/{external_id}")).json()
            else:
                note = r.json()
                items = (note.get("transcript") or [])
        return InputItem(
            external_id=external_id,
            title=note.get("title") or "Untitled meeting",
            text=_render_transcript(items),
            occurred_at=note.get("created_at"),
            source_url=note.get("web_url"),
            meta={"attendees": note.get("attendees") or [],
                  "summary_text": note.get("summary_text")},
        )

    def _paged_transcript(self, c: httpx.Client, note_id: str) -> list:
        items, cursor = [], None
        while True:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            r = self._check(c.get(f"/v1/notes/{note_id}/transcript", params=params))
            data = r.json()
            items.extend(data.get("transcript") or [])
            if not data.get("has_more") or not data.get("cursor"):
                return items
            cursor = data["cursor"]

def _render_transcript(items: list) -> str:
    """[MM:SS] Speaker: text, rebased to the first item's start_time."""
    if not items:
        return ""
    def ts(it):
        try:
            return datetime.fromisoformat(it["start_time"].replace("Z", "+00:00"))
        except Exception:
            return None
    t0 = ts(items[0]) or datetime.now(timezone.utc)
    lines = []
    for it in items:
        t = ts(it) or t0
        offset = max(0, int((t - t0).total_seconds()))
        mm, ss = offset // 60, offset % 60
        sp = it.get("speaker") or {}
        who = sp.get("name") or sp.get("label") or (
            "Me" if sp.get("attribution") == "me" else "Speaker")
        lines.append(f"[{mm:02d}:{ss:02d}] {who}: {it.get('text','').strip()}")
    return "\n".join(lines)
