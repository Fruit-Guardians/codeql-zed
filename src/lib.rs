use std::collections::HashMap;

use zed_extension_api::{
    self as zed,
    settings::{CommandSettings, LspSettings},
    Command, LanguageServerId, Result, Worktree,
};

const LANGUAGE_SERVER_ID: &str = "codeql";
const INSTALL_URL: &str = "https://github.com/github/codeql-cli-binaries";
const DEFAULT_ARGUMENTS: &[&str] = &["execute", "language-server", "--check-errors", "ON_CHANGE"];

struct CodeqlExtension;

fn ensure_language_server_id(language_server_id: &LanguageServerId) -> Result<()> {
    if language_server_id.as_ref() == LANGUAGE_SERVER_ID {
        Ok(())
    } else {
        Err(format!(
            "Unsupported CodeQL language server id: {language_server_id}"
        ))
    }
}

fn lsp_settings(worktree: &Worktree) -> Result<zed::settings::LspSettings> {
    LspSettings::for_worktree(LANGUAGE_SERVER_ID, worktree)
        .map_err(|error| format!("Could not read lsp.codeql settings: {error}"))
}

fn configured_binary_path(
    binary: Option<&CommandSettings>,
    discovered_path: Option<String>,
) -> Result<String> {
    if let Some(path) = binary.and_then(|settings| settings.path.as_deref()) {
        if path.trim().is_empty() {
            return Err("The configured CodeQL binary path is empty. Set lsp.codeql.binary.path to an executable file.".to_string());
        }
        return Ok(path.trim().to_string());
    }

    discovered_path.ok_or_else(|| {
        format!(
            "CodeQL CLI was not found in the worktree PATH. Install it from {INSTALL_URL}, then restart Zed or set lsp.codeql.binary.path to the absolute executable path."
        )
    })
}

fn configured_arguments(binary: Option<&CommandSettings>) -> Vec<String> {
    binary
        .and_then(|settings| settings.arguments.clone())
        .unwrap_or_else(|| {
            DEFAULT_ARGUMENTS
                .iter()
                .map(|argument| (*argument).to_string())
                .collect()
        })
}

fn merge_environment(
    mut shell_environment: Vec<(String, String)>,
    overrides: Option<&HashMap<String, String>>,
) -> Vec<(String, String)> {
    if let Some(overrides) = overrides {
        let mut entries: Vec<_> = overrides.iter().collect();
        entries.sort_unstable_by_key(|(key, _)| *key);

        for (key, value) in entries {
            if let Some((_, existing_value)) = shell_environment
                .iter_mut()
                .find(|(existing_key, _)| existing_key == key)
            {
                *existing_value = value.clone();
            } else {
                shell_environment.push((key.clone(), value.clone()));
            }
        }
    }

    shell_environment
}

fn build_command(
    binary: Option<&CommandSettings>,
    executable: String,
    shell_environment: Vec<(String, String)>,
) -> Command {
    Command {
        command: executable,
        args: configured_arguments(binary),
        env: merge_environment(
            shell_environment,
            binary.and_then(|settings| settings.env.as_ref()),
        ),
    }
}

impl zed::Extension for CodeqlExtension {
    fn new() -> Self {
        Self
    }

    fn language_server_command(
        &mut self,
        language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> Result<Command> {
        ensure_language_server_id(language_server_id)?;

        let settings = lsp_settings(worktree)?;
        let binary = settings.binary.as_ref();
        let executable = configured_binary_path(binary, worktree.which("codeql"))?;

        Ok(build_command(binary, executable, worktree.shell_env()))
    }

    fn language_server_initialization_options(
        &mut self,
        language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> Result<Option<zed::serde_json::Value>> {
        ensure_language_server_id(language_server_id)?;
        let settings = lsp_settings(worktree)?;
        Ok(settings.initialization_options)
    }

    fn language_server_workspace_configuration(
        &mut self,
        language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> Result<Option<zed::serde_json::Value>> {
        ensure_language_server_id(language_server_id)?;
        let settings = lsp_settings(worktree)?;
        Ok(settings.settings)
    }
}

zed::register_extension!(CodeqlExtension);

#[cfg(test)]
mod tests {
    use super::*;

    fn settings(arguments: Option<Vec<&str>>) -> CommandSettings {
        CommandSettings {
            path: None,
            arguments: arguments
                .map(|arguments| arguments.into_iter().map(str::to_string).collect()),
            env: None,
        }
    }

    #[test]
    fn uses_the_explicit_binary_path_before_path_discovery() {
        let binary = CommandSettings {
            path: Some("/opt/CodeQL CLI/codeql".to_string()),
            arguments: None,
            env: None,
        };

        assert_eq!(
            configured_binary_path(Some(&binary), Some("/usr/local/bin/codeql".to_string()))
                .unwrap(),
            "/opt/CodeQL CLI/codeql"
        );
    }

    #[test]
    fn trims_outer_whitespace_from_an_explicit_binary_path() {
        let binary = CommandSettings {
            path: Some("  /opt/CodeQL CLI/codeql  ".to_string()),
            arguments: None,
            env: None,
        };

        assert_eq!(
            configured_binary_path(Some(&binary), None).unwrap(),
            "/opt/CodeQL CLI/codeql"
        );
    }

    #[test]
    fn reports_a_helpful_error_when_codeql_is_missing() {
        let error = configured_binary_path(None, None).unwrap_err();

        assert!(error.contains("CodeQL CLI was not found"));
        assert!(error.contains("lsp.codeql.binary.path"));
        assert!(error.contains(INSTALL_URL));
    }

    #[test]
    fn default_arguments_start_the_codeql_language_server() {
        assert_eq!(
            configured_arguments(None),
            vec!["execute", "language-server", "--check-errors", "ON_CHANGE"]
        );
    }

    #[test]
    fn explicit_arguments_replace_defaults_even_when_empty() {
        let binary = settings(Some(vec![]));

        assert!(configured_arguments(Some(&binary)).is_empty());
    }

    #[test]
    fn user_environment_overrides_shell_environment() {
        let mut overrides = HashMap::new();
        overrides.insert("CODEQL_HOME".to_string(), "/custom/codeql".to_string());
        overrides.insert("CODEQL_THREADS".to_string(), "4".to_string());

        let environment = merge_environment(
            vec![("CODEQL_HOME".to_string(), "/default/codeql".to_string())],
            Some(&overrides),
        );

        assert!(environment.contains(&("CODEQL_HOME".to_string(), "/custom/codeql".to_string())));
        assert!(environment.contains(&("CODEQL_THREADS".to_string(), "4".to_string())));
    }

    #[test]
    fn command_keeps_paths_with_spaces_as_one_program_argument() {
        let binary = CommandSettings {
            path: Some("/opt/CodeQL CLI/codeql".to_string()),
            arguments: Some(vec!["execute".to_string(), "language-server".to_string()]),
            env: None,
        };

        let command = build_command(Some(&binary), binary.path.clone().unwrap(), Vec::new());

        assert_eq!(command.command, "/opt/CodeQL CLI/codeql");
        assert_eq!(command.args, vec!["execute", "language-server"]);
    }
}
