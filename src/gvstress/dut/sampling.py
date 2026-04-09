from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from gvstress.dut.nic_probe import NICProbe, NICSample
from gvstress.dut.system_probe import SystemProbe, SystemSample


@dataclass(slots=True)
class SamplingTick:
    started_at: float
    finished_at: float
    nic: NICSample
    system: SystemSample


class SamplingScheduler:
    def __init__(
        self,
        nic_probe: NICProbe,
        system_probe: SystemProbe,
        *,
        interval_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._nic_probe = nic_probe
        self._system_probe = system_probe
        self._interval_seconds = interval_seconds
        self._clock = clock
        self._sleep = sleep

    def sample_once(self) -> SamplingTick:
        started_at = self._clock()
        nic_sample = self._nic_probe.collect()
        system_sample = self._system_probe.collect()
        finished_at = self._clock()
        return SamplingTick(
            started_at=started_at,
            finished_at=finished_at,
            nic=nic_sample,
            system=system_sample,
        )

    def collect(self, samples: int) -> list[SamplingTick]:
        collected: list[SamplingTick] = []
        for index in range(samples):
            tick = self.sample_once()
            collected.append(tick)
            if index == samples - 1:
                continue
            self._sleep(
                max(0.0, self._interval_seconds - (tick.finished_at - tick.started_at))
            )
        return collected
