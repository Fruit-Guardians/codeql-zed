# Contributing

Thanks for helping improve CodeQL for Zed.

## Before opening a pull request

Run the complete local quality gate from the repository root:

```sh
cargo fmt --check
cargo test
cargo clippy --all-targets --all-features -- -D warnings
cargo build --release --target wasm32-wasip2
python3 scripts/validate_extension.py
python3 scripts/codeql_smoke.py --codeql /path/to/codeql --fixtures fixtures/qlpack
```

The Python validation scripts require Python 3.11 or newer.

If the CLI or query packs are in a non-standard location, pass the explicit
CodeQL path and, when needed, the search path to the smoke script.

## Extension changes

After changing `extension.toml`, Rust code, or language queries, rebuild the
dev extension in Zed with `zed: rebuild dev extension`. Verify both `.ql` and
`.qll` files, including diagnostics from `fixtures/qlpack/InvalidQuery.ql`.
