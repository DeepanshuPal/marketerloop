"""Spider Cloud connector - STUB. https://spider.cloud docs when implemented."""
import os
from .base import Connector

class SpiderCloudConnector(Connector):
    name = "spidercloud"
    label = "Spider Cloud"
    requires_key = "SPIDER_API_KEY"
    tier = "free"
    status = "stub"

    def configured(self) -> bool:
        return bool(os.environ.get("SPIDER_API_KEY"))

    def get_input(self, external_id: str):
        raise NotImplementedError("Spider Cloud connector is a stub. PRs welcome.")
