use std::collections::HashMap;
use std::path::Path;

use zed_extension_api::{
    self as zed,
    settings::{CommandSettings, LspSettings},
    Command, LanguageServerId, Result, Worktree,
};

const CODEQL_LANGUAGE_SERVER_ID: &str = "codeql";
const INSTALL_URL: &str = "https://github.com/github/codeql-cli-binaries";
const CODEQL_DEFAULT_ARGUMENTS: &[&str] =
    &["execute", "language-server", "--check-errors", "ON_CHANGE"];

struct CodeqlExtension;

fn settings_key(language_server_id: &LanguageServerId) -> Result<&'static str> {
    match language_server_id.as_ref() {
        CODEQL_LANGUAGE_SERVER_ID => Ok(CODEQL_LANGUAGE_SERVER_ID),
        _ => Err(format!(
            "Unsupported CodeQL language server id: {language_server_id}"
        )),
    }
}

fn lsp_settings(
    language_server_id: &LanguageServerId,
    worktree: &Worktree,
) -> Result<zed::settings::LspSettings> {
    let key = settings_key(language_server_id)?;
    LspSettings::for_worktree(key, worktree)
        .map_err(|error| format!("Could not read lsp.{key} settings: {error}"))
}

fn is_executable_file(path: &Path) -> bool {
    if !path.is_file() {
        return false;
    }

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;

        path.metadata()
            .map(|metadata| metadata.permissions().mode() & 0o111 != 0)
            .unwrap_or(false)
    }

    #[cfg(not(unix))]
    {
        true
    }
}

fn configured_binary_path(
    binary: Option<&CommandSettings>,
    discovered_path: Option<String>,
) -> Result<String> {
    if let Some(path) = binary.and_then(|settings| settings.path.as_deref()) {
        if path.trim().is_empty() {
            return Err(
                "The configured CodeQL binary path is empty. Set lsp.codeql.binary.path to an executable file."
                    .to_string(),
            );
        }
        let path = path.trim();
        if !is_executable_file(Path::new(path)) {
            return Err(format!(
                "The configured CodeQL binary path does not exist or is not executable: {path}"
            ));
        }
        return Ok(path.to_string());
    }

    discovered_path.ok_or_else(|| format!(
        "CodeQL CLI was not found in the worktree PATH. Install it from {INSTALL_URL}, then restart Zed or set lsp.codeql.binary.path to the absolute executable path."
    ))
}

