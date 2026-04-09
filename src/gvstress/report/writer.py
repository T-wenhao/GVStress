# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from gvstress.report.models import RunArtifact

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | dict[str, "JSONValue"] | list["JSONValue"]


def _path_to_str(path: Path | None) -> str | None:
    return str(path) if path is not None else None


def _convert_value(value: object) -> JSONValue:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return _convert_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _convert_value(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_convert_value(item) for item in value]
    return cast(JSONValue, value)


def _preflight_to_dict(preflight: object) -> dict[str, JSONValue]:
    if isinstance(preflight, dict):
        return cast(dict[str, JSONValue], _convert_value(preflight))
    if not is_dataclass(preflight) or isinstance(preflight, type):
        raise TypeError("preflight must be a dataclass or dict")
    raw = cast(dict[object, object], asdict(preflight))
    return cast(dict[str, JSONValue], _convert_value(raw))


class JSONWriter:
    def write(self, artifact: RunArtifact, output_path: Path) -> RunArtifact:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = artifact.model_dump(mode="json")
        data["preflight"] = _preflight_to_dict(artifact.preflight)
        data["samples"] = {
            key: _path_to_str(path) for key, path in artifact.samples.items()
        }

        _ = output_path.write_text(
            json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
        )
        return artifact
