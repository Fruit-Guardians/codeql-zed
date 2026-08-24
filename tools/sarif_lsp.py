#!/usr/bin/env python3
"""Small, dependency-free SARIF 2.1.0 diagnostic language server.

The server intentionally lives outside the Rust/WASM extension. CodeQL writes
SARIF, while this process owns SARIF parsing and publishes LSP diagnostics for
the source files named by the report.
"""

from __future__ import annotations

import argparse
import json
import ntpath
import os
import queue
import re
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, BinaryIO


WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")
SEVERITY = {"error": 1, "warning": 2, "note": 3, "none": 3}


def _message_text(value: Any, fallback: str = "") -> str:
    if isinstance(value, dict):
        return str(value.get("text") or value.get("markdown") or fallback)
    if value is None:
        return fallback
    return str(value)


def uri_to_path(uri: str) -> str | None:
    """Convert a file URI or a local path into a platform-neutral path."""

    if not uri:
        return None
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme and parsed.scheme != "file":
        return None
    if parsed.scheme == "file":
        path = urllib.parse.unquote(parsed.path)
        if parsed.netloc and parsed.netloc != "localhost":
            path = f"//{parsed.netloc}{path}"
        if re.match(r"^/[A-Za-z]:[\\/]", path):
            path = path[1:]
        return path.replace("/", "\\") if WINDOWS_PATH.match(path) else path
    return os.path.expanduser(uri)


def path_key(path: str) -> str:
    """Return a stable identity for POSIX, Windows-drive, and UNC paths."""

    if WINDOWS_PATH.match(path) or path.startswith(("\\\\", "//")):
        return ntpath.normcase(ntpath.normpath(path.replace("/", "\\")))
    return os.path.normcase(os.path.abspath(os.path.normpath(path)))


def path_to_uri(path: str) -> str:
    if WINDOWS_PATH.match(path):
        normalized = path.replace("\\", "/")
        return "file:///" + urllib.parse.quote(normalized, safe="/:~!$&'()*+,;=@")
    return Path(path).absolute().as_uri()


def resolve_path(value: str, base_dir: Path, uri_bases: dict[str, str]) -> str | None:
    if not value:
        return None
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme == "file":
        return uri_to_path(value)
    if parsed.scheme:
        return None
    if WINDOWS_PATH.match(value) or value.startswith(("\\\\", "/")):
        return value
    return str((base_dir / value).absolute())


def sarif_range(physical_location: dict[str, Any]) -> dict[str, Any]:
    region = physical_location.get("region") or {}
    start_line = max(int(region.get("startLine", 1)) - 1, 0)
    start_character = max(int(region.get("startColumn", 1)) - 1, 0)
    end_line = max(int(region.get("endLine", start_line + 1)) - 1, start_line)
    end_character = max(
        int(region.get("endColumn", start_character + 1)) - 1,
        start_character + (1 if end_line == start_line else 0),
    )
    return {
        "start": {"line": start_line, "character": start_character},
        "end": {"line": end_line, "character": end_character},
    }


def _location_uri(
    location: dict[str, Any],
    base_dir: Path,
    uri_bases: dict[str, str],
) -> tuple[str, dict[str, Any]] | None:
    physical = location.get("physicalLocation") or {}
    artifact = physical.get("artifactLocation") or {}
    artifact_uri = artifact.get("uri")
    if not artifact_uri:
        return None
    location_base = base_dir
    base_id = artifact.get("uriBaseId")
    if base_id and base_id in uri_bases:
        location_base = Path(uri_bases[base_id])
    path = resolve_path(str(artifact_uri), location_base, uri_bases)
    if path is None:
        return None
    return path_to_uri(path), sarif_range(physical)


