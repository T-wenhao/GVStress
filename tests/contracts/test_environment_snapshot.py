from __future__ import annotations

import json

from typer.testing import CliRunner

from gvstress.cli.main import app as main_app
from gvstress.dut.environment import EnvironmentSnapshot, InterfaceSnapshot


def _snapshot(hostname: str, interface_name: str, address: str) -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        hostname=hostname,
        platform="linux",
        python_version="3.10.0",
        interfaces=[
            InterfaceSnapshot(
                name=interface_name,
                ip_addresses=[address],
                driver="igb",
                driver_version="5.13.0",
                firmware="1.63",
                mtu=9000,
                speed=1000,
                link_state="UP",
                link_up=True,
            )
        ],
        required_binaries={"python3": True, "ip": True, "ethtool": True},
        sudo_available=True,
        arv_fake_camera_present=True,
        pktgen_available=True,
        msix_detected=True,
        irqbalance_detected=True,
    )


def test_snapshot_merges_generator_and_dut_context(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "gvstress.cli.dut.collect_local_environment_snapshot",
        lambda *args, **kwargs: _snapshot("generator", "eno1", "192.168.10.11"),
    )

    def fake_run_preflight(**kwargs):
        _ = kwargs
        from gvstress.core.models import RunValidity
        from gvstress.core.preflight import PreflightCheck, PreflightResult

        result = PreflightResult(
            run_validity=RunValidity.VALID,
            reasons=[],
            checks=[PreflightCheck(name="ssh", passed=True, reasons=[])],
            generator_environment=_snapshot("generator", "eno1", "192.168.10.11"),
            dut_environment=_snapshot("dut", "eth0", "192.168.10.21"),
        )
        return result.write(tmp_path)

    monkeypatch.setattr("gvstress.cli.dut.run_preflight", fake_run_preflight)
    runner = CliRunner()

    result = runner.invoke(
        main_app,
        [
            "dut",
            "inspect",
            "--host",
            "dut-lab",
            "--ifaces",
            "eth0,eth1",
            "--json",
            "--out",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["run_validity"] == "valid"
    assert payload["generator_environment"]["interfaces"][0]["driver"] == "igb"
    assert payload["dut_environment"]["interfaces"][0]["firmware"] == "1.63"
    assert payload["generator_environment_path"].endswith("generator_environment.json")
    assert payload["dut_environment_path"].endswith("dut_environment.json")
    assert payload["preflight_path"].endswith("preflight.json")


def test_environment_snapshot_parser_extracts_required_fields(monkeypatch) -> None:
    from gvstress.core.runner import LocalRunner
    from gvstress.dut.environment import collect_local_environment_snapshot

    class FakeRunner(LocalRunner):
        def run(self, command, argv=None, *, timeout=None):
            _ = timeout
            command_line = [command, *(argv or [])]
            if command_line[:4] == ["ip", "-j", "addr", "show"]:
                stdout = json.dumps(
                    [
                        {
                            "ifname": "eno1",
                            "operstate": "UP",
                            "mtu": 9000,
                            "addr_info": [{"local": "192.168.10.11"}],
                        }
                    ]
                )
                return type(
                    "Result", (), {"exit_code": 0, "stdout": stdout, "stderr": ""}
                )()
            if command_line == ["ethtool", "eno1"]:
                return type(
                    "Result",
                    (),
                    {
                        "exit_code": 0,
                        "stdout": "Speed: 1000Mb/s\nLink detected: yes\n",
                        "stderr": "",
                    },
                )()
            if command_line == ["ethtool", "-i", "eno1"]:
                return type(
                    "Result",
                    (),
                    {
                        "exit_code": 0,
                        "stdout": "driver: igb\nversion: 5.13.0\nfirmware-version: 1.63\n",
                        "stderr": "",
                    },
                )()
            if command_line == ["sudo", "-n", "true"]:
                return type(
                    "Result", (), {"exit_code": 0, "stdout": "", "stderr": ""}
                )()
            raise AssertionError(command_line)

    monkeypatch.setattr(
        "gvstress.dut.environment.shutil.which",
        lambda binary: f"/usr/bin/{binary}",
    )
    monkeypatch.setattr(
        "gvstress.dut.environment.Path.exists",
        lambda self: str(self) == "/proc/net/pktgen",
    )
    monkeypatch.setattr(
        "gvstress.dut.environment._file_contains",
        lambda path, needle: str(path) == "/proc/interrupts" and needle == "MSI-X",
    )
    monkeypatch.setattr("gvstress.dut.environment._irqbalance_detected", lambda: True)

    snapshot = collect_local_environment_snapshot(["eno1"], runner=FakeRunner())

    assert snapshot.interfaces[0].driver == "igb"
    assert snapshot.interfaces[0].driver_version == "5.13.0"
    assert snapshot.interfaces[0].firmware == "1.63"
    assert snapshot.interfaces[0].mtu == 9000
    assert snapshot.interfaces[0].speed == 1000
    assert snapshot.msix_detected is True
    assert snapshot.irqbalance_detected is True
