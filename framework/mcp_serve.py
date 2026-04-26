#!/usr/bin/env python3
"""
Power Platform MCP Server
MCP服务器入口 - 为Claude Code/Cursor提供工具访问

运行方式:
    python mcp_serve.py

或使用stdio模式:
    python mcp_serve.py --stdio

配置环境变量:
    TENANT_ID - Azure租户ID
    CLIENT_ID - 应用客户端ID
    CLIENT_SECRET - 应用客户端密钥
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加项目根目录到路径
# framework/mcp_serve.py 在 framework/ 目录下，需要向上两级到达项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.server import Server  # noqa: E402
from mcp.types import Tool, Resource, TextContent  # noqa: E402

from framework.agents.core_agent import CoreAgent, ToolHandler as CoreToolHandler  # noqa: E402
from framework.agents.metadata_agent import MetadataAgent  # noqa: E402
from framework.agents.plugin_agent import PluginAgent  # noqa: E402
from framework.agents.solution_agent import SolutionAgent  # noqa: E402


# ==================== MCP服务器 ====================

app = Server("power-platform-mcp")

# 全局代理实例
_core_agent: CoreAgent | None = None
_metadata_agent: MetadataAgent | None = None
_plugin_agent: PluginAgent | None = None
_solution_agent: SolutionAgent | None = None


def get_agents() -> tuple[CoreAgent | None, MetadataAgent | None, PluginAgent | None, SolutionAgent | None]:
    """获取所有代理实例（懒加载）"""
    global _core_agent, _metadata_agent, _plugin_agent, _solution_agent

    if _core_agent is None:
        _core_agent = CoreAgent()
        _metadata_agent = MetadataAgent(_core_agent)
        _plugin_agent = PluginAgent(_core_agent)
        _solution_agent = SolutionAgent(_core_agent)

    return _core_agent, _metadata_agent, _plugin_agent, _solution_agent


# ==================== 工具定义 ====================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用的MCP工具"""

    tools = [
        # ===== 认证与环境管理 =====
        Tool(
            name="auth_login",
            description="连接到Dataverse环境",
            inputSchema={
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "description": "环境名称 (dev/test/production)",
                        "enum": ["dev", "test", "production"]
                    },
                    "client_id": {
                        "type": "string",
                        "description": "客户端ID (可选，覆盖配置)"
                    },
                    "client_secret": {
                        "type": "string",
                        "description": "客户端密钥 (可选，覆盖配置)"
                    },
                    "tenant_id": {
                        "type": "string",
                        "description": "租户ID (可选，覆盖配置)"
                    }
                }
            }
        ),
        Tool(
            name="auth_status",
            description="查看当前连接状态",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="auth_logout",
            description="断开环境连接",
            inputSchema={
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "description": "环境名称"
                    }
                }
            }
        ),
        Tool(
            name="environment_switch",
            description="切换当前环境",
            inputSchema={
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "description": "目标环境名称"
                    }
                },
                "required": ["environment"]
            }
        ),
        Tool(
            name="environment_list",
            description="列出所有配置的环境",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        # ===== 元数据管理 =====
        Tool(
            name="metadata_parse",
            description="解析YAML元数据文件",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "YAML文件路径"
                    },
                    "type": {
                        "type": "string",
                        "description": "元数据类型",
                        "enum": ["table", "form", "view", "webresource", "ribbon", "sitemap"]
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="metadata_validate",
            description="验证元数据定义",
            inputSchema={
                "type": "object",
                "properties": {
                    "metadata_yaml": {
                        "type": "string",
                        "description": "YAML文件路径或JSON格式的元数据"
                    },
                    "schema": {
                        "type": "string",
                        "description": "Schema类型",
                        "enum": ["table_schema", "form_schema", "view_schema",
                                 "webresource_schema", "ribbon_schema",
                                 "sitemap_schema"]
                    }
                },
                "required": ["metadata_yaml", "schema"]
            }
        ),
        Tool(
            name="metadata_create_table",
            description="创建数据表",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_yaml": {
                        "type": "string",
                        "description": "表YAML文件路径或JSON格式数据"
                    },
                    "options": {
                        "type": "object",
                        "description": "创建选项",
                        "properties": {
                            "environment": {
                                "type": "string",
                                "description": "目标环境"
                            }
                        }
                    }
                },
                "required": ["table_yaml"]
            }
        ),
        Tool(
            name="metadata_create_attribute",
            description="创建字段",
            inputSchema={
                "type": "object",
                "properties": {
                    "attribute_yaml": {
                        "type": "string",
                        "description": "属性YAML文件路径或JSON格式数据"
                    },
                    "entity": {
                        "type": "string",
                        "description": "实体名称"
                    }
                },
                "required": ["attribute_yaml", "entity"]
            }
        ),
        Tool(
            name="metadata_create_form",
            description="创建表单",
            inputSchema={
                "type": "object",
                "properties": {
                    "form_yaml": {
                        "type": "string",
                        "description": "表单YAML文件路径或JSON格式数据"
                    }
                },
                "required": ["form_yaml"]
            }
        ),
        Tool(
            name="metadata_create_view",
            description="创建视图",
            inputSchema={
                "type": "object",
                "properties": {
                    "view_yaml": {
                        "type": "string",
                        "description": "视图YAML文件路径或JSON格式数据"
                    }
                },
                "required": ["view_yaml"]
            }
        ),
        Tool(
            name="metadata_get_form",
            description="获取实体的表单列表或单个表单详情（包含FormXml）",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "实体名称"
                    },
                    "form_id": {
                        "type": "string",
                        "description": "表单GUID（可选，指定后返回该表单完整数据）"
                    },
                    "form_type": {
                        "type": "integer",
                        "description": "表单类型: 2=Main, 5=Mobile, 6=QuickCreate, 7=QuickView",
                        "default": 2
                    }
                },
                "required": ["entity"]
            }
        ),
        Tool(
            name="metadata_export",
            description="导出云端元数据为YAML",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "实体名称"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "输出目录"
                    },
                    "metadata_type": {
                        "type": "string",
                        "description": "元数据类型",
                        "enum": ["table", "form", "view", "all"],
                        "default": "table"
                    }
                },
                "required": ["entity", "output_dir"]
            }
        ),
        Tool(
            name="metadata_diff",
            description="对比本地与云端元数据差异",
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {
                        "type": "string",
                        "description": "本地元数据文件路径"
                    },
                    "entity": {
                        "type": "string",
                        "description": "实体名称"
                    }
                },
                "required": ["local_path", "entity"]
            }
        ),
        Tool(
            name="metadata_apply",
            description="应用元数据到Dataverse",
            inputSchema={
                "type": "object",
                "properties": {
                    "metadata_type": {
                        "type": "string",
                        "description": "元数据类型",
                        "enum": ["table", "form", "view"]
                    },
                    "name": {
                        "type": "string",
                        "description": "名称（文件名或实体名）"
                    },
                    "environment": {
                        "type": "string",
                        "description": "目标环境"
                    }
                },
                "required": ["metadata_type", "name"]
            }
        ),
        Tool(
            name="metadata_list",
            description="列出元数据",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "元数据类型",
                        "enum": ["table", "attribute", "form"]
                    },
                    "entity": {
                        "type": "string",
                        "description": "实体名称 (attribute/form类型需要)"
                    }
                },
                "required": ["type"]
            }
        ),

        # ===== 命名规则 =====
        Tool(
            name="naming_convert",
            description="命名转换（根据配置规则）",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "输入名称"
                    },
                    "type": {
                        "type": "string",
                        "description": "类型",
                        "enum": ["schema_name", "webresource"],
                        "default": "schema_name"
                    },
                    "is_standard": {
                        "type": "boolean",
                        "description": "是否为标准实体",
                        "default": False
                    }
                },
                "required": ["input"]
            }
        ),
        Tool(
            name="naming_validate",
            description="验证命名是否符合规则",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "要验证的名称"
                    },
                    "type": {
                        "type": "string",
                        "description": "类型",
                        "enum": ["schema_name", "webresource"],
                        "default": "schema_name"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="naming_bulk_convert",
            description="批量转换命名",
            inputSchema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "项目列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string"
                                },
                                "is_standard": {
                                    "type": "boolean"
                                }
                            }
                        }
                    },
                    "type": {
                        "type": "string",
                        "description": "类型",
                        "enum": ["schema_name", "webresource", "attribute"],
                        "default": "schema_name"
                    }
                },
                "required": ["items"]
            }
        ),
        Tool(
            name="naming_rules_list",
            description="列出当前命名规则",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        # ===== 插件管理 =====
        Tool(
            name="plugin_build",
            description="构建插件项目",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "项目路径（.csproj文件或目录）"
                    },
                    "configuration": {
                        "type": "string",
                        "description": "构建配置",
                        "enum": ["Debug", "Release"],
                        "default": "Release"
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="plugin_deploy",
            description="部署插件",
            inputSchema={
                "type": "object",
                "properties": {
                    "assembly_path": {
                        "type": "string",
                        "description": "程序集路径（DLL文件）"
                    },
                    "environment": {
                        "type": "string",
                        "description": "目标环境"
                    }
                },
                "required": ["assembly_path"]
            }
        ),
        Tool(
            name="plugin_step_register",
            description="注册插件Step",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin_name": {
                        "type": "string",
                        "description": "插件名称"
                    },
                    "entity": {
                        "type": "string",
                        "description": "实体名称"
                    },
                    "message": {
                        "type": "string",
                        "description": "消息名称（Create, Update, Delete等）"
                    },
                    "stage": {
                        "type": "string",
                        "description": "阶段",
                        "enum": ["pre-validation", "pre-operation", "post-operation"],
                        "default": "post-operation"
                    },
                    "config": {
                        "type": "object",
                        "description": "配置选项"
                    }
                },
                "required": ["plugin_name", "entity", "message"]
            }
        ),
        Tool(
            name="plugin_step_list",
            description="列出插件Steps",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin_name": {
                        "type": "string",
                        "description": "插件名称"
                    },
                    "entity": {
                        "type": "string",
                        "description": "实体名称"
                    }
                }
            }
        ),
        Tool(
            name="plugin_step_delete",
            description="删除插件Step",
            inputSchema={
                "type": "object",
                "properties": {
                    "step_id": {
                        "type": "string",
                        "description": "Step ID"
                    }
                },
                "required": ["step_id"]
            }
        ),
        Tool(
            name="plugin_assembly_list",
            description="列出已部署的程序集",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="plugin_info",
            description="获取插件项目信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "项目路径"
                    }
                },
                "required": ["project_path"]
            }
        ),

        # ===== 解决方案管理 =====
        Tool(
            name="solution_export",
            description="导出解决方案",
            inputSchema={
                "type": "object",
                "properties": {
                    "solution_name": {
                        "type": "string",
                        "description": "解决方案名称"
                    },
                    "managed": {
                        "type": "boolean",
                        "description": "是否为托管解决方案",
                        "default": False
                    },
                    "output_path": {
                        "type": "string",
                        "description": "输出路径（可选）"
                    }
                },
                "required": ["solution_name"]
            }
        ),
        Tool(
            name="solution_import",
            description="导入解决方案",
            inputSchema={
                "type": "object",
                "properties": {
                    "solution_path": {
                        "type": "string",
                        "description": "解决方案文件路径"
                    },
                    "environment": {
                        "type": "string",
                        "description": "目标环境"
                    },
                    "publish": {
                        "type": "boolean",
                        "description": "是否发布自定义项",
                        "default": True
                    }
                },
                "required": ["solution_path"]
            }
        ),
        Tool(
            name="solution_diff",
            description="对比本地与解决方案差异",
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {
                        "type": "string",
                        "description": "本地元数据路径"
                    },
                    "solution_name": {
                        "type": "string",
                        "description": "解决方案名称"
                    }
                },
                "required": ["local_path", "solution_name"]
            }
        ),
        Tool(
            name="solution_sync",
            description="执行同步",
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "同步方向",
                        "enum": ["local_to_remote", "remote_to_local", "bidirectional"]
                    },
                    "components": {
                        "type": "array",
                        "description": "要同步的组件列表"
                    },
                    "environment": {
                        "type": "string",
                        "description": "目标环境"
                    }
                },
                "required": ["direction"]
            }
        ),
        Tool(
            name="solution_status",
            description="查看同步状态",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="solution_list",
            description="列出所有解决方案",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="solution_add_component",
            description="添加组件到解决方案",
            inputSchema={
                "type": "object",
                "properties": {
                    "component_type": {
                        "type": "string",
                        "description": "组件类型"
                    },
                    "component_id": {
                        "type": "string",
                        "description": "组件ID"
                    },
                    "solution_name": {
                        "type": "string",
                        "description": "解决方案名称"
                    }
                },
                "required": ["component_type", "component_id", "solution_name"]
            }
        ),

        # ===== 扩展管理 =====
        Tool(
            name="extension_list",
            description="列出已注册的扩展",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="health_check",
            description="健康检查",
            inputSchema={
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "description": "环境名称"
                    }
                }
            }
        ),
    ]

    return tools


