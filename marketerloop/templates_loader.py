"""Load template folders. template.yaml is the contract: inputs, connector
scopes, trigger, DAG, approval gates, budgets, state. The runner reads this
file and nothing else - there is no hidden behavior and no visual builder."""
import os
from pathlib import Path

import yaml

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

class Template:
    def __init__(self, folder: Path):
        self.folder = folder
        with open(folder / "template.yaml") as f:
            self.spec = yaml.safe_load(f)
        self.id = self.spec["id"]
        self.version = str(self.spec["version"])

    def prompt(self, name: str) -> tuple[str, str]:
        """Return (prompt_text, version) for a prompt file like draft_x_thread.v1.md."""
        rel = self._prompt_path(name)
        p = self.folder / rel
        text = p.read_text()
        parts = p.stem.split(".")
        tail = parts[-1]
        version = tail if tail.startswith("v") and tail[1:].isdigit() else "v1"
        return text, version

    def _prompt_path(self, name: str) -> str:
        for step in self.spec["dag"]:
            if step.get("prompt") and name in step["prompt"]:
                return step["prompt"]
            for fmt, path in (step.get("prompts") or {}).items():
                if fmt == name:
                    return path
        raise KeyError(f"prompt {name!r} not declared in {self.id}/template.yaml")

    @property
    def formats(self) -> list[str]:
        return self.spec["approval"]["formats"]

    @property
    def budgets(self) -> dict:
        return self.spec.get("budgets", {})

def list_templates() -> list[Template]:
    out = []
    for d in sorted(TEMPLATES_DIR.iterdir()):
        if (d / "template.yaml").exists():
            out.append(Template(d))
    return out

def get_template(template_id: str) -> Template:
    for t in list_templates():
        if t.id == template_id:
            return t
    raise KeyError(f"template {template_id!r} not found in {TEMPLATES_DIR}")
