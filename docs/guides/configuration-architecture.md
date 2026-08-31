# Configuration Architecture

## 清晰的配置分层

```
┌─────────────────────────────────────────────────────────────────────┐
│                        配置文件层次                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  .env (本地开发，不提交)                                      │   │
│  │  ─────────────────────────────────────────────────────────── │   │
│  │  DEV_CLIENT_ID=xxx          ────────┐                      │   │
│  │  DEV_CLIENT_SECRET=xxx      ────────┤                      │   │
│  │                                    │   │                      │   │
│  └────────────────────────────────────┼─────────────────────────┘   │
│                                       │                              │
│  ┌────────────────────────────────────┼─────────────────────────┐   │
│  │  config/environments.yaml (提交)   │   │                      │   │
│  │  ──────────────────────────────────│────────────────────────│   │
│  │                                   ▼   │                      │   │
│  │  environments:                      │                      │   │
│  │    dev:                             │                      │   │
│  │      url: "https://..."             │                      │   │
│  │      client_id: "${DEV_CLIENT_ID}" ◄─┼─ 引用环境变量      │   │
│  │      client_secret: "${DEV_CLIENT_SECRET}"                  │   │
│  │                                   │   │                      │   │
│  │  或直接填写（不使用变量）：          │                      │   │
│  │    dev:                             │                      │   │
│  │      client_id: "actual-id"         │                      │   │
│  │      client_secret: "actual-secret" │                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ─────────────────────────────────────────────────────────── │   │
│  │  llm:                                                         │   │
│  │    provider: "${LLM_PROVIDER:anthropic}"  │                  │   │
│  │    model: "claude-sonnet-4-20250514"      │                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘

优先级（从高到低）:
  1. 函数参数 ────────→ LangChainLLMClient(api_key="...")
  2. 环境变量 ───────→ os.getenv("DEV_CLIENT_ID")
  3. YAML 默认值 ───→ "${DEV_CLIENT_ID:default_value}"
```

## 两种配置方式

### 方式 1: 直接配置（推荐用于本地开发）

**优点**: 简单直接，无需 `.env`

**.env** - 只放 LLM 密钥
```bash
```

**config/environments.yaml** - 直接填写凭证
```yaml
environments:
  dev:
    url: "https://org.crm.dynamics.com"
    client_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    client_secret: "your-secret~xxxxxxxxxxxx"
```

### 方式 2: 环境变量（推荐用于团队协作）

**优点**: 凭证与配置分离，安全

**.env** - 包含所有凭证
```bash

DEV_CLIENT_ID=xxx
DEV_CLIENT_SECRET=xxx
```

**config/environments.yaml** - 引用变量
```yaml
environments:
  dev:
    url: "https://org.crm.dynamics.com"
    client_id: "${DEV_CLIENT_ID}"
    client_secret: "${DEV_CLIENT_SECRET}"
```

## 配置加载逻辑

```python
# 系统按以下顺序查找配置值：

# 1. --workspace <path> 显式指定（最高优先级）
# 2. PP_WORKSPACE 环境变量
# 3. CWD/pp-workspace.yaml 锚文件
# 4. 从 CWD 向上搜索（如 git）

凭据解析（get_client）：
1. config/environments.yaml 引用 ${DEV_CLIENT_ID} 等变量
2. workspace .env（不提交）展开变量
3. MSAL client-credentials 获取/刷新 token（缓存 .pp-local/state/tokens.json）
```

## 安全建议

| 场景 | 建议方式 |
|------|---------|
| 个人本地项目 | 方式 1：直接在 YAML 中配置 |
| 团队协作项目 | 方式 2：使用环境变量 |
| CI/CD 部署 | 方式 2：使用 CI/CD secrets |
| 开源项目 | 方式 2：README 中说明需要的环境变量 |
