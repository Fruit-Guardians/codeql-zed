#!/usr/bin/env python3
"""Validate the static resources shipped by the CodeQL Zed extension."""

from __future__ import annotations

import sys
import tomllib
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


def validate_main_extension() -> None:
    manifest_path = require_file("extension.toml")
    manifest = load_toml(manifest_path)
    package = load_toml(require_file("Cargo.toml")).get("package", {})
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
    if manifest["version"] != package.get("version"):
        raise AssertionError("extension.toml and Cargo.toml versions must match")

    language = load_toml(require_file("languages/codeql/config.toml"))
    if language.get("name") != "CodeQL" or language.get("grammar") != "ql":
        raise AssertionError("CodeQL language metadata is inconsistent")
    if set(language.get("path_suffixes", [])) != {"ql", "qll"}:
        raise AssertionError("CodeQL must claim exactly the .ql and .qll suffixes")
    servers = manifest.get("language_servers", {})
    if set(servers) != {"codeql"}:
        raise AssertionError("the main extension must register only the CodeQL language server")
    if servers.get("codeql", {}).get("languages") != ["CodeQL"]:
        raise AssertionError("CodeQL language server metadata is inconsistent")

    for relative_path in (
        "languages/codeql/highlights.scm",
        "languages/codeql/brackets.scm",
        "languages/codeql/indents.scm",
        "languages/codeql/outline.scm",
        "languages/codeql/textobjects.scm",
    ):
        require_file(relative_path)


def main() -> int:
    validate_main_extension()
    print("extension resources: ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, tomllib.TOMLDecodeError) as error:
        print(f"extension resources: FAILED: {error}", file=sys.stderr)
        raise SystemExit(1) from error
