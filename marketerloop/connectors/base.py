"""Connector interface. A connector with no key reports configured() == False;
it never crashes the app. Each connector normalizes its source into an
InputItem: title, text (with [MM:SS] timestamped speaker lines where the
source has them), occurred_at, source_url."""
from dataclasses import dataclass, field

@dataclass
class InputItem:
    external_id: str
    title: str
    text: str
    occurred_at: str | None = None
    source_url: str | None = None
    meta: dict = field(default_factory=dict)

class NotConfigured(Exception):
    """The connector needs a key/plan the user has not supplied."""

class Connector:
    name = "base"
    label = "Base"
    requires_key: str | None = None
    tier = "free"          # free | premium (premium = the source charges for API access)
    status = "live"        # live | stub

    def configured(self) -> bool:
        return True

    def list_inputs(self, limit: int = 25) -> list[dict]:
        """Recent items for the picker UI. Manual returns []."""
        return []

    def get_input(self, external_id: str) -> InputItem:
        raise NotImplementedError