def _rule_index(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    driver = ((run.get("tool") or {}).get("driver") or {})
    return {
        str(rule.get("id")): rule
        for rule in driver.get("rules", [])
        if isinstance(rule, dict) and rule.get("id")
    }


def _uri_bases(run: dict[str, Any], base_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in (run.get("originalUriBaseIds") or {}).items():
        if not isinstance(value, dict):
            continue
        uri = value.get("uri")
        if not uri:
            continue
        parent = base_dir
        parent_id = value.get("uriBaseId")
        if parent_id and parent_id in result:
            parent = Path(result[parent_id])
        path = resolve_path(str(uri), parent, result)
        if path:
            result[str(key)] = path
    return result


def _flow_locations(
    result: dict[str, Any],
    base_dir: Path,
    uri_bases: dict[str, str],
) -> list[dict[str, Any]]:
    related: list[dict[str, Any]] = []
    for code_flow in result.get("codeFlows", []) or []:
        for thread_flow in code_flow.get("threadFlows", []) or []:
            for step in thread_flow.get("locations", []) or []:
                location = step.get("location") or {}
                resolved = _location_uri(location, base_dir, uri_bases)
                if resolved is None:
                    continue
                uri, location_range = resolved
                message = _message_text(step.get("message"), _message_text(location.get("message"), "Code flow step"))
                related.append({"location": {"uri": uri, "range": location_range}, "message": message})
    return related


def diagnostics_from_sarif(
    document: dict[str, Any], source_path: Path, max_results: int = 2000
) -> dict[str, list[dict[str, Any]]]:
    """Convert SARIF results into diagnostics grouped by source-file URI."""

    diagnostics: dict[str, list[dict[str, Any]]] = {}
    base_dir = source_path.parent
    count = 0
    for run in document.get("runs", []) or []:
        if not isinstance(run, dict):
            continue
        rules = _rule_index(run)
        uri_bases = _uri_bases(run, base_dir)
        for result in run.get("results", []) or []:
            if count >= max_results:
                return diagnostics
            if not isinstance(result, dict):
                continue
            rule_id = str(result.get("ruleId") or "")
            rule = rules.get(rule_id, {})
            message = _message_text(result.get("message"), _message_text(rule.get("shortDescription"), rule_id))
            level = str(result.get("level") or "warning").lower()
            diagnostic: dict[str, Any] = {
                "severity": SEVERITY.get(level, 2),
                "source": "CodeQL",
                "message": message,
            }
            if rule_id:
                diagnostic["code"] = rule_id
            help_uri = rule.get("helpUri")
            if help_uri:
                diagnostic["codeDescription"] = {"href": str(help_uri)}
            related = _flow_locations(result, base_dir, uri_bases)
            if related:
                diagnostic["relatedInformation"] = related
            locations = result.get("locations") or []
            for location in locations:
                resolved = _location_uri(location, base_dir, uri_bases)
                if resolved is None:
                    continue
                uri, location_range = resolved
                item = dict(diagnostic)
                item["range"] = location_range
                diagnostics.setdefault(uri, []).append(item)
                count += 1
                if count >= max_results:
                    return diagnostics
    return diagnostics


class LspStream:
    def __init__(self, stdin: BinaryIO, stdout: BinaryIO):
        self.stdin = stdin
        self.stdout = stdout
        self.write_lock = threading.Lock()

    def read(self) -> dict[str, Any] | None:
        content_length: int | None = None
        while True:
            line = self.stdin.readline()
            if not line:
                return None
            if line in {b"\r\n", b"\n"}:
                break
            name, _, value = line.decode("ascii", errors="replace").partition(":")
            if name.lower() == "content-length":
                content_length = int(value.strip())
        if content_length is None:
            raise RuntimeError("LSP message has no Content-Length header")
        payload = self.stdin.read(content_length)
        if len(payload) != content_length:
            raise RuntimeError("LSP message ended before Content-Length")
        return json.loads(payload.decode("utf-8"))

    def write(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
        with self.write_lock:
            self.stdout.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
            self.stdout.write(payload)
            self.stdout.flush()


class SarifServer:
    def __init__(self, stream: LspStream, sarif_argument: str | None, max_results: int, poll_seconds: float):
        self.stream = stream
        self.sarif_argument = sarif_argument
        self.max_results = max_results
        self.poll_seconds = poll_seconds
        self.root_path: Path | None = None
        self.sarif_paths: list[Path] = []
        self.current_diagnostics: dict[str, list[dict[str, Any]]] = {}
        self.last_mtimes: dict[str, int | None] = {}
        self.stop_event = threading.Event()
        self.watcher: threading.Thread | None = None

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self.stream.write({"jsonrpc": "2.0", "method": method, "params": params})

    def _log(self, message: str, message_type: int = 3) -> None:
        self._notify("window/logMessage", {"type": message_type, "message": message})

    def _respond(self, request_id: Any, result: Any) -> None:
        self.stream.write({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _path_from_value(self, value: Any) -> Path | None:
        if not isinstance(value, str) or not value:
            return None
        path = uri_to_path(value)
        if path is None:
            return None
        return Path(path)

    def _configure_paths(self, params: dict[str, Any]) -> None:
        options = params.get("initializationOptions") or {}
        values: list[Any] = []
        if isinstance(options, dict):
            values.extend(options.get("sarifPaths") or [])
            if options.get("sarifPath"):
                values.append(options["sarifPath"])
        if self.sarif_argument:
            values.append(self.sarif_argument)
        if not values and os.environ.get("CODEQL_SARIF_OUTPUT"):
            values.append(os.environ["CODEQL_SARIF_OUTPUT"])
        if not values and self.root_path:
            values.append(str(self.root_path / ".codeql" / "results.sarif"))

        root = self.root_path or Path.cwd()
        configured: list[Path] = []
        for value in values:
            path = self._path_from_value(value)
            if path is None:
                continue
            if not path.is_absolute() and not WINDOWS_PATH.match(str(path)):
                path = root / path
            configured.append(path)
        self.sarif_paths = configured[:8]

    def _publish(self, diagnostics: dict[str, list[dict[str, Any]]]) -> None:
        for uri in sorted(set(self.current_diagnostics) | set(diagnostics)):
            self._notify(
                "textDocument/publishDiagnostics",
                {"uri": uri, "diagnostics": diagnostics.get(uri, [])},
            )
        self.current_diagnostics = diagnostics

    def _publish_file(self, path: Path) -> None:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            diagnostics: dict[str, list[dict[str, Any]]] = {}
            if isinstance(document, dict):
                diagnostics = diagnostics_from_sarif(document, path, self.max_results)
            self._publish(diagnostics)
        except FileNotFoundError:
            self._publish({})
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._log(f"CodeQL SARIF sidecar could not read {path}: {error}", 1)

    def _publish_text(self, uri: str, text: str) -> None:
        path = self._path_from_value(uri)
        if path is None:
            self._log(f"CodeQL SARIF sidecar received a non-file URI: {uri}", 2)
            return
        try:
            document = json.loads(text)
            self._publish(diagnostics_from_sarif(document, path, self.max_results))
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            self._log(f"CodeQL SARIF sidecar could not parse {uri}: {error}", 1)

    def _publish_configured_file(self) -> None:
        if self.sarif_paths:
            self._publish_file(self.sarif_paths[0])

    def _watch_files(self) -> None:
        while not self.stop_event.wait(self.poll_seconds):
            for path in self.sarif_paths:
                key = path_key(str(path))
                try:
                    mtime = path.stat().st_mtime_ns
                except FileNotFoundError:
                    mtime = None
                if key not in self.last_mtimes:
                    self.last_mtimes[key] = mtime
                    continue
                if self.last_mtimes[key] != mtime:
                    self.last_mtimes[key] = mtime
                    self._publish_file(path)

    def start_watcher(self) -> None:
        if self.watcher is None and self.sarif_paths:
            for path in self.sarif_paths:
                try:
                    mtime = path.stat().st_mtime_ns
                except FileNotFoundError:
                    mtime = None
                self.last_mtimes[path_key(str(path))] = mtime
            self.watcher = threading.Thread(target=self._watch_files, daemon=True)
            self.watcher.start()

    def handle(self, message: dict[str, Any]) -> bool:
        method = message.get("method")
        params = message.get("params") or {}
        if method == "initialize":
            root_uri = params.get("rootUri")
            if not root_uri and params.get("workspaceFolders"):
                root_uri = params["workspaceFolders"][0].get("uri")
            root = self._path_from_value(root_uri)
            self.root_path = root or Path.cwd()
            self._configure_paths(params)
            self._respond(
                message.get("id"),
                {
                    "capabilities": {
                        "textDocumentSync": {"openClose": True, "change": 1},
                        "workspace": {"workspaceFolders": {"supported": True}},
                    },
                    "serverInfo": {"name": "CodeQL SARIF Diagnostics", "version": "0.3.0"},
                },
            )
            return True
        if method == "initialized":
            self._publish_configured_file()
            self.start_watcher()
            return True
        if method == "shutdown":
            self._respond(message.get("id"), None)
            return True
        if method == "exit":
            return False
        if method == "workspace/didChangeWatchedFiles":
            self._publish_configured_file()
            return True
        if method == "workspace/didChangeConfiguration":
            self._configure_paths(params)
            self._publish_configured_file()
            return True
        if method in {"textDocument/didOpen", "textDocument/didChange"}:
            document = params.get("textDocument") or {}
            uri = document.get("uri")
            text = document.get("text")
            if method.endswith("didChange"):
                changes = params.get("contentChanges") or []
                text = changes[-1].get("text") if changes else text
            if uri and isinstance(text, str) and str(uri).lower().endswith((".sarif", ".sarif.json")):
                self._publish_text(str(uri), text)
            else:
                self._publish_configured_file()
            return True
        if method == "textDocument/didClose":
            uri = (params.get("textDocument") or {}).get("uri")
            if uri and str(uri).lower().endswith((".sarif", ".sarif.json")):
                self._publish({})
            return True
        return True

    def run(self) -> int:
        try:
            while not self.stop_event.is_set():
                message = self.stream.read()
                if message is None or not self.handle(message):
                    break
        finally:
            self.stop_event.set()
            if self.watcher:
                self.watcher.join(timeout=1)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdio", action="store_true", help="use LSP over stdin/stdout")
    parser.add_argument("--sarif", help="SARIF file to watch; defaults to .codeql/results.sarif")
    parser.add_argument("--max-results", type=int, default=2000)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    args = parser.parse_args()
    if not args.stdio:
        parser.error("the SARIF sidecar currently supports only --stdio")
    return SarifServer(
        LspStream(sys.stdin.buffer, sys.stdout.buffer),
        args.sarif,
        max(1, args.max_results),
        max(0.1, args.poll_seconds),
    ).run()


if __name__ == "__main__":
    raise SystemExit(main())
