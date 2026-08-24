# M0 validation record

This record captures the local M0 protocol check performed on 2026-08-24.

## Environment

- macOS arm64;
- Zed 1.16.1;
- Rust 1.97.1;
- CodeQL CLI 2.26.1;
- Tree-sitter QL commit `5b8ee9adaa1f2a1ea958064b61f8feb0a5a886c0`.

## Protocol smoke test

The CodeQL process was started with:

```text
codeql execute language-server --check-errors ON_CHANGE
```

The test sent `initialize`, `initialized`, `textDocument/didOpen`,
`shutdown`, and `exit` messages over stdin/stdout. Initialize and shutdown
responses were received successfully. Opening `fixtures/qlpack/InvalidQuery.ql`
produced two diagnostics.

The observed initialize capabilities were:

- completion, with `.` and `,` trigger characters;
- definition, hover, references, rename, formatting;
- document highlight, document symbols, and inlay hints;
- workspace-folder support;
- incremental text synchronization;
- CodeQL-specific error checking and location guessing extensions.

These capabilities are evidence for this local CLI version only. README text
intentionally describes LSP features as dependent on the installed CodeQL CLI.

## Zed UI check

The local development extension was installed from Zed's Extensions panel and
rebuilt after correcting the bracket and indent Tree-sitter queries. Both
`fixtures/qlpack/ValidQuery.ql` and
`fixtures/qlpack/library/Example.qll` are recognized as `CodeQL` in Zed's
status bar, and the CodeQL language server starts with the configured CLI.
