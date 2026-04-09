from __future__ import annotations

import json
from pathlib import Path

from gvstress.core.models import SecondaryAttribution
from gvstress.report.writer import JSONWriter
from tests.fixtures.reports.helpers import FixtureBuilder


def test_run_artifact_includes_secondary_attribution(tmp_path: Path) -> None:
    builder = FixtureBuilder(tmp_path)
    artifact = builder.build_run_artifact(
        secondary_attribution=SecondaryAttribution.STREAM_CONFIGURATION
    )

    assert artifact.secondary_attribution is SecondaryAttribution.STREAM_CONFIGURATION

    output_path = tmp_path / "run.json"
    JSONWriter().write(artifact, output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["secondary_attribution"] == "stream_configuration"
