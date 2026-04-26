#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档更新脚本

手动触发文档更新，支持多种模式：
- 分析模式：仅分析变更
- 建议模式：生成建议文件
- 自动模式：自动应用更新
- 交互模式：交互式确认

使用:
    python scripts/update_docs.py                    # 交互模式
    python scripts/update_docs.py --mode analyze     # 分析模式
    python scripts/update_docs.py --mode auto        # 自动模式
    python scripts/update_docs.py --all              # 全量更新
    python scripts/update_docs.py --skill design-dv-model  # 更新指定 SKILL
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "framework"))

from framework.agents.documentation_agent import DocumentationAgent


class UpdateMode:
    """更新模式"""
    ANALYZE = "analyze"      # 仅分析
    SUGGEST = "suggest"      # 生成建议
    AUTO = "auto"            # 自动应用
    INTERACTIVE = "interactive"  # 交互模式


async def analyze_changes(agent: DocumentationAgent, scope: str = "staged") -> dict:
    """分析变更"""
    print("🔍 正在分析代码变更...")

    result = await agent.analyze_changes(scope=scope)
    data = json.loads(result)

    print(f"\n📊 变更统计:")
    print(f"  总文件数: {data['changes']['total_files']}")
    print(f"  有意义变更: {data['changes']['significant_files']}")
    print(f"  Python 文件: {data['changes']['by_type']['python']}")
    print(f"  YAML 文件: {data['changes']['by_type']['yaml']}")

    print(f"\n📋 影响分析:")
    print(f"  影响文档数: {data['impacts']['total']}")
    print(f"  高置信度: {data['impacts']['high_confidence']}")
    print(f"  中置信度: {data['impacts']['medium_confidence']}")

    if data['impacts']['affected_docs']:
        print(f"\n📄 受影响的文档:")
        for doc in data['impacts']['affected_docs']:
            print(f"  - {doc}")

    return data


async def update_skills(
    agent: DocumentationAgent,
    skill_path: str = None,
    apply: bool = False
) -> dict:
    """更新 SKILL 文档"""
    if skill_path:
        print(f"🔄 正在更新 SKILL: {skill_path}")
    else:
        print("🔄 正在检测并更新 SKILL 文档...")

    result = await agent.update_skill(skill_path=skill_path, apply=apply)
    data = json.loads(result)

    for item in data.get("results", []):
        status = item.get("status")
        skill = item.get("skill")
        action = item.get("action", "")

        if status == "updated":
            print(f"  ✅ {skill}: 已更新")
        elif status == "suggestion_created":
            print(f"  💡 {skill}: 建议文件已创建 ({item.get('suggestion_file')})")
        elif status == "skipped":
            print(f"  ⏭️  {skill}: 跳过 ({item.get('reason')})")

    return data


async def update_claude_md(agent: DocumentationAgent, apply: bool = False) -> dict:
    """更新 CLAUDE.md"""
    print("🔄 正在更新 CLAUDE.md...")

    result = await agent.update_claude_md(apply=apply)
    data = json.loads(result)

    action = data.get("action", "")
    if action == "updated":
        print(f"  ✅ CLAUDE.md: 已更新")
    elif action == "suggestion_created":
        print(f"  💡 CLAUDE.md: 建议文件已创建 ({data.get('suggestion_file')})")

    return data


async def generate_summary(
    agent: DocumentationAgent,
    scope: str = "staged",
    output_file: str = None
) -> dict:
    """生成变更总结"""
    print("📝 正在生成变更总结...")

    result = await agent.generate_summary(scope=scope, output_file=output_file)
    data = json.loads(result)

    if data.get("success"):
        print(f"  ✅ 变更总结已生成: {data.get('output_file')}")

    return data


