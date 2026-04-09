from __future__ import annotations

import json
from collections.abc import Sequence

from gvstress.core.runner import CommandResult, CommandRunner
from gvstress.dut.nic_probe import NICProbe
from gvstress.dut.sampling import SamplingScheduler
from gvstress.dut.system_probe import SystemProbe


class FakeRunner(CommandRunner):
    def __init__(self) -> None:
        super().__init__()
        self._nic_iteration = 0
        self._system_iteration = 0

    def run(
        self,
        command: str,
        argv: Sequence[str] | None = None,
        *,
        timeout: float | None = None,
    ) -> CommandResult:
        _ = timeout
        argv = list(argv or [])
        if command == "ip" and argv[:5] == ["-j", "-s", "-s", "link", "show"]:
            interface = argv[-1]
            sample_index = self._nic_iteration // 2
            payload = self._ip_payload(interface, sample_index)
            self._nic_iteration += 1
            return self._result(command, argv, json.dumps([payload]))
        if command == "python3" and len(argv) >= 3 and argv[0] == "-c":
            target = argv[-1]
            if target.startswith("/proc/"):
                payload = {"text": self._proc_text(target, self._system_iteration // 2)}
                self._system_iteration += 1
                return self._result(command, argv, json.dumps(payload))
            interface = target
            return self._result(
                command, argv, json.dumps(self._sysfs_payload(interface))
            )
        if command == "ethtool" and argv[:1] == ["-S"]:
            interface = argv[1]
            sample_index = max(0, (self._nic_iteration - 1) // 2)
            return self._result(
                command, argv, self._ethtool_stats(interface, sample_index)
            )
        if command == "ethtool" and argv[:1] == ["-i"]:
            return self._result(command, argv, "driver: igb\nversion: 5.15.0\n")
        if command == "ethtool" and argv[:1] == ["-k"]:
            return self._result(command, argv, "rx-checksumming: on\n")
        if command == "ethtool" and argv[:1] == ["-l"]:
            return self._result(command, argv, "Combined: 4\n")
        raise AssertionError([command, *argv])

    @staticmethod
    def _result(command: str, argv: Sequence[str], stdout: str) -> CommandResult:
        return CommandResult(
            command=command,
            argv=[command, *list(argv)],
            exit_code=0,
            stdout=stdout,
            stderr="",
            duration=0.0,
            timed_out=False,
        )

    def _ip_payload(self, interface: str, sample_index: int) -> dict[str, object]:
        base = 1000 if interface == "eno1" else 2000
        step = 100 if interface == "eno1" else 150
        value = base + step * sample_index
        return {
            "ifname": interface,
            "stats64": {
                "rx": {
                    "packets": value,
                    "bytes": value * 10,
                    "errors": 0,
                    "dropped": 0,
                    "over_errors": 0,
                    "fifo_errors": 0,
                    "missed_errors": sample_index,
                },
                "tx": {
                    "packets": value // 2,
                    "bytes": value * 5,
                    "errors": 0,
                    "dropped": 0,
                },
            },
        }

    def _sysfs_payload(self, interface: str) -> dict[str, int]:
        return {"tx_errors": 0, "rx_packets": 0 if interface == "eno1" else 1}

    def _ethtool_stats(self, interface: str, sample_index: int) -> str:
        value = (10 if interface == "eno1" else 20) + sample_index * 3
        return (
            f"NIC statistics:\n  rx_queue_0_packets: {value}\n  tx_timeout_count: n/a\n"
        )

    def _proc_text(self, target: str, sample_index: int) -> str:
        if target == "/proc/stat":
            user0 = 100 + sample_index * 40
            user1 = 90 + sample_index * 20
            return (
                f"cpu  {user0 + user1} 0 50 {500 + sample_index * 10} 0 0 0 0 0 0\n"
                f"cpu0 {user0} 0 20 {200 + sample_index * 5} 0 0 0 0 0 0\n"
                f"cpu1 {user1} 0 30 {300 + sample_index * 5} 0 0 0 0 0 0\n"
            )
        if target == "/proc/interrupts":
            return (
                "           CPU0       CPU1\n"
                f" 24:        {100 + sample_index * 50}         {10 + sample_index * 2}  IR-PCI-MSI  eno1-TxRx-0\n"
                f" 25:        {5 + sample_index}         {20 + sample_index * 30}  IR-PCI-MSI  eno2-TxRx-0\n"
            )
        raise AssertionError(target)


def test_nic_and_system_samples_produce_deltas() -> None:
    runner = FakeRunner()
    nic_probe = NICProbe(
        runner,
        ["eno1", "eno2"],
        expected_driver_counters=["rx_queue_0_packets", "tx_timeout_count"],
    )
    system_probe = SystemProbe(runner, ["eno1", "eno2"])
    scheduler = SamplingScheduler(
        nic_probe,
        system_probe,
        interval_seconds=1.0,
        clock=iter([0.0, 0.1, 1.0, 1.1]).__next__,
        sleep=lambda seconds: None,
    )

    first, second = scheduler.collect(2)

    assert first.nic.aggregate_standard_counters["rx_packets"].delta is None
    assert second.nic.interfaces["eno1"].standard_counters["rx_packets"].delta == 100
    assert second.nic.interfaces["eno2"].standard_counters["rx_packets"].delta == 150
    assert second.nic.aggregate_standard_counters["rx_packets"].delta == 250
    assert (
        second.nic.interfaces["eno1"].driver_counters["rx_queue_0_packets"].delta == 3
    )
    assert (
        second.nic.interfaces["eno1"].driver_counters["tx_timeout_count"].available
        is False
    )

    assert second.system.cpus["cpu0"].deltas == {
        "user": 40,
        "nice": 0,
        "system": 0,
        "idle": 5,
        "iowait": 0,
        "irq": 0,
        "softirq": 0,
        "steal": 0,
        "guest": 0,
        "guest_nice": 0,
    }
    assert second.system.interfaces["eno1"].delta_counts == {"CPU0": 50, "CPU1": 2}
    assert second.system.interfaces["eno1"].dominant_cpu == "CPU0"
    assert second.system.interfaces["eno2"].dominant_cpu == "CPU1"
