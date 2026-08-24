# CodeQL for Zed 最终开发计划

| 项目 | 内容 |
| --- | --- |
| 版本 | v1.0 |
| 日期 | 2026-08-24 |
| 状态 | 可进入开发 |
| 首发目标 | Zed 扩展 `codeql` v0.1.0 |
| 首发周期 | 单人 7–10 个开发日；完整路线预计 5–8 周 |

## 1. 最终结论

项目可以立项，但必须按 Zed 当前公开扩展 API 拆成三个边界清晰的产品，而不是把语言支持、扫描 UI、SARIF diagnostics 和 MCP 全塞进一个扩展：

1. **CodeQL Zed Language Extension（首发、必须完成）**
   - 识别 `.ql`、`.qll`；
   - Tree-sitter 高亮、括号、缩进、Outline；
   - 启动用户本机的 `codeql execute language-server`；
   - 提供 diagnostics、completion、hover、definition 等原生 LSP 能力；
   - 通过 Zed 官方扩展仓库发布，扩展 ID 为 `codeql`。

2. **CodeQL Tasks / SARIF Bridge（后续、分两步）**
   - 先用语言扩展可提供的静态 Tasks 运行当前查询并生成 SARIF；
   - 如果必须把 SARIF 显示到 Problems 面板，再开发独立的 `codeql-sarif-lsp`，由它通过标准 LSP `publishDiagnostics` 发布结果；
   - 不把“扩展 WASM 主动推送任意 diagnostics”作为可用 API 假设。

3. **CodeQL MCP Server（后续、独立发布）**
   - 独立进程、独立包、独立版本；
   - 首先支持 Zed 的本地 Custom Server 配置；
   - 再发布到官方 MCP Registry；
   - 不和 `codeql` 语言扩展混装，也不把 Zed MCP Extension 作为长期分发主线。

首个可交付版本必须严格收敛为：

> Tree-sitter QL + CodeQL 原生 language server + 本地 CLI 配置 + 英文安装/排错文档。

## 2. 官方文档核对结果

以下结论以 2026-08-24 可见的官方文档和当前 Zed 扩展仓库为基准。

| 决策点 | 官方能力/限制 | 对本项目的决定 |
|---|---|---|
| 扩展形态 | Zed 扩展是含 `extension.toml` 的 Git 仓库 | 首版建立独立 `codeql` 扩展仓库 |
| Rust 运行时 | 程序部分编译为 `wasm32-wasip2` | Rust 代码只负责解析 Zed 设置、查找 CLI、返回 LSP 启动命令 |
| Grammar | 每个语言都需在 manifest 注册 Tree-sitter grammar，并固定 Git commit | 固定 `tree-sitter-ql` commit，不跟随分支浮动 |
| Language | 语言目录包含 `config.toml` 和 `.scm` queries | `.ql/.qll` 使用 `CodeQL` 语言；`.qls/qlpack.yml` 不冒充 QL |
| LSP | manifest 注册 language server；Rust 实现 `language_server_command` | 直接启动本机 `codeql execute language-server --check-errors ON_CHANGE` |
| 设置 | 扩展 API 可读取 `LspSettings` 的 `binary/settings/initialization_options` | 用户配置统一放在 `lsp.codeql`，删除未经 Zed 注册的顶层 `codeql` 设置设计 |
| 外部进程 | 任意 `process::Command` 受 capability 控制；`Extension` trait 没有通用命令或任意事件钩子 | v0.1 不运行扫描命令，不申请不必要的 `process:exec` |
| Diagnostics | 当前 `Extension` trait 没有直接发布任意 Problems diagnostics 的方法 | SARIF → Problems 只能通过独立 LSP 等受支持通道实现 |
| Tasks | Zed 支持语言扩展提供静态 task templates | v0.2 可添加当前查询的 Run/Analyze task；动态数据库列表仍不在扩展 API 内 |
| MCP | Zed 支持 MCP Tools/Prompts 和本地/远程 Custom Server | MCP 做独立 server，用户可直接在 Zed Settings 中添加 |
| MCP 发布 | Zed MCP Server Extension 计划弃用；发布规则要求一个扩展只能包含一个 MCP Server 且不能混合其他功能 | 不把 MCP 注册到 `codeql` 语言扩展，优先官方 MCP Registry |
| 发布审核 | ID 唯一、kebab-case，不能含 `zed`/`extension`；用户可见文本必须为英文 | ID 使用 `codeql`；README、错误文本、description 全部英文 |

