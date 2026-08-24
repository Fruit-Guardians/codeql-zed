# Changelog

## 0.1.0

- Add CodeQL and QL Tree-sitter language support for `.ql` and `.qll` files.
- Start the CodeQL CLI language server from Zed's LSP integration.
- Support PATH discovery, an explicit binary path, complete argument overrides, and environment overrides.

## 0.1.1 (implemented on main)

- Add Linux and Windows CI coverage with pinned CodeQL CLI versions.
- Add qlpack, old-CLI, malformed-query, path, and native LSP smoke checks.
- Improve missing-binary and invalid-argument errors.

## 0.2.0 (implemented on main)

- Add CodeQL compile/analyze tasks and query runnables.
- Save analysis output as SARIF with configurable database, query suite, search path, threads, RAM, and output path.

## 0.3.0 (prototype on main)

- Add an independent SARIF 2.1.0 LSP sidecar with diagnostics replacement and stale-result cleanup.
- Map rule IDs, severity, help links, Windows/relative paths, and code-flow related information.
- Keep SARIF parsing outside the Rust/WASM extension.
- Keep sidecar registration out of the base extension until a separate companion packaging path passes Zed review.

The official `zed-industries/extensions` pull request is intentionally not
submitted yet.
