"""Tests proving the suite runs in random, reproducible order (RT15)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TARGET = "tests/unit/test_fixtures.py"


def collected_order(seed: int) -> list[str]:
    """Return the test ids of ``TARGET`` in the order pytest-randomly picks."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            TARGET,
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--randomly-seed={seed}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return [line for line in result.stdout.splitlines() if "::" in line]


def test_random_order_plugin_is_active(pytestconfig: pytest.Config) -> None:
    assert pytestconfig.pluginmanager.hasplugin("randomly")


def test_same_seed_reproduces_the_same_order() -> None:
    assert collected_order(7) == collected_order(7)


def test_different_seeds_produce_different_orders() -> None:
    first = collected_order(1)
    second = collected_order(2)

    assert first != second
    assert sorted(first) == sorted(second)
