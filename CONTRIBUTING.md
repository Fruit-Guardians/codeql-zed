# Contributing

Thanks for helping improve CodeQL for Zed.

## Before opening a pull request

Run the complete local quality gate from the repository root:

```sh
cargo fmt --check
cargo test
cargo clippy --all-targets --all-features -- -D warnings
cargo check --target wasm32-wasip2
python3 scripts/validate_extension.py
bash scripts/check-codeql-fixtures.sh
```

The fixture script skips when the CodeQL CLI is not installed. If the CLI or
query packs are in a non-standard location, set `CODEQL_BIN` or
`CODEQL_SEARCH_PATH`.

## Extension changes

After changing `extension.toml`, Rust code, or language queries, rebuild the
dev extension in Zed with `zed: rebuild dev extension`. Verify both `.ql` and
`.qll` files, including diagnostics from `fixtures/qlpack/InvalidQuery.ql`.

Keep the main extension focused on language support. The optional icon theme
under `companion/codeql-icons` is intentionally a separate dev extension.
