from pathlib import Path

import pytest
from pydantic import ValidationError

from gvstress.config import load_config

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "configs"


def test_duplicate_camera_ip_rejected() -> None:
    with pytest.raises(ValidationError, match="generator.ip_conflict"):
        _ = load_config(FIXTURE_DIR / "duplicate-ip.yaml")


def test_invalid_loss_ratio_rejected() -> None:
    with pytest.raises(ValidationError, match="generator.invalid_loss_ratio"):
        _ = load_config(FIXTURE_DIR / "invalid-loss-ratio.yaml")


def test_missing_required_field_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "missing-field.yaml"
    _ = config_path.write_text(
        """
generator:
  cameras:
    - ip_address: 192.168.10.11
      serial_number: CAM-001
      genicam_filename: camera-a.xml
dut:
  ifaces: [eno1]
  sample_interval_ms: 1000
  collect:
    nic: true
    stream: true
    system: true
stream:
  packet_resend: true
  socket_buffer: true
  socket_buffer_size: 1048576
  frame_retention: 200000
  initial_packet_timeout: 1000
  packet_timeout: 2000
  packet_request_ratio: 0.25
  receiver_priority: 0
scenarios:
  - name: smoke
    duration: 60
    warmup: 5
    cooldown: 5
pktgen:
  interfaces: [eno1]
  duration: 300
  packet_size: 1500
  rate_mbps: 1000
output:
  root: artifacts/run-001
  raw_dir: artifacts/run-001/raw
  reports_dir: artifacts/run-001/reports
  logs_dir: artifacts/run-001/logs
  evidence_dir: artifacts/run-001/evidence
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as exc_info:
        _ = load_config(config_path)

    assert "interface_name" in str(exc_info.value)


def test_locked_v1_durations_are_enforced(tmp_path: Path) -> None:
    config_path = tmp_path / "locked-v1-duration.yaml"
    _ = config_path.write_text(
        """
generator:
  cameras:
    - ip_address: 192.168.10.11
      interface_name: eno1
      serial_number: CAM-001
      genicam_filename: camera-a.xml
dut:
  ifaces: [eno1]
  sample_interval_ms: 1000
  collect:
    nic: true
    stream: true
    system: true
stream:
  packet_resend: true
  socket_buffer: true
  socket_buffer_size: 1048576
  frame_retention: 200000
  initial_packet_timeout: 1000
  packet_timeout: 2000
  packet_request_ratio: 0.25
  receiver_priority: 0
scenarios:
  - name: soak
    duration: 3600
    warmup: 10
    cooldown: 5
pktgen:
  interfaces: [eno1]
  duration: 300
  packet_size: 1500
  rate_mbps: 1000
output:
  root: artifacts/run-001
  raw_dir: artifacts/run-001/raw
  reports_dir: artifacts/run-001/reports
  logs_dir: artifacts/run-001/logs
  evidence_dir: artifacts/run-001/evidence
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as exc_info:
        _ = load_config(config_path)

    error_message = str(exc_info.value)
    assert "soak" in error_message
    assert "1800" in error_message
