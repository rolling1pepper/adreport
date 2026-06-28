import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = REPO_ROOT / "fixtures"


@pytest.fixture()
def demo_full_raw() -> dict:
    return json.loads((FIXTURES_DIR / "demo_full.json").read_text(encoding="utf-8"))


@pytest.fixture()
def demo_public_raw() -> dict:
    return json.loads((FIXTURES_DIR / "demo_public.json").read_text(encoding="utf-8"))