# ==================== 工具调用处理 ====================

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    处理工具调用

    Args:
        name: 工具名称
        arguments: 工具参数

    Returns:
        文本内容列表
    """
    try:
        # 获取代理实例
        core_agent, metadata_agent, plugin_agent, solution_agent = get_agents()
        # get_agents() 确保所有代理都已初始化，这里断言它们不为 None
        assert core_agent is not None
        assert metadata_agent is not None
        assert plugin_agent is not None
        assert solution_agent is not None

        # 路由到相应的代理
        if name.startswith("auth_") or name.startswith("environment_"):
            handler = CoreToolHandler(core_agent)
            result = await handler.handle_tool(name, arguments)

        elif name.startswith("metadata_"):
            result = await metadata_agent.handle(name, arguments)

        elif name.startswith("plugin_"):
            result = await plugin_agent.handle(name, arguments)

        elif name.startswith("solution_"):
            result = await solution_agent.handle(name, arguments)

        elif name.startswith("naming_"):
            handler = CoreToolHandler(core_agent)
            result = await handler.handle_tool(name, arguments)

        elif name.startswith("extension_"):
            handler = CoreToolHandler(core_agent)
            result = await handler.handle_tool(name, arguments)

        elif name == "health_check":
            result = await core_agent.health_check(arguments.get("environment"))
            result = json.dumps(result, indent=2, ensure_ascii=False)

        else:
            logger.warning(f"Unknown tool requested: {name}")
            result = json.dumps({
                "error": f"Unknown tool: {name}"
            }, indent=2)

        return [TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error in call_tool for {name}: {e}", exc_info=True)
        error_result = json.dumps({
            "error": str(e),
            "tool": name
        }, indent=2, ensure_ascii=False)
        return [TextContent(type="text", text=error_result)]


# ==================== 资源定义 ====================

@app.list_resources()
async def list_resources() -> list[Resource]:
    """列出可用资源"""

    # framework/ 目录下的文件需要向上两级到达项目根目录
    project_root = Path(__file__).parent.parent

    # 导入 AnyUrl 来正确处理 URI 类型
    from pydantic import AnyUrl

    resources = [
        Resource(
            uri=AnyUrl(str(project_root / "metadata" / "**" / "*.yaml")),
            name="metadata_files",
            description="YAML元数据定义文件",
            mimeType="text/yaml"
        ),
        Resource(
            uri=AnyUrl(str(project_root / "plugins" / "**" / "*.csproj")),
            name="plugin_projects",
            description=".NET插件项目文件",
            mimeType="text/xml"
        ),
        Resource(
            uri=AnyUrl(str(project_root / "webresources" / "**" / "*")),
            name="webresource_files",
            description="Web Resource源文件",
            mimeType="text/plain"
        ),
        Resource(
            uri=AnyUrl(str(project_root / "config" / "**" / "*.yaml")),
            name="config_files",
            description="配置文件",
            mimeType="text/yaml"
        ),
    ]

    return resources


# ==================== 主函数 ====================

async def _run_stdio():
    """以 stdio 模式运行 MCP 服务器"""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def main():
    """主函数"""
    asyncio.run(_run_stdio())


if __name__ == "__main__":
    main()
