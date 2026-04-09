from __future__ import annotations

from gvstress.core.models import RunValidity, ScenarioType
from gvstress.core.preflight import InterfaceIPMapping, run_preflight
from gvstress.dut.environment import EnvironmentSnapshot, InterfaceSnapshot


class StubRunner:
    def __init__(self, exit_code: int = 0, stdout: str = '{"status": "ok"}') -> None:
        self.exit_code = exit_code
        self.stdout = stdout

    def run(
        self,
        command: str,
        argv: list[str] | None = None,
        *,
        timeout: float | None = None,
    ):
        _ = command
        _ = argv
        _ = timeout
        return type(
            "Result",
            (),
            {"exit_code": self.exit_code, "stdout": self.stdout, "stderr": ""},
        )()


def _snapshot(
    *,
    hostname: str,
    interfaces: list[InterfaceSnapshot],
    binaries: dict[str, bool] | None = None,
    sudo_available: bool = True,
    arv_present: bool = True,
    pktgen_available: bool = True,
) -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        hostname=hostname,
        platform="linux",
        python_version="3.10.0",
        interfaces=interfaces,
        required_binaries=binaries or {"python3": True, "ip": True, "ethtool": True},
        sudo_available=sudo_available,
        arv_fake_camera_present=arv_present,
        pktgen_available=pktgen_available,
        msix_detected=True,
        irqbalance_detected=True,
    )


def _iface(
    name: str,
    *,
    ip_addresses: list[str],
    link_up: bool = True,
    mtu: int = 1500,
    speed: int = 1000,
) -> InterfaceSnapshot:
    return InterfaceSnapshot(
        name=name,
        ip_addresses=ip_addresses,
        driver="igb",
        driver_version="1.0.0",
        firmware="fw1",
        mtu=mtu,
        speed=speed,
        link_state="UP" if link_up else "DOWN",
        link_up=link_up,
    )


def test_duplicate_interface_mapping_marks_invalid_mapping(
    monkeypatch,
) -> None:
    generator_snapshot = _snapshot(
        hostname="generator",
        interfaces=[_iface("eno1", ip_addresses=["192.168.10.11"])],
    )
    dut_snapshot = _snapshot(
        hostname="dut",
        interfaces=[_iface("eth0", ip_addresses=["192.168.10.21"])],
    )

    monkeypatch.setattr(
        "gvstress.core.preflight.collect_local_environment_snapshot",
        lambda *args, **kwargs: generator_snapshot,
    )
    monkeypatch.setattr(
        "gvstress.core.preflight.collect_remote_environment_snapshot",
        lambda *args, **kwargs: dut_snapshot,
    )

    result = run_preflight(
        dut_host="dut-lab",
        dut_ifaces=["eth0"],
        generator_mappings=[
            InterfaceIPMapping(interface_name="eno1", ip_address="192.168.10.11"),
            InterfaceIPMapping(interface_name="eno1", ip_address="192.168.10.12"),
        ],
        ssh_runner=StubRunner(),
    )

    assert result.run_validity is RunValidity.INVALID_MAPPING
    assert "generator.duplicate_mapping.interface:eno1" in result.reasons


def test_missing_binaries_marks_invalid_prereq(monkeypatch) -> None:
    generator_snapshot = _snapshot(
        hostname="generator",
        interfaces=[_iface("eno1", ip_addresses=["192.168.10.11"])],
        binaries={"python3": True, "ip": False, "ethtool": True},
    )
    dut_snapshot = _snapshot(
        hostname="dut",
        interfaces=[_iface("eth0", ip_addresses=["192.168.10.21"])],
    )

    monkeypatch.setattr(
        "gvstress.core.preflight.collect_local_environment_snapshot",
        lambda *args, **kwargs: generator_snapshot,
    )
    monkeypatch.setattr(
        "gvstress.core.preflight.collect_remote_environment_snapshot",
        lambda *args, **kwargs: dut_snapshot,
    )

    result = run_preflight(
        dut_host="dut-lab",
        dut_ifaces=["eth0"],
        generator_mappings=[
            InterfaceIPMapping(interface_name="eno1", ip_address="192.168.10.11")
        ],
        ssh_runner=StubRunner(),
    )

    assert result.run_validity is RunValidity.INVALID_PREREQ
    assert "generator.missing_binary:ip" in result.reasons


def test_valid_preflight_passes_and_requires_pktgen_for_baseline(monkeypatch) -> None:
    generator_snapshot = _snapshot(
        hostname="generator",
        interfaces=[_iface("eno1", ip_addresses=["192.168.10.11"])],
        pktgen_available=False,
    )
    dut_snapshot = _snapshot(
        hostname="dut",
        interfaces=[_iface("eth0", ip_addresses=["192.168.10.21"])],
    )

    monkeypatch.setattr(
        "gvstress.core.preflight.collect_local_environment_snapshot",
        lambda *args, **kwargs: generator_snapshot,
    )
    monkeypatch.setattr(
        "gvstress.core.preflight.collect_remote_environment_snapshot",
        lambda *args, **kwargs: dut_snapshot,
    )

    result = run_preflight(
        dut_host="dut-lab",
        dut_ifaces=["eth0"],
        generator_mappings=[
            InterfaceIPMapping(interface_name="eno1", ip_address="192.168.10.11")
        ],
        ssh_runner=StubRunner(),
        scenario=ScenarioType.PKTGEN_BASELINE,
    )

    assert result.run_validity is RunValidity.INVALID_PREREQ
    assert "generator.missing_binary:pktgen" in result.reasons
