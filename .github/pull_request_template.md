## What changed?

<!-- Describe the user-visible behavior and implementation briefly. -->

## Validation

- [ ] `cargo fmt --check`
- [ ] `cargo test`
- [ ] `cargo clippy --all-targets --all-features -- -D warnings`
- [ ] `cargo build --release --target wasm32-wasip2`
- [ ] `python3 scripts/validate_extension.py`
- [ ] `python3 scripts/codeql_smoke.py --codeql /path/to/codeql --fixtures fixtures/qlpack`
- [ ] Zed dev extension rebuilt and `.ql`/`.qll` verified

## Notes

<!-- Mention compatibility, CodeQL CLI assumptions, or follow-up work. -->
