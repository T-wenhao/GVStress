# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic_core import PydanticCustomError

from gvstress.core.models import ScenarioType


class StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class FakeCameraConfig(StrictModel):
    ip_address: str
    interface_name: str
    serial_number: str
    genicam_filename: str
    gvsp_lost_ratio: float = 0.0

    @model_validator(mode="after")
    def validate_gvsp_lost_ratio(self) -> FakeCameraConfig:
        if not 0.0 <= self.gvsp_lost_ratio <= 1.0:
            raise PydanticCustomError(
                "generator.invalid_loss_ratio",
                "generator.invalid_loss_ratio",
                {"gvsp_lost_ratio": self.gvsp_lost_ratio},
            )
        return self


class GeneratorConfig(StrictModel):
    cameras: list[FakeCameraConfig]

    @model_validator(mode="after")
    def validate_unique_mappings(self) -> GeneratorConfig:
        seen_ips: set[str] = set()
        seen_interfaces: set[str] = set()

        for camera in self.cameras:
            if camera.ip_address in seen_ips:
                raise PydanticCustomError(
                    "generator.ip_conflict",
                    "generator.ip_conflict",
                    {"ip_address": camera.ip_address},
                )
            seen_ips.add(camera.ip_address)

            if camera.interface_name in seen_interfaces:
                raise PydanticCustomError(
                    "generator.interface_conflict",
                    "generator.interface_conflict",
                    {"interface_name": camera.interface_name},
                )
            seen_interfaces.add(camera.interface_name)

        return self


class DUTCollectOptions(StrictModel):
    nic: bool
    stream: bool
    system: bool


class DUTConfig(StrictModel):
    ifaces: list[str]
    sample_interval_ms: int
    collect: DUTCollectOptions
    host: str = ""
    user: str = ""
    port: int = 22
    python_bin: str = "python3"


class StreamConfig(StrictModel):
    packet_resend: bool
    socket_buffer: bool
    socket_buffer_size: int
    frame_retention: int
    initial_packet_timeout: int
    packet_timeout: int
    packet_request_ratio: float
    receiver_priority: int
    buffer_count: int = 16

    @model_validator(mode="after")
    def validate_stream_settings(self) -> StreamConfig:
        non_negative_fields = {
            "socket_buffer_size": self.socket_buffer_size,
            "frame_retention": self.frame_retention,
            "initial_packet_timeout": self.initial_packet_timeout,
            "packet_timeout": self.packet_timeout,
        }
        for field_name, value in non_negative_fields.items():
            if value < 0:
                raise PydanticCustomError(
                    "stream.invalid_property",
                    "stream.invalid_property",
                    {"field": field_name, "value": value},
                )

        if not 0.0 <= self.packet_request_ratio <= 2.0:
            raise PydanticCustomError(
                "stream.invalid_packet_request_ratio",
                "stream.invalid_packet_request_ratio",
                {"packet_request_ratio": self.packet_request_ratio},
            )

        if self.buffer_count <= 0:
            raise PydanticCustomError(
                "stream.invalid_buffer_count",
                "stream.invalid_buffer_count",
                {"buffer_count": self.buffer_count},
            )

        return self

    def property_snapshot(self) -> dict[str, bool | int | float]:
        return {
            "packet_resend": self.packet_resend,
            "socket_buffer": self.socket_buffer,
            "socket_buffer_size": self.socket_buffer_size,
            "frame_retention": self.frame_retention,
            "initial_packet_timeout": self.initial_packet_timeout,
            "packet_timeout": self.packet_timeout,
            "packet_request_ratio": self.packet_request_ratio,
            "receiver_priority": self.receiver_priority,
            "buffer_count": self.buffer_count,
        }

    def applied_property_values(self) -> dict[str, int | float]:
        return {
            "packet-resend": 1 if self.packet_resend else 0,
            "socket-buffer": 1 if self.socket_buffer else 0,
            "socket-buffer-size": self.socket_buffer_size,
            "frame-retention": self.frame_retention,
            "initial-packet-timeout": self.initial_packet_timeout,
            "packet-timeout": self.packet_timeout,
            "packet-request-ratio": self.packet_request_ratio,
        }


