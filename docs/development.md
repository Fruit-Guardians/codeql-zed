# Development

## Prerequisites

- Rust 1.97 or newer;
- the `wasm32-wasip2` Rust target;
- Zed 1.16 or newer;
- CodeQL CLI 2.26 or newer for local language-server checks.

Install the target if necessary:

```sh
rustup target add wasm32-wasip2
```

## Checks

Run the Rust checks from the repository root:

```sh
cargo fmt --check
cargo test
cargo check --target wasm32-wasip2
```

Run the repository-level resource checks as well:

```sh
python3 scripts/validate_extension.py
bash scripts/check-codeql-fixtures.sh
```

The fixture check skips cleanly when the CodeQL CLI is not installed. When it
is available, `ValidQuery.ql` must compile and `InvalidQuery.ql` must fail with
diagnostics. Set `CODEQL_BIN` or `CODEQL_SEARCH_PATH` when the CLI or query
packs are outside the normal environment.

The fixture files under `fixtures/qlpack` are intentionally small. They are
used for grammar/outline checks and for manual CodeQL language-server tests.
The fixture pack declares the CodeQL CLI 2.26.1 JavaScript library pack so the
valid query can be compiled when that pack is installed locally.
`InvalidQuery.ql` should produce a diagnostic.

## Install as a dev extension

1. Open this repository in Zed.
2. Run `zed: install dev extension` from the command palette.
3. Select the repository root.
4. Open `fixtures/qlpack/ValidQuery.ql`.
5. Confirm that the file is recognized as CodeQL and that the CodeQL language
   server starts.

The optional `companion/codeql-icons` directory is a separate dev extension.
Install it separately and select `CodeQL Icons` from `icon theme selector:
toggle` if you want a CodeQL-specific file icon for `.ql` and `.qll` files.

To test the missing-CLI path, temporarily set `lsp.codeql.binary.path` to an
invalid path or use a worktree with no `codeql` executable on PATH. The editor
should retain Tree-sitter support and show an actionable language-server error.

## Manual LSP protocol smoke test

The CodeQL CLI speaks LSP over standard input and output. The extension starts
it with:

```sh
codeql execute language-server --check-errors ON_CHANGE
```

Do not append `--additional-packs` or `--library-path`; use `--search-path`
when a query pack root must be configured.
