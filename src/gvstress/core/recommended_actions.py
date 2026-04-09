# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from gvstress.core.models import PrimaryAttribution

NIC_RECOMMENDED_ACTIONS: tuple[str, ...] = (
    "Check MTU consistency across generator and DUT interfaces.",
    "Inspect IRQ affinity and irqbalance behavior for the affected NIC.",
    "Verify MSI-X queue allocation and interrupt distribution.",
    "Review NIC offload settings for unexpected drops or errors.",
)

STREAM_RECOMMENDED_ACTIONS: tuple[str, ...] = (
    "Tune stream socket buffer sizing on the receiver.",
    "Adjust stream receiver priority for the stressed ports.",
    "Tune packet resend behavior and timeout settings.",
    "Increase frame retention to tolerate transient delivery jitter.",
)

ENVIRONMENT_RECOMMENDED_ACTIONS: tuple[str, ...] = (
    "Run preflight remediation before rerunning the scenario.",
)


def recommended_actions_for(
    attribution: PrimaryAttribution,
) -> tuple[str, ...]:
    if attribution is PrimaryAttribution.NIC:
        return NIC_RECOMMENDED_ACTIONS
    if attribution is PrimaryAttribution.STREAM:
        return STREAM_RECOMMENDED_ACTIONS
    if attribution is PrimaryAttribution.MIXED:
        return NIC_RECOMMENDED_ACTIONS + STREAM_RECOMMENDED_ACTIONS
    if attribution is PrimaryAttribution.ENVIRONMENT:
        return ENVIRONMENT_RECOMMENDED_ACTIONS
    return ()
