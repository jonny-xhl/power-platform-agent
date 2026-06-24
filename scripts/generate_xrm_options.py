#!/usr/bin/env python
"""
生成 XRM.Options.js（OptionSet 语义化常量模块）—— 默认同时生成「单文件」与「按实体拆分」两种模式。

数据源为连接的 Dataverse 环境（client-credentials 静默认证，凭据见
config/environments.yaml + .env）。用于在 JS/HTML 中以
XRM.Options.entities.<entity>.<field>.<Name> 取代 picklist 魔法数字。

必须在仓库根目录运行：python scripts/generate_xrm_options.py

示例：
    # 默认：为 contact 生成两种模式到 webresources/shared/js/
    python scripts/generate_xrm_options.py

    # 指定多个实体、不含全局选项集
    python scripts/generate_xrm_options.py --entities contact account --no-include-global

    # 仅生成拆分模式
    python scripts/generate_xrm_options.py --entities contact --modes split
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# Windows GBK 控制台无法打印中文，统一改 utf-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 确保可从仓库根导入 framework
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from framework.agents.core_agent import CoreAgent  # noqa: E402
from framework.agents.metadata_agent import MetadataAgent  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 XRM.Options.js（OptionSet 语义化常量）")
    parser.add_argument(
        "--entities", nargs="*", default=None,
        help="实体逻辑名列表；不传则默认 contact（仅生成全局时传空）"
    )
    parser.add_argument("--include-global", dest="include_global", action="store_true", default=True)
    parser.add_argument("--no-include-global", dest="include_global", action="store_false", help="不导出全局选项集")
    parser.add_argument("--env", default="dev", help="目标环境（默认 dev）")
    parser.add_argument("--output-dir", default="webresources/shared/js", help="输出目录")
    parser.add_argument("--modes", default="single,split", help="生成模式，逗号分隔：single,split")
    parser.add_argument("--label-lang-name", default="en", choices=["en", "zh"], help="常量名语言")
    parser.add_argument("--label-lang-display", default="zh", choices=["en", "zh"], help="显示标签语言")
    args = parser.parse_args()

    entities = args.entities if args.entities is not None else ["contact"]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    core = CoreAgent()
    meta = MetadataAgent(core_agent=core)

    results = {}
    for mode in modes:
        if mode == "single":
            res = asyncio.run(meta.generate_optionset_constants(
                entities=entities,
                include_global=args.include_global,
                output_file=str(out_dir / "XRM.Options.js"),
                label_lang_name=args.label_lang_name,
                label_lang_display=args.label_lang_display,
                split_by_entity=False,
                environment=args.env,
            ))
        elif mode == "split":
            res = asyncio.run(meta.generate_optionset_constants(
                entities=entities,
                include_global=args.include_global,
                output_file=str(out_dir),  # split 模式 output_file 视为目录
                label_lang_name=args.label_lang_name,
                label_lang_display=args.label_lang_display,
                split_by_entity=True,
                environment=args.env,
            ))
        else:
            results[mode] = {"error": f"unknown mode: {mode}"}
            continue
        try:
            results[mode] = json.loads(res)
        except (ValueError, TypeError):
            results[mode] = {"raw": res}

    print(json.dumps(
        {"env": args.env, "entities": entities,
         "include_global": args.include_global, "results": results},
        indent=2, ensure_ascii=False,
    ))

    failed = [m for m, r in results.items() if isinstance(r, dict) and r.get("error")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
