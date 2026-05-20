"""Tests for Docker Compose configuration."""

import subprocess
from pathlib import Path

import pytest
import yaml


def test_compose_file_exists():
    """Compose file exists."""
    compose_path = Path("deploy/compose/docker-compose.single.yml")
    assert compose_path.exists()


def test_compose_config_valid():
    """Compose config validates without errors."""
    result = subprocess.run(
        ["docker", "compose", "-f", "deploy/compose/docker-compose.single.yml", "config"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Config failed: {result.stderr}"


def test_prometheus_config_exists():
    """Prometheus config exists."""
    config_path = Path("deploy/compose/prometheus.yml")
    assert config_path.exists()


def test_prometheus_config_valid():
    """Prometheus config is valid YAML."""
    config_path = Path("deploy/compose/prometheus.yml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    assert "global" in config
    assert "scrape_configs" in config


def test_prometheus_has_node_exporter_job():
    """Prometheus config includes node_exporter job."""
    config_path = Path("deploy/compose/prometheus.yml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    jobs = [job["job_name"] for job in config["scrape_configs"]]
    assert "node-exporter" in jobs


def test_prometheus_has_gvstress_job():
    """Prometheus config includes gvstress-node job."""
    config_path = Path("deploy/compose/prometheus.yml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    jobs = [job["job_name"] for job in config["scrape_configs"]]
    assert "gvstress-node" in jobs


def test_compose_has_prometheus_service():
    """Compose includes prometheus service."""
    compose_path = Path("deploy/compose/docker-compose.single.yml")
    with open(compose_path) as f:
        compose = yaml.safe_load(f)
    assert "services" in compose
    assert "prometheus" in compose["services"]


def test_compose_has_grafana_service():
    """Compose includes grafana service."""
    compose_path = Path("deploy/compose/docker-compose.single.yml")
    with open(compose_path) as f:
        compose = yaml.safe_load(f)
    assert "grafana" in compose["services"]


def test_compose_has_node_exporter_service():
    """Compose includes node-exporter service."""
    compose_path = Path("deploy/compose/docker-compose.single.yml")
    with open(compose_path) as f:
        compose = yaml.safe_load(f)
    assert "node-exporter" in compose["services"]


def test_compose_has_bridge_warning():
    """Compose file contains Docker bridge warning."""
    compose_path = Path("deploy/compose/docker-compose.single.yml")
    with open(compose_path) as f:
        content = f.read()
    assert "bridge" in content.lower()
    assert "WARNING" in content


def test_grafana_provisioning_exists():
    """Grafana provisioning directory exists."""
    provisioning_path = Path("deploy/compose/grafana/provisioning")
    assert provisioning_path.exists()


def test_grafana_datasources_config():
    """Grafana datasources config exists."""
    datasources_path = Path("deploy/compose/grafana/provisioning/datasources/datasources.yml")
    assert datasources_path.exists()


def test_grafana_dashboards_config():
    """Grafana dashboards config exists."""
    dashboards_config_path = Path("deploy/compose/grafana/provisioning/dashboards/dashboards.yml")
    assert dashboards_config_path.exists()
