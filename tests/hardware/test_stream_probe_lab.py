from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TypeAlias, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


def _pythonpath_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}:{existing}"
    return env


def _camera_selectors() -> list[str]:
    raw_value = os.environ.get("GVSTRESS_STREAM_CAMERAS", "")
    selectors = [value.strip() for value in raw_value.split(",") if value.strip()]
    if not selectors:
        pytest.skip("set GVSTRESS_STREAM_CAMERAS=SERIAL@IP,... to run hardware tests")
    return selectors


def _run_stream_runner(*, duration: float) -> list[dict[str, JSONValue]]:
    command = [
        sys.executable,
        "-m",
        "gvstress",
        "dut-agent",
        "stream-runner",
        "--sample-interval-ms",
        os.environ.get("GVSTRESS_STREAM_SAMPLE_INTERVAL_MS", "1000"),
        "--duration",
        str(duration),
        "--json",
    ]
    for selector in _camera_selectors():
        command.extend(["--camera", selector])

    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=_pythonpath_env(),
        timeout=max(30, int(duration) + 15),
    )

    assert completed.returncode == 0, completed.stderr
    return [
        cast(dict[str, JSONValue], json.loads(line))
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def _final_samples_by_serial(
    payloads: list[dict[str, JSONValue]],
) -> dict[str, dict[str, JSONValue]]:
    final_samples: dict[str, dict[str, JSONValue]] = {}
    for payload in payloads:
        if payload.get("record_type") != "stream_sample":
            continue
        final_samples[str(payload["serial_number"])] = payload
    return final_samples


def _counter_value(sample: dict[str, JSONValue], field_name: str) -> int:
    value = sample.get(field_name)
    if not isinstance(value, int):
        raise AssertionError(f"expected integer {field_name}, got {value!r}")
    return value


@pytest.mark.hardware
def test_four_stream_statistics_capture() -> None:
    selectors = _camera_selectors()
    payloads = _run_stream_runner(
        duration=float(os.environ.get("GVSTRESS_STREAM_DURATION", "3"))
    )

    snapshots = [
        payload
        for payload in payloads
        if payload.get("record_type") == "stream_property_snapshot"
    ]
    final_samples = _final_samples_by_serial(payloads)

    assert len(snapshots) == len(selectors)
    assert set(final_samples) == {selector.split("@", 1)[0] for selector in selectors}
    assert all(
        _counter_value(sample, "n_completed_buffers") >= 0
        for sample in final_samples.values()
    )
    assert all("property_snapshot" in sample for sample in final_samples.values())


@pytest.mark.hardware
def test_loss_injection_changes_stream_statistics() -> None:
    target_serial = os.environ.get("GVSTRESS_STREAM_LOSS_SERIAL")
    if not target_serial:
        pytest.skip("set GVSTRESS_STREAM_LOSS_SERIAL to validate loss injection")

    payloads = _run_stream_runner(
        duration=float(os.environ.get("GVSTRESS_STREAM_DURATION", "3"))
    )
    final_samples = _final_samples_by_serial(payloads)

    if target_serial not in final_samples:
        pytest.skip(
            f"loss target {target_serial} is not part of GVSTRESS_STREAM_CAMERAS"
        )

    target_sample = final_samples[target_serial]
    assert (
        _counter_value(target_sample, "n_failures") > 0
        or _counter_value(target_sample, "n_underruns") > 0
    )

    for serial_number, sample in final_samples.items():
        if serial_number == target_serial:
            continue
        assert _counter_value(sample, "n_failures") == 0
        assert _counter_value(sample, "n_underruns") == 0
