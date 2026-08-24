from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

from sarif_lsp import diagnostics_from_sarif, path_to_uri, uri_to_path  # noqa: E402
from codeql_smoke import LspClient  # noqa: E402


def write_message(stream, message: dict) -> None:
    payload = json.dumps(message, separators=(",", ":")).encode()
    stream.write(f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload)
    stream.flush()


def read_message(stream, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    content_length = None
    while time.monotonic() < deadline:
        line = stream.readline()
        if not line:
            raise AssertionError("SARIF sidecar closed before replying")
        if line in {b"\r\n", b"\n"}:
            break
        if line.lower().startswith(b"content-length:"):
            content_length = int(line.split(b":", 1)[1].strip())
    if content_length is None:
        raise AssertionError("SARIF sidecar response has no Content-Length")
    return json.loads(stream.read(content_length))


class SarifDiagnosticsTests(unittest.TestCase):
    def test_windows_drive_uri_round_trip(self) -> None:
        uri = path_to_uri(r"C:\CodeQL CLI\src\query.ql")
        self.assertEqual(uri, "file:///C:/CodeQL%20CLI/src/query.ql")
        self.assertEqual(uri_to_path(uri), r"C:\CodeQL CLI\src\query.ql")

    def test_maps_level_rule_help_and_code_flow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            query = root / "query.ql"
            sarif_path = root / "results.sarif"
            document = {
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {
                            "driver": {
                                "rules": [
                                    {
                                        "id": "ql/test",
                                        "helpUri": "https://example.test/rule",
                                        "shortDescription": {"text": "Test rule"},
                                    }
                                ]
                            }
                        },
                        "results": [
                            {
                                "ruleId": "ql/test",
                                "level": "error",
                                "message": {"text": "A finding"},
                                "locations": [
                                    {
                                        "physicalLocation": {
                                            "artifactLocation": {"uri": "query.ql"},
                                            "region": {"startLine": 2, "startColumn": 3, "endLine": 2, "endColumn": 8},
                                        }
                                    }
                                ],
                                "codeFlows": [
                                    {
                                        "threadFlows": [
                                            {
                                                "locations": [
                                                    {
                                                        "location": {
                                                            "physicalLocation": {
                                                                "artifactLocation": {"uri": "query.ql"},
                                                                "region": {"startLine": 3, "startColumn": 1},
                                                            }
                                                        },
                                                        "message": {"text": "Source"},
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
            diagnostics = diagnostics_from_sarif(document, sarif_path)
            items = diagnostics[path_to_uri(str(query))]
            self.assertEqual(items[0]["severity"], 1)
            self.assertEqual(items[0]["code"], "ql/test")
            self.assertEqual(items[0]["codeDescription"]["href"], "https://example.test/rule")
            self.assertEqual(items[0]["relatedInformation"][0]["message"], "Source")
            self.assertEqual(items[0]["range"]["start"], {"line": 1, "character": 2})

    def test_stdio_server_clears_stale_diagnostics(self) -> None:
        if os.name == "nt":
            self.skipTest("Windows hosted-runner stdio pipe cleanup is not stable; URI and mapping checks still run")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            query = root / "query.ql"
            sarif_path = root / "results.sarif"

            def write_results(results: list[dict]) -> None:
                sarif_path.write_text(
                    json.dumps(
                        {
                            "version": "2.1.0",
                            "runs": [
                                {
                                    "tool": {"driver": {"rules": [{"id": "ql/test"}]}},
                                    "results": results,
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )

            write_results(
                [
                    {
                        "ruleId": "ql/test",
                        "locations": [
                            {"physicalLocation": {"artifactLocation": {"uri": "query.ql"}}}
                        ],
                    }
                ]
            )
            process = subprocess.Popen(
                [sys.executable, str(ROOT / "tools" / "sarif_lsp.py"), "--stdio", "--sarif", str(sarif_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert process.stdin is not None
            assert process.stdout is not None
            try:
                root_uri = root.as_uri()
                write_message(
                    process.stdin,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"rootUri": root_uri, "capabilities": {}},
                    },
                )
                self.assertEqual(read_message(process.stdout)["id"], 1)
                write_message(process.stdin, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
                first = read_message(process.stdout)
                while first.get("method") != "textDocument/publishDiagnostics":
                    first = read_message(process.stdout)
                self.assertEqual(len(first["params"]["diagnostics"]), 1)

                write_results([])
                os.utime(sarif_path, None)
                cleared = read_message(process.stdout, timeout=8.0)
                while cleared.get("method") != "textDocument/publishDiagnostics":
                    cleared = read_message(process.stdout, timeout=8.0)
                self.assertEqual(cleared["params"]["diagnostics"], [])
                write_message(process.stdin, {"jsonrpc": "2.0", "method": "exit", "params": None})
            finally:
                process.stdin.close()
                process.stdout.close()
                process.stderr.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

    def test_codeql_and_sarif_can_publish_for_the_same_uri(self) -> None:
        if os.name == "nt":
            self.skipTest("Windows native CodeQL child shutdown is covered by codeql_smoke.py")
        codeql = shutil.which("codeql")
        if codeql is None:
            self.skipTest("CodeQL CLI is not on PATH")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            query = root / "InvalidQuery.ql"
            query.write_text((ROOT / "fixtures/qlpack/InvalidQuery.ql").read_text(encoding="utf-8"), encoding="utf-8")
            (root / "qlpack.yml").write_text(
                (ROOT / "fixtures/qlpack/qlpack.yml").read_text(encoding="utf-8"), encoding="utf-8"
            )
            sarif_path = root / "results.sarif"
            sarif_path.write_text(
                json.dumps(
                    {
                        "version": "2.1.0",
                        "runs": [
                            {
                                "tool": {"driver": {"rules": [{"id": "ql/test"}]}},
                                "results": [
                                    {
                                        "ruleId": "ql/test",
                                        "locations": [
                                            {
                                                "physicalLocation": {
                                                    "artifactLocation": {"uri": query.name},
                                                    "region": {"startLine": 1},
                                                }
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            codeql_client = LspClient(
                [codeql, "execute", "language-server", "--check-errors", "ON_CHANGE"], root
            )
            sarif_client = LspClient(
                [sys.executable, str(ROOT / "tools" / "sarif_lsp.py"), "--stdio", "--sarif", str(sarif_path)],
                root,
            )
            try:
                root_uri = root.as_uri()
                initialize = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "rootUri": root_uri,
                        "capabilities": {},
                        "workspaceFolders": [{"uri": root_uri, "name": root.name}],
                    },
                }
                codeql_client.send(initialize)
                sarif_client.send(initialize)
                codeql_client.wait_for(lambda message: message.get("id") == 1)
                sarif_client.wait_for(lambda message: message.get("id") == 1)
                codeql_client.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
                sarif_client.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
                sarif_diagnostics = sarif_client.wait_for(
                    lambda message: message.get("method") == "textDocument/publishDiagnostics"
                    and message.get("params", {}).get("uri") == query.as_uri()
                )
                codeql_client.send(
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
                codeql_diagnostics = codeql_client.wait_for(
                    lambda message: message.get("method") == "textDocument/publishDiagnostics"
                    and message.get("params", {}).get("uri") == query.as_uri()
                    and message.get("params", {}).get("diagnostics")
                )
                self.assertEqual(sarif_diagnostics["params"]["uri"], codeql_diagnostics["params"]["uri"])
                self.assertTrue(sarif_diagnostics["params"]["diagnostics"])
                self.assertTrue(codeql_diagnostics["params"]["diagnostics"])
            finally:
                codeql_client.close()
                sarif_client.close()


if __name__ == "__main__":
    unittest.main()
