"""
Tests for single-sourced versioning and /api/version endpoint.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from app.main import app, get_api_version, get_library_version
from fastapi.testclient import TestClient
import validedi


def get_pyproject_version() -> str:
    """Helper to extract project.version from pyproject.toml."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def test_api_version_matches_pyproject():
    """Verify that /api/version library_version matches pyproject.toml."""
    expected_version = get_pyproject_version()
    client = TestClient(app)
    response = client.get("/api/version")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["library"] == "validedi"
    assert payload["library_version"] == expected_version


def test_validedi_dunder_version_matches_pyproject():
    """Verify that validedi.__version__ matches pyproject.toml."""
    expected_version = get_pyproject_version()
    assert validedi.__version__ == expected_version


def test_api_version_env_var_override():
    """Verify that API_VERSION environment variable dynamically sets the api_version."""
    with patch.dict(os.environ, {"API_VERSION": "2.5.0"}):
        assert get_api_version() == "2.5.0"
        client = TestClient(app)
        response = client.get("/api/version")
        assert response.status_code == 200
        assert response.json()["api_version"] == "2.5.0"


def test_api_version_from_version_file(tmp_path):
    """Verify that VERSION file is read when API_VERSION env is not set."""
    version_file = tmp_path / "VERSION"
    version_file.write_text("3.1.4\n", encoding="utf-8")
    with patch.dict(os.environ, {}, clear=True):
        if "API_VERSION" in os.environ:
            del os.environ["API_VERSION"]
        with patch("app.main.Path.is_file", return_value=True):
            with patch("app.main.Path.read_text", return_value="3.1.4\n"):
                assert get_api_version() == "3.1.4"
