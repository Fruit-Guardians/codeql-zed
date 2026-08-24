# CodeQL for Zed

[![CI](https://github.com/Fruit-Guardians/codeql-zed/actions/workflows/ci.yml/badge.svg)](https://github.com/Fruit-Guardians/codeql-zed/actions/workflows/ci.yml)
[![Zed Extension](https://img.shields.io/badge/Zed-extension-4d8cff?logo=zedindustries&logoColor=white)](https://zed.dev/docs/extensions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

CodeQL language support for [Zed](https://zed.dev/). The extension combines
Tree-sitter QL syntax support with the CodeQL CLI's native language server.

![CodeQL-inspired extension mark](assets/codeql-mark.svg)

## Scope

Version 0.1.0 supports:

- `.ql` and `.qll` language detection;
- syntax highlighting, brackets, indentation, and outline symbols;
- diagnostics and other LSP features provided by the installed CodeQL CLI;
- CodeQL binary discovery from the worktree PATH;
- explicit binary paths, complete argument overrides, and environment overrides.
- Vim-mode text objects for query, class, and predicate declarations.

The extension does not download CodeQL, create databases, run scans, parse
SARIF, or upload source code and results. Tasks, SARIF-to-Problems integration,
and MCP are planned as separate follow-up components.

## Requirements

- Zed 1.16 or newer;
- CodeQL CLI installed separately and available to the worktree environment.

Install the CodeQL CLI using the [official CodeQL CLI binaries](https://github.com/github/codeql-cli-binaries)
documentation. Review GitHub's CodeQL terms and licensing requirements for
your use case. This extension does not bundle or redistribute the CLI.

## Installation

For development, use Zed's `Install Dev Extension` command and select this
repository.

After installation, open a `.ql` file. If `codeql` is on the worktree PATH,
the language server starts automatically.

### Optional CodeQL file icons

Zed obtains file icons from the active icon theme rather than from a language
extension's `config.toml`. This repository includes an optional companion icon
theme at `companion/codeql-icons`. Install that directory as a separate dev
extension and select `CodeQL Icons` from Zed's icon theme selector to show the
CodeQL-inspired mark for `.ql` and `.qll` files. The mark is an original design,
not an official GitHub or CodeQL logo.

## Configuration

No settings are needed when `codeql` is already on PATH. To select a specific
CLI executable, add this to Zed settings:

```json
{
  "lsp": {
    "codeql": {
      "binary": {
        "path": "/absolute/path/to/codeql"
      }
    }
  }
}
```

When `binary.arguments` is present, it replaces the defaults. Provide the
complete command, including `execute language-server --check-errors`:

```json
{
  "lsp": {
    "codeql": {
      "binary": {
        "path": "/absolute/path/to/codeql",
        "arguments": [
          "execute",
          "language-server",
          "--check-errors",
          "ON_CHANGE",
          "--search-path=/absolute/path/to/qlpacks"
        ],
        "env": {
          "CODEQL_HOME": "/absolute/path/to/codeql-home"
        }
      }
    }
  }
}
```

The extension starts the CLI directly with an argument array. It does not run
a shell command, and it uses Zed's worktree shell environment as the base
environment before applying the configured overrides.

## Limitations

- CodeQL CLI installation and query-pack configuration are user responsibilities.
- The GUI application PATH may differ from the PATH in a terminal. Use
  `lsp.codeql.binary.path` when discovery fails.
- A custom argument list is not merged with defaults; it must be complete.
- `.qls` files and `qlpack.yml` remain YAML files and are not claimed by this
  extension.
- The exact completion, hover, definition, references, rename, formatting,
  and inlay-hint support depends on the installed CodeQL CLI language-server
  capabilities.

## Development

See [docs/development.md](docs/development.md) for build, fixture, and quality
check commands.
See [docs/troubleshooting.md](docs/troubleshooting.md) when the language
server does not start.

## License and third-party notices

The extension is licensed under the MIT License. Its bundled Tree-sitter query
files are adapted from `tree-sitter-ql`, which is also MIT licensed:

- repository: <https://github.com/tree-sitter/tree-sitter-ql>
- pinned commit: `5b8ee9adaa1f2a1ea958064b61f8feb0a5a886c0`
- copyright: Sam Lanning and contributors

The CodeQL CLI is a separate GitHub distribution and is subject to its own
license and terms.
