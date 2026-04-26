# Configuration Guide

This guide explains how to configure Power Platform Agent.

## Configuration Overview

The project uses a **layered configuration approach**:

| File | Purpose | Contains |
|------|---------|----------|
| `.env` | **Secrets only** | API keys, credentials |
| `config/environments.yaml` | **Environment config** | Dataverse URLs, settings (references `.env`) |
| `config/hermes_profile.yaml` | **Project settings** | Naming rules, LLM config, defaults |
| `config/naming_rules.yaml` | **Naming conventions** | Schema name patterns |

## Quick Setup

### 1. Create `.env` file

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```bash
# LLM for documentation updates
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

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

### 3. Configure LLM (optional)

Edit `config/hermes_profile.yaml` to set LLM preferences:

```yaml
llm:
  provider: "${LLM_PROVIDER:anthropic}"  # Use .env or default
  temperature: 0.3
  max_tokens: 4000
```

## Environment Variable Reference

### LLM Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider | `anthropic`, `zhipu`, `qwen` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `ZHIPUAI_API_KEY` | Zhipu AI API key | `...` |
| `DASHSCOPE_API_KEY` | Qwen/DashScope key | `sk-...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |

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
provider: "${LLM_PROVIDER:anthropic}"

# In strings
url: "https://${ORG}.crm.dynamics.com"

# Nested expansion
connection_string: "Server=${DB_HOST};Database=${DB_NAME}"
```

## Loading Configuration in Code

```python
from framework.utils.env_config import EnvConfig, load_yaml_with_env

# Option 1: Use EnvConfig manager
config = EnvConfig()
provider = config.get("llm.provider", "anthropic")

# Option 2: Load YAML with auto-expansion
env_config = load_yaml_with_env("config/hermes_profile.yaml")

# Option 3: Direct environment access
import os
api_key = os.getenv("ANTHROPIC_API_KEY")
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
# Use load_yaml_with_env instead of yaml.safe_load
from framework.utils.env_config import load_yaml_with_env
config = load_yaml_with_env("config/environments.yaml")
```

### Test your configuration

```bash
# Test environment loading
python -c "
from framework.utils.env_config import EnvConfig
config = EnvConfig()
print('Provider:', config.get('llm.provider'))
print('Current env:', config.get('environments.current'))
"
```
