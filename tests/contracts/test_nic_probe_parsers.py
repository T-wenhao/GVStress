from __future__ import annotations

import json

from gvstress.dut.nic_probe import NICProbe


def test_ip_and_ethtool_outputs_map_to_sample_schema() -> None:
    ip_payload = {
        "ifname": "eno1",
        "stats64": {
            "rx": {
                "packets": 101,
                "bytes": 1001,
                "errors": 0,
                "dropped": 2,
                "over_errors": 3,
                "fifo_errors": 4,
                "missed_errors": 5,
            },
            "tx": {
                "packets": 201,
                "bytes": 2001,
                "errors": 0,
                "dropped": 6,
            },
        },
    }
    sysfs_payload = {"rx_packets": 999, "tx_errors": 7}
    driver_stats = """
NIC statistics:
     rx_queue_0_packets: 111
     tx_queue_0_packets: 222
     fw_rx_dropped: n/a
"""
    driver_info = "driver: igb\nversion: 5.15.0\nfirmware-version: 1.63\n"
    features = "rx-checksumming: on\ntx-checksumming: off\n"
    channels = "Combined: 4\nCurrent hardware settings: 4\n"

    standard = NICProbe.parse_standard_counters(
        ip_payload=ip_payload,
        sysfs_payload=sysfs_payload,
    )
    driver = NICProbe.parse_driver_counters(
        driver_stats,
        expected_counters=["rx_queue_0_packets", "tx_queue_0_packets", "fw_rx_dropped"],
    )

    assert standard["rx_packets"].absolute == 101
    assert standard["rx_missed_errors"].absolute == 5
    assert standard["tx_errors"].absolute == 0
    assert standard["tx_errors"].available is True
    assert standard["rx_packets"].absolute == 101

    assert driver["rx_queue_0_packets"].absolute == 111
    assert driver["tx_queue_0_packets"].absolute == 222
    assert driver["fw_rx_dropped"].absolute is None
    assert driver["fw_rx_dropped"].available is False

    assert NICProbe.parse_key_value_output(driver_info)["driver"] == "igb"
    assert NICProbe.parse_ethtool_features(features)["rx-checksumming"] is True
    assert NICProbe.parse_ethtool_features(features)["tx-checksumming"] is False
    assert NICProbe.parse_ethtool_channels(channels)["Combined"] == 4


def test_missing_driver_stats_are_marked_unavailable() -> None:
    driver = NICProbe.parse_driver_counters(
        "NIC statistics:\n     rx_packets: 10\n",
        expected_counters=["rx_packets", "tx_timeout_count"],
    )

    assert driver["rx_packets"].available is True
    assert driver["rx_packets"].absolute == 10
    assert driver["tx_timeout_count"].available is False
    assert driver["tx_timeout_count"].absolute is None


def test_standard_counter_parser_falls_back_to_sysfs_when_ip_payload_is_incomplete() -> (
    None
):
    parsed = NICProbe.parse_standard_counters(
        ip_payload={"stats64": {"rx": {}, "tx": {}}},
        sysfs_payload=json.loads('{"rx_packets": 7, "tx_errors": 2}'),
    )

    assert parsed["rx_packets"].absolute == 7
    assert parsed["tx_errors"].absolute == 2
    assert parsed["rx_bytes"].available is False
