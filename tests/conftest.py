import os, tempfile

os.environ.setdefault("MOCK_LLM", "1")
_tmp = tempfile.mkdtemp(prefix="marketerloop-test-")
os.environ["MARKETERLOOP_DB"] = os.path.join(_tmp, "test.db")
