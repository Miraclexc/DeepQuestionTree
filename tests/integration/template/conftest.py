from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def config():
    import yaml

    def load(profile):
        return yaml.safe_load(
            (ROOT / "configs/studies" / f"{profile}.yaml").read_text(encoding="utf-8")
        )

    return load
