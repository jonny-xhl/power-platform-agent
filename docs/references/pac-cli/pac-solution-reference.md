# `pac solution` - Complete Command Reference

> **Source**: [Microsoft Learn - pac solution reference](https://learn.microsoft.com/en-us/power-platform/developer/cli/reference/solution)
> **Last Updated**: 2026-07-23
> **Purpose**: Project reference asset for future pac CLI integration into power-platform-agent

---

## Commands Summary

| Command | Description |
|---------|-------------|
| `pac solution add-license` | Add license and plan info to the solution |
| `pac solution add-reference` | Adds a reference from the current project to another project |
| `pac solution add-solution-component` | Add one or more solution components to a target unmanaged solution in Dataverse |
| `pac solution check` | Upload a solution project to run against the Power Apps Checker service |
| `pac solution clone` | Create a solution project based on an existing solution in your org |
| `pac solution create-settings` | Create a settings file from solution zip or solution folder |
| `pac solution delete` | Delete a solution from Dataverse in the current environment |
| `pac solution export` | Export a solution from Dataverse |
| `pac solution import` | Import a solution into Dataverse |
| `pac solution init` | Initialize a directory with a new Dataverse solution project |
| `pac solution list` | List all solutions from the current Dataverse organization |
| `pac solution online-version` | Get or set version for solution loaded in Dataverse |
| `pac solution pack` | Package solution components on local filesystem into solution.zip (SolutionPackager) |
| `pac solution publish` | Publish all customizations |
| `pac solution sync` | Sync the current Dataverse solution project to the current state in your org |
| `pac solution unpack` | Extract solution components from solution.zip onto local filesystem (SolutionPackager) |
| `pac solution upgrade` | Apply solution upgrade |
| `pac solution version` | Update build or revision version for the solution |

---

## pac solution add-license

Add license and plan info to the solution.

### Example

```powershell
pac solution add-license --planDefinitionFile ../ISV_Plan_Definition.csv --planMappingFile ../ISV_Plan_Mapping.csv
```

### Plan Definition File (CSV)

Expected columns: `ServiceID`, `Display name`, `More info URL`

```csv
ServiceID,Display name,More info URL
test_isvconnect1599092224747.d365_isvconnect_prod_licensable.bronzeplan,Fabrikam Bronze Plan,http://www.microsoft.com
test_isvconnect1599092224747.d365_isvconnect_prod_licensable.silverplan,Fabrikam Silver Plan,http://www.microsoft.com
test_isvconnect1599092224747.d365_isvconnect_prod_licensable.goldplan,Fabrikam Gold Plan,http://www.microsoft.com
```

### Plan Mapping File (CSV)

Expected columns: `Service ID`, `Component name`

```csv
Service ID,Component name
test_isvconnect1599092224747.d365_isvconnect_prod_licensable.bronzeplan,crf36_BronzeApp
test_isvconnect1599092224747.d365_isvconnect_prod_licensable.silverplan,crf36_BronzeApp
test_isvconnect1599092224747.d365_isvconnect_prod_licensable.silverplan,crf36_SilverApp
test_isvconnect1599092224747.d365_isvconnect_prod_licensable.goldplan,crf36_BronzeApp
test_isvconnect1599092224747.d365_isvconnect_prod_licensable.goldplan,crf36_SilverApp
test_isvconnect1599092224747.d365_isvconnect_prod_licensable.goldplan,crf36_GoldApp
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--planDefinitionFile` | `-pd` | Yes | License plan definition file in CSV format |
| `--planMappingFile` | `-pm` | Yes | License plan mapping file in CSV format |

---

## pac solution add-reference

Adds a reference from the project in the current directory to the project at the specified path.

### Example

```powershell
pac solution add-reference --path c:\Users\Downloads\SampleComponent
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--path` | `-p` | Yes | The path to the referenced project |

---

## pac solution add-solution-component

Add one or more solution components to the target unmanaged solution in Dataverse.

### Example

Add the `contact` table (component type 1) to solution `SampleSolution`:

```powershell
pac solution add-solution-component --solutionUniqueName SampleSolution --component contact --componentType 1
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--component` | `-c` | Yes | The schema name or ID of the component to add |
| `--componentType` | `-ct` | Yes | The value representing the solution component type |
| `--solutionUniqueName` | `-sn` | Yes | Name of the solution |
| `--AddRequiredComponents` | `-arc` | No | Also add required components (switch) |
| `--async` | `-a` | No | Import asynchronously (switch) |
| `--environment` | `-env` | No | Environment URL or ID |

### Common Component Types

| Type ID | Component |
|---------|-----------|
| 1 | Entity (Table) |
| 2 | Attribute (Column) |
| 3 | Relationship |
| 4 | Attribute Picklist |
| 9 | Option Set |
| 10 | Entity Relationship |
| 29 | Ribbon Customization |
| 59 | Saved Query (View) |
| 60 | System Form |
| 61 | Web Resource |
| 62 | Plugin Assembly |
| 63 | Plugin Type |
| 64 | Sdk Message Processing Step |
| 70 | Workflow |
| 92 | App Module |

---

## pac solution check

Upload a Dataverse solution project to run against the Power Apps Checker service.

### Example

```powershell
pac solution check --path c:\Users\Documents\Solution.zip --outputDirectory c:\samplepackage --geo UnitedStates
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--path` | `-p` | No | Path to solution file(s) to check (supports glob/wildcard) |
| `--outputDirectory` | `-o` | No | Output directory |
| `--geo` | `-g` | No | Geographical instance of Power Apps Checker |
| `--environment` | `-env` | No | Target Dataverse (Guid or URL) |
| `--customEndpoint` | `-ce` | No | Custom URL for Power Apps Checker |
| `--excludedFiles` | `-ef` | No | Exclude files from analysis (comma-separated) |
| `--ruleLevelOverride` | `-rl` | No | JSON file with rule level overrides |
| `--ruleSet` | `-rs` | No | Rule set: Guid, "AppSource Certification", or "Solution Checker" (default) |
| `--saveResults` | `-sav` | No | Store results in Solution Health Hub (switch) |
| `--solutionUrl` | `-u` | No | SAS URI pointing to solution.zip |
| `--clearCache` | `-cc` | No | Clear solution checker enforcement cache (switch) |

### `--geo` Accepted Values

`PreviewUnitedStates`, `UnitedStates`, `Europe`, `Asia`, `Australia`, `Japan`, `India`, `Canada`, `SouthAmerica`, `UnitedKingdom`, `France`, `SouthAfrica`, `Germany`, `UnitedArabEmirates`, `Switzerland`, `Norway`, `Singapore`, `Korea`, `Sweden`, `Italy`, `Poland`, `NewZealand`, `USGovernment`, `USGovernmentL4`, `USGovernmentL5DoD`, `China`

### `--ruleLevelOverride` Example

```json
[
  {"Id":"meta-remove-dup-reg","OverrideLevel":"Medium"},
  {"Id":"il-avoid-specialized-update-ops","OverrideLevel":"Medium"}
]
```

Accepted OverrideLevel values: `Critical`, `High`, `Medium`, `Low`, `Informational`

---

## pac solution clone

Create a solution project based on an existing solution in your organization.

### Examples

```powershell
# Basic clone
pac solution clone --name sampleSolution

# Clone with settings included
pac solution clone --name sampleSolution --include general,autonumbering
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--name` | `-n` | Yes | The name of the solution to export |
| `--async` | `-a` | No | Export asynchronously (switch) |
| `--environment` | `-env` | No | Target Dataverse (Guid or URL) |
| `--include` | `-i` | No | Settings to include (comma-separated, see below) |
| `--localize` | `-loc` | No | Extract/merge string resources into .resx files (switch) |
| `--map` | `-m` | No | Path to mapping XML file |
| `--max-async-wait-time` | `-wt` | No | Max async wait time in minutes (default: 60) |
| `--outputDirectory` | `-o` | No | Output directory |
| `--packagetype` | `-p` | No | Extraction type: `Unmanaged`, `Managed`, or `Both` (default: Both) |
| `--targetversion` | `-v` | No | **Deprecated** - ignored |

### `--include` Accepted Values

`autonumbering`, `calendar`, `customization`, `emailtracking`, `externalapplications`, `general`, `isvconfig`, `marketing`, `outlooksynchronization`, `relationshiproles`, `sales`

---

## pac solution create-settings

Create a settings file from solution zip or solution folder.

### Example

```powershell
pac solution create-settings --solution-zip C:\SampleSolution.zip --settings-file .\SampleDeploymentSettingsDev.json
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--solution-zip` | `-z` | No | Path to solution zip file |
| `--solution-folder` | `-f` | No | Path to unpacked solution folder (.cdsproj or Solution.xml root) |
| `--settings-file` | `-s` | No | .json file with deployment settings for connection references and environment variables |

---

## pac solution delete

Delete a solution from Dataverse in the current environment.

### Example

```powershell
pac solution delete --solution-name Samplesolution
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--solution-name` | `-sn` | Yes | Name of the solution |
| `--environment` | `-env` | No | Target Dataverse (Guid or URL) |

---

## pac solution export

Export a solution from Dataverse.

### Example

```powershell
pac solution export --path c:\Users\Documents\Solution.zip --name SampleComponentSolution --managed true --include general
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--name` | `-n` | Yes | The name of the solution to export |
| `--path` | `-p` | No | Path where the exported solution zip is written |
| `--managed` | `-m` | No | Export as managed solution (true/false) |
| `--overwrite` | `-ow` | No | Overwrite existing file |
| `--async` | `-a` | No | Export asynchronously (switch) |
| `--environment` | `-env` | No | Target Dataverse (Guid or URL) |
| `--include` | `-i` | No | Settings to include (comma-separated) |
| `--max-async-wait-time` | `-wt` | No | Max async wait time in minutes (default: 60) |
| `--targetversion` | `-v` | No | **Deprecated** - ignored |

---

## pac solution import

Import a solution into Dataverse.

### Example

```powershell
pac solution import --path c:\Users\Documents\Solution.zip
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--path` | `-p` | No | Path to solution zip. If not specified, assumes current folder is a cdsproj |
| `--activate-plugins` | `-ap` | No | Activate plugins after import (switch) |
| `--async` | `-a` | No | Import asynchronously (switch) |
| `--environment` | `-env` | No | Target Dataverse (Guid or URL) |
| `--force-overwrite` | `-f` | No | Force overwrite of unmanaged customizations (switch) |
| `--import-as-holding` | `-h` | No | Import as holding solution (switch) |
| `--max-async-wait-time` | `-wt` | No | Max async wait time in minutes (default: 60) |
| `--publish-changes` | `-pc` | No | Publish customizations after import (switch) |
| `--settings-file` | | No | Path to deployment settings file |
| `--skip-dependency-check` | `-s` | No | Skip dependency checking (switch) |
| `--skip-lower-version` | `-slv` | No | Skip importing lower version components (switch) |
| `--stage-and-upgrade` | `-up` | No | Stage the solution for upgrade (switch) |

---

## pac solution init

Initialize a directory with a new Dataverse solution project.

### Example

```powershell
pac solution init --publisher-name developer --publisher-prefix dev
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--publisher-name` | `-pn` | Yes | Name of the publisher. Allowed: [A-Z], [a-z], [0-9], `_`. First char: [A-Z], [a-z], or `_` |
| `--publisher-prefix` | `-pp` | Yes | Customization prefix. 2-8 chars, alphanumeric, starts with a letter, cannot start with `mscrm` |
| `--outputDirectory` | `-o` | No | Output directory |

---

## pac solution list

List all solutions from the current Dataverse organization.

### Example

```powershell
pac solution list
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--environment` | `-env` | No | Target Dataverse (Guid or URL) |
| `--includeSystemSolutions` | | No | Include system solutions (switch) |
| `--json` | | No | Return output in JSON format (switch) |

---

## pac solution online-version

Get or set version for solution loaded in Dataverse.

### Example

```powershell
pac solution online-version --solution-name Samplesolution --solution-version 1.0.0.2
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--solution-name` | `-sn` | Yes | Name of the solution |
| `--solution-version` | `-sv` | No | Version number. If omitted, returns current online version |
| `--environment` | `-env` | No | Target Dataverse (Guid or URL) |

---

## pac solution pack

Package solution components on local filesystem into solution.zip (SolutionPackager).

### Example

```powershell
pac solution pack --zipfile C:\SampleSolution.zip --folder .\SampleSolutionUnpacked\.
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--zipfile` | `-z` | Yes | Full path to the solution ZIP file |
| `--folder` | `-f` | No | Source folder path |
| `--packagetype` | `-p` | No | Package type: `Unmanaged`, `Managed`, or `Both` |
| `--allowDelete` | `-ad` | No | Allow delete operations (default: false) |
| `--allowWrite` | `-aw` | No | Allow write operations (default: false) |
| `--clobber` | `-c` | No | Overwrite existing files |
| `--disablePluginRemap` | `-dpm` | No | Disable plugin type name remapping (default: false) |
| `--errorlevel` | `-e` | No | Logging error level |
| `--localize` | `-loc` | No | Extract/merge string resources into .resx files |
| `--log` | `-l` | No | Path to log file |
| `--map` | `-m` | No | Path to mapping XML file |
| `--singleComponent` | `-sc` | No | Process only a single component type |
| `--sourceLoc` | `-src` | No | Source language locale |
| `--useLcid` | `-lcid` | No | Use LCID instead of culture name |
| `--useUnmanagedFileForMissingManaged` | `-same` | No | Use unmanaged files for missing managed files |

### Remarks: Source Folder Formats

`pac solution pack` supports **two source folder layouts**:

#### XML Format (Legacy - Default)
- Requires `Other\Solution.xml` and `Other\Customizations.xml`
- Created by default when no `solutions/` subdirectory exists

#### YAML Source Control Format (v2.4.1+)
- Requires `solutions/` subdirectory with `*solution.yml` files
- Used by native Dataverse Git integration and `pac solution clone`
- Structure:
```
<folder>/
├── solutions/
│   └── <SolutionUniqueName>/
│       ├── solution.yml
│       ├── solutioncomponents.yml
│       ├── rootcomponents.yml
│       └── missingdependencies.yml
├── publishers/
│   └── <PublisherUniqueName>/
│       └── publisher.yml
└── [component folders — entities/, workflows/, canvasapps/, ...]
```

> **Important**: YAML format requires Microsoft.PowerApps.CLI **version 2.4.1 or later**.

### Equivalent SolutionPackager.exe

```bash
SolutionPackager.exe /action:Pack /zipfile:SolutionA.zip /folder:C:\repos\myrepo /SolutionName:SolutionA
```

---

## pac solution publish

Publish all customizations.

### Example

```powershell
pac solution publish
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--async` | `-a` | No | Publish asynchronously (switch) |
| `--environment` | `-env` | No | Target Dataverse (Guid or URL) |
| `--max-async-wait-time` | `-wt` | No | Max async wait time in minutes (default: 60) |

---

## pac solution sync

Sync the current Dataverse solution project to the current state of the solution in your organization.

### Example

```powershell
pac solution sync
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--async` | `-a` | No | Sync asynchronously (switch) |
| `--environment` | `-env` | No | Target Dataverse (Guid or URL) |
| `--include` | `-i` | No | Settings to include (comma-separated) |
| `--localize` | `-loc` | No | Extract/merge string resources into .resx files |
| `--map` | `-m` | No | Path to mapping XML file |
| `--max-async-wait-time` | `-wt` | No | Max async wait time in minutes (default: 60) |
| `--packagetype` | `-p` | No | Extraction type: `Unmanaged`, `Managed`, or `Both` |
| `--solution-folder` | `-f` | No | Path to local unpacked solution folder |

---

## pac solution unpack

Extract solution components from solution.zip onto local filesystem (SolutionPackager).

### Example

```powershell
pac solution unpack --zipfile C:\SampleSolution.zip --folder .\SampleSolutionUnpacked\.
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--zipfile` | `-z` | Yes | Full path to the solution ZIP file |
| `--folder` | `-f` | No | Destination folder path |
| `--packagetype` | `-p` | No | Package type: `Unmanaged`, `Managed`, or `Both` |
| `--allowDelete` | `-ad` | No | Allow delete operations (default: false) |
| `--allowWrite` | `-aw` | No | Allow write operations (default: false) |
| `--clobber` | `-c` | No | Overwrite existing files |
| `--disablePluginRemap` | `-dpm` | No | Disable plugin type name remapping (default: false) |
| `--errorlevel` | `-e` | No | Logging error level |
| `--localize` | `-loc` | No | Extract/merge string resources into .resx files |
| `--log` | `-l` | No | Path to log file |
| `--map` | `-m` | No | Path to mapping XML file |
| `--singleComponent` | `-sc` | No | Process only a single component type |
| `--sourceLoc` | `-src` | No | Source language locale |
| `--useLcid` | `-lcid` | No | Use LCID instead of culture name |
| `--useUnmanagedFileForMissingManaged` | `-same` | No | Use unmanaged files for missing managed files |

### Remarks

By default, `pac solution unpack` extracts into the **XML format** (creates `Other\Solution.xml` hierarchy).

When working with solutions managed through native Dataverse Git integration or extracted via `pac solution clone`, the folder uses the **YAML source control format** (see pack section above for structure).

To repack a YAML-layout folder: `pac solution pack --folder <rootFolder>`. The `solutions/` subdirectory auto-detects YAML format.

---

## pac solution upgrade

Apply solution upgrade.

### Example

```powershell
pac solution upgrade --solution-name SampleSolution --async --max-async-wait-time 60
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--solution-name` | `-sn` | Yes | Name of the solution |
| `--async` | `-a` | No | Upgrade asynchronously (switch) |
| `--environment` | `-env` | No | Target Dataverse (Guid or URL) |
| `--max-async-wait-time` | `-wt` | No | Max async wait time in minutes (default: 60) |

---

## pac solution version

Update build or revision version for the solution.

### Examples

```powershell
# Set specific revision version
pac solution version --patchversion 2

# Use Git tags strategy
pac solution version --strategy gittags

# Set build version
pac solution version --buildversion 5

# Set revision version
pac solution version --revisionversion 3
```

### Parameters

| Parameter | Alias | Required | Description |
|-----------|-------|----------|-------------|
| `--buildversion` | `-bv` | No | Build version for the solution |
| `--revisionversion` | `-rv` | No | Revision version for the solution |
| `--strategy` | `-s` | No | Versioning strategy. Values: `None`, `GitTags`, `FileTracking`, `Solution` |
| `--filename` | `-fn` | No | Filename for FileTracking strategy |
| `--solutionPath` | `-sp` | No | Path to solution directory or Solution.xml |
| `--patchversion` | `-pv` | No | **Deprecated** - ignored |

### Strategy Notes

- **GitTags**: Requires `PacCli.PAT` environment variable for personal access token
- **FileTracking**: Uses a file to track version increments
- **Solution**: Uses solution version from Solution.xml

---

## Key Differences: `clone` vs `export`

| Aspect | `pac solution clone` | `pac solution export` |
|--------|----------------------|-----------------------|
| **Use case** | Need to **add new components** to the solution | Need to **modify existing content** without adding components |
| **Project file** | Creates a `.cdsproj` project file (supports references) | Does NOT create `.cdsproj` (no references) |
| **Directory structure** | Same as export + `.cdsproj` file | Same as clone minus `.cdsproj` |
| **Add references** | Yes (`pac solution add-reference`) | No |

> **Warning**: Never open solution zip files with standard tools. Always use `pac solution unpack` to extract contents.

---

## Solution Settings (`--include` values)

All commands that accept `--include` support these values (comma-separated):

| Setting | Description |
|---------|-------------|
| `autonumbering` | Auto-numbering settings |
| `calendar` | Calendar settings |
| `customization` | Customization settings |
| `emailtracking` | Email tracking settings |
| `externalapplications` | External application settings |
| `general` | General settings |
| `isvconfig` | ISV configuration |
| `marketing` | Marketing settings |
| `outlooksynchronization` | Outlook sync settings |
| `relationshiproles` | Relationship role settings |
| `sales` | Sales settings |

---

## Typical ALM Workflows

### Workflow 1: New Solution Development

```powershell
# 1. Initialize solution project
pac solution init --publisher-name developer --publisher-prefix dev

# 2. Add component references (e.g., code components)
pac solution add-reference --path c:\Projects\SampleComponent

# 3. Build/pack the solution
pac solution pack --zipfile C:\output\MySolution.zip --folder .\MySolution

# 4. Import to Dataverse
pac solution import --path C:\output\MySolution.zip
```

### Workflow 2: Clone Existing Solution for Modification

```powershell
# 1. Clone from Dataverse
pac solution clone --name MyExistingSolution

# 2. Modify files in the unpacked folder
# (edit XML/YAML files manually)

# 3. Pack back to zip
pac solution pack --zipfile C:\output\MySolution.zip --folder .\MyExistingSolution

# 4. Import back
pac solution import --path C:\output\MySolution.zip --publish-changes
```

### Workflow 3: Export → Unpack → Modify → Pack → Import

```powershell
# 1. Export from Dataverse
pac solution export --name MySolution --path C:\output\MySolution.zip --managed false

# 2. Unpack
pac solution unpack --zipfile C:\output\MySolution.zip --folder .\MySolutionUnpacked

# 3. Modify files...

# 4. Pack
pac solution pack --zipfile C:\output\MySolution_updated.zip --folder .\MySolutionUnpacked

# 5. Import
pac solution import --path C:\output\MySolution_updated.zip
```

### Workflow 4: CI/CD Pipeline

```powershell
# 1. Authenticate (non-interactive)
pac auth create --deviceCode

# 2. Export solution from DEV
pac solution export --name MySolution --path artifacts\MySolution.zip --managed false

# 3. Run solution checker
pac solution check --path artifacts\MySolution.zip --outputDirectory artifacts\check-results --geo UnitedStates

# 4. Import to TEST
pac auth select --index 2
pac solution import --path artifacts\MySolution.zip --publish-changes --force-overwrite

# 5. Promote to PROD
pac auth select --index 3
pac solution import --path artifacts\MySolution.zip --publish-changes
```

### Workflow 5: Solution Sync (Git-based ALM)

```powershell
# 1. Sync current state from Dataverse to local
pac solution sync

# 2. Commit changes to Git
git add .
git commit -m "Update solution components"

# 3. After Git pull on another machine, pack and import
pac solution pack --zipfile MySolution.zip --folder .
pac solution import --path MySolution.zip
```
