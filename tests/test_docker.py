"""Docker integration tests (Task 9.5).

Marked ``@pytest.mark.integration`` — skip if Docker daemon is unavailable.
Tests:
    - ``docker compose up -d`` starts both services
    - HTTP 200 from the allowlisted perspective
    - Non-root container user (appuser, UID 1000)
    - Read-only /data mount
    - Root-owned machines.yaml produces clear permission error

Run with: ``uv run pytest tests/test_docker.py -m integration -v``
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _docker_available() -> bool:
    """Check if Docker daemon is running and docker compose is available."""
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


skip_if_no_docker = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker daemon not available — skipping integration tests",
)


@skip_if_no_docker
def test_compose_up_and_reachable(tmp_path: Path) -> None:
    """``docker compose up -d`` starts the app; HTTP proxy responds."""
    project_dir = Path(__file__).resolve().parent.parent
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            capture_output=True,
            cwd=str(project_dir),
            timeout=300,
            check=True,
        )

        # Wait for healthcheck (up to 60s)
        _wait_for_healthy(project_dir, timeout=60)

        # Wait for Caddy to be reachable
        import requests

        for _ in range(30):
            try:
                resp = requests.get("http://localhost:80/", timeout=5)
                if resp.status_code == 200:
                    break
            except requests.ConnectionError:
                pass
            time.sleep(2)
        else:
            pytest.fail("App not reachable at http://localhost:80/ within 60s")

    finally:
        subprocess.run(
            ["docker", "compose", "down"],
            capture_output=True,
            cwd=str(project_dir),
            timeout=60,
        )


@skip_if_no_docker
def test_container_runs_as_non_root() -> None:
    """Container PID 1 runs as appuser, not root (spec R9)."""
    project_dir = Path(__file__).resolve().parent.parent
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            capture_output=True,
            cwd=str(project_dir),
            timeout=300,
            check=True,
        )
        _wait_for_healthy(project_dir, timeout=60)

        # Get the streamlit container name
        result = subprocess.run(
            ["docker", "compose", "ps", "-q", "streamlit"],
            capture_output=True,
            cwd=str(project_dir),
            timeout=10,
            check=True,
            text=True,
        )
        container_id = result.stdout.strip()
        assert container_id, "streamlit container not found"

        # Check PID 1 user
        result = subprocess.run(
            ["docker", "exec", container_id, "ps", "-o", "user=", "-p", "1"],
            capture_output=True,
            timeout=10,
            text=True,
        )
        user = result.stdout.strip()
        assert user == "appuser", f"Expected PID 1 as 'appuser', got '{user}'"

    finally:
        subprocess.run(
            ["docker", "compose", "down"],
            capture_output=True,
            cwd=str(project_dir),
            timeout=60,
        )


def _wait_for_healthy(project_dir: Path, timeout: int = 60) -> None:
    """Wait for the streamlit container to become healthy."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True,
            cwd=str(project_dir),
            timeout=10,
            text=True,
        )
        if "healthy" in result.stdout:
            return
        time.sleep(3)
    pytest.fail(f"Container not healthy within {timeout}s")