async def full_update(
    agent: DocumentationAgent,
    scope: str = "staged",
    auto_apply: bool = False
) -> dict:
    """执行完整更新流程"""
    print("🚀 开始完整文档更新流程...\n")

    result = await agent.full_update(scope=scope, auto_apply=auto_apply)
    data = json.loads(result)

    print(f"\n📋 更新摘要:")
    for action in data.get("actions", []):
        action_name = action.get("action", "")
        print(f"  - {action_name}: 完成")

    message = data.get("message", "")
    if message:
        print(f"\n{message}")

    return data


async def interactive_mode(agent: DocumentationAgent, scope: str = "staged"):
    """交互模式"""
    print("🎯 进入交互模式\n")

    # 1. 分析变更
    analysis = await analyze_changes(agent, scope)

    # 2. 询问用户要做什么
    print("\n" + "="*50)
    print("请选择要执行的操作:")
    print("  1. 更新 SKILL 文档")
    print("  2. 更新 CLAUDE.md")
    print("  3. 生成变更总结")
    print("  4. 执行完整更新")
    print("  5. 退出")
    print("="*50)

    while True:
        choice = input("\n请输入选项 (1-5): ").strip()

        if choice == "1":
            skill_path = input("SKILL 路径 (留空自动检测): ").strip() or None
            apply_input = input("直接应用更新? (y/N): ").strip().lower()
            apply = apply_input == "y"
            await update_skills(agent, skill_path, apply)

        elif choice == "2":
            apply_input = input("直接应用更新? (y/N): ").strip().lower()
            apply = apply_input == "y"
            await update_claude_md(agent, apply)

        elif choice == "3":
            await generate_summary(agent, scope)

        elif choice == "4":
            apply_input = input("自动应用所有更新? (y/N): ").strip().lower()
            auto_apply = apply_input == "y"
            await full_update(agent, scope, auto_apply)

        elif choice == "5":
            print("👋 再见!")
            break

        else:
            print("❌ 无效选项，请重新输入")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="文档更新脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/update_docs.py                    # 交互模式
  python scripts/update_docs.py --mode analyze     # 分析模式
  python scripts/update_docs.py --mode auto        # 自动应用更新
  python scripts/update_docs.py --scope unstaged    # 分析未暂存的变更
  python scripts/update_docs.py --skill design-dv-model  # 更新指定 SKILL
  python scripts/update_docs.py --all              # 全量更新并应用
        """
    )

    parser.add_argument(
        "--mode",
        choices=["analyze", "suggest", "auto", "interactive"],
        default="interactive",
        help="更新模式 (默认: interactive)"
    )

    parser.add_argument(
        "--scope",
        choices=["staged", "unstaged", "head"],
        default="staged",
        help="变更范围 (默认: staged)"
    )

    parser.add_argument(
        "--skill",
        help="更新指定 SKILL (如: design-dv-model)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="执行完整更新流程"
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="直接应用更新（不生成建议文件）"
    )

    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="不使用 LLM（仅分析变更）"
    )

    parser.add_argument(
        "--provider",
        help="LLM 提供商 (anthropic, zhipu, qwen, etc.)"
    )

    parser.add_argument(
        "--model",
        help="LLM 模型"
    )

    args = parser.parse_args()

    # 初始化代理
    print("🔧 初始化文档代理...")
    agent = DocumentationAgent(
        llm_provider=args.provider,
        llm_model=args.model
    )

    # 执行相应操作
    if args.mode == "analyze" or args.no_llm:
        await analyze_changes(agent, args.scope)

    elif args.mode == "suggest":
        if args.skill:
            await update_skills(agent, args.skill, apply=False)
        else:
            await update_skills(agent, apply=False)
            await update_claude_md(agent, apply=False)

    elif args.mode == "auto":
        if args.all:
            await full_update(agent, args.scope, auto_apply=True)
        else:
            if args.skill:
                await update_skills(agent, args.skill, apply=True)
            else:
                await update_skills(agent, apply=True)
                await update_claude_md(agent, apply=True)
            await generate_summary(agent, args.scope)

    elif args.mode == "interactive":
        await interactive_mode(agent, args.scope)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 操作已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
