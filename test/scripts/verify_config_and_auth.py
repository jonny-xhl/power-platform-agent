#!/usr/bin/env python3
"""
Power Platform Agent - Configuration and Authentication Verification
验证配置文件是否正确，并测试认证功能

Usage:
    # 验证配置（不需要认证）
    python test/scripts/verify_config_and_auth.py

    # 验证配置并测试认证（需要环境变量）
    PP_ACCESS_TOKEN=your_token python test/scripts/verify_config_and_auth.py --test-auth

    # 使用客户端凭据认证
    PP_CLIENT_ID=your_id PP_CLIENT_SECRET=your_secret python test/scripts/verify_config_and_auth.py --test-auth
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import argparse


# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "framework"))


class TestResult:
    """测试结果"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: List[str] = []

    def add_pass(self, message: str = ""):
        """添加通过项"""
        self.passed += 1
        print(f"  [OK] {message}")

    def add_fail(self, message: str):
        """添加失败项"""
        self.failed += 1
        self.errors.append(message)
        print(f"  [FAIL] {message}")

    @property
    def total(self) -> int:
        return self.passed + self.failed

    def summary(self) -> bool:
        """打印摘要并返回是否全部通过"""
        print()
        print("=" * 60)
        print(f"测试结果: {self.passed} 通过, {self.failed} 失败")
        print("=" * 60)

        if self.errors:
            print("\n失败的测试:")
            for error in self.errors:
                print(f"  - {error}")

        return self.failed == 0


def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """加载YAML文件"""
    try:
        import yaml
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"  [ERROR] 无法加载 {file_path}: {e}")
        return {}


def verify_config_structure(result: TestResult) -> bool:
    """验证配置文件结构"""
    print("\n1. 验证配置文件结构")

    config_dir = PROJECT_ROOT / "config"

    # 检查配置目录
    if not config_dir.exists():
        result.add_fail("配置目录不存在: config/")
        return False
    result.add_pass("配置目录存在")

    # 检查必需的配置文件
    required_files = [
        "hermes_profile.yaml",
        "environments.yaml",
    ]

    for filename in required_files:
        file_path = config_dir / filename
        if file_path.exists():
            result.add_pass(f"配置文件存在: {filename}")
        else:
            result.add_fail(f"配置文件不存在: {filename}")

    return True


def verify_hermes_profile(result: TestResult) -> bool:
    """验证 hermes_profile.yaml 配置"""
    print("\n2. 验证 hermes_profile.yaml")

    config_file = PROJECT_ROOT / "config" / "hermes_profile.yaml"
    config = load_yaml_file(config_file)

    if not config:
        result.add_fail("无法加载 hermes_profile.yaml")
        return False

    result.add_pass("hermes_profile.yaml 加载成功")

    # 验证必需的顶层键
    hermes_section = config.get("hermes", {})
    if hermes_section:
        result.add_pass(f"hermes.profile_name: {hermes_section.get('profile_name')}")
        result.add_pass(f"hermes.version: {hermes_section.get('version')}")
    else:
        result.add_fail("缺少 hermes 配置节")

    # 验证环境配置
    env_section = config.get("environments", {})
    if env_section:
        current_env = env_section.get("current", "dev")
        result.add_pass(f"environments.current: {current_env}")
    else:
        result.add_fail("缺少 environments 配置节")

    # 验证命名配置
    naming_section = config.get("naming", {})
    if naming_section:
        prefix = naming_section.get("publisher_prefix", "new")
        result.add_pass(f"naming.publisher_prefix: {prefix}")

        schema_config = naming_section.get("schema_name", {})
        if schema_config:
            style = schema_config.get("style", "lowercase")
            result.add_pass(f"naming.schema_name.style: {style}")
    else:
        result.add_fail("缺少 naming 配置节")

    return True


