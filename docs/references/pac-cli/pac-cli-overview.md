# Microsoft Power Platform CLI (pac) - Overview

> **Source**: [Microsoft Learn - PAC CLI Introduction](https://learn.microsoft.com/en-us/power-platform/developer/cli/introduction?tabs=windows)
> **Last Updated**: 2026-07-23
> **Purpose**: Project reference asset for future pac CLI integration into power-platform-agent

---

## 1. What is Power Platform CLI?

Microsoft Power Platform CLI is a **one-stop developer CLI** that enables developers and ISVs to perform operations in Microsoft Power Platform, including:

- Environment lifecycle management
- Authentication (multi-profile)
- Microsoft Dataverse environments
- Solution packages (pack/unpack/import/export/clone/sync)
- Power Pages
- Code components (Power Apps Component Framework)
- And more...

---

## 2. Installation Methods

There are three installation methods. Multiple methods can coexist on the same machine.

| Method | OS Support | Description |
|--------|-----------|-------------|
| **VS Code Extension** | Windows, Linux, macOS | Enables commands within a VS Code PowerShell terminal. By default, PAC CLI is only available within VS Code terminal unless [enabled system-wide](https://learn.microsoft.com/en-us/power-platform/developer/howto/install-vs-code-extension#enable-pac-cli-in-command-prompt-cmd-and-powershell-terminals-for-windows). |
| **.NET Tool** | Windows, Linux, macOS | Enables commands in PowerShell, CMD, or Bash. **Does NOT** support `pac data` or `pac package deploy/show` commands. |
| **Windows MSI** | Windows only | Enables commands within a PowerShell terminal in VS Code on Windows. Supports [version management](https://learn.microsoft.com/en-us/power-platform/developer/howto/install-cli-msi#manage-versions). |

### Windows-Only Commands

The following commands are **only available on Windows** (require VS Code Extension or MSI install):

- `pac data` - Data operations
- `pac package deploy` - Package deployment
- `pac package show` - Package inspection

> **Note**: If you only install via .NET Tool, these commands will NOT be available even on Windows.

---

## 3. Verification

### Check if PAC CLI is installed (Windows)

```powershell
# Check if pac is available
Get-Command pac | Format-List

# Check installed version
pac
# Output example:
# Microsoft PowerPlatform CLI
# Version: 1.30.3+g0f0e0b9
```

### Check if PAC CLI is installed (Linux/macOS)

```bash
which pac
pac --version
```

---

## 4. Authentication Management

Most PAC CLI commands require authenticated access. PAC uses **auth profiles** to manage connections.

### 4.1 Create an Auth Profile

```powershell
# Interactive - connects to default environment
pac auth create

# Connect to a specific environment by name, ID, URL, or partial name
pac auth create --environment "HR-Dev"

# Non-interactive (GitHub Codespaces, CI/CD)
pac auth create --deviceCode

# Specify cloud (US Sovereign clouds supported)
pac auth create --cloud USGovernment
```

**Key `--cloud` values**: `Public` (default), `USGovernment`, `USGovernmentL4`, `USGovernmentL5DoD`, `China`

### 4.2 List Auth Profiles

```powershell
pac auth list
```

Output example:
```
Index Active Kind      Name Friendly Name                   Url                                 User                                     Cloud  Type
[1]   *      UNIVERSAL      Personal Productivity (Default) https://x.crm.dynamics.com/         user@contoso.onmicrosoft.com             Public User
```

### 4.3 Switch Auth Profile

```powershell
pac auth select --index 2
```

### 4.4 Other Auth Commands

| Command | Description |
|---------|-------------|
| `pac auth create` | Create a new authentication profile |
| `pac auth list` | List all auth profiles |
| `pac auth select` | Select a different active profile |
| `pac auth delete` | Delete an auth profile |
| `pac auth clear` | Clear all auth profiles |
| `pac auth name` | Name/rename an auth profile |
| `pac auth update` | Update auth profile credentials |

---

## 5. Tab Completion (PowerShell)

Add the following to your PowerShell `$PROFILE`:

```powershell
$scriptblock = {
    param($wordToComplete, $commandAst, $cursorPosition)

    &pac complete -s "$($commandAst.ToString())" | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }
}

Register-ArgumentCompleter -Native -CommandName pac -ScriptBlock $scriptblock
```

Also supports bash, zsh, fish, and nushell (use `pac complete` instead of `dotnet complete`).

---

## 6. PAC CLI Command Groups (Full List)

Run `pac help` or `pac <subcommand> help` for detailed info.

| Command Group | Description |
|--------------|-------------|
| `pac admin` | Admin operations (environments, tenants, policies) |
| `pac application` | Application lifecycle management |
| `pac auth` | Authentication profile management |
| `pac canvas` | Canvas app operations |
| `pac catalog` | Power Platform catalog management |
| `pac code` | Code generation (early-bound types) |
| `pac connector` | Custom connector management |
| `pac data` | Data operations (Windows only) |
| `pac env` | Environment variable management |
| `pac fence` | Boundary management |
| `pac help` | Show help |
| `pac package` | Package deploy/show (Windows only) |
| `pac paportal` | Power Pages portal operations |
| `pac pcfx` | Power Apps Component Framework operations |
| `pac plugin` | Plugin (C#) development tooling |
| `pac powerapps` | Power Apps operations |
| `pac solution` | Solution lifecycle (pack/unpack/import/export/clone/sync) |
| `pac telemetry` | Telemetry management |
| `pac test` | Test engine operations |
| `pac tools` | Tool management |
| `pac org` | Organization/environment operations |

---

## 7. US Sovereign Cloud Support

PAC CLI supports GCC and GCC High (US Sovereign cloud) regions. Use the `--cloud` parameter with `pac auth create`:

| Cloud Value | Region |
|-------------|--------|
| `Public` | Commercial (default) |
| `USGovernment` | GCC |
| `USGovernmentL4` | GCC High |
| `USGovernmentL5DoD` | DoD |
| `China` | China (operated by 21Vianet) |

---

## 8. Useful Links

| Resource | URL |
|----------|-----|
| PAC CLI Introduction | https://learn.microsoft.com/en-us/power-platform/developer/cli/introduction |
| Command Groups Reference | https://learn.microsoft.com/en-us/power-platform/developer/cli/reference/ |
| Release Notes (NuGet) | https://www.nuget.org/packages/Microsoft.PowerApps.CLI#releasenotes-body-tab |
| Troubleshooting | https://learn.microsoft.com/en-us/power-platform/developer/cli/troubleshooting |
| GitHub Discussions | https://github.com/microsoft/powerplatform-build-tools/discussions |
| VS Code Extension Install | https://learn.microsoft.com/en-us/power-platform/developer/howto/install-vs-code-extension |
| .NET Tool Install | https://learn.microsoft.com/en-us/power-platform/developer/howto/install-cli-net-tool |
| MSI Install | https://learn.microsoft.com/en-us/power-platform/developer/howto/install-cli-msi |

---

## 9. Integration Notes for power-platform-agent

### Current Project Architecture

This project (`power-platform-agent`) currently uses two isolated paths:
1. **`framework_power` CLI** (Python-first, recommended) - Type-safe Python models, idempotent deploy/plan/reverse
2. **MCP Server** (Legacy) - AI-assisted development via Claude Code / Cursor

### Potential PAC CLI Integration Points

| PAC CLI Capability | Current Project Equivalent | Integration Value |
|-------------------|---------------------------|-------------------|
| `pac solution pack/unpack` | `framework_power` solution deploy | PAC provides YAML source control format (v2.4.1+), native Git integration |
| `pac solution import/export` | `framework_power` solution deploy | PAC handles managed/unmanaged, async, settings files |
| `pac solution clone/sync` | `framework_power` reverse | PAC creates .cdsproj, supports references |
| `pac solution check` | (none) | Power Apps Checker integration - new capability |
| `pac auth` | `framework/utils/DataverseClient` (MSAL) | PAC profiles could replace env-var-based auth |
| `pac plugin` | `framework_power` plugin build | PAC provides NuGet PluginPackage workflow |
| `pac data` | (none) | Data import/export - new capability |
| `pac code` | (none) | Early-bound type generation - new capability |
| `pac canvas` | (none) | Canvas app source control - new capability |
| `pac admin` | (none) | Environment lifecycle management - new capability |

### Recommended Integration Strategy

1. **Phase 1**: Use PAC CLI as a subprocess wrapper for solution pack/unpack operations, replacing custom SolutionPackager logic
2. **Phase 2**: Add `pac solution check` as a CI/CD quality gate
3. **Phase 3**: Leverage `pac auth` profiles for multi-environment authentication
4. **Phase 4**: Explore `pac code` for type generation, `pac data` for data operations
