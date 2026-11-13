import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_only_uv_lock_dependency_file():
    assert (ROOT / "uv.lock").exists()
    for name in ["requirements.txt", "Pipfile", "environment.yml"]:
        assert not (ROOT / name).exists(), name
    assert (ROOT / ".python-version").read_text().strip().startswith("3.12")


def test_upload_limit_configured():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
    assert config["server"]["maxUploadSize"] == 25


def test_readme_has_deploy_steps():
    readme = (ROOT / "README.md").read_text()
    assert "share.streamlit.io" in readme and "SOURCE_URL" in readme and "3.12" in readme
