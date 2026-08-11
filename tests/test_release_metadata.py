import tomllib
from pathlib import Path

from agent_whisper import __version__

ROOT = Path(__file__).parents[1]


def test_release_version_is_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    installer = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert project["project"]["version"] == __version__
    assert f"DisplayVersion = '{__version__}'" in installer


def test_project_license_metadata_and_files() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    metadata = project["project"]

    assert metadata["license"] == "MIT"
    for path in ("LICENSE", "NOTICE.md", "THIRD_PARTY_NOTICES.md"):
        assert (ROOT / path).is_file()
