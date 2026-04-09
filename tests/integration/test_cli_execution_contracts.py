# pyright: reportPrivateUsage=false, reportPrivateLocalImportUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownParameterType=false, reportMissingParameterType=false

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

from gvstress.cli.main import app
from gvstress.config.models import (
    Config,
    DUTCollectOptions,
    DUTConfig,
    FakeCameraConfig,
    GeneratorConfig,
    OutputConfig,
    PktgenConfig,
    ScenarioConfig,
    StreamConfig,
)
from gvstress.core.models import RunValidity, ScenarioType
from gvstress.core.preflight import PreflightResult
from gvstress.dut.nic_probe import NICProbe
from gvstress.dut.stream_probe import StreamProbe
from gvstress.dut.system_probe import SystemProbe


def _missing_binary_error(binary: str) -> FileNotFoundError:
    return FileNotFoundError(2, "No such file or directory", binary)


def _build_config(tmp_path: Path) -> Config:
    return Config(
        generator=GeneratorConfig(
            cameras=[
                FakeCameraConfig(
                    ip_address="192.168.10.11",
                    interface_name="eno1",
                    serial_number="CAM-001",
                    genicam_filename="camera.xml",
                    gvsp_lost_ratio=0.0,
                )
            ]
        ),
        dut=DUTConfig(
            ifaces=["eno1", "eno2"],
            sample_interval_ms=1000,
            collect=DUTCollectOptions(nic=True, stream=True, system=True),
        ),
        stream=StreamConfig(
            packet_resend=True,
            socket_buffer=True,
            socket_buffer_size=262144,
            frame_retention=30,
            initial_packet_timeout=500,
            packet_timeout=100,
            packet_request_ratio=0.1,
            receiver_priority=5,
        ),
        scenarios=[
            ScenarioConfig(name=ScenarioType.SMOKE, duration=60, warmup=10, cooldown=5)
        ],
        pktgen=PktgenConfig(
            interfaces=["eno1", "eno2"],
            duration=2,
            packet_size=1500,
            rate="1000M",
            xmit_mode="start_xmit",
        ),
        output=OutputConfig(
            root=tmp_path / "artifacts",
            raw_dir=tmp_path / "artifacts" / "raw",
            reports_dir=tmp_path / "artifacts" / "reports",
            logs_dir=tmp_path / "artifacts" / "logs",
            evidence_dir=tmp_path / "artifacts" / "evidence",
        ),
    )


def _build_preflight_result() -> PreflightResult:
    return PreflightResult(
        run_validity=RunValidity.VALID,
        reasons=[],
        checks=[],
        generator_environment=None,
        dut_environment=None,
    )


def test_scenario_runner_constructs_all_dut_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gvstress.cli import test as cli_test

    config = _build_config(tmp_path)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        cli_test,
        "collect_local_environment_snapshot",
        lambda: SimpleNamespace(interfaces=[SimpleNamespace(name="generator0")]),
    )
    monkeypatch.setattr(
        cli_test, "run_preflight", lambda **_: _build_preflight_result()
    )
    monkeypatch.setattr(
        cli_test,
        "attach_compatible_baseline_to_report",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        cli_test.FakeCameraManager,
        "from_generator_config",
        lambda *args, **kwargs: SimpleNamespace(),
    )

    class FakeRunOrchestrator:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def run(self):
            from gvstress.core.models import (
                PrimaryAttribution,
                SecondaryAttribution,
                Verdict,
            )
            from gvstress.core.verdict import VerdictDecision

            return SimpleNamespace(
                run_id="run-001",
                run_validity=RunValidity.VALID,
                aborted=False,
                abort_reason=None,
                sample_counts={"nic": 0, "system": 0, "stream": 0},
                artifacts=SimpleNamespace(root=tmp_path / "run-001"),
                transitions=[],
                verdict=VerdictDecision(
                    verdict=Verdict.PASS,
                    primary_attribution=PrimaryAttribution.UNKNOWN,
                    secondary_attribution=SecondaryAttribution.UNKNOWN,
                    recommended_actions=(),
                    reasons=(),
                ),
            )

    monkeypatch.setattr(cli_test, "RunOrchestrator", FakeRunOrchestrator)

    with pytest.raises(typer.Exit) as exc_info:
        cli_test._run_scenario(config, "smoke", output_dir=tmp_path)

    assert exc_info.value.exit_code == 0
    assert isinstance(captured["nic_probe"], NICProbe)
    assert isinstance(captured["system_probe"], SystemProbe)
    assert isinstance(captured["stream_probe"], StreamProbe)
    assert [target.label() for target in captured["stream_probe"]._targets] == [
        "CAM-001@192.168.10.11"
    ]
    assert captured["stream_probe"]._sample_interval_s == 1.0


