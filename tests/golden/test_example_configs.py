from __future__ import annotations

from pathlib import Path

from gvstress.config import load_config
from gvstress.config.models import Config as RunConfig

EXAMPLES_DIR = Path("examples")


class TestFakecam4pConfig:
    def test_config_exists(self):
        config_file = EXAMPLES_DIR / "fakecam_4p.yaml"
        assert config_file.exists()

    def test_config_loads(self):
        config_file = EXAMPLES_DIR / "fakecam_4p.yaml"
        config = load_config(config_file)
        assert isinstance(config, RunConfig)
        assert len(config.generator.cameras) == 4
        assert config.dut.sample_interval_ms > 0

    def test_camera_ips_unique(self):
        config_file = EXAMPLES_DIR / "fakecam_4p.yaml"
        config = load_config(config_file)
        ips = [cam.ip_address for cam in config.generator.cameras]
        assert len(ips) == len(set(ips))

    def test_camera_interfaces_unique(self):
        config_file = EXAMPLES_DIR / "fakecam_4p.yaml"
        config = load_config(config_file)
        ifaces = [cam.interface_name for cam in config.generator.cameras]
        assert len(ifaces) == len(set(ifaces))

    def test_loss_ratio_valid(self):
        config_file = EXAMPLES_DIR / "fakecam_4p.yaml"
        config = load_config(config_file)
        for camera in config.generator.cameras:
            assert 0.0 <= camera.gvsp_lost_ratio <= 1.0

    def test_dut_ifaces_match_cameras(self):
        config_file = EXAMPLES_DIR / "fakecam_4p.yaml"
        config = load_config(config_file)
        camera_ifaces = {cam.interface_name for cam in config.generator.cameras}
        dut_ifaces = set(config.dut.ifaces)
        assert camera_ifaces == dut_ifaces


class TestScenarioSmokeConfig:
    def test_config_exists(self):
        config_file = EXAMPLES_DIR / "scenario_smoke.yaml"
        assert config_file.exists()

    def test_config_loads(self):
        config_file = EXAMPLES_DIR / "scenario_smoke.yaml"
        config = load_config(config_file)
        assert isinstance(config, RunConfig)
        smoke_scenarios = [s for s in config.scenarios if s.name.value == "smoke"]
        assert len(smoke_scenarios) == 1
        assert smoke_scenarios[0].duration == 60

    def test_warmup_cooldown_positive(self):
        config_file = EXAMPLES_DIR / "scenario_smoke.yaml"
        config = load_config(config_file)
        for scenario in config.scenarios:
            assert scenario.warmup >= 0
            assert scenario.cooldown >= 0

    def test_output_dirs_defined(self):
        config_file = EXAMPLES_DIR / "scenario_smoke.yaml"
        config = load_config(config_file)
        assert config.output.root
        assert config.output.raw_dir
        assert config.output.reports_dir
        assert config.output.logs_dir
        assert config.output.evidence_dir


class TestScenario4StreamConfig:
    def test_config_exists(self):
        config_file = EXAMPLES_DIR / "scenario_4stream.yaml"
        assert config_file.exists()

    def test_config_loads(self):
        config_file = EXAMPLES_DIR / "scenario_4stream.yaml"
        config = load_config(config_file)
        assert isinstance(config, RunConfig)
        four_stream_scenarios = [
            s for s in config.scenarios if s.name.value == "four_stream"
        ]
        assert len(four_stream_scenarios) == 1

    def test_duration_longer_than_smoke(self):
        smoke_file = EXAMPLES_DIR / "scenario_smoke.yaml"
        four_stream_file = EXAMPLES_DIR / "scenario_4stream.yaml"
        smoke_config = load_config(smoke_file)
        four_stream_config = load_config(four_stream_file)
        smoke_duration = smoke_config.scenarios[0].duration
        four_stream_duration = four_stream_config.scenarios[0].duration
        assert four_stream_duration > smoke_duration


class TestScenarioSoakConfig:
    def test_config_exists(self):
        config_file = EXAMPLES_DIR / "scenario_soak.yaml"
        assert config_file.exists()

    def test_config_loads(self):
        config_file = EXAMPLES_DIR / "scenario_soak.yaml"
        config = load_config(config_file)
        assert isinstance(config, RunConfig)
        soak_scenarios = [s for s in config.scenarios if s.name.value == "soak"]
        assert len(soak_scenarios) == 1
        assert soak_scenarios[0].duration == 1800

    def test_longest_duration(self):
        config_file = EXAMPLES_DIR / "scenario_soak.yaml"
        config = load_config(config_file)
        for scenario in config.scenarios:
            if scenario.name.value == "soak":
                assert scenario.duration >= 1800


def test_scenario_soak_matches_locked_v1_contract() -> None:
    config = load_config(EXAMPLES_DIR / "scenario_soak.yaml")
    soak_scenario = next(s for s in config.scenarios if s.name.value == "soak")

    assert soak_scenario.duration == 1800
    assert soak_scenario.warmup == 10
    assert soak_scenario.cooldown == 5


class TestScenarioLossConfig:
    def test_config_exists(self):
        config_file = EXAMPLES_DIR / "scenario_loss.yaml"
        assert config_file.exists()

    def test_config_loads(self):
        config_file = EXAMPLES_DIR / "scenario_loss.yaml"
        config = load_config(config_file)
        assert isinstance(config, RunConfig)
        loss_scenarios = [
            s for s in config.scenarios if s.name.value == "loss_injection"
        ]
        assert len(loss_scenarios) == 1

    def test_loss_ratio_nonzero(self):
        config_file = EXAMPLES_DIR / "scenario_loss.yaml"
        config = load_config(config_file)
        for camera in config.generator.cameras:
            assert camera.gvsp_lost_ratio > 0.0


class TestPktgen4pConfig:
    def test_config_exists(self):
        config_file = EXAMPLES_DIR / "pktgen_4p.yaml"
        assert config_file.exists()

    def test_config_loads(self):
        config_file = EXAMPLES_DIR / "pktgen_4p.yaml"
        config = load_config(config_file)
        assert isinstance(config, RunConfig)
        assert len(config.pktgen.interfaces) > 0
        assert config.pktgen.duration > 0
        assert config.pktgen.packet_size > 0
        assert config.pktgen.rate_mbps is not None
        assert config.pktgen.rate_mbps > 0

    def test_pktgen_interfaces_match_dut(self):
        config_file = EXAMPLES_DIR / "pktgen_4p.yaml"
        config = load_config(config_file)
        pktgen_ifaces = set(config.pktgen.interfaces)
        dut_ifaces = set(config.dut.ifaces)
        assert pktgen_ifaces.issubset(dut_ifaces)


class TestAllConfigs:
    def test_stream_config_valid(self):
        for config_file in EXAMPLES_DIR.glob("*.yaml"):
            config = load_config(config_file)
            assert config.stream.socket_buffer_size >= 0
            assert config.stream.frame_retention >= 0
            assert 0.0 <= config.stream.packet_request_ratio <= 2.0

    def test_camera_serials_unique(self):
        for config_file in EXAMPLES_DIR.glob("*.yaml"):
            config = load_config(config_file)
            serials = [cam.serial_number for cam in config.generator.cameras]
            assert len(serials) == len(set(serials))
