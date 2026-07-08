import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Run each test with its own data/ dir so sqlite files don't leak between tests."""
    monkeypatch.chdir(tmp_path)
    yield