def verify_environments_config(result: TestResult) -> bool:
    """验证 environments.yaml 配置"""
    print("\n3. 验证 environments.yaml")

    config_file = PROJECT_ROOT / "config" / "environments.yaml"
    config = load_yaml_file(config_file)

    if not config:
        result.add_fail("无法加载 environments.yaml")
        return False

    result.add_pass("environments.yaml 加载成功")

    # 验证环境配置
    environments = config.get("environments", {})
    if not environments:
        result.add_fail("没有定义任何环境")
        return False

    result.add_pass(f"已定义 {len(environments)} 个环境")

    for env_name, env_config in environments.items():
        print(f"\n  环境: {env_name}")

        # 验证必需字段
        if "url" in env_config:
            result.add_pass(f"  {env_name}.url: {env_config['url']}")
        else:
            result.add_fail(f"{env_name} 缺少 url 配置")

        if "name" in env_config:
            result.add_pass(f"  {env_name}.name: {env_config['name']}")

        # 检查认证配置
        has_client_id = "client_id" in env_config and env_config["client_id"]
        has_client_secret = "client_secret" in env_config and env_config["client_secret"]

        if has_client_id:
            client_id = env_config["client_id"]
            # 检查是否为环境变量占位符
            if client_id.startswith("${") and client_id.endswith("}"):
                env_var = client_id[2:-1].upper()
                value = os.environ.get(env_var)
                if value:
                    result.add_pass(f"  {env_name}.client_id: 从环境变量 {env_var} 获取")
                else:
                    result.add_pass(f"  {env_name}.client_id: 环境变量 {env_var} 未设置（测试时需要）")
            else:
                result.add_pass(f"  {env_name}.client_id: 已配置")

        if has_client_secret:
            client_secret = env_config["client_secret"]
            if client_secret.startswith("${") and client_secret.endswith("}"):
                env_var = client_secret[2:-1].upper()
                if os.environ.get(env_var):
                    result.add_pass(f"  {env_name}.client_secret: 从环境变量获取")
                else:
                    result.add_pass(f"  {env_name}.client_secret: 环境变量未设置")
            else:
                result.add_pass(f"  {env_name}.client_secret: 已配置")

    # 验证当前环境
    current = config.get("current", "dev")
    if current in environments:
        result.add_pass(f"当前环境: {current}")
    else:
        result.add_fail(f"当前环境 '{current}' 不在定义的环境中")

    return True


def verify_naming_converter(result: TestResult) -> bool:
    """验证命名转换器"""
    print("\n4. 验证命名转换器")

    try:
        from framework.utils.naming_converter import NamingConverter

        converter = NamingConverter()
        result.add_pass("NamingConverter 实例化成功")

        # 测试基本转换
        test_cases = [
            ("MyEntity", False, "schema_name"),
            ("AnotherEntity", True, "schema_name_standard"),
            ("TestEntity", False, "schema_name_simple"),
        ]

        for input_name, is_standard, test_type in test_cases:
            try:
                converted_name = converter.convert_schema_name(input_name, is_standard)
                result.add_pass(f"命名转换 ({test_type}): {input_name} -> {converted_name}")

            except Exception as e:
                result.add_fail(f"命名转换失败 {input_name}: {e}")

        return True

    except ImportError as e:
        result.add_fail(f"无法导入 NamingConverter: {e}")
        return False
    except Exception as e:
        result.add_fail(f"NamingConverter 初始化失败: {e}")
        return False


def verify_core_agent_init(result: TestResult) -> bool:
    """验证 CoreAgent 初始化"""
    print("\n5. 验证 CoreAgent 初始化")

    try:
        from framework.agents.core_agent import CoreAgent

        agent = CoreAgent()
        result.add_pass("CoreAgent 实例化成功")

        # 验证初始状态
        if agent._config is not None:
            result.add_pass("CoreAgent 配置已加载")
        else:
            result.add_fail("CoreAgent 配置未加载")

        if agent._current_environment:
            result.add_pass(f"当前环境: {agent._current_environment}")
        else:
            result.add_fail("当前环境未设置")

        if agent.naming_converter is not None:
            result.add_pass("NamingConverter 已初始化")
        else:
            result.add_fail("NamingConverter 未初始化")

        # 测试获取环境配置
        try:
            env_config = agent.get_environment_config()
            result.add_pass(f"可获取环境配置: {env_config.get('name', 'N/A')}")
        except Exception as e:
            result.add_fail(f"获取环境配置失败: {e}")

        return True

    except ImportError as e:
        result.add_fail(f"无法导入 CoreAgent: {e}")
        return False
    except Exception as e:
        result.add_fail(f"CoreAgent 初始化失败: {e}")
        return False


