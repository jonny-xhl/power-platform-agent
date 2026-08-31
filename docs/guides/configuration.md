# Configuration Guide

This guide explains how to configure Power Platform Agent.

## Configuration Overview

The project uses a **layered configuration approach**:

| File | Purpose | Contains |
|------|---------|----------|
| `.env` | **Secrets only** (workspace-level) | Dataverse credentials |
| `config/environments.yaml` | **Environment config** | Dataverse URLs, settings |
| `config/publishers.yaml` | **Publisher + naming** | Publisher prefix, naming rules, validation |
| `config/pipeline.yaml` | **CI/CD pipeline** | Branch→environment→strategy mapping |
| `config/environment_settings.yaml` | **Post-deploy config** | Connection refs, env variables |

## Quick Setup

### 1. Create `.env` file

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```bash
# Dataverse credentials
DEV_CLIENT_ID=your-client-id
DEV_CLIENT_SECRET=your-client-secret
DEV_TENANT_ID=your-tenant-id
```

### 2. Configure environments (optional)

Edit `config/environments.yaml` to match your Dataverse environments:

```yaml
environments:
  dev:
    url: "https://your-org.crm5.dynamics.com"
    client_id: "${DEV_CLIENT_ID}"        # References .env
    client_secret: "${DEV_CLIENT_SECRET}" # References .env
```

## Environment Variable Reference

### Dataverse Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `DEV_CLIENT_ID` | Azure AD client ID | `GUID` |
| `DEV_CLIENT_SECRET` | Azure AD client secret | `secret` |
| `DEV_TENANT_ID` | Azure AD tenant ID | `GUID` (optional) |

## Variable Expansion in YAML

YAML files support `${VAR_NAME}` syntax to reference environment variables:

```yaml
# Single variable
client_id: "${DEV_CLIENT_ID}"

# With default value
tenant_id: "${DEV_TENANT_ID:common}"

# In strings
url: "https://${ORG}.crm.dynamics.com"
```

## Loading Configuration in Code

```python
from framework_power.client.env_config import load_yaml_with_env, load_env_file

# 1. Load workspace .env (auto-discovered; also explicit path)
load_env_file()

# 2. Load YAML with ${VAR} expansion
config = load_yaml_with_env("config/environments.yaml")
print(config["environments"]["dev"]["url"])
```

## Configuration Priority

When multiple sources define the same value:

1. **Direct parameters** (function arguments)
2. **Environment variables** (from `.env` or system)
3. **YAML files** (with `${VAR}` expansion)
4. **Default values** (built-in)

## Security Best Practices

1. **Never commit `.env`** - It's in `.gitignore`
2. **Use different credentials** for dev/test/prod
3. **Rotate keys regularly** - Update `.env` when needed
4. **Limit access** - Share `.env` only with trusted team members

## Troubleshooting

### Credentials not loading

```bash
# Check if .env exists
ls -la .env

# Verify format (no spaces around =)
# Correct:  DEV_CLIENT_ID=abc123
# Wrong:   DEV_CLIENT_ID = abc123
```

### YAML variables not expanding

```python
# Use load_yaml_with_env (expands ${VAR}) instead of plain yaml.safe_load
from framework_power.client.env_config import load_yaml_with_env
config = load_yaml_with_env("config/environments.yaml")
```

### Test your configuration

```bash
# 引擎侧冒烟：列出 workspace 内的表定义（会走完整认证链）
python -m framework_power --workspace <ws> list
```
