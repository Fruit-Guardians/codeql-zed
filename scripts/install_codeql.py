#!/usr/bin/env python3
"""Install a pinned CodeQL CLI release for CI on Linux or Windows x64."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import stat
import urllib.request
import zipfile
from pathlib import Path


RELEASE_ROOT = "https://github.com/github/codeql-cli-binaries/releases/download"


def asset_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"}:
        raise RuntimeError(f"This CI installer only supports x64, got {machine}")
    if system == "linux":
        return "codeql-linux64.zip"
    if system == "windows":
        return "codeql-win64.zip"
    raise RuntimeError(f"This CI installer only supports Linux and Windows, got {system}")


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "codeql-zed-ci"})
    with urllib.request.urlopen(request) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)


def expected_checksum(text: str) -> str:
    match = re.search(r"\b([0-9a-fA-F]{64})\b", text)
    if not match:
        raise RuntimeError("Could not read a SHA-256 checksum from the release asset")
    return match.group(1).lower()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_binary(destination: Path) -> Path:
    name = "codeql.exe" if platform.system().lower() == "windows" else "codeql"
    candidates = [path for path in destination.rglob(name) if path.is_file()]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one {name} executable under {destination}, found {candidates}")
    binary = candidates[0]
    if platform.system().lower() != "windows":
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return binary


def fix_linux_runtime_permissions(destination: Path) -> None:
    if platform.system().lower() != "linux":
        return
    for name in ("codeql", "java"):
        for path in destination.rglob(name):
            if path.is_file():
                path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_github_path(binary: Path) -> None:
    github_path = os.environ.get("GITHUB_PATH")
    if github_path:
        with Path(github_path).open("a", encoding="utf-8") as output:
            output.write(f"{binary.parent}{os.linesep}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="CodeQL CLI version without the leading v")
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()

    asset = asset_name()
    base_url = f"{RELEASE_ROOT}/v{args.version}"
    args.destination.mkdir(parents=True, exist_ok=True)
    archive = args.destination / asset
    checksum_file = args.destination / f"{asset}.checksum.txt"
    download(f"{base_url}/{asset}", archive)
    download(f"{base_url}/{asset}.checksum.txt", checksum_file)

    actual = sha256(archive)
    expected = expected_checksum(checksum_file.read_text(encoding="utf-8"))
    if actual != expected:
        raise RuntimeError(f"Checksum mismatch for {asset}: expected {expected}, got {actual}")

    with zipfile.ZipFile(archive) as package:
        package.extractall(args.destination)
    fix_linux_runtime_permissions(args.destination)
    binary = find_binary(args.destination)
    write_github_path(binary)
    print(binary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