def verify_dataverse_client(result: TestResult) -> bool:
    """验证 DataverseClient 初始化"""
    print("\n6. 验证 DataverseClient")

    try:
        from framework.utils.dataverse_client import DataverseClient

        client = DataverseClient(environment="dev")
        result.add_pass("DataverseClient 实例化成功")

        # 验证属性
        if client.environment == "dev":
            result.add_pass(f"环境: {client.environment}")

        # 验证配置加载
        if client.config:
            result.add_pass("配置已加载")
        else:
            result.add_fail("配置未加载")

        # 验证 base_url
        base_url = client.base_url
        if base_url:
            result.add_pass(f"API Base URL: {base_url}")
        else:
            result.add_fail("无法获取 API Base URL")

        return True

    except ImportError as e:
        result.add_fail(f"无法导入 DataverseClient: {e}")
        return False
    except Exception as e:
        result.add_fail(f"DataverseClient 初始化失败: {e}")
        return False


async def verify_authentication(result: TestResult, test_auth: bool = False) -> bool:
    """验证认证功能"""
    print("\n7. 验证认证功能")

    try:
        from framework.agents.core_agent import CoreAgent

        agent = CoreAgent()

        # 检查认证方式
        access_token = os.environ.get("PP_ACCESS_TOKEN")
        client_id = os.environ.get("PP_CLIENT_ID")
        client_secret = os.environ.get("PP_CLIENT_SECRET")

        if not test_auth:
            result.add_pass("认证功能可用 (跳过实际认证测试，使用 --test-auth 进行测试)")

            # 显示如何进行认证测试
            print("\n  要进行认证测试，设置以下环境变量之一:")
            print("    - PP_ACCESS_TOKEN: 直接使用访问令牌 (推荐)")
            print("    - PP_CLIENT_ID + PP_CLIENT_SECRET: 使用客户端凭据")

            return True

        # 使用 access_token 认证
        if access_token:
            print(f"\n  使用 access_token 认证...")
            login_result = await agent.login(access_token=access_token)

            if login_result.get("success"):
                result.add_pass(f"认证成功: {login_result.get('auth_mode')}")
                result.add_pass(f"环境: {login_result.get('environment')}")

                # 测试状态
                status = await agent.status()
                result.add_pass(f"已认证环境: {status.get('authenticated_environments')}")

                # 测试健康检查
                health = await agent.health_check()
                result.add_pass(f"健康检查: {health.get('status')}")

            else:
                result.add_fail(f"认证失败: {login_result.get('error')}")

        # 使用客户端凭据认证
        elif client_id and client_secret:
            print(f"\n  使用客户端凭据认证...")
            login_result = await agent.login(
                client_id=client_id,
                client_secret=client_secret
            )

            if login_result.get("success"):
                result.add_pass(f"认证成功: {login_result.get('auth_mode')}")
            else:
                result.add_fail(f"认证失败: {login_result.get('error')}")

        else:
            result.add_fail("未设置认证凭据 (PP_ACCESS_TOKEN 或 PP_CLIENT_ID + PP_CLIENT_SECRET)")

        return True

    except ImportError as e:
        result.add_fail(f"无法导入 CoreAgent: {e}")
        return False
    except Exception as e:
        result.add_fail(f"认证测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_tests(test_auth: bool = False) -> bool:
    """运行所有测试"""
    result = TestResult()

    print("=" * 60)
    print("Power Platform Agent - 配置和认证验证")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")

    # 运行测试
    verify_config_structure(result)
    verify_hermes_profile(result)
    verify_environments_config(result)
    verify_naming_converter(result)
    verify_core_agent_init(result)
    verify_dataverse_client(result)
    await verify_authentication(result, test_auth=test_auth)

    # 打印摘要
    return result.summary()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="验证 Power Platform Agent 配置和认证"
    )
    parser.add_argument(
        "--test-auth",
        action="store_true",
        help="执行认证测试（需要设置环境变量）"
    )

    args = parser.parse_args()

    import asyncio
    success = asyncio.run(run_tests(test_auth=args.test_auth))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
