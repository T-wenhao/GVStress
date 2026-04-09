from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gvstress.config.models import Config


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(
    loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def load_config(path: str | Path) -> Config:
    config_path = Path(path)
    raw_data = yaml.load(
        config_path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader
    )

    if raw_data is None:
        raw_data = {}

    return Config.model_validate(raw_data)
