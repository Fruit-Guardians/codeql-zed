# Configuration

## Use CodeQL from PATH

If the CodeQL executable is visible to the worktree environment, no Zed
setting is needed. The extension asks Zed to resolve `codeql` with
`Worktree::which`.

## Use an explicit executable

```json
{
  "lsp": {
    "codeql": {
      "binary": {
        "path": "/Applications/CodeQL/codeql"
      }
    }
  }
}
```

An explicit path takes precedence over PATH discovery. Paths containing spaces
are passed as a single executable path.

## Configure arguments

The default arguments are:

```text
execute language-server --check-errors ON_CHANGE
```

To add a search path, configure the full argument list:

```json
{
  "lsp": {
    "codeql": {
      "binary": {
        "arguments": [
          "execute",
          "language-server",
          "--check-errors",
          "ON_CHANGE",
          "--search-path=/workspace/qlpacks"
        ]
      }
    }
  }
}
```

Multiple search paths use `:` on Unix-like systems and `;` on Windows. Keep
the list to one root until a cross-platform setup has been tested.

## Configure the environment

Values in `binary.env` override the corresponding variables from Zed's
worktree shell environment:

```json
{
  "lsp": {
    "codeql": {
      "binary": {
        "env": {
          "CODEQL_HOME": "/opt/codeql"
        }
      }
    }
  }
}
```

The extension does not read `std::env` and does not log the environment.
