from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypedDict, cast

from gvstress.core.runner import CommandRunner

_READ_TEXT_SCRIPT = """
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
print(json.dumps({'text': path.read_text(encoding='utf-8', errors='ignore')}))
""".strip()


@dataclass(slots=True)
class CPUCoreSample:
    counters: dict[str, int]
    deltas: dict[str, int] | None
    usage_pct: float | None


@dataclass(slots=True)
class IRQLineSample:
    irq: str
    cpu_counts: dict[str, int]
    delta_counts: dict[str, int] | None
    description: str


@dataclass(slots=True)
class InterfaceIRQSample:
    interface: str
    irqs: list[IRQLineSample]
    total_counts: dict[str, int]
    delta_counts: dict[str, int] | None
    dominant_cpu: str | None


@dataclass(slots=True)
class SystemSample:
    timestamp: float
    interval: float | None
    cpus: dict[str, CPUCoreSample]
    interfaces: dict[str, InterfaceIRQSample]


@dataclass(slots=True)
class _SystemSnapshot:
    cpus: dict[str, dict[str, int]]
    interfaces: dict[str, dict[str, dict[str, int]]]


class _ParsedIRQLine(TypedDict):
    irq: str
    cpu_counts: dict[str, int]
    description: str


class SystemProbe:
    def __init__(
        self,
        runner: CommandRunner,
        interfaces: Sequence[str],
        *,
        python_bin: str = "python3",
        timeout: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._runner = runner
        self._interfaces = list(interfaces)
        self._python_bin = python_bin
        self._timeout = timeout
        self._clock = clock
        self._previous_snapshot: _SystemSnapshot | None = None
        self._previous_timestamp: float | None = None

    def collect(self) -> SystemSample:
        timestamp = self._clock()
        proc_stat = self._read_text_file("/proc/stat")
        proc_interrupts = self._read_text_file("/proc/interrupts")

        cpu_counters = self.parse_proc_stat(proc_stat)
        interface_irq_lines = self.parse_proc_interrupts(
            proc_interrupts, self._interfaces
        )

        previous_snapshot = self._previous_snapshot
        cpus: dict[str, CPUCoreSample] = {}
        for cpu_name, counters in cpu_counters.items():
            previous = (
                None
                if previous_snapshot is None
                else previous_snapshot.cpus.get(cpu_name)
            )
            deltas = _delta_counter_map(counters, previous)
            cpus[cpu_name] = CPUCoreSample(
                counters=counters,
                deltas=deltas,
                usage_pct=_cpu_usage_pct(deltas),
            )

        interfaces: dict[str, InterfaceIRQSample] = {}
        for interface_name, irq_lines in interface_irq_lines.items():
            previous_lines = (
                {}
                if previous_snapshot is None
                else previous_snapshot.interfaces.get(interface_name, {})
            )
            irq_samples: list[IRQLineSample] = []
            for irq_line in irq_lines:
                previous_counts = previous_lines.get(irq_line["irq"], None)
                delta_counts = _delta_counter_map(
                    irq_line["cpu_counts"], previous_counts
                )
                irq_samples.append(
                    IRQLineSample(
                        irq=irq_line["irq"],
                        cpu_counts=irq_line["cpu_counts"],
                        delta_counts=delta_counts,
                        description=irq_line["description"],
                    )
                )

            total_counts = _sum_counter_maps([irq.cpu_counts for irq in irq_samples])
            delta_counts = _sum_counter_maps(
                [
                    irq.delta_counts
                    for irq in irq_samples
                    if irq.delta_counts is not None
                ]
            )
            interfaces[interface_name] = InterfaceIRQSample(
                interface=interface_name,
                irqs=irq_samples,
                total_counts=total_counts,
                delta_counts=None if not delta_counts else delta_counts,
                dominant_cpu=_dominant_cpu(delta_counts),
            )

        self._previous_snapshot = _SystemSnapshot(
            cpus=cpu_counters,
            interfaces={
                interface_name: {
                    irq_line["irq"]: irq_line["cpu_counts"] for irq_line in irq_lines
                }
                for interface_name, irq_lines in interface_irq_lines.items()
            },
        )
        sample = SystemSample(
            timestamp=timestamp,
            interval=(
                None
                if self._previous_timestamp is None
                else timestamp - self._previous_timestamp
            ),
            cpus=cpus,
            interfaces=interfaces,
        )
        self._previous_timestamp = timestamp
        return sample

    @staticmethod
    def parse_proc_stat(raw_output: str) -> dict[str, dict[str, int]]:
        payload: dict[str, dict[str, int]] = {}
        field_names = [
            "user",
            "nice",
            "system",
            "idle",
            "iowait",
            "irq",
            "softirq",
            "steal",
            "guest",
            "guest_nice",
        ]
        for line in raw_output.splitlines():
            if not line.startswith("cpu"):
                continue
            parts = line.split()
            cpu_name = parts[0]
            values = [int(value) for value in parts[1:]]
            payload[cpu_name] = {
                field_names[index]: value
                for index, value in enumerate(values)
                if index < len(field_names)
            }
        return payload

    @staticmethod
    def parse_proc_interrupts(
        raw_output: str,
        interfaces: Sequence[str],
    ) -> dict[str, list[_ParsedIRQLine]]:
        lines = raw_output.splitlines()
        if not lines:
            return {interface: [] for interface in interfaces}
        cpu_names = lines[0].split()
        payload: dict[str, list[_ParsedIRQLine]] = {
            interface: [] for interface in interfaces
        }
        for line in lines[1:]:
            if ":" not in line:
                continue
            irq_name, remainder = line.split(":", 1)
            parts = remainder.split()
            if len(parts) < len(cpu_names):
                continue
            cpu_values = parts[: len(cpu_names)]
            description = " ".join(parts[len(cpu_names) :])
            cpu_counts = {
                cpu_name: int(value)
                for cpu_name, value in zip(cpu_names, cpu_values, strict=True)
            }
            for interface in interfaces:
                if interface in description:
                    payload[interface].append(
                        _ParsedIRQLine(
                            irq=irq_name.strip(),
                            cpu_counts=cpu_counts,
                            description=description,
                        )
                    )
        return payload

    def _read_text_file(self, path: str) -> str:
        result = self._runner.run(
            self._python_bin,
            ["-c", _READ_TEXT_SCRIPT, path],
            timeout=self._timeout,
        )
        if result.exit_code != 0:
            raise RuntimeError(result.stderr or f"failed to read {path}")
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise RuntimeError(f"unexpected text payload for {path}")
        value = cast(object, payload.get("text"))
        if not isinstance(value, str):
            raise RuntimeError(f"missing text payload for {path}")
        return value


def _delta_counter_map(
    current: Mapping[str, int],
    previous: Mapping[str, int] | None,
) -> dict[str, int] | None:
    if previous is None:
        return None
    payload: dict[str, int] = {}
    for key, value in current.items():
        previous_value = previous.get(key)
        if previous_value is None:
            continue
        payload[key] = value - previous_value if value >= previous_value else value
    return payload


def _cpu_usage_pct(deltas: Mapping[str, int] | None) -> float | None:
    if not deltas:
        return None
    total = sum(deltas.values())
    if total <= 0:
        return None
    idle = deltas.get("idle", 0) + deltas.get("iowait", 0)
    busy = total - idle
    return busy / total * 100.0


def _sum_counter_maps(
    counter_maps: Sequence[Mapping[str, int] | None],
) -> dict[str, int]:
    payload: dict[str, int] = {}
    for counter_map in counter_maps:
        if counter_map is None:
            continue
        for key, value in counter_map.items():
            payload[key] = payload.get(key, 0) + value
    return payload


def _dominant_cpu(counter_map: Mapping[str, int] | None) -> str | None:
    if not counter_map:
        return None
    return max(counter_map.items(), key=lambda item: item[1])[0]
