from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from gvstress.config.models import PktgenConfig, PktgenInterfaceConfig


@dataclass(slots=True, frozen=True)
class PktgenThreadAssignment:
    thread_name: str
    interface: str
    device_name: str
    source_path: Path


@dataclass(slots=True, frozen=True)
class PktgenControlScripts:
    thread_scripts: dict[str, str]
    device_scripts: dict[str, str]
    start_script: str
    stop_script: str


@dataclass(slots=True, frozen=True)
class PktgenParsedResult:
    interface: str
    device_name: str
    thread_name: str
    source_path: str
    packets: int | None
    packet_size: int | None
    frags: int | None
    errors: int | None
    duration_usec: int | None
    pps: int | None
    mbps: int | None
    bps: int | None
    result: str
    rate: str | None
    ratep: int | None
    xmit_mode: str | None
    params: dict[str, str]
    current: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PktgenRunner:
    _RESULT_RE = re.compile(
        r"(?P<duration_usec>\d+)\([^)]*\)\s+usec,\s+"
        r"(?P<packets>\d+)\s+\((?P<packet_size>\d+)byte,(?P<frags>\d+)frags\)"
    )
    _THROUGHPUT_RE = re.compile(
        r"(?P<pps>\d+)pps\s+(?P<mbps>\d+)Mb/sec\s+\((?P<bps>\d+)bps\)\s+errors:\s+(?P<errors>\d+)"
    )

    def __init__(
        self,
        config: PktgenConfig,
        *,
        proc_root: str | Path = "/proc/net/pktgen",
    ) -> None:
        self._config = config
        self._proc_root = Path(proc_root)

    def build_assignments(self) -> list[PktgenThreadAssignment]:
        assignments: list[PktgenThreadAssignment] = []
        for index, interface in enumerate(self._config.interfaces):
            assignments.append(
                PktgenThreadAssignment(
                    thread_name=f"kpktgend_{index}",
                    interface=interface,
                    device_name=f"{interface}@{index}",
                    source_path=self._proc_root / f"{interface}@{index}",
                )
            )
        return assignments

    def build_control_scripts(self) -> PktgenControlScripts:
        assignments = self.build_assignments()
        rate = self._config.resolved_rate()
        thread_scripts = {
            assignment.thread_name: (
                f"rem_device_all\nadd_device {assignment.device_name}\n"
            )
            for assignment in assignments
        }
        device_scripts: dict[str, str] = {}
        for assignment in assignments:
            net_cfg = self._resolve_network_config(assignment.interface)
            count = 0 if net_cfg is None else net_cfg.count
            commands = [f"count {count}"]
            commands.append(f"pkt_size {self._config.packet_size}")
            commands.append(f"xmit_mode {self._config.xmit_mode}")
            if rate is not None:
                commands.append(f"rate {rate}")
            if self._config.ratep is not None:
                commands.append(f"ratep {self._config.ratep}")
            if net_cfg is not None:
                if net_cfg.dst_ip is not None:
                    commands.append("flag IPDST_RND 0")
                    commands.append(f"dst {net_cfg.dst_ip}")
                if net_cfg.udp:
                    commands.append("flag UDPSRC_RND 0")
                    commands.append("udp_dst_min 9")
                    commands.append("udp_dst_max 9")

            device_scripts[assignment.device_name] = "\n".join(commands) + "\n"
        return PktgenControlScripts(
            thread_scripts=thread_scripts,
            device_scripts=device_scripts,
            start_script="start\n",
            stop_script="stop\n",
        )

    def _resolve_network_config(
        self, interface_name: str
    ) -> PktgenInterfaceConfig | None:
        if self._config.network is None:
            return None
        match = [
            cfg for cfg in self._config.network if cfg.name == interface_name
        ]
        if len(match) == 1:
            return match[0]
        return None

    def materialize_control_scripts(
        self,
        output_dir: str | Path,
    ) -> tuple[list[PktgenThreadAssignment], dict[str, Path]]:
        scripts_dir = Path(output_dir)
        scripts_dir.mkdir(parents=True, exist_ok=True)
        assignments = self.build_assignments()
        scripts = self.build_control_scripts()
        written_paths: dict[str, Path] = {}
        for assignment in assignments:
            thread_path = scripts_dir / f"{assignment.thread_name}.pg"
            device_path = scripts_dir / f"{assignment.device_name}.pg"
            thread_path.write_text(
                scripts.thread_scripts[assignment.thread_name], encoding="utf-8"
            )
            device_path.write_text(
                scripts.device_scripts[assignment.device_name], encoding="utf-8"
            )
            written_paths[thread_path.name] = thread_path
            written_paths[device_path.name] = device_path
        start_path = scripts_dir / "pgctrl-start.pg"
        stop_path = scripts_dir / "pgctrl-stop.pg"
        start_path.write_text(scripts.start_script, encoding="utf-8")
        stop_path.write_text(scripts.stop_script, encoding="utf-8")
        written_paths[start_path.name] = start_path
        written_paths[stop_path.name] = stop_path
        return assignments, written_paths

    def prepare(self) -> list[PktgenThreadAssignment]:
        assignments = self.build_assignments()
        scripts = self.build_control_scripts()
        for assignment in assignments:
            _write_pktgen_control(
                self._proc_root / assignment.thread_name,
                scripts.thread_scripts[assignment.thread_name],
            )
            _write_pktgen_control(
                assignment.source_path,
                scripts.device_scripts[assignment.device_name],
            )
        return assignments

    def start(self) -> None:
        _write_pktgen_control(self._proc_root / "pgctrl", "start\n")

    def stop(self) -> None:
        _write_pktgen_control(self._proc_root / "pgctrl", "stop\n")

    def collect_results(
        self,
        assignments: list[PktgenThreadAssignment] | None = None,
    ) -> list[PktgenParsedResult]:
        resolved_assignments = assignments or self.build_assignments()
        return [
            self.parse_result(
                assignment.source_path.read_text(encoding="utf-8", errors="ignore"),
                assignment=assignment,
            )
            for assignment in resolved_assignments
        ]

    @classmethod
    def parse_result(
        cls,
        raw_output: str,
        *,
        assignment: PktgenThreadAssignment,
    ) -> PktgenParsedResult:
        sections = cls._parse_sections(raw_output)
        params = cls._parse_key_value_blob(sections.get("Params", ""))
        current = cls._parse_key_value_blob(sections.get("Current", ""))
        result_line = sections.get("Result", "").strip()
        result_match = cls._RESULT_RE.search(result_line)
        throughput_match = cls._THROUGHPUT_RE.search(result_line)
        return PktgenParsedResult(
            interface=assignment.interface,
            device_name=assignment.device_name,
            thread_name=assignment.thread_name,
            source_path=str(assignment.source_path),
            packets=_group_int(result_match, "packets"),
            packet_size=_group_int(result_match, "packet_size"),
            frags=_group_int(result_match, "frags"),
            errors=_group_int(throughput_match, "errors")
            if throughput_match is not None
            else _coerce_int(current.get("errors")),
            duration_usec=_group_int(result_match, "duration_usec"),
            pps=_group_int(throughput_match, "pps"),
            mbps=_group_int(throughput_match, "mbps"),
            bps=_group_int(throughput_match, "bps"),
            result=result_line,
            rate=params.get("rate"),
            ratep=_coerce_int(params.get("ratep")),
            xmit_mode=params.get("xmit_mode"),
            params=params,
            current=current,
        )

    @staticmethod
    def _parse_sections(raw_output: str) -> dict[str, str]:
        sections: dict[str, list[str]] = {}
        current_section: str | None = None
        for line in raw_output.splitlines():
            stripped = line.strip()
            if stripped in {"Params:", "Current:"}:
                current_section = stripped[:-1]
                sections.setdefault(current_section, [])
                continue
            if stripped.startswith("Result:"):
                current_section = "Result"
                sections[current_section] = [stripped.partition(":")[2].strip()]
                continue
            if current_section is not None and stripped:
                sections.setdefault(current_section, []).append(stripped)
        return {key: " ".join(value).strip() for key, value in sections.items()}

    @staticmethod
    def _parse_key_value_blob(raw_blob: str) -> dict[str, str]:
        payload: dict[str, str] = {}
        cleaned_blob = raw_blob.replace("\n", " ")
        for match in re.finditer(
            r"([A-Za-z0-9_\-]+):?\s+([^:]+?)(?=\s+[A-Za-z0-9_\-]+:?\s+|$)", cleaned_blob
        ):
            key = match.group(1).rstrip(":")
            value = match.group(2).strip()
            payload[key] = value
        return payload


def _group_int(match: re.Match[str] | None, name: str) -> int | None:
    if match is None:
        return None
    return int(match.group(name))


def _coerce_int(value: str | None) -> int | None:
    if value is None:
        return None
    digits = value.strip()
    if digits.endswith("us"):
        digits = digits[:-2]
    try:
        return int(digits)
    except ValueError:
        return None


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _write_pktgen_control(path: Path, script: str) -> None:
    if not _is_real_procfs_path(path):
        path.write_text(script, encoding="utf-8")
        return

    for command in script.splitlines():
        command = command.strip()
        if command:
            path.write_text(command + "\n", encoding="utf-8")


def _is_real_procfs_path(path: Path) -> bool:
    try:
        path.resolve().relative_to("/proc")
    except ValueError:
        return False
    return True
