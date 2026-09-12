"""Browserbase connector - STUB. For logged-in capture (the sources that need
a session). https://docs.browserbase.com when implemented."""
import os
from .base import Connector

class BrowserbaseConnector(Connector):
    name = "browserbase"
    label = "Browserbase"
    requires_key = "BROWSERBASE_API_KEY"
    tier = "premium"
    status = "stub"

    def configured(self) -> bool:
        return bool(os.environ.get("BROWSERBASE_API_KEY"))

    def get_input(self, external_id: str):
        raise NotImplementedError("Browserbase connector is a stub. PRs welcome.")
