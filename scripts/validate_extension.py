#!/usr/bin/env python3
"""Validate the static resources shipped by the CodeQL Zed extensions."""

from __future__ import annotations

import json
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_toml(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def require_file(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file():
        raise AssertionError(f"missing required file: {relative_path}")
    return path


def validate_svg(path: Path) -> None:
    root = ET.parse(path).getroot()
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise AssertionError(f"{path} is not an SVG document")
    if root.get("viewBox") != "0 0 64 64":
        raise AssertionError(f"{path} must use a 64x64 viewBox")


def validate_main_extension() -> None:
    manifest_path = require_file("extension.toml")
    manifest = load_toml(manifest_path)
    required = {"id", "name", "version", "schema_version", "authors", "description", "repository"}
    missing = required.difference(manifest)
    if missing:
        raise AssertionError(f"extension.toml is missing fields: {sorted(missing)}")
    if manifest["id"] != "codeql":
        raise AssertionError("the main extension id must be codeql")
    if manifest["schema_version"] != 1:
        raise AssertionError("the main extension must use schema_version = 1")
    if not manifest["repository"].startswith("https://"):
        raise AssertionError("the main extension repository must be an HTTPS URL")

    language = load_toml(require_file("languages/codeql/config.toml"))
    if language.get("name") != "CodeQL" or language.get("grammar") != "ql":
        raise AssertionError("CodeQL language metadata is inconsistent")
    if set(language.get("path_suffixes", [])) != {"ql", "qll"}:
        raise AssertionError("CodeQL must claim exactly the .ql and .qll suffixes")

    for relative_path in (
        "languages/codeql/highlights.scm",
        "languages/codeql/brackets.scm",
        "languages/codeql/indents.scm",
        "languages/codeql/outline.scm",
        "languages/codeql/textobjects.scm",
        "assets/codeql-mark.svg",
    ):
        require_file(relative_path)

    validate_svg(ROOT / "assets/codeql-mark.svg")


def validate_companion_icon_theme() -> None:
    manifest = load_toml(require_file("companion/codeql-icons/extension.toml"))
    if manifest.get("id") != "codeql-icons":
        raise AssertionError("the companion icon theme id must be codeql-icons")

    icon_theme_path = require_file("companion/codeql-icons/icon_themes/codeql.json")
    icon_theme = json.loads(icon_theme_path.read_text(encoding="utf-8"))
    if icon_theme.get("name") != "CodeQL Icons":
        raise AssertionError("unexpected companion icon theme name")
    themes = icon_theme.get("themes", [])
    if {theme.get("appearance") for theme in themes} != {"dark", "light"}:
        raise AssertionError("the companion icon theme must provide dark and light variants")
    for theme in themes:
        if theme.get("file_suffixes") != {"ql": "codeql", "qll": "codeql"}:
            raise AssertionError("the companion icon theme must map ql and qll suffixes")
        icon_path = ROOT / "companion/codeql-icons" / theme["file_icons"]["codeql"]["path"]
        if not icon_path.is_file():
            raise AssertionError(f"missing companion icon: {icon_path}")
        validate_svg(icon_path)
        if icon_path.read_bytes() != (ROOT / "assets/codeql-mark.svg").read_bytes():
            raise AssertionError("the companion icon must stay in sync with the main mark")


def main() -> int:
    validate_main_extension()
    validate_companion_icon_theme()
    print("extension resources: ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"extension resources: FAILED: {error}", file=sys.stderr)
        raise SystemExit(1) from error
