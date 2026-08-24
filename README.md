# CodeQL for Zed

[![CI](https://github.com/Fruit-Guardians/codeql-zed/actions/workflows/ci.yml/badge.svg)](https://github.com/Fruit-Guardians/codeql-zed/actions/workflows/ci.yml)
[![Zed Extension](https://img.shields.io/badge/Zed-extension-4d8cff?logo=zedindustries&logoColor=white)](https://zed.dev/docs/extensions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

CodeQL language support for [Zed](https://zed.dev/), combining Tree-sitter
syntax support with the official CodeQL CLI language server.

![CodeQL query diagnostics in Zed](assets/zed-codeql-valid-query.png)

> Status: `v0.1.1` is the current release candidate. The official
> `zed-industries/extensions` pull request has not been submitted yet.
> `plan.md` and the private `docs/` folder are local-only and are not tracked.

## Included

- `.ql` and `.qll` language detection;
- syntax highlighting, brackets, indentation, outline symbols, and Vim-mode
  text objects;
- the official CodeQL CLI language server, including diagnostics, completion,
  hover, and definition support;
- CodeQL CLI discovery through PATH;
- explicit binary paths, complete argument overrides, and environment
  overrides;
- actionable errors for missing, invalid, or non-executable CodeQL binaries.

The extension does not bundle CodeQL, create databases, run repository scans,
parse SARIF, or upload source code and results. Query execution remains the
responsibility of the CodeQL CLI and the user's existing workflow.

## Requirements

Install the CodeQL CLI separately from the [official CodeQL CLI binaries](https://github.com/github/codeql-cli-binaries).
The supported minimum is CodeQL CLI 2.26.1.

| Component | Supported baseline | Verification |
| --- | --- | --- |
| Zed | 1.16 or newer | macOS Zed 1.16.1 |
| Linux | x64, Ubuntu 22.04 runner | CI matrix |
| Windows | x64, Windows Server 2022 runner | CI matrix; real-device regression pending |
| CodeQL CLI | 2.26.1 or newer | local 2.26.1; CI 2.26.1 and 2.26.3 |
| Paths | spaces; Windows drive configuration | Rust tests, smoke tests, and README examples |

The CodeQL CLI is not redistributed by this extension and remains subject to
GitHub's own license and terms.

## Installation

Until the Gallery review is submitted, install the extension as a Zed dev
extension:

```sh
git clone https://github.com/Fruit-Guardians/codeql-zed.git
```

In Zed, run `zed: install dev extension`, select the cloned repository, then
open any `.ql` or `.qll` file. Confirm that CodeQL is available to Zed:

```sh
codeql version
```

If Zed cannot see the terminal PATH, configure the absolute executable path
under `lsp.codeql.binary.path`.

## CodeQL LSP configuration

No settings are needed when `codeql` is already on PATH. To select a specific
CLI executable, add this to Zed settings:

```json
{
  "lsp": {
    "codeql": {
      "binary": {
        "path": "/absolute/path/to/CodeQL CLI/codeql"
      }
    }
  }
}
```

When `binary.arguments` is present, it replaces the defaults. Provide the
complete command, including the language-server subcommand:

```json
{
  "lsp": {
    "codeql": {
      "binary": {
        "path": "C:/Tools/CodeQL CLI/codeql.exe",
        "arguments": [
          "execute",
          "language-server",
          "--check-errors",
          "ON_CHANGE",
          "--search-path=C:/CodeQL Packs"
        ],
        "env": {
          "CODEQL_HOME": "C:/Tools/CodeQL CLI"
        }
      }
    }
  }
}
```

The extension starts CodeQL directly with an argument array. Paths containing
spaces and Windows drive letters remain single arguments.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `codeql` not found | Run `codeql version`; set `lsp.codeql.binary.path` to an absolute path and restart the LSP. |
| CLI too old | Use CodeQL CLI 2.26.1 or newer. |
| CLI cannot start | Check executable permission, GUI PATH, and the Zed log. |
| Custom arguments fail | `binary.arguments` must begin with `execute language-server`; do not provide only flags. |
| Query errors | Run `codeql query compile path/to/query.ql` from the query-pack root. |

## Quality checks

```sh
cargo fmt --check
cargo test
cargo clippy --all-targets --all-features -- -D warnings
cargo build --release --target wasm32-wasip2
python3 scripts/validate_extension.py
python3 scripts/codeql_smoke.py --codeql /path/to/codeql --fixtures fixtures/qlpack
```

The Python validation scripts require Python 3.11 or newer.

GitHub Actions runs these checks on Linux x64 and Windows x64 against CodeQL
CLI 2.26.1 and 2.26.3.

## Release status

| Milestone | State |
| --- | --- |
| v0.1.0 | released as tag and GitHub Release |
| v0.1.1 | current release candidate; basic LSP stability work complete |
| Official Zed Gallery PR | prepared locally, not submitted |

## License and third-party notices

The extension is licensed under the MIT License. Its bundled Tree-sitter query
files are adapted from `tree-sitter-ql`, which is also MIT licensed:

- repository: <https://github.com/tree-sitter/tree-sitter-ql>
- pinned commit: `5b8ee9adaa1f2a1ea958064b61f8feb0a5a886c0`
- copyright: Sam Lanning and contributors

The CodeQL CLI is a separate GitHub distribution and is subject to its own
license and terms.