fn configured_arguments(binary: Option<&CommandSettings>) -> Result<Vec<String>> {
    let arguments = binary
        .and_then(|settings| settings.arguments.clone())
        .unwrap_or_else(|| {
            CODEQL_DEFAULT_ARGUMENTS
                .iter()
                .map(|argument| (*argument).to_string())
                .collect()
        });

    if arguments.len() < 2 || arguments[0] != "execute" || arguments[1] != "language-server" {
        return Err("lsp.codeql.binary.arguments must start with `execute language-server`; include the complete CodeQL language-server command.".to_string());
    }

    Ok(arguments)
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
) -> Result<Command> {
    Ok(Command {
        command: executable,
        args: configured_arguments(binary)?,
        env: merge_environment(
            shell_environment,
            binary.and_then(|settings| settings.env.as_ref()),
        ),
    })
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
        let settings = lsp_settings(language_server_id, worktree)?;
        let binary = settings.binary.as_ref();
        let executable = configured_binary_path(binary, worktree.which("codeql"))?;

        build_command(binary, executable, worktree.shell_env())
    }

    fn language_server_initialization_options(
        &mut self,
        language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> Result<Option<zed::serde_json::Value>> {
        let settings = lsp_settings(language_server_id, worktree)?;
        Ok(settings.initialization_options)
    }

    fn language_server_workspace_configuration(
        &mut self,
        language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> Result<Option<zed::serde_json::Value>> {
        let settings = lsp_settings(language_server_id, worktree)?;
        Ok(settings.settings)
    }
}

zed::register_extension!(CodeqlExtension);

#[cfg(test)]
mod tests {
    use super::*;

    fn write_executable(path: &Path) {
        std::fs::write(path, b"placeholder").unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;

            let mut permissions = std::fs::metadata(path).unwrap().permissions();
            permissions.set_mode(0o755);
            std::fs::set_permissions(path, permissions).unwrap();
        }
    }

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
        let directory = std::env::temp_dir().join(format!("CodeQL CLI {}", line!()));
        std::fs::create_dir_all(&directory).unwrap();
        let path = directory.join("codeql");
        write_executable(&path);
        let binary = CommandSettings {
            path: Some(path.to_string_lossy().to_string()),
            arguments: None,
            env: None,
        };

        assert_eq!(
            configured_binary_path(Some(&binary), Some("/usr/local/bin/codeql".to_string()),)
                .unwrap(),
            path.to_string_lossy()
        );
        let _ = std::fs::remove_file(path);
        let _ = std::fs::remove_dir(directory);
    }

    #[test]
    fn trims_outer_whitespace_from_an_explicit_binary_path() {
        let directory = std::env::temp_dir().join(format!("CodeQL CLI {}", line!()));
        std::fs::create_dir_all(&directory).unwrap();
        let path = directory.join("codeql");
        write_executable(&path);
        let binary = CommandSettings {
            path: Some(format!("  {}  ", path.to_string_lossy())),
            arguments: None,
            env: None,
        };

        assert_eq!(
            configured_binary_path(Some(&binary), None).unwrap(),
            path.to_string_lossy()
        );
        let _ = std::fs::remove_file(path);
        let _ = std::fs::remove_dir(directory);
    }

    #[test]
    fn reports_a_helpful_error_when_configured_path_is_missing() {
        let binary = CommandSettings {
            path: Some("/definitely/missing/CodeQL CLI/codeql".to_string()),
            arguments: None,
            env: None,
        };

        let error = configured_binary_path(Some(&binary), None).unwrap_err();

        assert!(error.contains("does not exist"));
        assert!(error.contains("CodeQL CLI"));
    }

    #[cfg(unix)]
    #[test]
    fn rejects_a_configured_non_executable_file() {
        let directory = std::env::temp_dir().join(format!("CodeQL CLI {}", line!()));
        std::fs::create_dir_all(&directory).unwrap();
        let path = directory.join("codeql");
        std::fs::write(&path, b"placeholder").unwrap();
        let binary = CommandSettings {
            path: Some(path.to_string_lossy().to_string()),
            arguments: None,
            env: None,
        };

        let error = configured_binary_path(Some(&binary), None).unwrap_err();

        assert!(error.contains("not executable"));
        let _ = std::fs::remove_file(path);
        let _ = std::fs::remove_dir(directory);
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
            configured_arguments(None).unwrap(),
            vec!["execute", "language-server", "--check-errors", "ON_CHANGE"]
        );
    }

    #[test]
    fn rejects_empty_custom_arguments() {
        let binary = settings(Some(vec![]));

        let error = configured_arguments(Some(&binary)).unwrap_err();

        assert!(error.contains("binary.arguments"));
    }

    #[test]
    fn rejects_custom_arguments_without_the_language_server_command() {
        let binary = settings(Some(vec!["execute", "query", "compile"]));

        let error = configured_arguments(Some(&binary)).unwrap_err();

        assert!(error.contains("execute language-server"));
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
            path: Some("/definitely/missing/CodeQL CLI/codeql".to_string()),
            arguments: Some(vec!["execute".to_string(), "language-server".to_string()]),
            env: None,
        };

        let command =
            build_command(Some(&binary), binary.path.clone().unwrap(), Vec::new()).unwrap();

        assert_eq!(command.command, "/definitely/missing/CodeQL CLI/codeql");
        assert_eq!(command.args, vec!["execute", "language-server"]);
    }
}
