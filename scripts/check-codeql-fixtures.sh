#!/usr/bin/env bash
set -euo pipefail

codeql_bin="${CODEQL_BIN:-codeql}"
if ! command -v "$codeql_bin" >/dev/null 2>&1 && [[ ! -x "$codeql_bin" ]]; then
  echo "CodeQL CLI not found; skipping fixture compilation"
  exit 0
fi

query_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../fixtures/qlpack" && pwd)"
search_path_args=()
if [[ -n "${CODEQL_SEARCH_PATH:-}" ]]; then
  search_path_args+=("--search-path=${CODEQL_SEARCH_PATH}")
fi

compile_query() {
  local query="$1"
  if ((${#search_path_args[@]} > 0)); then
    "$codeql_bin" query compile "${search_path_args[@]}" "$query"
  else
    "$codeql_bin" query compile "$query"
  fi
}

pushd "$query_root" >/dev/null
compile_query ValidQuery.ql
if compile_query InvalidQuery.ql >/dev/null 2>&1; then
  echo "InvalidQuery.ql unexpectedly compiled successfully" >&2
  exit 1
fi
popd >/dev/null

echo "CodeQL fixtures: ok"
