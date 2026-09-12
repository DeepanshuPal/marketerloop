"""Exa connector - STUB. Discovery/search input (find sources worth drafting
from). Quality pick for discovery, BYOK. https://docs.exa.ai when implemented."""
import os
from .base import Connector

class ExaConnector(Connector):
    name = "exa"
    label = "Exa"
    requires_key = "EXA_API_KEY"
    tier = "premium"   # quality pick for discovery; paid per search
    status = "stub"

    def configured(self) -> bool:
        return bool(os.environ.get("EXA_API_KEY"))

    def get_input(self, external_id: str):
        raise NotImplementedError("Exa connector is a stub. PRs welcome.")
