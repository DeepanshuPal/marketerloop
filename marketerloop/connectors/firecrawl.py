"""Firecrawl connector - STUB. Registered so the pattern (and the devrel
'works with' story) is visible; fetch raises until implemented.
Docs to build against: https://docs.firecrawl.dev"""
import os
from .base import Connector

class FirecrawlConnector(Connector):
    name = "firecrawl"
    label = "Firecrawl"
    requires_key = "FIRECRAWL_API_KEY"
    tier = "free"      # free tier exists; paid when you need volume/quality
    status = "stub"

    def configured(self) -> bool:
        return bool(os.environ.get("FIRECRAWL_API_KEY"))

    def get_input(self, external_id: str):
        raise NotImplementedError(
            "Firecrawl connector is a stub. Scrape/crawl a URL into clean "
            "markdown, then treat it like any other InputItem. PRs welcome.")
