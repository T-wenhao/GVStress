from pathlib import Path

from gvstress.config import load_config
from gvstress.core.models import (
    PrimaryAttribution,
    RunArtifact,
    RunArtifacts,
    RunValidity,
    ScenarioType,
    Verdict,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "configs"


def test_enum_values_match_contract() -> None:
    assert [member.value for member in RunValidity] == [
        "valid",
        "invalid_environment",
        "invalid_prereq",
        "invalid_mapping",
        "invalid_telemetry",
        "interrupted",
    ]
    assert [member.value for member in Verdict] == [
        "pass",
        "warn",
        "fail",
        "not_applicable",
    ]
    assert [member.value for member in PrimaryAttribution] == [
        "nic",
        "stream",
        "mixed",
        "environment",
        "unknown",
    ]
    assert [member.value for member in ScenarioType] == [
        "smoke",
        "four_stream",
        "soak",
        "loss_injection",
        "pktgen_baseline",
    ]


def test_valid_4port_config_roundtrip() -> None:
    config = load_config(FIXTURE_DIR / "valid-4port.yaml")

    assert len(config.generator.cameras) == 4
    assert len({camera.serial_number for camera in config.generator.cameras}) == 4
    assert len({camera.ip_address for camera in config.generator.cameras}) == 4
    assert len({camera.interface_name for camera in config.generator.cameras}) == 4
    assert config.dut.ifaces == ["eno1", "eno2", "eno3", "eno4"]
    assert config.scenarios[0].name is ScenarioType.FOUR_STREAM
    assert config.output.root == Path("artifacts/run-001")


def test_run_artifact_models_accept_paths() -> None:
    artifact = RunArtifact(name="summary", path=Path("reports/summary.md"))
    artifacts = RunArtifacts(
        root=Path("artifacts/run-001"),
        raw_dir=Path("artifacts/run-001/raw"),
        reports_dir=Path("artifacts/run-001/reports"),
        logs_dir=Path("artifacts/run-001/logs"),
        evidence_dir=Path("artifacts/run-001/evidence"),
        run_json=Path("artifacts/run-001/reports/run.json"),
        summary_md=Path("artifacts/run-001/reports/summary.md"),
    )

    assert artifact.name == "summary"
    assert artifacts.run_json.name == "run.json"
