#!/usr/bin/env python3
"""Run cross-platform CodeQL CLI, qlpack, and native LSP smoke checks."""

from __future__ import annotations

import argparse
import json
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.parse
from pathlib import Path


MINIMUM_VERSION = (2, 26, 1)


def parse_version(text: str) -> tuple[int, int, int]:
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", text)
    if not match:
        raise ValueError(f"No semantic CodeQL version found in: {text!r}")
    return tuple(int(part) for part in match.groups())


def file_uri_to_path(uri: str, windows: bool = False) -> str:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Expected a file URI, got {uri!r}")
    path = urllib.parse.unquote(parsed.path)
    if windows and re.match(r"^/[A-Za-z]:", path):
        path = path[1:]
    return path.replace("/", "\\") if windows else path


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def read_lsp_message(stream) -> dict | None:
    content_length: int | None = None
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in {b"\r\n", b"\n"}:
            break
        name, _, value = line.decode("ascii", errors="replace").partition(":")
        if name.lower() == "content-length":
            content_length = int(value.strip())
    if content_length is None:
        raise RuntimeError("LSP message has no Content-Length header")
    payload = stream.read(content_length)
    if len(payload) != content_length:
        raise RuntimeError("LSP server closed in the middle of a message")
    return json.loads(payload.decode("utf-8"))


def write_lsp_message(stream, message: dict) -> None:
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    stream.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload)
    stream.flush()


class LspClient:
    def __init__(self, command: list[str], cwd: Path):
        self.process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.messages: queue.Queue[dict | None] = queue.Queue()
        self.reader = threading.Thread(target=self._read_messages, daemon=True)
        self.reader.start()

    def _read_messages(self) -> None:
        try:
            while True:
                message = read_lsp_message(self.process.stdout)
                self.messages.put(message)
                if message is None:
                    return
        except Exception as error:  # pragma: no cover - only exercised on broken servers
            self.messages.put({"__reader_error__": str(error)})

    def send(self, message: dict) -> None:
        assert self.process.stdin is not None
        write_lsp_message(self.process.stdin, message)

    def wait_for(self, predicate, timeout: float = 20.0) -> dict:
        messages: list[dict] = []
        while True:
            try:
                message = self.messages.get(timeout=timeout)
            except queue.Empty as error:
                raise RuntimeError(f"Timed out waiting for LSP response; received {messages[-5:]}") from error
            if message is None:
                raise RuntimeError("CodeQL language server exited before responding")
            if "__reader_error__" in message:
                raise RuntimeError(message["__reader_error__"])
            messages.append(message)
            if predicate(message):
                return message

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.send({"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": None})
                self.wait_for(lambda message: message.get("id") == 2, timeout=5)
                self.send({"jsonrpc": "2.0", "method": "exit", "params": None})
            except (BrokenPipeError, RuntimeError):
                self.process.kill()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()


def smoke_lsp(codeql: Path, fixture_root: Path) -> None:
    query = fixture_root / "InvalidQuery.ql"
    client = LspClient([str(codeql), "execute", "language-server", "--check-errors", "ON_CHANGE"], fixture_root)
    try:
        root_uri = fixture_root.as_uri()
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": None,
                    "rootUri": root_uri,
                    "capabilities": {},
                    "workspaceFolders": [{"uri": root_uri, "name": fixture_root.name}],
                },
            }
        )
        client.wait_for(lambda message: message.get("id") == 1)
        client.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        client.send(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": query.as_uri(),
                        "languageId": "ql",
                        "version": 1,
                        "text": query.read_text(encoding="utf-8"),
                    }
                },
            }
        )
        diagnostics = client.wait_for(
            lambda message: message.get("method") == "textDocument/publishDiagnostics"
            and message.get("params", {}).get("uri") == query.as_uri()
            and len(message.get("params", {}).get("diagnostics", [])) >= 1
        )
        if not diagnostics["params"]["diagnostics"]:
            raise RuntimeError("InvalidQuery.ql did not produce diagnostics")
    finally:
        client.close()


def check_malformed_qlpack(codeql: Path, fixture_root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="codeql-zed-malformed-") as directory:
        root = Path(directory)
        shutil.copy2(fixture_root / "ValidQuery.ql", root / "ValidQuery.ql")
        (root / "qlpack.yml").write_text("name: [this is not valid yaml\n", encoding="utf-8")
        result = run([str(codeql), "query", "compile", str(root / "ValidQuery.ql")], root)
        if result.returncode == 0:
            raise RuntimeError("Malformed qlpack.yml unexpectedly compiled successfully")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codeql", type=Path, default=Path("codeql"))
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--require-space-path", action="store_true")
    args = parser.parse_args()
    discovered_codeql = shutil.which(str(args.codeql))
    codeql = Path(discovered_codeql or args.codeql).resolve()
    fixture_root = args.fixtures.resolve()
    if not codeql.is_file():
        raise RuntimeError(f"CodeQL executable does not exist: {codeql}")
    if args.require_space_path and " " not in str(codeql):
        raise RuntimeError(f"Smoke test requires a path containing spaces: {codeql}")

    version_result = run([str(codeql), "version"], fixture_root)
    if version_result.returncode != 0:
        raise RuntimeError(version_result.stderr or version_result.stdout)
    version = parse_version(version_result.stdout + version_result.stderr)
    if version < MINIMUM_VERSION:
        raise RuntimeError(f"CodeQL CLI {version} is older than the supported minimum {MINIMUM_VERSION}")

    valid = run([str(codeql), "query", "compile", "ValidQuery.ql"], fixture_root)
    if valid.returncode != 0:
        raise RuntimeError(f"ValidQuery.ql failed to compile:\n{valid.stdout}\n{valid.stderr}")
    invalid = run([str(codeql), "query", "compile", "InvalidQuery.ql"], fixture_root)
    if invalid.returncode == 0:
        raise RuntimeError("InvalidQuery.ql unexpectedly compiled successfully")

    check_malformed_qlpack(codeql, fixture_root)
    if file_uri_to_path("file:///C:/CodeQL%20CLI/query.ql", windows=True) != r"C:\CodeQL CLI\query.ql":
        raise RuntimeError("Windows drive URI handling is broken")
    smoke_lsp(codeql, fixture_root)
    print(f"CodeQL smoke checks passed for CLI {version[0]}.{version[1]}.{version[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
