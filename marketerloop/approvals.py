"""Approve / edit / reject. Every accepted edit is stored as a before/after
pair (with a unified diff) and few-shots the next draft in the same format.
Rejections are recorded with a reason so the audit trail explains taste."""
import difflib

from .db import DB, new_id

def approve(db: DB, draft_id: str):
    db.execute("UPDATE drafts SET status='approved' WHERE id=?", (draft_id,))
    db.draft_event(draft_id, "approved")

def reject(db: DB, draft_id: str, reason: str | None = None):
    db.execute("UPDATE drafts SET status='rejected' WHERE id=?", (draft_id,))
    db.draft_event(draft_id, "rejected", reason=reason)

def edit(db: DB, draft_id: str, final_body: str) -> dict:
    draft = db.one("SELECT * FROM drafts WHERE id=?", (draft_id,))
    assert draft, f"draft {draft_id} not found"
    original = draft["body"]
    diff = "\n".join(difflib.unified_diff(
        original.splitlines(), final_body.splitlines(),
        fromfile="original", tofile="edited", lineterm=""))
    db.execute("UPDATE drafts SET status='edited', body=? WHERE id=?", (final_body, draft_id))
    db.draft_event(draft_id, "edited",
                   diff={"unified": diff,
                         "chars_before": len(original), "chars_after": len(final_body)},
                   final_body=final_body)
    db.insert("edit_examples", {
        "id": new_id("edit"), "draft_id": draft_id, "format": draft["format"],
        "original_body": original, "edited_body": final_body, "diff": diff,
        "created_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
    })
    return {"diff": diff}
