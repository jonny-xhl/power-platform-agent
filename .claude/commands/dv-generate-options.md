从 Dataverse 环境重新生成 OptionSet 语义化常量模块 `XRM.Options*`（默认**同时**生成「单文件」与「按实体拆分」两种模式），用于在 JS/HTML 中以 `XRM.Options.entities.<entity>.<field>.<Name>` 取代 picklist 魔法数字。数据源为环境（非 YAML）。

参数: `$ARGUMENTS`（实体逻辑名，空格分隔，如 `contact account`；为空时默认 `contact`）

## 默认行为（`scripts/generate_xrm_options.py`）
- 实体：`$ARGUMENTS` 或默认 `contact`
- 模式：`single,split`（两种都生成）
- `include_global=true`、`env=dev`、输出目录 `webresources/shared/js/`
- 常量名语言 `en`（英文标签→PascalCase，仅中文标签时回退 `Option{value}`），显示标签 `zh`

## 执行流程

### Step 1: 运行生成脚本（在仓库根目录）
```bash
python scripts/generate_xrm_options.py --entities <实体列表>
```
若 `$ARGUMENTS` 为空，去掉 `--entities` 参数即可走默认 `contact`。常见可选项：
- `--no-include-global`：不导出全局选项集（contact 这类测试建议带上，避免拖入上百个全局选项集）
- `--modes single` 或 `--modes split`：只生成一种模式
- `--env <环境>`、`--output-dir <目录>`、`--label-lang-name en|zh`

### Step 2: 清理上一轮的残留文件
该脚本**不会删除**旧产物。若本轮范围缩小或关闭了 global，需手动删除不再需要的文件，例如：
```bash
# 本轮不含全局时，删除上一轮可能遗留的全局文件
rm -f webresources/shared/js/XRM.Options.global.js
# 本轮不再包含某实体时，删除该实体的旧文件
rm -f webresources/shared/js/XRM.Options.<旧实体>.js
```

### Step 3: 语法校验
对生成的每个文件跑 `node --check`：
```bash
for f in webresources/shared/js/XRM.Options*.js; do node --check "$f" && echo "OK $f"; done
```
任一失败必须修复后再继续。

### Step 4: 汇报
简述两种模式各自的产物文件、`global_count`/`entity_count`/`field_count`/`option_count`，并提醒：
- **同一 form 不要同时挂「单文件」与「拆分」两种模式**（二者都会定义 `window.XRM.Options`，会冲突）。
- 拆分模式下，form 窗体库按顺序挂 `XRM.Options.core.js` + `XRM.Options.<entity>.js`（用到全局再加 `XRM.Options.global.js`）；part 文件依赖 core 先加载，顺序错会抛错。

## 备注
- 认证走 client-credentials 静默流程（凭据在 `config/environments.yaml` + `.env`），无需交互登录。
- 本脚本是 `metadata_generate_optionset_constants` MCP 工具的离线等价物；MCP server 重启后也可直接用该工具。
