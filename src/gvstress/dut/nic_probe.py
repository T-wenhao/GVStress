from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from gvstress.core.runner import CommandRunner

STANDARD_NIC_COUNTERS: tuple[str, ...] = (
    "rx_packets",
    "rx_bytes",
    "rx_errors",
    "rx_dropped",
    "rx_over_errors",
    "rx_fifo_errors",
    "rx_missed_errors",
    "tx_packets",
    "tx_bytes",
    "tx_errors",
    "tx_dropped",
)

_SYSFS_STATS_SCRIPT = """
import json
import pathlib
import sys

iface = sys.argv[1]
root = pathlib.Path('/sys/class/net') / iface / 'statistics'
payload = {}
for path in root.iterdir() if root.exists() else []:
    try:
        payload[path.name] = int(path.read_text(encoding='utf-8').strip())
    except OSError:
        payload[path.name] = None
print(json.dumps(payload, sort_keys=True))
""".strip()


@dataclass(slots=True)
class CounterSample:
    absolute: int | None
    delta: int | None
    available: bool


@dataclass(slots=True)
class NICInterfaceSample:
    name: str
    standard_counters: dict[str, CounterSample]
    driver_counters: dict[str, CounterSample]
    aggregate_driver_counter: CounterSample
    driver_info: dict[str, str]
    features: dict[str, str | bool]
    channels: dict[str, int | str]
    source: dict[str, object]


@dataclass(slots=True)
class NICSample:
    timestamp: float
    interval: float | None
    interfaces: dict[str, NICInterfaceSample]
    aggregate_standard_counters: dict[str, CounterSample]
    aggregate_driver_counters: dict[str, CounterSample]


@dataclass(slots=True)
class _InterfaceSnapshot:
    standard_counters: dict[str, tuple[int | None, bool]]
    driver_counters: dict[str, tuple[int | None, bool]]


