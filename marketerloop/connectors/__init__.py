from .base import Connector, InputItem, NotConfigured
from .manual import ManualConnector
from .granola import GranolaConnector
from .firecrawl import FirecrawlConnector
from .spidercloud import SpiderCloudConnector
from .browserbase import BrowserbaseConnector
from .exa import ExaConnector

_REGISTRY = [
    ManualConnector, GranolaConnector, FirecrawlConnector,
    SpiderCloudConnector, BrowserbaseConnector, ExaConnector,
]

def get_connector(name: str) -> Connector:
    for cls in _REGISTRY:
        if cls.name == name:
            return cls()
    raise KeyError(f"connector {name!r} not registered")

def list_connectors() -> list[Connector]:
    return [cls() for cls in _REGISTRY]
