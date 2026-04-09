# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false

from __future__ import annotations

from gvstress.core.models import PrimaryAttribution
from gvstress.core.recommended_actions import (
    ENVIRONMENT_RECOMMENDED_ACTIONS,
    NIC_RECOMMENDED_ACTIONS,
    STREAM_RECOMMENDED_ACTIONS,
    recommended_actions_for,
)


def test_recommended_actions_match_single_domain() -> None:
    assert recommended_actions_for(PrimaryAttribution.NIC) == NIC_RECOMMENDED_ACTIONS
    assert (
        recommended_actions_for(PrimaryAttribution.STREAM) == STREAM_RECOMMENDED_ACTIONS
    )
    assert (
        recommended_actions_for(PrimaryAttribution.ENVIRONMENT)
        == ENVIRONMENT_RECOMMENDED_ACTIONS
    )


def test_recommended_actions_for_mixed_are_deterministic() -> None:
    assert recommended_actions_for(PrimaryAttribution.MIXED) == (
        NIC_RECOMMENDED_ACTIONS + STREAM_RECOMMENDED_ACTIONS
    )


def test_recommended_actions_for_unknown_are_empty() -> None:
    assert recommended_actions_for(PrimaryAttribution.UNKNOWN) == ()
