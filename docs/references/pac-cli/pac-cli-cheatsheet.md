# PAC CLI Quick-Reference Cheat Sheet

> **Purpose**: Fast lookup for common pac CLI operations
> **Detailed Reference**: See `pac-solution-reference.md` and `pac-cli-overview.md`

---

## Authentication

```bash
# Create auth profile (interactive)
pac auth create

# Create auth profile for specific environment
pac auth create --environment "HR-Dev"

# Non-interactive auth (CI/CD, Codespaces)
pac auth create --deviceCode

# Specify cloud
pac auth create --cloud USGovernment

# List all profiles
pac auth list

# Switch profile
pac auth select --index 2

# Delete profile
pac auth delete --index 3

# Clear all profiles
pac auth clear
```

---

## Solution Lifecycle

### Create / Initialize

```bash
# Initialize new solution project
pac solution init --publisher-name developer --publisher-prefix dev

# Add reference to another project
pac solution add-reference --path c:\Projects\SampleComponent
```

### Export / Import

```bash
# Export (unmanaged)
pac solution export --name MySolution --path .\MySolution.zip --managed false

# Export (managed)
pac solution export --name MySolution --path .\MySolution.zip --managed true

# Import
pac solution import --path .\MySolution.zip

# Import with options
pac solution import --path .\MySolution.zip --publish-changes --force-overwrite

# Delete solution
pac solution delete --solution-name MySolution
```

### Pack / Unpack

```bash
# Pack folder to zip
pac solution pack --zipfile .\MySolution.zip --folder .\MySolutionSrc

# Unpack zip to folder
pac solution unpack --zipfile .\MySolution.zip --folder .\MySolutionSrc

# Pack with managed type
pac solution pack --zipfile .\MySolution.zip --folder .\MySolutionSrc --packagetype Managed
```

### Clone / Sync

```bash
# Clone existing solution (creates .cdsproj)
pac solution clone --name MySolution

# Sync current state from Dataverse
pac solution sync

# Clone with settings
pac solution clone --name MySolution --include general,autonumbering
```

### Version Management

```bash
# Get current online version
pac solution online-version --solution-name MySolution

# Set online version
pac solution online-version --solution-name MySolution --solution-version 1.0.0.2

# Update local version (build)
pac solution version --buildversion 5

# Update local version (revision)
pac solution version --revisionversion 3

# Auto-version with Git tags
pac solution version --strategy gittags
```

### Upgrade

```bash
# Apply solution upgrade
pac solution upgrade --solution-name MySolution

# Async upgrade
pac solution upgrade --solution-name MySolution --async --max-async-wait-time 60
```

### Publish

```bash
# Publish all customizations
pac solution publish

# Async publish
pac solution publish --async
```

### List & Check

```bash
# List all solutions
pac solution list

# List as JSON
pac solution list --json

# Run Power Apps Checker
pac solution check --path .\MySolution.zip --geo UnitedStates

# Check with output directory
pac solution check --path .\MySolution.zip --outputDirectory .\check-results
```

### Settings & License

```bash
# Create deployment settings file
pac solution create-settings --solution-zip .\MySolution.zip --settings-file .\deploy-settings.json

# Add license info
pac solution add-license --planDefinitionFile .\plans.csv --planMappingFile .\mapping.csv
```

---

## Component Management

```bash
# Add component to solution (table = type 1)
pac solution add-solution-component --solutionUniqueName MySolution --component contact --componentType 1

# Add with required components
pac solution add-solution-component --solutionUniqueName MySolution --component account --componentType 1 --AddRequiredComponents
```

### Common Component Types

| Type | Component |
|------|-----------|
| 1 | Entity (Table) |
| 2 | Attribute (Column) |
| 9 | Option Set |
| 29 | Ribbon Customization |
| 59 | Saved Query (View) |
| 60 | System Form |
| 61 | Web Resource |
| 62 | Plugin Assembly |
| 70 | Workflow |
| 92 | App Module |

---

## Common `--include` Settings Values

```
autonumbering, calendar, customization, emailtracking, externalapplications,
general, isvconfig, marketing, outlooksynchronization, relationshiproles, sales
```

---

## Source Folder Formats

### XML Format (Legacy)
```
MySolution/
├── Other/
│   ├── Solution.xml
│   └── Customizations.xml
├── Entities/
├── Workflows/
└── ...
```

### YAML Format (v2.4.1+, Git Integration)
```
MySolution/
├── solutions/
│   └── MySolution/
│       ├── solution.yml
│       ├── solutioncomponents.yml
│       ├── rootcomponents.yml
│       └── missingdependencies.yml
├── publishers/
│   └── dev/
│       └── publisher.yml
└── [component folders]
```

> PAC auto-detects format: if `solutions/` subdirectory exists → YAML; otherwise → XML.

---

## Environment Targeting

Most commands accept `--environment`:

```bash
# By URL
pac solution list --environment https://myorg.crm.dynamics.com

# By ID (Guid)
pac solution import --path .\MySolution.zip --environment 00000000-0000-0000-0000-000000000000
```

---

## Async Operations

Many commands support async with wait time:

```bash
--async                    # Run asynchronously (switch)
--max-async-wait-time 60   # Wait up to 60 minutes (default)
```

Commands supporting async: `export`, `import`, `clone`, `sync`, `upgrade`, `publish`

---

## CI/CD Quick Reference

```bash
# Non-interactive auth
pac auth create --deviceCode

# Export from source env
pac solution export --name MySolution --path artifacts\MySolution.zip --managed false

# Quality check
pac solution check --path artifacts\MySolution.zip --geo UnitedStates

# Import to target env
pac solution import --path artifacts\MySolution.zip --publish-changes

# Version bump
pac solution version --strategy gittags
```

---

## clone vs export - When to Use Which

| Need | Use |
|------|-----|
| Add new components to solution | `clone` (creates .cdsproj) |
| Modify existing solution content only | `export` (no .cdsproj) |
| Need to add references | `clone` |
| Simple round-trip edit | `export` → `unpack` → edit → `pack` → `import` |
