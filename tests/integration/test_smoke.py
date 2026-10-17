"""Smoke test: start the real server and call GET /health over the network."""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx2
import pytest

from tests.flows import walk_through_the_main_flow

ROOT = Path(__file__).resolve().parents[2]
STARTUP_TIMEOUT_SECONDS = 20.0


def free_port() -> int:
    """Ask the OS for a TCP port that is currently free."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def server_url(tmp_path: Path) -> Iterator[str]:
    """Run ``python -m app`` on a free port and stop it after the test."""
    port = free_port()
    log_file = tmp_path / "server.log"
    environment = {
        **os.environ,
        "TASKS_HOST": "127.0.0.1",
        "TASKS_PORT": str(port),
        "TASKS_LOG_LEVEL": "WARNING",
        "TASKS_DATABASE_URL": f"sqlite:///{tmp_path / 'smoke.db'}",
    }

    with log_file.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "app"],
            cwd=ROOT,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            yield f"http://127.0.0.1:{port}"
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def wait_until_healthy(url: str) -> httpx2.Response:
    """Poll ``/health`` until the server answers, failing after a timeout."""
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return httpx2.get(f"{url}/health", timeout=2.0)
        except httpx2.HTTPError as error:
            last_error = error
            time.sleep(0.2)
    pytest.fail(f"server did not become reachable: {last_error!r}")


def test_server_starts_and_reports_health(server_url: str) -> None:
    response = wait_until_healthy(server_url)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_main_flow_against_a_running_server(server_url: str) -> None:
    """The whole flow over the network, on a real server and a database file."""
    wait_until_healthy(server_url)

    with httpx2.Client(base_url=server_url, timeout=10.0) as client:
        walk_through_the_main_flow(client)