class NICProbe:
    def __init__(
        self,
        runner: CommandRunner,
        interfaces: Sequence[str],
        *,
        python_bin: str = "python3",
        timeout: float = 5.0,
        expected_driver_counters: Mapping[str, Sequence[str]]
        | Sequence[str]
        | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._runner = runner
        self._interfaces = list(interfaces)
        self._python_bin = python_bin
        self._timeout = timeout
        self._expected_driver_counters = expected_driver_counters
        self._clock = clock
        self._previous_snapshot: dict[str, _InterfaceSnapshot] | None = None
        self._previous_timestamp: float | None = None

    def collect(self) -> NICSample:
        timestamp = self._clock()
        previous_snapshot = self._previous_snapshot or {}
        interface_snapshots: dict[str, _InterfaceSnapshot] = {}
        interfaces: dict[str, NICInterfaceSample] = {}

        for interface_name in self._interfaces:
            ip_payload = self._read_ip_link_payload(interface_name)
            sysfs_payload = self._read_sysfs_statistics_payload(interface_name)
            ethtool_stats_payload = self._read_ethtool_stats_payload(interface_name)
            driver_info = self._read_key_value_command(
                "ethtool", ["-i", interface_name]
            )
            features = self._read_ethtool_features_payload(interface_name)
            channels = self._read_ethtool_channels_payload(interface_name)

            standard_values = self.parse_standard_counters(
                ip_payload=ip_payload,
                sysfs_payload=sysfs_payload,
            )
            driver_values = self.parse_driver_counters(
                ethtool_stats_payload,
                expected_counters=self._expected_counters_for(interface_name),
            )

            interface_snapshot = _InterfaceSnapshot(
                standard_counters={
                    key: (value.absolute, value.available)
                    for key, value in standard_values.items()
                },
                driver_counters={
                    key: (value.absolute, value.available)
                    for key, value in driver_values.items()
                },
            )
            interface_snapshots[interface_name] = interface_snapshot

            previous_interface = previous_snapshot.get(interface_name)
            standard_counters = self._apply_deltas(
                standard_values,
                previous_interface.standard_counters if previous_interface else None,
            )
            driver_counters = self._apply_deltas(
                driver_values,
                previous_interface.driver_counters if previous_interface else None,
            )
            interfaces[interface_name] = NICInterfaceSample(
                name=interface_name,
                standard_counters=standard_counters,
                driver_counters=driver_counters,
                aggregate_driver_counter=self._aggregate_counters(driver_counters),
                driver_info=driver_info,
                features=features,
                channels=channels,
                source={
                    "ip": ip_payload,
                    "sysfs_statistics": sysfs_payload,
                    "ethtool_stats": ethtool_stats_payload,
                },
            )

        sample = NICSample(
            timestamp=timestamp,
            interval=(
                None
                if self._previous_timestamp is None
                else timestamp - self._previous_timestamp
            ),
            interfaces=interfaces,
            aggregate_standard_counters=self._aggregate_interface_counters(
                [interface.standard_counters for interface in interfaces.values()]
            ),
            aggregate_driver_counters=self._aggregate_interface_counters(
                [interface.driver_counters for interface in interfaces.values()]
            ),
        )
        self._previous_snapshot = interface_snapshots
        self._previous_timestamp = timestamp
        return sample

    @staticmethod
    def parse_standard_counters(
        *,
        ip_payload: Mapping[str, object],
        sysfs_payload: Mapping[str, object] | None = None,
    ) -> dict[str, CounterSample]:
        stats_root = ip_payload.get("stats64")
        if not isinstance(stats_root, dict):
            stats_root = ip_payload.get("stats")
        rx_root = stats_root.get("rx") if isinstance(stats_root, dict) else None
        tx_root = stats_root.get("tx") if isinstance(stats_root, dict) else None
        rx_dict: Mapping[str, object] = rx_root if isinstance(rx_root, dict) else {}
        tx_dict: Mapping[str, object] = tx_root if isinstance(tx_root, dict) else {}

        payload: dict[str, CounterSample] = {}
        for counter_name in STANDARD_NIC_COUNTERS:
            section_name, field_name = counter_name.split("_", 1)
            source_root = rx_dict if section_name == "rx" else tx_dict
            value = _coerce_optional_int(source_root.get(field_name))
            if value is None and sysfs_payload is not None:
                value = _coerce_optional_int(sysfs_payload.get(counter_name))
            payload[counter_name] = CounterSample(
                absolute=value,
                delta=None,
                available=value is not None,
            )
        return payload

    @staticmethod
    def parse_driver_counters(
        raw_output: str,
        *,
        expected_counters: Sequence[str] | None = None,
    ) -> dict[str, CounterSample]:
        parsed: dict[str, CounterSample] = {}
        for line in raw_output.splitlines():
            stripped = line.strip()
            if not stripped or stripped.endswith(":") or ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            counter_name = key.strip()
            counter_value = value.strip()
            if counter_value.lower() in {"n/a", "na", "unavailable"}:
                parsed[counter_name] = CounterSample(
                    absolute=None,
                    delta=None,
                    available=False,
                )
                continue
            numeric_value = _coerce_optional_int(counter_value)
            parsed[counter_name] = CounterSample(
                absolute=numeric_value,
                delta=None,
                available=numeric_value is not None,
            )

        if expected_counters is not None:
            for counter_name in expected_counters:
                if counter_name not in parsed:
                    parsed[counter_name] = CounterSample(
                        absolute=None,
                        delta=None,
                        available=False,
                    )
        return parsed

    @staticmethod
    def parse_key_value_output(raw_output: str) -> dict[str, str]:
        payload: dict[str, str] = {}
        for line in raw_output.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            payload[key.strip()] = value.strip()
        return payload

    @classmethod
    def parse_ethtool_features(cls, raw_output: str) -> dict[str, str | bool]:
        payload: dict[str, str | bool] = {}
        for key, value in cls.parse_key_value_output(raw_output).items():
            normalized = value.lower()
            if normalized in {"on", "off", "fixed", "off [fixed]", "on [fixed]"}:
                payload[key] = normalized.startswith("on")
            else:
                payload[key] = value
        return payload

    @classmethod
    def parse_ethtool_channels(cls, raw_output: str) -> dict[str, int | str]:
        payload: dict[str, int | str] = {}
        for key, value in cls.parse_key_value_output(raw_output).items():
            numeric_value = _coerce_optional_int(value)
            payload[key] = value if numeric_value is None else numeric_value
        return payload

    def _read_ip_link_payload(self, interface_name: str) -> dict[str, object]:
        result = self._runner.run(
            "ip",
            ["-j", "-s", "-s", "link", "show", "dev", interface_name],
            timeout=self._timeout,
        )
        if result.exit_code != 0:
            raise RuntimeError(
                result.stderr or f"ip link stats failed for {interface_name}"
            )
        payload = json.loads(result.stdout)
        if (
            not isinstance(payload, list)
            or not payload
            or not isinstance(payload[0], dict)
        ):
            raise RuntimeError(f"unexpected ip payload for {interface_name}")
        return payload[0]

    def _read_sysfs_statistics_payload(self, interface_name: str) -> dict[str, object]:
        result = self._runner.run(
            self._python_bin,
            ["-c", _SYSFS_STATS_SCRIPT, interface_name],
            timeout=self._timeout,
        )
        if result.exit_code != 0:
            return {}
        payload = json.loads(result.stdout)
        return payload if isinstance(payload, dict) else {}

    def _read_ethtool_stats_payload(self, interface_name: str) -> str:
        result = self._runner.run(
            "ethtool",
            ["-S", interface_name],
            timeout=self._timeout,
        )
        return "" if result.exit_code != 0 else result.stdout

    def _read_key_value_command(
        self, command: str, argv: Sequence[str]
    ) -> dict[str, str]:
        result = self._runner.run(command, argv, timeout=self._timeout)
        return (
            {} if result.exit_code != 0 else self.parse_key_value_output(result.stdout)
        )

    def _read_ethtool_features_payload(
        self, interface_name: str
    ) -> dict[str, str | bool]:
        result = self._runner.run(
            "ethtool",
            ["-k", interface_name],
            timeout=self._timeout,
        )
        return (
            {} if result.exit_code != 0 else self.parse_ethtool_features(result.stdout)
        )

    def _read_ethtool_channels_payload(
        self, interface_name: str
    ) -> dict[str, int | str]:
        result = self._runner.run(
            "ethtool",
            ["-l", interface_name],
            timeout=self._timeout,
        )
        return (
            {} if result.exit_code != 0 else self.parse_ethtool_channels(result.stdout)
        )

    def _expected_counters_for(self, interface_name: str) -> Sequence[str] | None:
        expected = self._expected_driver_counters
        if expected is None:
            return None
        if isinstance(expected, Mapping):
            return list(expected.get(interface_name, ()))
        return list(expected)

    def _apply_deltas(
        self,
        values: dict[str, CounterSample],
        previous: Mapping[str, tuple[int | None, bool]] | None,
    ) -> dict[str, CounterSample]:
        payload: dict[str, CounterSample] = {}
        for counter_name, current in values.items():
            previous_value = None if previous is None else previous.get(counter_name)
            payload[counter_name] = CounterSample(
                absolute=current.absolute,
                delta=_counter_delta(
                    current.absolute,
                    None if previous_value is None else previous_value[0],
                    current.available,
                    True if previous_value is None else previous_value[1],
                ),
                available=current.available,
            )
        return payload

    def _aggregate_interface_counters(
        self,
        counter_sets: Sequence[Mapping[str, CounterSample]],
    ) -> dict[str, CounterSample]:
        counter_names = sorted({name for counters in counter_sets for name in counters})
        payload: dict[str, CounterSample] = {}
        for counter_name in counter_names:
            payload[counter_name] = self._aggregate_counters(
                {
                    str(index): counters[counter_name]
                    for index, counters in enumerate(counter_sets)
                    if counter_name in counters
                }
            )
        return payload

    @staticmethod
    def _aggregate_counters(
        counters: Mapping[str, CounterSample],
    ) -> CounterSample:
        available_samples = [sample for sample in counters.values() if sample.available]
        if not available_samples:
            return CounterSample(absolute=None, delta=None, available=False)
        absolute_values = [
            sample.absolute
            for sample in available_samples
            if sample.absolute is not None
        ]
        delta_values = [
            sample.delta for sample in available_samples if sample.delta is not None
        ]
        return CounterSample(
            absolute=sum(absolute_values) if absolute_values else None,
            delta=sum(delta_values) if delta_values else None,
            available=True,
        )


def _coerce_optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _counter_delta(
    current: int | None,
    previous: int | None,
    current_available: bool,
    previous_available: bool,
) -> int | None:
    if not current_available or not previous_available:
        return None
    if current is None or previous is None:
        return None
    if current >= previous:
        return current - previous
    return current