关键依据：

- [Developing Extensions](https://zed.dev/docs/extensions/developing-extensions)
- [Language Extensions](https://zed.dev/docs/extensions/languages)
- [Extension Capabilities](https://zed.dev/docs/extensions/capabilities)
- [Zed Extension API](https://docs.rs/zed_extension_api/latest/zed_extension_api/)
- [MCP Server Extensions](https://zed.dev/docs/extensions/mcp-extensions)
- [Model Context Protocol in Zed](https://zed.dev/docs/ai/mcp)
- [Tasks](https://zed.dev/docs/tasks)
- [Publishing Prerequisites](https://zed.dev/docs/extensions/publishing/prerequisites)
- [Publishing Guide](https://zed.dev/docs/extensions/publishing/publishing-guide)
- [CodeQL execute language-server](https://docs.github.com/en/code-security/reference/code-scanning/codeql/codeql-cli-manual/execute-language-server)
- [CodeQL database analyze](https://docs.github.com/en/code-security/reference/code-scanning/codeql/codeql-cli-manual/database-analyze)

补充核对：当前 [`zed-industries/extensions`](https://github.com/zed-industries/extensions) 的 `extensions.toml` 和 `.gitmodules` 中仍无 `codeql` 条目，因此扩展 ID 当前不存在明显冲突；正式提交 PR 前必须再查一次。

### 2.1 manifest 字段兼容性说明

Zed 文档的 grammar 片段目前展示 `rev`，而当前官方扩展仓库中的 schema v1 manifest 普遍使用 `commit`。本项目采用当前仓库实际格式：

```toml
[grammars.ql]
repository = "https://github.com/tree-sitter/tree-sitter-ql"
commit = "5b8ee9adaa1f2a1ea958064b61f8feb0a5a886c0"
```

M0 技术验证必须用本机 Zed 实际安装一次 dev extension；若 Zed schema 在开发时再次变化，以当时的 Zed 源码和官方扩展仓库为准，并同步修改本文。

## 3. 已验证基线

当前开发机：

- macOS arm64；
- Zed 1.16.1；
- Rust 1.97.1；
- CodeQL CLI 2.26.1，路径 `/Users/zhangboxiang/tools/codeql/codeql`；
- `tree-sitter-ql`：MIT，grammar metadata 版本 0.23.1；
- 计划固定的 grammar commit：`5b8ee9adaa1f2a1ea958064b61f8feb0a5a886c0`；
- 当前 docs.rs 最新 `zed_extension_api`：0.7.0。

本机 `codeql execute language-server --help` 已确认：

- `--check-errors` 是必需参数，可选 `ON_CHANGE` 或 `EXPLICIT`；
- `--search-path` 支持多个路径；Unix 分隔符为 `:`，Windows 为 `;`；
- language server 由 IDE 在后台通过 stdin/stdout 通信；
- 不应向该命令追加 `--additional-packs` 或 `--library-path`。

## 4. 产品范围

### 4.1 v0.1.0 必须完成

- 注册 `CodeQL` 语言；
- 识别 `.ql`、`.qll`；
- 接入固定 commit 的 `tree-sitter-ql`；
- 语法高亮；
- 括号匹配；
- 基础自动缩进；
- Outline；
- 在 manifest 注册 `codeql` language server；
- 从 Zed `lsp.codeql.binary` 读取用户配置；
- 未配置路径时通过 `Worktree::which("codeql")` 查找 PATH；
- 启动 CodeQL 原生 language server；
- 默认 `--check-errors ON_CHANGE`；
- 自定义 CLI 路径、完整 arguments、env；
- CodeQL 不存在时返回可操作的英文错误；
- README、LICENSE、安装、配置、故障排查；
- macOS arm64 完整验收；
- Linux x64、Windows x64 发布前冒烟测试。

### 4.2 v0.1.0 明确不做

- 不自动下载或捆绑 CodeQL CLI；
- 不创建 CodeQL 数据库；
- 不运行 `database analyze`；
- 不解析 SARIF；
- 不向 Problems 主动注入扫描结果；
- 不做自定义面板、侧栏或 Webview；
- 不做 MCP；
- 不在保存普通源文件时运行 CodeQL 扫描；
- 不声明 `.qls` 是 QL 代码；
- 不接管 `qlpack.yml`。

`.qls` 和 `qlpack.yml` 本质上属于 YAML 配置文件，应继续由 Zed 的 YAML 支持处理。首版文档只说明如何配置 YAML schema，不将它们放进 CodeQL grammar 的 `path_suffixes`。

### 4.3 长期不做

- 自研 CodeQL 查询引擎、extractor 或 QL language server；
- 完整复刻 VS Code CodeQL 的数据库侧栏；
- Variant Analysis；
- GitHub 云端数据库管理；
- 自动上传 GitHub Code Scanning；
- 未经用户明确触发的全仓扫描；
- 绕过 Zed extension API 限制的非官方 hack。

## 5. 最终架构

```text
                        ┌───────────────────────────┐
                        │            Zed            │
                        └─────────────┬─────────────┘
                                      │
                ┌─────────────────────┼─────────────────────┐
                │                     │                     │
                ▼                     ▼                     ▼
      ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
      │ codeql extension │  │ codeql-sarif-lsp│  │   codeql-mcp     │
      │  grammar + LSP   │  │    optional     │  │     optional     │
      └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
               │                     │                     │
               ▼                     ▼                     ▼
      CodeQL language-server    SARIF diagnostics      Agent tools
               │                     ▲                     │
               └───────────┬─────────┴──────────┬──────────┘
                           ▼                    ▼
                       CodeQL CLI        CodeQL databases/SARIF
```

边界：

- `codeql`：Zed 官方语言扩展，只负责 QL 编辑体验和静态 Tasks；
- `codeql-sarif-lsp`：可选原生 sidecar，负责 SARIF 文件监听/读取和 `publishDiagnostics`；
- `codeql-mcp`：可选 MCP Server，负责显式的数据库、查询和结果工具；
- CodeQL CLI 始终由用户安装并承担许可责任；
- 三者可以共享 SARIF 数据模型，但不能为了共享代码破坏各自发布边界。

## 6. v0.1 仓库设计

```text
codeql-zed/
├── extension.toml
├── Cargo.toml
├── Cargo.lock
├── LICENSE
├── README.md
├── CHANGELOG.md
├── src/
│   └── lib.rs
├── languages/
│   └── codeql/
│       ├── config.toml
│       ├── highlights.scm
│       ├── brackets.scm
│       ├── indents.scm
│       └── outline.scm
├── fixtures/
│   └── qlpack/
│       ├── qlpack.yml
│       ├── ValidQuery.ql
│       ├── InvalidQuery.ql
│       └── library/
│           └── Example.qll
└── docs/
    ├── configuration.md
    ├── development.md
    └── troubleshooting.md
```

v0.2 再按实际验证结果增加：

```text
languages/codeql/
├── runnables.scm
└── tasks.json
```

## 7. manifest 与语言配置

### 7.1 `extension.toml` 目标形态

```toml
id = "codeql"
name = "CodeQL"
version = "0.1.0"
schema_version = 1
authors = ["<maintainer name and email>"]
description = "CodeQL query language support powered by Tree-sitter and the CodeQL CLI language server."
repository = "https://github.com/Fruit-Guardians/codeql-zed"

[grammars.ql]
repository = "https://github.com/tree-sitter/tree-sitter-ql"
commit = "5b8ee9adaa1f2a1ea958064b61f8feb0a5a886c0"

[language_servers.codeql]
name = "CodeQL Language Server"
languages = ["CodeQL"]

[language_servers.codeql.language_ids]
CodeQL = "ql"
```

最终提交前必须补齐真实作者和仓库地址。v0.1 不声明 `[[capabilities]]`，除非 dev extension 验证表明当前 Zed 版本启动外部 LSP 需要额外 capability；不得预先申请通配权限。

### 7.2 `languages/codeql/config.toml`

最低配置：

```toml
name = "CodeQL"
grammar = "ql"
path_suffixes = ["ql", "qll"]
line_comments = ["// "]
tab_size = 2
hard_tabs = false
```

开发时补充合法的 brackets 配置，并用 fixtures 验证注释、字符串、QLDoc、class、predicate、module、from/where/select 等结构。

### 7.3 Tree-sitter queries

实现优先级：

1. `highlights.scm`：P0；
2. `brackets.scm`：P0；
3. `indents.scm`：P0；
4. `outline.scm`：P0；
5. `textobjects.scm`：v0.2；
6. `runnables.scm`：v0.2。

`tree-sitter-ql` 自带的 `queries/highlights.scm` 可作为起点，但必须：

- 只使用 Zed 官方支持的 capture；
- 对照固定 commit 的 `node-types.json`；
- 在保留 MIT 许可通知的前提下复用；
- 增加 fixtures，避免 grammar 更新后 query 静默失效。

Outline 至少覆盖：

- class；
- module；
- predicate；
- top-level select query。

## 8. Rust 扩展实现

### 8.1 依赖

```toml
[package]
name = "codeql"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[dependencies]
zed_extension_api = "0.7.0"
```

开发开始时再次检查 crates.io 最新版本。升级 `zed_extension_api` 必须和实际支持的 Zed 版本一起验证，并提交 `Cargo.lock`。

### 8.2 `language_server_command` 规则

固定解析顺序：

1. 调用 `LspSettings::for_worktree("codeql", worktree)`；
2. 若 `binary.path` 存在，使用该路径；
3. 否则调用 `worktree.which("codeql")`；
4. 找不到时返回包含安装文档链接的英文错误；
5. 若 `binary.arguments` 存在，它完整替换默认参数；
6. 否则使用默认参数：

```text
execute
language-server
--check-errors
ON_CHANGE
```

7. 环境变量以 `worktree.shell_env()` 为基础，再应用用户 `binary.env` 覆盖；
8. 不调用 `std::env::var` 获取用户 shell 环境；
9. 不硬编码 Homebrew、用户主目录或平台安装路径；
10. Windows 可执行文件解析交给 `Worktree::which` 和用户显式路径。

### 8.3 用户配置

PATH 中已有 CodeQL 时不需要任何设置。

自定义路径：

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

自定义 search path：

```json
{
  "lsp": {
    "codeql": {
      "binary": {
        "path": "/absolute/path/to/codeql",
        "arguments": [
          "execute",
          "language-server",
          "--check-errors",
          "ON_CHANGE",
          "--search-path=/absolute/path/to/qlpacks"
        ]
      }
    }
  }
}
```

注意：一旦配置 `binary.arguments`，用户必须提供完整参数，包括必需的 `execute language-server --check-errors ON_CHANGE`。多个 search path 在 Unix 使用 `:`，Windows 使用 `;`；文档示例默认只使用一个根目录，跨平台多路径示例必须经过相应系统实测后再发布。

不再采用原计划中的以下顶层配置：

```json
{
  "codeql": {
    "cli_path": "...",
    "database_directory": "..."
  }
}
```

原因是当前 Zed 扩展 API 没有通用的扩展自定义设置注册机制；v0.1 只使用官方 `lsp.<server>` 设置结构。

## 9. 开发阶段与任务分解

### M0：API/协议验证（1 天，必须先完成）

任务：

- 建立最小 extension manifest；
- 用固定 grammar commit 安装 dev extension；
- 确认 manifest 使用 `commit` 可编译；
- 确认 `CodeQL -> ql` 的 LSP language ID；
- 用本机 CodeQL 2.26.1 完成 initialize/shutdown；
- 记录 server capabilities；
- 验证不存在 CLI 时 Zed 的错误呈现；
- 检查 `zed: open log` 和 `zed --foreground` 输出。

退出条件：

- `.ql` 被识别为 CodeQL；
- grammar 编译成功；
- CodeQL language server 稳定启动；
- 能收到至少一条错误 query diagnostic；
- 没有 manifest/API 阻断项。

若 M0 失败，不进入后续开发；先更新技术决策和本文。

### M1：工程骨架（1 天）

- 完成 `extension.toml`、`Cargo.toml`、`Cargo.lock`；
- 实现最小 `Extension` trait 和 `register_extension!`；
- 添加 LICENSE、README 骨架；
- 建立 fixtures；
- 配置 `cargo fmt`、`cargo check --target wasm32-wasip2`；
- 加入基础 CI。

验收：全新 clone 可按 `docs/development.md` 安装 dev extension。

### M2：语言体验（2–3 天）

- 完成 `config.toml`；
- 移植并适配 highlights；
- 完成 brackets；
- 完成 indents；
- 完成 outline；
- 检查 `.ql`/`.qll` 大小写和路径识别；
- 验证 `.qls` 仍由 YAML 处理。

验收：fixtures 无 Tree-sitter query 错误，常见 CodeQL 语法着色和结构展示正确。

### M3：LSP 适配（2 天）

- 实现 CLI 路径发现；
- 实现默认参数；
- 实现用户 binary path/arguments/env 覆盖；
- 合并 shell env；
- 提供英文错误；
- 验证 diagnostics、completion、hover、definition、references；
- 验证 rename、formatting、inlay hints，并根据 server capability 标记支持状态。

验收：配置路径和 PATH 两种安装方式均工作；路径含空格时也能启动。

### M4：QA 与文档（2 天）

- 完成 README；
- 完成安装、配置、排错文档；
- 记录 CodeQL 许可提示；
- 添加截图/GIF；
- 测试无 CodeQL 环境；
- 测试无 qlpacks、错误 qlpack、缺失 import；
- macOS arm64 完整回归；
- Linux x64、Windows x64 冒烟；
- 形成已知限制清单。

验收：不阅读源码的用户可仅按 README 完成安装和首个 `.ql` 文件诊断。

### M5：v0.1.0 发布（1–3 天，不含维护者排队时间）

- 再查官方 registry 是否已有 CodeQL；
- 确认扩展代码使用允许的开源许可证；
- 确认全部用户可见文本为英文；
- 打 tag `v0.1.0`；
- 在提交 commit 上手工安装测试；
- fork `zed-industries/extensions`；
- 以 HTTPS submodule 添加 `extensions/codeql`；
- 添加版本一致的 `extensions.toml` 条目；
- 运行 `pnpm sort-extensions`；
- PR 只新增 `codeql` 一个扩展；
- 3 周内响应维护者反馈。

## 10. v0.1.0 验收标准

### 安装

- Zed 可安装 dev extension；
- 没安装 CodeQL 时，Tree-sitter 功能仍可用；
- 没安装 CodeQL 时，打开 `.ql` 得到可读、可操作的错误，而不是崩溃；
- 扩展不自动下载 CodeQL；
- 扩展不请求与 v0.1 无关的能力。

### 语言

- `.ql`、`.qll` 自动识别为 CodeQL；
- `.qls`、`qlpack.yml` 不被误识别为 CodeQL；
- 关键字、类型、函数/predicate、变量、字符串、数字、注释、QLDoc 有合理高亮；
- 圆括号、方括号、花括号匹配；
- class/module/predicate/select 可出现在 Outline；
- 编辑普通 Python/JavaScript/Go 等文件不启动 CodeQL QL language server。

### LSP

- PATH 中的 CodeQL 能被发现；
- `binary.path` 能覆盖 PATH；
- `binary.arguments` 能配置单个和多个 search path；
- 无效 binary path、无效 search path、缺失 qlpack 的错误可区分；
- 错误 query 出现 diagnostics；
- completion、hover、go to definition 工作；
- find references 工作；
- rename、formatting、inlay hints 以 M0/M3 实际 capability 为准，不做虚假承诺；
- Zed UI 不因 server 启动阻塞；
- Zed 日志中没有 extension panic。

### 发布

- README 明确依赖、安装、配置、隐私、许可和已知限制；
- manifest version、Git tag、官方 registry version 一致；
- extension repository 公开；
- submodule 指向分支可达 commit；
- 官方扩展 PR 满足 prerequisites。

## 11. v0.2：静态 Tasks 与当前查询运行

预计：2–4 个开发日。此阶段仍属于 `codeql` 语言扩展，但只提供和 QL 文件直接相关的静态任务。

功能：

- `runnables.scm` 在 top-level select query 处显示 runnable；
- `languages/codeql/tasks.json` 提供固定模板；
- `CodeQL: Compile Current Query`；
- `CodeQL: Analyze Current Query`；
- 使用 `$ZED_FILE`、`$ZED_STEM`、`$ZED_WORKTREE_ROOT`；
- 默认数据库约定为 `$ZED_WORKTREE_ROOT/.codeql/databases/default`；
- 默认结果约定为 `$ZED_WORKTREE_ROOT/.codeql/results/$ZED_STEM.sarif`；
- 文档提供用户在 `.zed/tasks.json` 中覆盖数据库、suite、threads、RAM 的示例。

限制：

- language extension 只能提供静态 task templates，不能动态列出数据库；
- 数据库创建需要指定目标语言和 build mode，不适合作为无参数的通用 language task；
- 创建数据库只提供文档模板，由项目级 `.zed/tasks.json` 明确配置；
- task 输出在 Terminal；生成 SARIF 不等于自动进入 Problems；
- 不默认 analyze-on-save；
- 不允许并发运行相同扫描任务；
- 命令参数使用 `args` 数组，避免路径空格和 shell 注入问题。

验收：

- 打开 `.ql` 可从 task picker 运行当前查询；
- 有效数据库生成 `sarifv2.1.0`；
- 路径含空格时任务仍工作；
- 失败日志能区分 query、database、pack 解析错误；
- Windows 任务模板通过实机验证后才标记支持。

## 12. v0.3：SARIF → Problems（独立 LSP，带前置门槛）

预计：先做 2 天技术验证；通过后再投入 8–12 个开发日。

### 12.1 开发前门槛

必须先验证并记录：

- Zed 允许同一源文件同时运行现有语言 LSP 和 `codeql-sarif-lsp`；
- 多语言 server 的发布形态符合 Zed 审核规则；
- CodeQL 扫描触发选择：Task、LSP code action 或 MCP；
- Zed 对 `publishDiagnostics`、`relatedInformation`、进度和清理旧 diagnostics 的表现；
- sidecar 通过 PATH 还是 GitHub Release 下载；
- 下载 capability 能精确到发行域名和路径，不申请通配权限；
- 先在 Zed issue/discussion 向维护者确认上架方案，避免完成后被拒。

任一关键项不成立，则 v0.3 保持为外部工具，不提交 Zed registry。

### 12.2 组件职责

`codeql-sarif-lsp`：

- 读取 SARIF 2.1.0；
- 规范化 file URI、相对路径、Windows drive path；
- 映射 rule ID、message、level、location；
- 将 code flow 作为 related information（以 Zed 实际显示能力为准）；
- 发布、替换、清空 diagnostics；
- 标记结果生成时间和输入 SARIF；
- 不负责解释或自动修复漏洞；
- 不上传源代码、数据库或 SARIF。

建议映射：

| SARIF | LSP Diagnostic |
|---|---|
| `ruleId` | `code` |
| `message.text/markdown` | `message` |
| `level=error` | Error |
| `level=warning` | Warning |
| `level=note/none` | Information/Hint |
| primary location | `range` |
| `helpUri` | `codeDescription.href`，若客户端支持 |
| code flow locations | `relatedInformation` |

### 12.3 验收

- 解析空 SARIF、单 run、多 run、多 result；
- Zed Problems 显示结果并可跳转；
- 新结果替换旧结果；
- 删除/失效 SARIF 后清理 diagnostics；
- 路径逃逸工作区时不读取不受信任文件；
- severity、零基/一基行列转换正确；
- 不覆盖源语言原有 LSP diagnostics；
- 10k results 有明确上限、截断提示和性能指标。

## 13. v0.4：CodeQL MCP Server

预计：7–10 个开发日，与语言扩展独立版本。

### 13.1 分发

第一步以本地 Custom Server 使用：

```json
{
  "context_servers": {
    "codeql": {
      "command": "codeql-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

稳定后发布官方 MCP Registry。由于 Zed 已说明 MCP Server Extensions 将弃用，不为本项目新建混合型 Zed MCP extension；如短期确需 Zed registry 包装，也必须是独立 ID、只含一个 MCP server，并同时准备迁移。

### 13.2 工具清单

首版工具：

```text
codeql_check_installation
codeql_list_databases
codeql_create_database
codeql_analyze_database
codeql_run_query
codeql_read_sarif
codeql_filter_findings
```

原则：

- 每个工具使用明确 JSON Schema；
- 数据库、query、output 必须是显式路径或受控 workspace-relative path；
- create/analyze 只在用户或 Agent 明确调用时运行；
- 返回结构化 finding，不让 server 伪装成 LLM 做“解释”；
- 解释与修复建议交给 Agent，server 只提供证据；
- 所有命令记录可审计参数、耗时、退出码和 stderr 摘要；
- 提供 timeout、cancel、threads、RAM 上限；
- 默认不下载 packs、不联网、不上传；
- 不接受任意 shell command 字符串；
- Zed 默认 MCP 工具权限为 confirm，文档不鼓励全局 allow。

### 13.3 验收

- Zed 能显示 server active；
- Agent 能检查 CodeQL 安装；
- 能列出受控根目录内数据库；
- 能创建小型 Python/JavaScript fixture 数据库；
- 能运行自定义 query 和标准 suite；
- 能读取、过滤、总结 SARIF 证据；
- 越界路径、未知参数、超时、取消均有确定错误；
- 不经确认不执行耗时扫描；
- 不泄露源码内容到日志。

## 14. 测试计划

### 14.1 自动化测试

v0.1：

- `cargo fmt --check`；
- `cargo check --target wasm32-wasip2`；
- 路径发现逻辑；
- 用户配置优先级；
- 默认参数和完整 arguments 覆盖；
- env 合并；
- 错误消息快照；
- manifest/TOML 解析；
- Tree-sitter query 编译；
- fixture 节点覆盖。

v0.3/v0.4：

- SARIF 2.1.0 解析；
- URI 与跨平台路径；
- severity；
- related information；
- 去重和旧结果清理；
- 大文件上限；
- 命令参数构造；
- timeout/cancel；
- workspace path containment；
- MCP JSON Schema 和错误响应。

### 14.2 手工 LSP 场景

- initialize/shutdown；
- didOpen/didChange/didSave；
- diagnostics；
- completion；
- hover；
- definition；
- references；
- rename；
- formatting；
- inlay hints；
- 重启 server；
- 多 worktree；
- remote worktree（后续发布门槛）。

### 14.3 平台矩阵

| 平台 | v0.1 | v0.2 | v0.3/v0.4 |
|---|---|---|---|
| macOS arm64 | 完整回归 | 完整回归 | 完整回归 |
| macOS x64 | 冒烟 | 冒烟 | 原生 binary 构建/回归 |
| Linux x64 | 发布前冒烟 | 发布前冒烟 | 原生 binary 构建/回归 |
| Linux arm64 | 尽力支持，不阻塞 v0.1 | 尽力支持 | 有 release binary 后支持 |
| Windows x64 | 发布前冒烟 | 必须实机验证 task/path | 原生 binary 构建/回归 |
| Windows arm64 | 首版不承诺 | 首版不承诺 | 有 CodeQL 与 sidecar 支持后再评估 |

Zed 语言扩展本身是 WASM，不需要为每个平台打扩展二进制；跨平台工作的主要风险来自用户的 CodeQL CLI、PATH、search-path 分隔符、Tasks 和未来 sidecar。

## 15. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| Zed extension API 变化 | 编译或审核失败 | 固定 API 版本；每次发布用当前稳定 Zed 安装 dev extension |
| 文档与 manifest 实际字段不一致 | grammar 无法编译 | M0 用当前 Zed 和官方扩展仓库双重验证 |
| CodeQL language server 使用自定义协议细节 | 部分 LSP 能力不可用 | 只承诺实测功能；保存初始化日志与 capability 快照 |
| CodeQL CLI 不在 GUI 的 PATH | LSP 启动失败 | 支持 `lsp.codeql.binary.path`；错误中给出配置入口 |
| 用户配置 arguments 覆盖默认值 | 丢失必需参数 | 文档明确必须提供完整参数；单测覆盖 |
| qlpack/search path 复杂 | import 无法解析 | 一个根 search path 的最小示例；跨平台实测多路径 |
| Tree-sitter grammar 变更 | query 失效 | 固定 commit；升级必须跑 fixtures |
| 扩展无法直接推送 SARIF diagnostics | v0.2 不能进入 Problems | 明确采用独立 LSP bridge，先做发布可行性验证 |
| 静态 Tasks 无法动态列数据库 | UX 有限 | 约定默认数据库；提供项目 `.zed/tasks.json` 模板；MCP 负责动态操作 |
| CodeQL 数据库创建慢且依赖构建环境 | 用户误以为卡死 | 不放 v0.1；Tasks/sidecar 显示日志，MCP 支持 timeout/cancel |
| MCP Extension 正在弃用 | 后续分发失效 | 直接支持 Custom Server 与官方 MCP Registry |
| CodeQL 许可限制 | 商业/闭源使用风险 | 不捆绑 CLI；README 链接官方条款并要求用户自行确认 |
| SARIF 路径不一致 | 无法跳转 | URI/path 模块单测；真实跨平台 fixture |
| 大型 SARIF/数据库消耗资源 | 卡顿或 OOM | 结果上限、流式解析、threads/RAM/timeout 配置 |
| 过度申请 capability | 审核或信任风险 | v0.1 最小权限；后续限定 command/host/path |

## 16. 安全、隐私与许可

- 扩展默认不联网；
- 扩展不收集 telemetry；
- 不自动下载 CodeQL CLI；
- 不上传源代码、数据库、BQRS 或 SARIF；
- CLI 和 query packs 的许可与扩展代码许可分开说明；
- grammar 为 MIT，复用 query 时保留必要通知；
- 扩展代码选用 Zed 允许的许可证，优先 Apache-2.0 或 MIT；
- MCP/sidecar 所有路径限制在显式允许的 workspace/database/results roots；
- 不将用户输入拼成 shell 字符串，统一参数数组；
- 日志不得包含源码正文、密钥或完整环境变量；
- README 明确 CodeQL 官方使用条款适用范围。

## 17. Definition of Done

v0.1.0 只有同时满足以下条件才算完成：

- 本文 M0–M4 全部退出条件满足；
- 所有 P0 自动化检查通过；
- macOS arm64 完整回归通过；
- Linux x64、Windows x64 至少各一次发布前冒烟通过；
- 无 CodeQL 环境的退化体验可接受；
- README 能让新用户从零完成配置；
- 用户可见文本全部为英文；
- 许可文件和第三方归属完整；
- dev extension 在将要发布的 commit 上安装成功；
- 没有把 v0.2+ 的能力写成 v0.1 已支持；
- 官方扩展 PR 已创建并满足发布规则。

项目整体完成的判定分层：

| 层级 | 完成标志 |
|---|---|
| Language MVP | v0.1.0 发布，QL 编辑体验可用 |
| Query workflow | v0.2 Tasks 可运行当前 query 并生成 SARIF |
| Problems integration | 独立 SARIF LSP 经技术/审核门槛后发布 |
| Agent integration | 独立 MCP Server 可被 Zed Custom Server/Registry 使用 |

## 18. 开发优先级与首周安排

### P0 backlog

1. `P0-01`：最小 manifest + dev extension 安装；
2. `P0-02`：固定 grammar commit 并验证编译；
3. `P0-03`：CodeQL language config；
4. `P0-04`：highlights/brackets/indents/outline；
5. `P0-05`：LSP 注册和 `language_id=ql`；
6. `P0-06`：PATH 与 binary.path 发现；
7. `P0-07`：default/custom args 与 env；
8. `P0-08`：LSP 功能回归；
9. `P0-09`：无 CLI/错误 qlpack/缺 import 错误体验；
10. `P0-10`：英文 README、许可与发布材料。

### 第一周

**Day 1：M0**

- 最小工程；
- dev extension；
- grammar + LSP initialize；
- 记录 capability 和阻断项。

**Day 2：工程骨架**

- manifest/Cargo/CI；
- fixtures；
- PATH 与配置读取框架。

**Day 3：Tree-sitter**

- config；
- highlights；
- brackets。

**Day 4：编辑体验**

- indents；
- outline；
- fixture 回归。

**Day 5：LSP 完整适配**

- command、args、env；
- diagnostics/completion/hover/definition；
- 错误处理。

第一周结束必须得到一个可日常编辑 `.ql/.qll` 的 dev extension。第二周只做 QA、跨平台、文档和发布，不提前扩展到 SARIF/MCP。

## 19. 最终开发顺序

```text
M0 可行性验证
  └─> v0.1 CodeQL 语言扩展
        └─> 官方 Zed registry 发布
              ├─> v0.2 静态 Tasks / runnable
              ├─> SARIF LSP 技术与审核验证
              │     └─> 通过后开发 Problems 集成
              └─> 独立 codeql-mcp
                    └─> Custom Server 验证
                          └─> 官方 MCP Registry
```

任何后续阶段都不得阻塞 v0.1。首要成功指标不是“复刻 VS Code CodeQL”，而是：

> 在 Zed 中稳定、低摩擦地编写 CodeQL 查询，并使用用户本机 CodeQL CLI 获得可信的语言服务。
