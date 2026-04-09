from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from gvstress.core.models import RunValidity, ScenarioType
from gvstress.core.runner import CommandRunner, LocalRunner
from gvstress.dut.environment import (
    EnvironmentSnapshot,
    collect_local_environment_snapshot,
    collect_remote_environment_snapshot,
)


@dataclass(slots=True)
class InterfaceIPMapping:
    interface_name: str
    ip_address: str


@dataclass(slots=True)
class PreflightCheck:
    name: str
    passed: bool
    reasons: list[str]


@dataclass(slots=True)
class PreflightResult:
    run_validity: RunValidity
    reasons: list[str]
    checks: list[PreflightCheck]
    generator_environment: EnvironmentSnapshot | None
    dut_environment: EnvironmentSnapshot | None
    generator_environment_path: Path | None = None
    dut_environment_path: Path | None = None
    preflight_path: Path | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_validity": self.run_validity.value,
            "reasons": list(self.reasons),
            "checks": [asdict(check) for check in self.checks],
            "generator_environment": (
                self.generator_environment.to_dict()
                if self.generator_environment is not None
                else None
            ),
            "dut_environment": (
                self.dut_environment.to_dict()
                if self.dut_environment is not None
                else None
            ),
            "generator_environment_path": _path_to_str(self.generator_environment_path),
            "dut_environment_path": _path_to_str(self.dut_environment_path),
            "preflight_path": _path_to_str(self.preflight_path),
        }

    def write(self, out_dir: str | Path) -> PreflightResult:
        output_dir = Path(out_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.generator_environment is not None:
            self.generator_environment_path = output_dir / "generator_environment.json"
            self.generator_environment_path.write_text(
                json.dumps(
                    self.generator_environment.to_dict(), indent=2, sort_keys=True
                ),
                encoding="utf-8",
            )

        if self.dut_environment is not None:
            self.dut_environment_path = output_dir / "dut_environment.json"
            self.dut_environment_path.write_text(
                json.dumps(self.dut_environment.to_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )

        self.preflight_path = output_dir / "preflight.json"
        self.preflight_path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return self


def run_preflight(
    *,
    dut_host: str,
    dut_ifaces: list[str],
    ssh_runner: CommandRunner,
    generator_mappings: list[InterfaceIPMapping] | None = None,
    generator_ifaces: list[str] | None = None,
    local_runner: CommandRunner | None = None,
    scenario: ScenarioType | None = None,
    out_dir: str | Path | None = None,
    ssh_python_bin: str = "python3",
) -> PreflightResult:
    checks: list[PreflightCheck] = []
    reasons_by_validity: dict[RunValidity, list[str]] = {}
    generator_environment: EnvironmentSnapshot | None = None
    dut_environment: EnvironmentSnapshot | None = None
    command_runner = local_runner or LocalRunner()

    ssh_result = ssh_runner.run(
        ssh_python_bin,
        ["-m", "gvstress", "dut-agent", "ping", "--json"],
        timeout=10,
    )
    ssh_reasons: list[str] = []
    if ssh_result.exit_code != 0:
        ssh_reasons.append(f"dut.ssh_unreachable:{dut_host}")
        _record_reason(
            reasons_by_validity, RunValidity.INVALID_ENVIRONMENT, ssh_reasons[0]
        )
    checks.append(
        PreflightCheck(name="ssh", passed=not ssh_reasons, reasons=ssh_reasons)
    )

    if not ssh_reasons:
        generator_environment = collect_local_environment_snapshot(
            generator_ifaces
            or [mapping.interface_name for mapping in generator_mappings or []],
            runner=command_runner,
        )
        try:
            dut_environment = collect_remote_environment_snapshot(
                ssh_runner,
                dut_ifaces,
                python_bin=ssh_python_bin,
            )
        except RuntimeError as exc:
            _record_reason(
                reasons_by_validity,
                RunValidity.INVALID_ENVIRONMENT,
                f"dut.inspect_failed:{exc}",
            )

    binaries_reasons = _check_binaries(generator_environment, dut_environment, scenario)
    if binaries_reasons:
        for reason in binaries_reasons:
            _record_reason(reasons_by_validity, RunValidity.INVALID_PREREQ, reason)
    checks.append(
        PreflightCheck(
            name="binaries", passed=not binaries_reasons, reasons=binaries_reasons
        )
    )

    privilege_reasons = _check_privileges(generator_environment, dut_environment)
    if privilege_reasons:
        for reason in privilege_reasons:
            _record_reason(reasons_by_validity, RunValidity.INVALID_PREREQ, reason)
    checks.append(
        PreflightCheck(
            name="privileges", passed=not privilege_reasons, reasons=privilege_reasons
        )
    )

    interfaces_reasons = _check_interfaces(
        generator_environment, dut_environment, generator_mappings or [], dut_ifaces
    )
    if interfaces_reasons:
        for reason in interfaces_reasons:
            validity = (
                RunValidity.INVALID_MAPPING
                if "mapping" in reason or "duplicate" in reason
                else RunValidity.INVALID_ENVIRONMENT
            )
            _record_reason(reasons_by_validity, validity, reason)
    checks.append(
        PreflightCheck(
            name="interfaces", passed=not interfaces_reasons, reasons=interfaces_reasons
        )
    )

    link_reasons = _check_link_state(generator_environment, dut_environment, dut_ifaces)
    if link_reasons:
        for reason in link_reasons:
            _record_reason(reasons_by_validity, RunValidity.INVALID_ENVIRONMENT, reason)
    checks.append(
        PreflightCheck(name="link_state", passed=not link_reasons, reasons=link_reasons)
    )

    run_validity = _select_run_validity(reasons_by_validity)
    reasons = [reason for values in reasons_by_validity.values() for reason in values]
    result = PreflightResult(
        run_validity=run_validity,
        reasons=reasons,
        checks=checks,
        generator_environment=generator_environment,
        dut_environment=dut_environment,
    )
    if out_dir is not None:
        result.write(out_dir)
    return result


def invalid_prereq_result_for_missing_binary(
    binary: str,
    *,
    host_name: str = "generator",
    out_dir: str | Path | None = None,
) -> PreflightResult:
    reason = missing_binary_reason(binary, host_name=host_name)
    result = PreflightResult(
        run_validity=RunValidity.INVALID_PREREQ,
        reasons=[reason],
        checks=[PreflightCheck(name="binaries", passed=False, reasons=[reason])],
        generator_environment=None,
        dut_environment=None,
    )
    if out_dir is not None:
        result.write(out_dir)
    return result


def missing_binary_reason(binary: str, *, host_name: str = "generator") -> str:
    return f"{host_name}.missing_binary:{binary}"


def _check_binaries(
    generator_environment: EnvironmentSnapshot | None,
    dut_environment: EnvironmentSnapshot | None,
    scenario: ScenarioType | None,
) -> list[str]:
    reasons: list[str] = []
    for host_name, snapshot in (
        ("generator", generator_environment),
        ("dut", dut_environment),
    ):
        if snapshot is None:
            continue
        for binary, present in snapshot.required_binaries.items():
            if not present:
                reasons.append(f"{host_name}.missing_binary:{binary}")
    if (
        generator_environment is not None
        and not generator_environment.arv_fake_camera_present
    ):
        reasons.append("generator.missing_binary:arv-fake-gv-camera-0.10")
    if (
        scenario is ScenarioType.PKTGEN_BASELINE
        and generator_environment is not None
        and not generator_environment.pktgen_available
    ):
        reasons.append("generator.missing_binary:pktgen")
    return reasons


def _check_privileges(
    generator_environment: EnvironmentSnapshot | None,
    dut_environment: EnvironmentSnapshot | None,
) -> list[str]:
    reasons: list[str] = []
    if generator_environment is not None and not generator_environment.sudo_available:
        reasons.append("generator.sudo_unavailable")
    if dut_environment is not None and not dut_environment.sudo_available:
        reasons.append("dut.sudo_unavailable")
    return reasons


def _check_interfaces(
    generator_environment: EnvironmentSnapshot | None,
    dut_environment: EnvironmentSnapshot | None,
    generator_mappings: list[InterfaceIPMapping],
    dut_ifaces: list[str],
) -> list[str]:
    reasons: list[str] = []
    seen_interfaces: set[str] = set()
    seen_ips: set[str] = set()
    for mapping in generator_mappings:
        if mapping.interface_name in seen_interfaces:
            reasons.append(
                f"generator.duplicate_mapping.interface:{mapping.interface_name}"
            )
        seen_interfaces.add(mapping.interface_name)
        if mapping.ip_address in seen_ips:
            reasons.append(f"generator.duplicate_mapping.ip:{mapping.ip_address}")
        seen_ips.add(mapping.ip_address)

    if len(set(dut_ifaces)) != len(dut_ifaces):
        reasons.append("dut.duplicate_mapping.interface")

    if generator_environment is not None:
        available_generator_ifaces = {
            interface.name: interface for interface in generator_environment.interfaces
        }
        for mapping in generator_mappings:
            interface = available_generator_ifaces.get(mapping.interface_name)
            if interface is None:
                reasons.append(f"generator.missing_interface:{mapping.interface_name}")
                continue
            if mapping.ip_address not in interface.ip_addresses:
                reasons.append(
                    f"generator.mapping_ip_mismatch:{mapping.interface_name}:{mapping.ip_address}"
                )

    if dut_environment is not None:
        available_dut_ifaces = {
            interface.name for interface in dut_environment.interfaces
        }
        for interface_name in dut_ifaces:
            if interface_name not in available_dut_ifaces:
                reasons.append(f"dut.missing_interface:{interface_name}")
    return reasons


def _check_link_state(
    generator_environment: EnvironmentSnapshot | None,
    dut_environment: EnvironmentSnapshot | None,
    dut_ifaces: list[str],
) -> list[str]:
    reasons: list[str] = []
    if generator_environment is not None:
        for interface in generator_environment.interfaces:
            if interface.link_up is False:
                reasons.append(f"generator.link_down:{interface.name}")
            if interface.mtu is None or interface.mtu <= 0:
                reasons.append(f"generator.invalid_mtu:{interface.name}")
            if interface.speed is None or interface.speed <= 0:
                reasons.append(f"generator.invalid_speed:{interface.name}")
    if dut_environment is not None:
        wanted = set(dut_ifaces)
        for interface in dut_environment.interfaces:
            if interface.name not in wanted:
                continue
            if interface.link_up is False:
                reasons.append(f"dut.link_down:{interface.name}")
            if interface.mtu is None or interface.mtu <= 0:
                reasons.append(f"dut.invalid_mtu:{interface.name}")
            if interface.speed is None or interface.speed <= 0:
                reasons.append(f"dut.invalid_speed:{interface.name}")
    return reasons


def _record_reason(
    reasons_by_validity: dict[RunValidity, list[str]],
    validity: RunValidity,
    reason: str,
) -> None:
    reasons_by_validity.setdefault(validity, []).append(reason)


def _select_run_validity(
    reasons_by_validity: dict[RunValidity, list[str]],
) -> RunValidity:
    for validity in (
        RunValidity.INVALID_MAPPING,
        RunValidity.INVALID_PREREQ,
        RunValidity.INVALID_ENVIRONMENT,
        RunValidity.INVALID_TELEMETRY,
        RunValidity.INTERRUPTED,
    ):
        if reasons_by_validity.get(validity):
            return validity
    return RunValidity.VALID


def _path_to_str(path: Path | None) -> str | None:
    return str(path) if path is not None else None
