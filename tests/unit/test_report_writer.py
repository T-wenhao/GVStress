from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from gvstress.report.writer import JSONWriter
from tests.fixtures.reports.helpers import FixtureBuilder


@dataclass(slots=True)
class _NestedMetadata:
    sample_path: Path


def test_json_writer_serializes_dict_preflight_and_nested_dataclasses(
    tmp_path: Path,
) -> None:
    artifact = (
        FixtureBuilder(tmp_path)
        .build_run_artifact()
        .model_copy(
            update={
                "preflight": {
                    "preflight_path": tmp_path / "preflight.json",
                    "metadata": _NestedMetadata(sample_path=tmp_path / "nested.jsonl"),
                    "items": [_NestedMetadata(sample_path=tmp_path / "item.jsonl")],
                }
            }
        )
    )
    output_path = tmp_path / "reports" / "run.json"

    returned = JSONWriter().write(artifact, output_path)

    payload = cast(
        dict[str, object], json.loads(output_path.read_text(encoding="utf-8"))
    )
    preflight = cast(dict[str, object], payload["preflight"])
    samples = cast(dict[str, str], payload["samples"])
    assert returned is artifact
    assert preflight == {
        "preflight_path": str(tmp_path / "preflight.json"),
        "metadata": {"sample_path": str(tmp_path / "nested.jsonl")},
        "items": [{"sample_path": str(tmp_path / "item.jsonl")}],
    }
    assert samples["nic"] == str(tmp_path / "raw" / "nic_samples.jsonl")


def test_json_writer_rejects_invalid_preflight_payload(tmp_path: Path) -> None:
    artifact = (
        FixtureBuilder(tmp_path)
        .build_run_artifact()
        .model_copy(update={"preflight": "invalid"})
    )

    with pytest.raises(TypeError, match="preflight must be a dataclass or dict"):
        _ = JSONWriter().write(artifact, tmp_path / "reports" / "run.json")
