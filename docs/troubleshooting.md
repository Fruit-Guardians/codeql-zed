# Troubleshooting

## CodeQL CLI was not found

Zed can have a different PATH from an interactive terminal. Verify the CLI in
the same environment used by Zed, or configure the absolute executable path:

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

Restart the language server after changing settings.

## The server starts and immediately exits

Check that the configured arguments are complete and use the required command:

```text
execute language-server --check-errors ON_CHANGE
```

If `binary.arguments` is configured, the extension does not add any missing
defaults.

## Imports cannot be resolved

Configure a query-pack root with `--search-path`. On macOS and Linux, separate
multiple roots with `:`. On Windows, separate them with `;`. Confirm that the
root contains the expected packs and that the project has a valid `qlpack.yml`.

## There are no diagnostics

Open `fixtures/qlpack/InvalidQuery.ql` to check the basic server connection.
For project queries, verify the qlpack, imports, and search path first. Also
inspect Zed's language-server log from `zed: open log`.

## `.qls` or `qlpack.yml` is highlighted as CodeQL

This extension only claims `.ql` and `.qll`. `.qls` and `qlpack.yml` should be
handled by YAML support. Check that the CodeQL language was not selected
manually for those files.
