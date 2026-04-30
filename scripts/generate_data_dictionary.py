#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据字典生成脚本

从 metadata/ 自动生成数据字典 Markdown 文档

功能:
1. 解析 metadata/tables/*.yaml
2. 解析 metadata/optionsets/*.yaml
3. 过滤虚拟字段
4. 生成 Markdown 文档
5. 更新汇总索引

使用:
    python scripts/generate_data_dictionary.py --all              # 生成所有
    python scripts/generate_data_dictionary.py --files file1.yaml  # 生成指定文件
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# 虚拟字段检测模式
VIRTUAL_FIELD_PATTERNS = {
    'lookup_name': r'_[a-z]+_name$',  # Lookup 的 _name 后缀
}


class VirtualFieldFilter:
    """虚拟字段过滤器"""

    @staticmethod
    def is_virtual_field(field: Dict[str, Any]) -> bool:
        """
        判断是否为虚拟字段

        Dataverse 虚拟字段类型:
        1. Lookup 的 _name 后缀 (如: new_primary_contact_id_name)
        2. 计算字段 (is_calculated: true)
        3. 汇总/Rollup 字段 (aggregate_type 存在)

        Args:
            field: 字段定义字典

        Returns:
            bool: True 表示虚拟字段, 应被过滤
        """
        schema_name = field.get('name', field.get('schema_name', ''))

        # Lookup 的 _name 后缀
        if re.search(VIRTUAL_FIELD_PATTERNS['lookup_name'], schema_name):
            return True

        # 计算字段
        if field.get('is_calculated'):
            return True

        # 汇总字段
        if field.get('aggregate_type'):
            return True

        # Virtual 类型
        if field.get('type') == 'Virtual':
            return True

        return False


class YamlParser:
    """YAML 解析器"""

    @staticmethod
    def load_yaml(file_path: Path) -> Optional[Dict[str, Any]]:
        """加载 YAML 文件"""
        try:
            import yaml
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return None

    @staticmethod
    def load_all_tables(tables_dir: Path) -> List[Dict[str, Any]]:
        """加载所有表定义"""
        tables = []
        for yaml_file in tables_dir.glob('*.yaml'):
            data = YamlParser.load_yaml(yaml_file)
            if data and data.get('schema'):
                tables.append({
                    'data': data,
                    'file_path': yaml_file,
                    'file_name': yaml_file.stem
                })
        return tables

    @staticmethod
    def load_all_optionsets(optionsets_dir: Path) -> List[Dict[str, Any]]:
        """加载所有选项集定义"""
        optionsets = []
        for yaml_file in optionsets_dir.glob('*.yaml'):
            data = YamlParser.load_yaml(yaml_file)
            if data:
                optionsets.append({
                    'data': data,
                    'file_path': yaml_file,
                    'file_name': yaml_file.stem
                })
        return optionsets


class MarkdownGenerator:
    """Markdown 生成器"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_table_doc(self, table: Dict[str, Any]) -> Path:
        """生成单个表的数据字典文档"""
        data = table['data']
        schema = data.get('schema', {})
        attributes = data.get('attributes', [])
        relationships = data.get('relationships', [])

        schema_name = schema.get('schema_name', 'unknown')
        display_name = schema.get('display_name', '')
        description = schema.get('description', '')
        ownership_type = schema.get('ownership_type', 'UserOwned')

        # 过滤虚拟字段
        filtered_attributes = [
            attr for attr in attributes
            if not VirtualFieldFilter.is_virtual_field(attr)
        ]

        # 生成 Markdown 内容
        lines = [
            f"# {display_name} (`{schema_name}`)",
            "",
            f"**说明**: {description}",
            "",
            f"**所有权类型**: `{ownership_type}`",
            "",
            "---",
            "",
            "## 字段列表",
            "",
            "| Schema Name | 显示名称 | 类型 | 必填 | 说明 | 选项集引用 |",
            "|-------------|----------|------|------|------|------------|",
        ]

        for attr in filtered_attributes:
            name = attr.get('name', attr.get('schema_name', ''))
            display = attr.get('display_name', '')
            attr_type = attr.get('type', '')
            required = "是" if attr.get('required') else "否"
            desc = attr.get('description', '')
            option_ref = attr.get('option_set_ref', '')

            # 处理选项集
            options_info = ""
            if option_ref:
                options_info = f"[{option_ref}](../optionsets/{option_ref}.md)"
            elif attr.get('options'):
                options_info = "本地选项集"
                # 显示选项值
                options = attr.get('options', [])
                if options:
                    option_labels = ", ".join([
                        f"{opt.get('label', opt.get('label_zh', ''))}({opt.get('value', '')})"
                        for opt in options[:3]
                    ])
                    if len(options) > 3:
                        option_labels += "..."
                    desc = f"{desc}\\n选项: {option_labels}"

            lines.append(
                f"| `{name}` | {display} | `{attr_type}` | {required} | {desc} | {options_info} |"
            )

        # 添加关系
        if relationships:
            lines.extend([
                "",
                "## 关系",
                "",
                "| 关系名称 | 关联实体 | 关系类型 | 级联删除 |",
                "|----------|----------|----------|----------|",
            ])
            for rel in relationships:
                rel_name = rel.get('name', '')
                related = rel.get('related_entity', '')
                rel_type = rel.get('relationship_type', '')
                cascade = rel.get('cascade_delete', 'NoCascade')
                lines.append(f"| `{rel_name}` | `{related}` | {rel_type} | {cascade} |")

        # 添加元数据
        lines.extend([
            "",
            "---",
            "",
            "## 元数据",
            "",
            f"- **Schema Name**: `{schema_name}`",
            f"- **源文件**: [`{table['file_name']}.yaml`](../../metadata/tables/{table['file_name']}.yaml)",
            f"- **最后更新**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        ])

        # 写入文件
        output_path = self.output_dir / 'tables' / f'{schema_name}.md'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = '\n'.join(lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path

    def generate_optionset_doc(self, optionset: Dict[str, Any]) -> Path:
        """生成选项集文档"""
        data = optionset['data']

        # 处理全局选项集格式
        if 'global_optionsets' in data:
            return self._generate_global_optionsets_doc(optionset)

        # 处理单个选项集格式
        name = data.get('name', data.get('schema_name', 'unknown'))
        display_name = data.get('display_name', '')
        display_name_en = data.get('display_name_en', '')
        description = data.get('description', '')
        options = data.get('options', [])

        lines = [
            f"# {display_name} (`{name}`)",
            "",
            f"**英文名称**: {display_name_en}",
            "",
            f"**说明**: {description}",
            "",
            "---",
            "",
            "## 选项列表",
            "",
            "| 值 | 中文标签 | 英文标签 | 颜色 |",
            "|----|----------|----------|------|",
        ]

        for opt in options:
            value = opt.get('value', '')
            label_zh = opt.get('label_zh', opt.get('label', ''))
            label_en = opt.get('label_en', '')
            color = opt.get('color', '')

            color_display = f"![](# [{color}]{color})" if color else ''
            lines.append(f"| {value} | {label_zh} | {label_en} | {color_display} |")

        # 添加元数据
        lines.extend([
            "",
            "---",
            "",
            "## 元数据",
            "",
            f"- **Schema Name**: `{name}`",
            f"- **源文件**: [`{optionset['file_name']}.yaml`](../../metadata/optionsets/{optionset['file_name']}.yaml)",
            f"- **最后更新**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        ])

        output_path = self.output_dir / 'optionsets' / f'{name}.md'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = '\n'.join(lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path

    def _generate_global_optionsets_doc(self, optionset: Dict[str, Any]) -> Path:
        """生成全局选项集文档（包含多个选项集）"""
        data = optionset['data']
        optionsets = data.get('global_optionsets', [])

        # 为每个选项集生成单独的文档
        generated_files = []
        for opt_def in optionsets:
            name = opt_def.get('schema_name') or opt_def.get('name', 'unknown')
            display_name = opt_def.get('display_name', '')
            display_name_en = opt_def.get('display_name_en', '')
            description = opt_def.get('description', '')
            options = opt_def.get('options', [])

            lines = [
                f"# {display_name} (`{name}`)",
                "",
                f"**英文名称**: {display_name_en}",
                "",
                f"**说明**: {description}",
                "",
                "---",
                "",
                "## 选项列表",
                "",
                "| 值 | 中文标签 | 英文标签 | 颜色 |",
                "|----|----------|----------|------|",
            ]

            for opt in options:
                value = opt.get('value', '')
                label_zh = opt.get('label_zh', opt.get('label', ''))
                label_en = opt.get('label_en', '')
                color = opt.get('color', '')
                color_display = f"![](# [{color}]{color})" if color else ''
                lines.append(f"| {value} | {label_zh} | {label_en} | {color_display} |")

            lines.extend([
                "",
                "---",
                "",
                "## 元数据",
                "",
                f"- **Schema Name**: `{name}`",
                f"- **类型**: 全局选项集",
                f"- **源文件**: [`global_optionsets.yaml`](../../metadata/optionsets/global_optionsets.yaml)",
                f"- **最后更新**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
            ])

            output_path = self.output_dir / 'optionsets' / f'{name}.md'
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            generated_files.append(output_path)

        # 返回第一个生成的文件路径（或主索引路径）
        return generated_files[0] if generated_files else (self.output_dir / 'optionsets' / 'index.md')

    def generate_all_tables_doc(self, tables: List[Dict[str, Any]]) -> Path:
        """生成所有表的汇总文档"""
        lines = [
            "# 所有表结构定义",
            "",
            f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "---",
            "",
        ]

        for table in tables:
            schema = table['data'].get('schema', {})
            schema_name = schema.get('schema_name', 'unknown')
            display_name = schema.get('display_name', '')
            description = schema.get('description', '')
            attributes = table['data'].get('attributes', [])
            filtered_attributes = [
                attr for attr in attributes
                if not VirtualFieldFilter.is_virtual_field(attr)
            ]

            lines.extend([
                f"## {display_name} (`{schema_name}`)",
                "",
                f"{description}",
                "",
                f"**字段数**: {len(filtered_attributes)}",
                "",
                f"[查看详情](tables/{schema_name}.md)",
                "",
            ])

        output_path = self.output_dir / 'all_tables.md'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return output_path

    def generate_all_optionsets_doc(self, optionsets: List[Dict[str, Any]]) -> Path:
        """生成所有选项集的汇总文档"""
        lines = [
            "# 所有选项集定义",
            "",
            f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "---",
            "",
        ]

        # 收集所有选项集
        all_optionsets = []
        for opt_file in optionsets:
            data = opt_file['data']
            if 'global_optionsets' in data:
                all_optionsets.extend(data['global_optionsets'])
            else:
                all_optionsets.append(data)

        for opt in all_optionsets:
            name = opt.get('name', 'unknown')
            display_name = opt.get('display_name', '')
            description = opt.get('description', '')
            options = opt.get('options', [])

            lines.extend([
                f"## {display_name} (`{name}`)",
                "",
                f"{description}",
                "",
                f"**选项数**: {len(options)}",
                "",
                f"[查看详情](optionsets/{name}.md)",
                "",
            ])

        output_path = self.output_dir / 'all_optionsets.md'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return output_path

    def generate_index(self, tables: List[Dict[str, Any]], optionsets: List[Dict[str, Any]]) -> Path:
        """生成汇总索引"""
        lines = [
            "# 数据字典索引",
            "",
            f"*自动生成于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "---",
            "",
            "## 表 (Tables)",
            "",
            "| 表名 | Schema Name | 字段数 | 最后更新 | 说明 |",
            "|------|-------------|--------|----------|------|",
        ]

        for table in tables:
            schema = table['data'].get('schema', {})
            schema_name = schema.get('schema_name', 'unknown')
            display_name = schema.get('display_name', '')
            description = schema.get('description', '')
            attributes = table['data'].get('attributes', [])
            filtered_attributes = [
                attr for attr in attributes
                if not VirtualFieldFilter.is_virtual_field(attr)
            ]

            display_name_linked = f"[{display_name}](tables/{schema_name}.md)"
            lines.append(
                f"| {display_name_linked} | `{schema_name}` | {len(filtered_attributes)} | "
                f"{datetime.now().strftime('%Y-%m-%d')} | {description} |"
            )

        # 收集所有选项集
        lines.extend([
            "",
            "## 选项集 (Option Sets)",
            "",
            "| 选项集 | Schema Name | 类型 | 选项数量 |",
            "|--------|-------------|------|----------|",
        ])

        all_optionsets = []
        for opt_file in optionsets:
            data = opt_file['data']
            if 'global_optionsets' in data:
                all_optionsets.extend(data['global_optionsets'])
            else:
                all_optionsets.append(data)

        for opt in all_optionsets:
            name = opt.get('name', 'unknown')
            display_name = opt.get('display_name', '')
            options = opt.get('options', [])

            display_name_linked = f"[{display_name}](optionsets/{name}.md)"
            lines.append(f"| {display_name_linked} | `{name}` | 全局 | {len(options)} |")

        lines.extend([
            "",
            "---",
            "",
            "## 快速导航",
            "",
            "- [所有表结构](all_tables.md) - 完整的表结构列表",
            "- [所有选项集](all_optionsets.md) - 完整的选项集定义",
            "",
        ])

        output_path = self.output_dir / 'index.md'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return output_path


def main():
    parser = argparse.ArgumentParser(description='生成数据字典')
    parser.add_argument('--all', action='store_true', help='生成所有文档')
    parser.add_argument('--files', nargs='+', help='指定要处理的文件')
    parser.add_argument('--output', default='docs/data_dictionary', help='输出目录')
    parser.add_argument('--metadata', default='metadata', help='元数据目录')

    args = parser.parse_args()

    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    metadata_dir = project_root / args.metadata
    output_dir = project_root / args.output

    tables_dir = metadata_dir / 'tables'
    optionsets_dir = metadata_dir / 'optionsets'

    generator = MarkdownGenerator(output_dir)

    if args.all:
        # 生成所有文档
        print("正在生成所有文档...")

        tables = YamlParser.load_all_tables(tables_dir)
        optionsets = YamlParser.load_all_optionsets(optionsets_dir)

        for table in tables:
            path = generator.generate_table_doc(table)
            print(f"  [OK] {path}")

        for opt in optionsets:
            path = generator.generate_optionset_doc(opt)
            print(f"  [OK] {path}")

        generator.generate_all_tables_doc(tables)
        print(f"  [OK] {output_dir}/all_tables.md")

        generator.generate_all_optionsets_doc(optionsets)
        print(f"  [OK] {output_dir}/all_optionsets.md")

        generator.generate_index(tables, optionsets)
        print(f"  [OK] {output_dir}/index.md")

        print(f"\n[OK] Done! Generated {len(tables)} table docs and {len(optionsets)} optionset files.")

    elif args.files:
        # 生成指定文件
        print(f"正在处理指定文件: {args.files}")

        for file_path in args.files:
            file_path = Path(file_path)

            if not file_path.is_absolute():
                file_path = metadata_dir / file_path

            if str(file_path).startswith(str(tables_dir)):
                data = YamlParser.load_yaml(file_path)
                if data and data.get('schema'):
                    table = {
                        'data': data,
                        'file_path': file_path,
                        'file_name': file_path.stem
                    }
                    path = generator.generate_table_doc(table)
                    print(f"  [OK] {path}")

            elif str(file_path).startswith(str(optionsets_dir)):
                data = YamlParser.load_yaml(file_path)
                if data:
                    opt = {
                        'data': data,
                        'file_path': file_path,
                        'file_name': file_path.stem
                    }
                    path = generator.generate_optionset_doc(opt)
                    print(f"  [OK] {path}")

        # 更新索引
        tables = YamlParser.load_all_tables(tables_dir)
        optionsets = YamlParser.load_all_optionsets(optionsets_dir)
        generator.generate_index(tables, optionsets)
        print(f"  [OK] {output_dir}/index.md")

        print("\n[OK] Done!")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
