from __future__ import annotations

from gvstress.dut.system_probe import SystemProbe


def test_proc_stat_parser_extracts_per_core_counters() -> None:
    raw = """cpu  100 0 50 500 10 2 4 0 0 0
cpu0 50 0 20 200 5 1 2 0 0 0
cpu1 50 0 30 300 5 1 2 0 0 0
intr 1
"""

    parsed = SystemProbe.parse_proc_stat(raw)

    assert parsed["cpu"]["user"] == 100
    assert parsed["cpu0"]["system"] == 20
    assert parsed["cpu1"]["idle"] == 300


def test_proc_interrupts_parser_groups_irqs_per_interface() -> None:
    raw = """           CPU0       CPU1
 24:        100         10  IR-PCI-MSI  eno1-TxRx-0
 25:          4         60  IR-PCI-MSI  eno1-TxRx-1
 26:          3          9  IR-PCI-MSI  eno2-TxRx-0
NMI:          1          1  Non-maskable interrupts
"""

    parsed = SystemProbe.parse_proc_interrupts(raw, ["eno1", "eno2"])

    assert [irq["irq"] for irq in parsed["eno1"]] == ["24", "25"]
    assert parsed["eno1"][0]["cpu_counts"] == {"CPU0": 100, "CPU1": 10}
    assert parsed["eno2"][0]["description"] == "IR-PCI-MSI eno2-TxRx-0"
