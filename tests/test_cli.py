"""CLI smoke: the same loop a user drives in their terminal."""
import sys

from marketerloop import cli
from marketerloop.db import DB

def _argv(*args):
    sys.argv = ["marketerloop", *args]

def test_cli_loop(capsys):
    _argv("templates", "list"); cli.main()
    assert "meeting-to-content" in capsys.readouterr().out

    _argv("connectors"); cli.main()
    out = capsys.readouterr().out
    assert "granola" in out and "stub" in out

    _argv("run", "meeting-to-content", "--sample"); cli.main()
    out = capsys.readouterr().out
    assert "awaiting_approval" in out

    _argv("queue"); cli.main()
    out = capsys.readouterr().out
    assert "linkedin_post" in out and "x_thread" in out

    db = DB.__new__(DB)
    import marketerloop.config as cfg
    db.__init__(cfg.DB_PATH)
    draft = db.one("SELECT * FROM drafts ORDER BY created_at DESC LIMIT 1")
    _argv("show", draft["id"][-8:]); cli.main()
    assert draft["body"].splitlines()[0][:20] in capsys.readouterr().out

    _argv("approve", draft["id"][-8:]); cli.main()
    assert "approved" in capsys.readouterr().out

    _argv("config"); cli.main()
    assert "OPENROUTER_API_KEY" in capsys.readouterr().out

def test_cli_edit_via_file(capsys, tmp_path):
    _argv("run", "meeting-to-content", "--sample"); cli.main(); capsys.readouterr()
    import marketerloop.config as cfg
    db = DB(cfg.DB_PATH)
    draft = db.one("SELECT * FROM drafts ORDER BY created_at DESC LIMIT 1")
    f = tmp_path / "edit.md"
    f.write_text(draft["body"] + "\n\nMy edit.")
    _argv("edit", draft["id"][-8:], "--file", str(f)); cli.main()
    out = capsys.readouterr().out
    assert "edit saved" in out
    assert db.one("SELECT COUNT(*) c FROM edit_examples")["c"] >= 1
