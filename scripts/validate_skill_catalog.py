#!/usr/bin/env python3
"""Validate skill frontmatter and the public README catalog."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import yaml


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
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
    _construct_unique_mapping,
)


def _load_frontmatter(skill: Path) -> dict[str, Any]:
    text = skill.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing opening frontmatter delimiter")
    try:
        frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("missing closing frontmatter delimiter") from exc
    if not body.strip():
        raise ValueError("skill body is empty")

    metadata = yaml.load(frontmatter, Loader=UniqueKeyLoader)
    if not isinstance(metadata, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    for required in ("name", "description"):
        value = metadata.get(required)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{required} must be a non-empty string")
    if "disable-model-invocation" in metadata and not isinstance(
        metadata["disable-model-invocation"],
        bool,
    ):
        raise ValueError("disable-model-invocation must be a boolean")
    return metadata


def main() -> None:
    skills = sorted(Path("skills").rglob("SKILL.md"))
    if not skills:
        raise SystemExit("No skill entrypoints found")

    names: dict[str, Path] = {}
    for skill in skills:
        try:
            metadata = _load_frontmatter(skill)
        except (ValueError, yaml.YAMLError) as exc:
            raise SystemExit(f"Invalid frontmatter in {skill}: {exc}") from exc
        name = metadata["name"].strip()
        if name in names:
            raise SystemExit(
                f"Duplicate skill name {name}: {names[name]} and {skill}"
            )
        names[name] = skill

    readme = Path("README.md").read_text(encoding="utf-8")
    catalogued_skills = [
        skill
        for skill in skills
        if skill.parts[1] not in {"deprecated", "in-progress", "personal"}
    ]
    uncatalogued = [
        str(skill) for skill in catalogued_skills if f"./{skill}" not in readme
    ]
    if uncatalogued:
        raise SystemExit(
            "Skills missing from README catalog:\n" + "\n".join(uncatalogued)
        )

    missing_links = []
    for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", readme):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = Path(target.split("#", 1)[0])
        if not path.exists():
            missing_links.append(target)
    if missing_links:
        raise SystemExit("Broken README links:\n" + "\n".join(missing_links))


if __name__ == "__main__":
    main()
