# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from __future__ import annotations

from pathlib import Path

from gvstress.baseline.pktgen_runner import PktgenRunner
from gvstress.config.models import PktgenConfig


def test_pktgen_script_generation_and_result_parsing(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc" / "net" / "pktgen"
    proc_root.mkdir(parents=True)
    for name in ["kpktgend_0", "kpktgend_1", "eno1@0", "eno2@1", "pgctrl"]:
        (proc_root / name).write_text("", encoding="utf-8")

    runner = PktgenRunner(
        PktgenConfig(
            interfaces=["eno1", "eno2"],
            duration=300,
            packet_size=1500,
            rate="1000M",
            xmit_mode="start_xmit",
        ),
        proc_root=proc_root,
    )

    assignments, script_paths = runner.materialize_control_scripts(tmp_path / "scripts")
    assert (tmp_path / "scripts" / "kpktgend_0.pg").read_text(encoding="utf-8") == (
        "rem_device_all\nadd_device eno1@0\n"
    )
    device_script = (tmp_path / "scripts" / "eno1@0.pg").read_text(encoding="utf-8")
    assert "pkt_size 1500" in device_script
    assert "xmit_mode start_xmit" in device_script
    assert "rate 1000M" in device_script
    assert script_paths["pgctrl-start.pg"].exists()

    runner.prepare()
    assert (proc_root / "kpktgend_0").read_text(encoding="utf-8") == (
        "rem_device_all\nadd_device eno1@0\n"
    )
    runner.start()
    assert (proc_root / "pgctrl").read_text(encoding="utf-8") == "start\n"
    runner.stop()
    assert (proc_root / "pgctrl").read_text(encoding="utf-8") == "stop\n"

    sample_output = """Params:
 count 0  pkt_size 1500  xmit_mode start_xmit rate 1000M
Current:
 pkts-sofar: 100000  errors: 0
Result: OK: 15430(c15405+d25) usec, 100000 (1500byte,0frags)
6480562pps 3110Mb/sec (3110669760bps) errors: 0
"""
    for assignment in assignments:
        (proc_root / assignment.device_name).write_text(sample_output, encoding="utf-8")

    results = runner.collect_results(assignments)
    assert [result.interface for result in results] == ["eno1", "eno2"]
    assert results[0].device_name == "eno1@0"
    assert results[0].packets == 100000
    assert results[0].packet_size == 1500
    assert results[0].pps == 6480562
    assert results[0].mbps == 3110
    assert results[0].errors == 0
    assert results[0].rate == "1000M"
    assert results[0].xmit_mode == "start_xmit"
