"""Vector store behind an adapter, deliberately. sqlite-vec is pre-v1; the
default store is SQL/FTS-only. Swap the implementation, keep the interface."""

class VectorStore:
    def upsert(self, namespace: str, key: str, text: str, vector: list[float]): ...
    def search(self, namespace: str, vector: list[float], k: int = 10): ...

class NullVectorStore(VectorStore):
    """Default: no vectors. Keyword/SQL search carries v0."""
    def upsert(self, namespace, key, text, vector):
        return None
    def search(self, namespace, vector, k: int = 10):
        return []

class SqliteVecStore(VectorStore):
    """Available once sqlite-vec stabilises. Import-guarded on purpose."""
    def __init__(self, db_path: str):
        import sqlite_vec  # noqa: F401  (raises if not installed - opt-in only)
        self.db_path = db_path
