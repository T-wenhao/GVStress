# pyright: reportArgumentType=false

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from gvstress.report.models import SCHEMA_VERSION, RunArtifact
from gvstress.report.writer import JSONWriter
from tests.fixtures.reports.helpers import FixtureBuilder


def _load_json(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


class TestRunArtifactSchema:
    def test_run_id_is_required(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        payload = cast(
            dict[str, object], builder.build_run_artifact().model_dump(mode="json")
        )
        _ = payload.pop("run_id")

        with pytest.raises(ValidationError, match="run_id"):
            _ = RunArtifact(**payload)

    def test_schema_version_default(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact()
        assert artifact.schema_version == SCHEMA_VERSION

    def test_run_validity_required(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact()
        assert artifact.run_validity.value == "valid"

    def test_verdict_required(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact()
        assert artifact.verdict.value == "pass"

    def test_primary_attribution_required(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact()
        assert artifact.primary_attribution.value == "nic"

    def test_secondary_attribution_required(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact()
        assert artifact.secondary_attribution.value == "nic_driver_configuration"


class TestRunArtifactSerialization:
    def test_roundtrip_json(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        original = builder.build_run_artifact()

        output_path = tmp_path / "run.json"
        writer = JSONWriter()
        _ = writer.write(original, output_path)

        loaded_data = _load_json(output_path)
        assert loaded_data["run_id"] == original.run_id
        assert loaded_data["run_validity"] == original.run_validity.value
        assert loaded_data["schema_version"] == SCHEMA_VERSION
        assert loaded_data["verdict"] == original.verdict.value
        assert loaded_data["primary_attribution"] == original.primary_attribution.value
        assert (
            loaded_data["secondary_attribution"] == original.secondary_attribution.value
        )

    def test_samples_serialized_as_paths(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact()

        output_path = tmp_path / "run.json"
        writer = JSONWriter()
        _ = writer.write(artifact, output_path)

        loaded_data = _load_json(output_path)
        samples = cast(dict[str, object], loaded_data["samples"])
        assert isinstance(samples, dict)
        for key, path_str in samples.items():
            assert key in ["nic", "stream", "system", "events"]
            assert path_str is None or isinstance(path_str, str)


class TestRunArtifactGolden:
    def test_golden_run_json_structure(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact(run_id="golden-001")

        output_path = tmp_path / "run.json"
        writer = JSONWriter()
        _ = writer.write(artifact, output_path)

        loaded_data = _load_json(output_path)

        required_fields = [
            "schema_version",
            "run_id",
            "run_validity",
            "timestamp",
            "scenario",
            "fake_camera_config",
            "dut_config",
            "stream_config",
            "preflight",
            "samples",
            "verdict",
            "primary_attribution",
            "secondary_attribution",
            "recommended_actions",
        ]

        for field in required_fields:
            assert field in loaded_data, f"Missing required field: {field}"

        assert loaded_data["run_id"] == "golden-001"
        assert loaded_data["schema_version"] == SCHEMA_VERSION

    def test_golden_run_json_preflight_structure(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact()

        output_path = tmp_path / "run.json"
        writer = JSONWriter()
        _ = writer.write(artifact, output_path)

        loaded_data = _load_json(output_path)
        preflight = cast(dict[str, object], loaded_data["preflight"])

        assert "run_validity" in preflight
        assert "reasons" in preflight
        assert "checks" in preflight
        assert "generator_environment" in preflight
        assert "dut_environment" in preflight

    def test_golden_run_json_config_sections(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact()

        output_path = tmp_path / "run.json"
        writer = JSONWriter()
        _ = writer.write(artifact, output_path)

        loaded_data = _load_json(output_path)
        scenario = cast(dict[str, object], loaded_data["scenario"])
        fake_camera_config = cast(dict[str, object], loaded_data["fake_camera_config"])
        dut_config = cast(dict[str, object], loaded_data["dut_config"])
        stream_config = cast(dict[str, object], loaded_data["stream_config"])

        assert scenario["name"] == "four_stream"
        assert fake_camera_config["ip_address"] == "192.168.1.100"
        assert "eth0" in cast(list[object], dut_config["ifaces"])
        assert stream_config["packet_resend"] is True

    def test_golden_run_json_verdict_fields(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact(verdict="fail", attribution="stream")

        output_path = tmp_path / "run.json"
        writer = JSONWriter()
        _ = writer.write(artifact, output_path)

        loaded_data = _load_json(output_path)

        assert loaded_data["verdict"] == "fail"
        assert loaded_data["primary_attribution"] == "stream"
        assert loaded_data["secondary_attribution"] == "stream_configuration"
        assert len(cast(list[object], loaded_data["recommended_actions"])) > 0


class TestRunArtifactConsistency:
    def test_run_validity_matches_preflight(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)
        artifact = builder.build_run_artifact(validity="invalid_environment")

        assert artifact.run_validity.value == "invalid_environment"

    def test_verdict_consistency_across_scenarios(self, tmp_path: Path) -> None:
        builder = FixtureBuilder(tmp_path)

        pass_artifact = builder.build_run_artifact(verdict="pass")
        fail_artifact = builder.build_run_artifact(verdict="fail")

        assert pass_artifact.verdict == "pass"
        assert fail_artifact.verdict == "fail"
        assert pass_artifact.verdict != fail_artifact.verdict