def test_preflight_receives_non_none_ssh_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test: ssh_runner must be passed to run_preflight, not None."""
    from gvstress.cli import test as cli_test

    config = _build_config(tmp_path)
    captured_preflight_kwargs: dict[str, object] = {}
    sentinel_runner = object()

    def fake_build_runner(cfg: Config) -> object:
        return sentinel_runner

    def capture_preflight(**kwargs) -> PreflightResult:
        captured_preflight_kwargs.update(kwargs)
        return PreflightResult(
            run_validity=RunValidity.VALID,
            reasons=[],
            checks=[],
            generator_environment=None,
            dut_environment=None,
        )

    monkeypatch.setattr(cli_test, "_build_runner", fake_build_runner)
    monkeypatch.setattr(
        cli_test,
        "collect_local_environment_snapshot",
        lambda: SimpleNamespace(interfaces=[SimpleNamespace(name="generator0")]),
    )
    monkeypatch.setattr(cli_test, "run_preflight", capture_preflight)
    monkeypatch.setattr(
        cli_test, "attach_compatible_baseline_to_report", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        cli_test.FakeCameraManager,
        "from_generator_config",
        lambda *args, **kwargs: SimpleNamespace(),
    )

    class FakeRunOrchestrator:
        def __init__(self, **kwargs) -> None:
            pass

        def run(self):
            from gvstress.core.models import (
                PrimaryAttribution,
                SecondaryAttribution,
                Verdict,
            )
            from gvstress.core.verdict import VerdictDecision

            return SimpleNamespace(
                run_id="run-001",
                run_validity=RunValidity.VALID,
                aborted=False,
                abort_reason=None,
                sample_counts={"nic": 0, "system": 0, "stream": 0},
                artifacts=SimpleNamespace(root=tmp_path / "run-001"),
                transitions=[],
                verdict=VerdictDecision(
                    verdict=Verdict.PASS,
                    primary_attribution=PrimaryAttribution.UNKNOWN,
                    secondary_attribution=SecondaryAttribution.UNKNOWN,
                    recommended_actions=(),
                    reasons=(),
                ),
            )

    monkeypatch.setattr(cli_test, "RunOrchestrator", FakeRunOrchestrator)

    with pytest.raises(typer.Exit) as exc_info:
        cli_test._run_scenario(config, "smoke", output_dir=tmp_path)

    assert exc_info.value.exit_code == 0
    assert "ssh_runner" in captured_preflight_kwargs
    assert captured_preflight_kwargs["ssh_runner"] is sentinel_runner
    assert captured_preflight_kwargs["ssh_runner"] is not None


def test_scenario_runner_passes_probes_into_orchestrator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gvstress.cli import test as cli_test

    config = _build_config(tmp_path)
    captured: dict[str, object] = {}
    sentinel_nic = object()
    sentinel_system = object()
    sentinel_stream = object()

    monkeypatch.setattr(
        cli_test,
        "collect_local_environment_snapshot",
        lambda: SimpleNamespace(interfaces=[SimpleNamespace(name="generator0")]),
    )
    monkeypatch.setattr(
        cli_test, "run_preflight", lambda **_: _build_preflight_result()
    )
    monkeypatch.setattr(
        cli_test,
        "attach_compatible_baseline_to_report",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        cli_test.FakeCameraManager,
        "from_generator_config",
        lambda *args, **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(cli_test, "_build_nic_probe", lambda cfg: sentinel_nic)
    monkeypatch.setattr(cli_test, "_build_system_probe", lambda cfg: sentinel_system)

    class FakeStreamProbe:
        def __init__(self, *args, **kwargs) -> None:
            captured["stream_probe_ctor_args"] = args
            captured["stream_probe_ctor_kwargs"] = kwargs

        def __new__(cls, *args, **kwargs):
            return sentinel_stream

    class FakeRunOrchestrator:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def run(self):
            from gvstress.core.models import (
                PrimaryAttribution,
                SecondaryAttribution,
                Verdict,
            )
            from gvstress.core.verdict import VerdictDecision

            return SimpleNamespace(
                run_id="run-001",
                run_validity=RunValidity.VALID,
                aborted=False,
                abort_reason=None,
                sample_counts={"nic": 0, "system": 0, "stream": 0},
                artifacts=SimpleNamespace(root=tmp_path / "run-001"),
                transitions=[],
                verdict=VerdictDecision(
                    verdict=Verdict.PASS,
                    primary_attribution=PrimaryAttribution.UNKNOWN,
                    secondary_attribution=SecondaryAttribution.UNKNOWN,
                    recommended_actions=(),
                    reasons=(),
                ),
            )

    monkeypatch.setattr(cli_test, "StreamProbe", FakeStreamProbe)
    monkeypatch.setattr(cli_test, "RunOrchestrator", FakeRunOrchestrator)

    with pytest.raises(typer.Exit) as exc_info:
        cli_test._run_scenario(config, "smoke", output_dir=tmp_path)

    assert exc_info.value.exit_code == 0
    assert captured["nic_probe"] is sentinel_nic
    assert captured["system_probe"] is sentinel_system
    assert captured["stream_probe"] is sentinel_stream


def test_missing_ethtool_returns_invalid_prereq_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gvstress.cli import test as cli_test

    runner = CliRunner()
    config = _build_config(tmp_path)
    config_path = tmp_path / "scenario.yaml"
    config_path.write_text("scenario: ignored\n", encoding="utf-8")

    monkeypatch.setattr(cli_test, "load_config", lambda _: config)
    monkeypatch.setattr(
        cli_test,
        "collect_local_environment_snapshot",
        lambda: (_ for _ in ()).throw(_missing_binary_error("ethtool")),
    )

    result = runner.invoke(
        app,
        ["test", "smoke", "--config", str(config_path)],
        catch_exceptions=False,
    )

    combined_output = result.stdout
    assert result.exit_code == 1
    assert "run_validity=invalid_prereq" in combined_output
    assert "abort_reason=generator.missing_binary:ethtool" in combined_output
    assert "Traceback" not in combined_output


def test_dut_inspect_missing_ethtool_is_controlled_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gvstress.cli import dut as cli_dut

    runner = CliRunner()

    monkeypatch.setattr(
        cli_dut,
        "collect_local_environment_snapshot",
        lambda: (_ for _ in ()).throw(_missing_binary_error("ethtool")),
    )

    result = runner.invoke(
        app,
        [
            "dut",
            "inspect",
            "--host",
            "localhost",
            "--ifaces",
            "eno1",
            "--json",
        ],
        catch_exceptions=False,
    )

    payload = json.loads(result.stdout)
    combined_output = result.stdout
    assert result.exit_code == 1
    assert payload["run_validity"] == "invalid_prereq"
    assert payload["reasons"] == ["generator.missing_binary:ethtool"]
    assert payload["checks"] == [
        {
            "name": "binaries",
            "passed": False,
            "reasons": ["generator.missing_binary:ethtool"],
        }
    ]
    assert "Traceback" not in combined_output