class ScenarioConfig(StrictModel):
    name: ScenarioType
    duration: int
    warmup: int
    cooldown: int

    @model_validator(mode="after")
    def validate_locked_v1_contract(self) -> ScenarioConfig:
        locked_durations = {
            ScenarioType.SMOKE: 60,
            ScenarioType.FOUR_STREAM: 300,
            ScenarioType.SOAK: 1800,
            ScenarioType.LOSS_INJECTION: 300,
            ScenarioType.PKTGEN_BASELINE: 300,
        }
        expected_duration = locked_durations[self.name]
        if self.duration != expected_duration:
            raise PydanticCustomError(
                "scenario.locked_duration",
                "scenario '{scenario}' duration must be {expected_duration}s for locked V1",
                {
                    "scenario": self.name.value,
                    "expected_duration": expected_duration,
                    "duration": self.duration,
                },
            )

        if self.warmup != 10:
            raise PydanticCustomError(
                "scenario.locked_warmup",
                "scenario '{scenario}' warmup must be 10s for locked V1",
                {"scenario": self.name.value, "warmup": self.warmup},
            )

        if self.cooldown != 5:
            raise PydanticCustomError(
                "scenario.locked_cooldown",
                "scenario '{scenario}' cooldown must be 5s for locked V1",
                {"scenario": self.name.value, "cooldown": self.cooldown},
            )

        return self


class PktgenConfig(StrictModel):
    interfaces: list[str]
    duration: int = 300
    packet_size: int
    rate_mbps: int | None = None
    rate: str | None = None
    ratep: int | None = None
    xmit_mode: str = "start_xmit"

    @model_validator(mode="after")
    def validate_rate_configuration(self) -> PktgenConfig:
        if self.duration <= 0:
            raise PydanticCustomError(
                "pktgen.invalid_duration",
                "pktgen.invalid_duration",
                {"duration": self.duration},
            )
        if self.packet_size <= 0:
            raise PydanticCustomError(
                "pktgen.invalid_packet_size",
                "pktgen.invalid_packet_size",
                {"packet_size": self.packet_size},
            )

        configured_rates = [
            self.rate_mbps is not None,
            self.rate is not None,
            self.ratep is not None,
        ]
        if sum(configured_rates) != 1:
            raise PydanticCustomError(
                "pktgen.invalid_rate",
                "pktgen.invalid_rate",
                {
                    "rate_mbps": self.rate_mbps,
                    "rate": self.rate,
                    "ratep": self.ratep,
                },
            )

        if self.rate_mbps is not None and self.rate_mbps <= 0:
            raise PydanticCustomError(
                "pktgen.invalid_rate",
                "pktgen.invalid_rate",
                {"rate_mbps": self.rate_mbps},
            )
        if self.ratep is not None and self.ratep <= 0:
            raise PydanticCustomError(
                "pktgen.invalid_rate",
                "pktgen.invalid_rate",
                {"ratep": self.ratep},
            )
        if self.xmit_mode not in {"start_xmit", "netif_receive"}:
            raise PydanticCustomError(
                "pktgen.invalid_xmit_mode",
                "pktgen.invalid_xmit_mode",
                {"xmit_mode": self.xmit_mode},
            )
        return self

    def resolved_rate(self) -> str | None:
        if self.rate is not None:
            return self.rate
        if self.rate_mbps is not None:
            return f"{self.rate_mbps}M"
        return None


class OutputConfig(StrictModel):
    root: Path
    raw_dir: Path
    reports_dir: Path
    logs_dir: Path
    evidence_dir: Path


class Config(StrictModel):
    generator: GeneratorConfig
    dut: DUTConfig
    stream: StreamConfig
    scenarios: list[ScenarioConfig]
    pktgen: PktgenConfig
    output: OutputConfig
