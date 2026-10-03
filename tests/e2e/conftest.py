"""
Pytest fixtures for Playwright E2E browser test suite.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def launch_uvicorn(api_key: str = "secret-e2e-key") -> tuple[subprocess.Popen, str]:
    port = find_free_port()
    repo_root = Path(__file__).resolve().parent.parent.parent
    env = os.environ.copy()
    env["EDI_API_KEYS"] = f"{api_key}:admin"
    env["ENVIRONMENT"] = "development"
    env["PYTHONPATH"] = (
        str(repo_root / "src")
        + os.pathsep
        + str(repo_root / "src" / "backend")
        + os.pathsep
        + env.get("PYTHONPATH", "")
    )

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    ready = False
    for _ in range(60):
        try:
            r = httpx.get(f"{url}/api/health", timeout=0.5)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.1)

    if not ready:
        proc.kill()
        out, err = proc.communicate(timeout=2)
        raise RuntimeError(f"Uvicorn server failed to start: {err.decode('utf-8', errors='ignore')}")

    return proc, url


@pytest.fixture(scope="session")
def live_server():
    proc, url = launch_uvicorn()
    yield url
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        proc.kill()


@pytest.fixture
def uvicorn_launcher():
    return launch_uvicorn
