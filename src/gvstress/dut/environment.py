from __future__ import annotations

import json
import platform
import shutil
import socket
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from gvstress.core.runner import CommandRunner, LocalRunner


@dataclass(slots=True)
class InterfaceSnapshot:
    name: str
    ip_addresses: list[str]
    driver: str | None
    driver_version: str | None
    firmware: str | None
    mtu: int | None
    speed: int | None
    link_state: str | None
    link_up: bool | None

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> InterfaceSnapshot:
        ip_values = payload.get("ip_addresses")
        return cls(
            name=str(payload["name"]),
            ip_addresses=[str(value) for value in cast(list[object], ip_values or [])],
            driver=_coerce_optional_str(payload.get("driver")),
            driver_version=_coerce_optional_str(payload.get("driver_version")),
            firmware=_coerce_optional_str(payload.get("firmware")),
            mtu=_coerce_optional_int(payload.get("mtu")),
            speed=_coerce_optional_int(payload.get("speed")),
            link_state=_coerce_optional_str(payload.get("link_state")),
            link_up=_coerce_optional_bool(payload.get("link_up")),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class EnvironmentSnapshot:
    hostname: str
    platform: str
    python_version: str
    interfaces: list[InterfaceSnapshot]
    required_binaries: dict[str, bool]
    sudo_available: bool
    arv_fake_camera_present: bool
    pktgen_available: bool
    msix_detected: bool
    irqbalance_detected: bool

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> EnvironmentSnapshot:
        raw_interfaces = payload.get("interfaces")
        return cls(
            hostname=str(payload["hostname"]),
            platform=str(payload["platform"]),
            python_version=str(payload["python_version"]),
            interfaces=[
                InterfaceSnapshot.from_dict(item)
                for item in cast(list[object], raw_interfaces or [])
                if isinstance(item, dict)
            ],
            required_binaries={
                str(key): bool(value)
                for key, value in _coerce_dict(payload.get("required_binaries")).items()
            },
            sudo_available=bool(payload.get("sudo_available", False)),
            arv_fake_camera_present=bool(payload.get("arv_fake_camera_present", False)),
            pktgen_available=bool(payload.get("pktgen_available", False)),
            msix_detected=bool(payload.get("msix_detected", False)),
            irqbalance_detected=bool(payload.get("irqbalance_detected", False)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "hostname": self.hostname,
            "platform": self.platform,
            "python_version": self.python_version,
            "interfaces": [interface.to_dict() for interface in self.interfaces],
            "required_binaries": dict(self.required_binaries),
            "sudo_available": self.sudo_available,
            "arv_fake_camera_present": self.arv_fake_camera_present,
            "pktgen_available": self.pktgen_available,
            "msix_detected": self.msix_detected,
            "irqbalance_detected": self.irqbalance_detected,
        }


def collect_local_environment_snapshot(
    ifaces: list[str] | tuple[str, ...] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> EnvironmentSnapshot:
    command_runner = runner or LocalRunner()
    interface_names = (
        list(ifaces) if ifaces is not None else _discover_local_interfaces()
    )

    return EnvironmentSnapshot(
        hostname=socket.gethostname(),
        platform=platform.system().lower(),
        python_version=platform.python_version(),
        interfaces=[
            _collect_interface_snapshot(command_runner, interface_name)
            for interface_name in interface_names
        ],
        required_binaries={
            binary: shutil.which(binary) is not None
            for binary in ["python3", "ip", "ethtool"]
        },
        sudo_available=_sudo_available(command_runner),
        arv_fake_camera_present=shutil.which("arv-fake-gv-camera-0.10") is not None,
        pktgen_available=Path("/proc/net/pktgen").exists(),
        msix_detected=_file_contains(Path("/proc/interrupts"), "MSI-X"),
        irqbalance_detected=_irqbalance_detected(),
    )


def collect_remote_environment_snapshot(
    runner: CommandRunner,
    ifaces: list[str] | tuple[str, ...],
    *,
    python_bin: str = "python3",
    timeout: float = 30.0,
) -> EnvironmentSnapshot:
    result = runner.run(
        python_bin,
        [
            "-m",
            "gvstress",
            "dut-agent",
            "inspect",
            "--ifaces",
            ",".join(ifaces),
            "--json",
        ],
        timeout=timeout,
    )
    if result.exit_code != 0:
        raise RuntimeError(result.stderr or "remote environment inspection failed")
    return EnvironmentSnapshot.from_dict(json.loads(result.stdout))


def _collect_interface_snapshot(
    runner: CommandRunner, interface_name: str
) -> InterfaceSnapshot:
    ip_payload = _read_ip_payload(runner, interface_name)
    ethtool_payload = _read_ethtool_payload(runner, interface_name)
    ethtool_info_payload = _read_ethtool_info_payload(runner, interface_name)

    return InterfaceSnapshot(
        name=interface_name,
        ip_addresses=_parse_ip_addresses(ip_payload),
        driver=ethtool_info_payload.get("driver"),
        driver_version=ethtool_info_payload.get("version"),
        firmware=ethtool_info_payload.get("firmware-version"),
        mtu=_parse_mtu(ip_payload),
        speed=_parse_speed(ethtool_payload.get("Speed")),
        link_state=_parse_link_state(ip_payload),
        link_up=_parse_link_up(ip_payload, ethtool_payload),
    )


def _read_ip_payload(runner: CommandRunner, interface_name: str) -> dict[str, object]:
    result = runner.run("ip", ["-j", "addr", "show", "dev", interface_name], timeout=5)
    if result.exit_code != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        return {}
    return payload[0]


def _read_ethtool_payload(runner: CommandRunner, interface_name: str) -> dict[str, str]:
    result = runner.run("ethtool", [interface_name], timeout=5)
    if result.exit_code != 0:
        return {}
    return _parse_key_value_lines(result.stdout)


def _read_ethtool_info_payload(
    runner: CommandRunner, interface_name: str
) -> dict[str, str]:
    result = runner.run("ethtool", ["-i", interface_name], timeout=5)
    if result.exit_code != 0:
        return {}
    return _parse_key_value_lines(result.stdout)


def _parse_key_value_lines(raw_output: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for line in raw_output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        payload[key.strip()] = value.strip()
    return payload


def _parse_ip_addresses(payload: dict[str, object]) -> list[str]:
    addresses: list[str] = []
    addr_info = payload.get("addr_info")
    if not isinstance(addr_info, list):
        return addresses
    for item in addr_info:
        if not isinstance(item, dict):
            continue
        local = item.get("local")
        if isinstance(local, str):
            addresses.append(local)
    return addresses


def _parse_mtu(payload: dict[str, object]) -> int | None:
    mtu = payload.get("mtu")
    return mtu if isinstance(mtu, int) else None


def _parse_link_state(payload: dict[str, object]) -> str | None:
    operstate = payload.get("operstate")
    return operstate if isinstance(operstate, str) else None


def _parse_link_up(
    ip_payload: dict[str, object], ethtool_payload: dict[str, str]
) -> bool | None:
    link_detected = ethtool_payload.get("Link detected")
    if link_detected is not None:
        return link_detected.lower() == "yes"
    operstate = _parse_link_state(ip_payload)
    if operstate is None:
        return None
    return operstate.upper() == "UP"


def _parse_speed(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.lower() == "unknown!":
        return None
    if normalized.endswith("Mb/s"):
        normalized = normalized[:-4]
    try:
        return int(normalized)
    except ValueError:
        return None


def _sudo_available(runner: CommandRunner) -> bool:
    if shutil.which("sudo") is None:
        return False
    result = runner.run("sudo", ["-n", "true"], timeout=5)
    return result.exit_code == 0


def _discover_local_interfaces() -> list[str]:
    sys_class_net = Path("/sys/class/net")
    if not sys_class_net.exists():
        return []
    return sorted(
        path.name
        for path in sys_class_net.iterdir()
        if path.is_dir() and path.name != "lo"
    )


def _file_contains(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _irqbalance_detected() -> bool:
    proc_root = Path("/proc")
    if not proc_root.exists():
        return False
    for proc_dir in proc_root.iterdir():
        if not proc_dir.name.isdigit():
            continue
        comm_path = proc_dir / "comm"
        try:
            if (
                comm_path.read_text(encoding="utf-8", errors="ignore").strip()
                == "irqbalance"
            ):
                return True
        except OSError:
            continue
    return False


def _coerce_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _coerce_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _coerce_optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _coerce_optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None
