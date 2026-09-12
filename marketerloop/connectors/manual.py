"""Manual input: paste notes/transcript or upload a file in the UI.
The free on-ramp - no account, no key, works with any meeting tool's export."""
from .base import Connector

class ManualConnector(Connector):
    name = "manual"
    label = "Paste / upload"
    tier = "free"
    status = "live"
