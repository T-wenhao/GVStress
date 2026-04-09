from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _pythonpath_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}:{existing}"
    return env


def test_dut_agent_json_contract() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "gvstress", "dut-agent", "inspect", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=_pythonpath_env(),
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    assert payload["hostname"]
    assert payload["platform"]
    assert payload["python_version"]


def test_dut_agent_invalid_subcommand_exits_non_zero() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "gvstress", "dut-agent", "missing-command", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=_pythonpath_env(),
    )

    assert completed.returncode != 0
