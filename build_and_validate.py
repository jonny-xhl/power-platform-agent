#!/usr/bin/env python3
"""
Power Platform Agent Build and Validation Script
构建和验证项目脚本
"""

import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class ProjectValidator:
    """项目验证器"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.errors = []
        self.warnings = []
        self.results = {
            "python_syntax": [],
            "yaml_syntax": [],
            "project_structure": {},
            "dependencies": {},
            "summary": {}
        }

    def validate_all(self) -> bool:
        """执行所有验证"""
        print("=" * 60)
        print("Power Platform Agent - Build and Validation")
        print("=" * 60)
        print()

        # 1. 验证Python语法
        print("1. Validating Python syntax...")
        self._validate_python_syntax()
        print(f"   Checked {len(self.results['python_syntax'])} Python files")
        if self.errors:
            print(f"   Errors: {len([e for e in self.errors if 'python' in e.lower()])}")
        print()

        # 2. 验证项目结构
        print("2. Validating project structure...")
        self._validate_project_structure()
        print(f"   Required components: {len(self.results['project_structure'].get('required', {}))}")
        print(f"   Optional components: {len(self.results['project_structure'].get('optional', {}))}")
        print()

        # 3. 验证依赖
        print("3. Validating dependencies...")
        self._validate_dependencies()
        print(f"   Required packages: {len(self.results['dependencies'].get('required', []))}")
        print()

        # 4. 验证YAML结构
        print("4. Validating YAML files...")
        self._validate_yaml_structure()
        print(f"   Checked {len(self.results['yaml_syntax'])} YAML files")
        print()

        # 5. 生成摘要
        print("5. Generating summary...")
        self._generate_summary()

        # 打印结果
        self._print_results()

        return len(self.errors) == 0

    def _validate_python_syntax(self):
        """验证Python文件语法"""
        python_files = list(self.project_root.rglob("*.py"))
        python_files = [f for f in python_files if "__pycache__" not in str(f)]

        for py_file in python_files:
            rel_path = py_file.relative_to(self.project_root)
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    ast.parse(f.read())
                self.results["python_syntax"].append({
                    "file": str(rel_path),
                    "status": "OK"
                })
            except SyntaxError as e:
                self.errors.append(f"Python syntax error in {rel_path}: {e}")
                self.results["python_syntax"].append({
                    "file": str(rel_path),
                    "status": "ERROR",
                    "message": str(e)
                })
            except Exception as e:
                self.warnings.append(f"Could not read {rel_path}: {e}")
                self.results["python_syntax"].append({
                    "file": str(rel_path),
                    "status": "WARNING",
                    "message": str(e)
                })

    def _validate_project_structure(self):
        """验证项目结构"""
        required_structure = {
            "agents": ["core_agent.py", "metadata_agent.py", "plugin_agent.py", "solution_agent.py"],
            "utils": ["dataverse_client.py", "yaml_parser.py", "schema_validator.py", "naming_converter.py"],
            "config": ["environments.yaml", "naming_rules.yaml", "settings.yaml"],
            "metadata/_schema": ["table_schema.yaml", "form_schema.yaml", "view_schema.yaml"],
        }

        optional_structure = {
            "metadata": ["tables", "forms", "views"],
            "plugins": [],
            "docs": [],
            "skills": [],
        }

        for category, files in required_structure.items():
            category_path = self.project_root / category
            result = {"category": category, "exists": category_path.exists(), "files": []}

            if category_path.exists():
                for file_name in files:
                    file_path = category_path / file_name
                    result["files"].append({
                        "name": file_name,
                        "exists": file_path.exists()
                    })
                    if not file_path.exists():
                        self.errors.append(f"Missing required file: {category}/{file_name}")

            self.results["project_structure"].setdefault("required", {})[category] = result

        for category, files in optional_structure.items():
            category_path = self.project_root / category
            result = {"category": category, "exists": category_path.exists(), "files": []}

            if category_path.exists():
                for file_name in files:
                    file_path = category_path / file_name
                    result["files"].append({
                        "name": file_name,
                        "exists": file_path.exists()
                    })

            self.results["project_structure"].setdefault("optional", {})[category] = result

    def _validate_dependencies(self):
        """验证依赖项"""
        requirements_file = self.project_root / "requirements.txt"
        setup_file = self.project_root / "setup.py"

        dependencies = {
            "required": [
                "mcp",
                "PyYAML",
                "jsonschema",
                "msal",
                "requests",
                "urllib3",
                "python-dateutil",
            ],
            "optional": [
                "pytest",
                "black",
                "flake8",
                "mypy",
                "click",
                "rich",
            ]
        }

        self.results["dependencies"] = dependencies

        if requirements_file.exists():
            with open(requirements_file, "r") as f:
                requirements_content = f.read()

            for dep in dependencies["required"]:
                # 检查包名在requirements.txt中的各种形式
                dep_variants = [
                    dep.lower(),
                    dep.lower().replace("-", "_"),
                    dep.lower().replace("_", "-"),
                ]
                found = any(variant in requirements_content.lower() for variant in dep_variants)
                if not found:
                    self.warnings.append(f"Dependency '{dep}' may be missing from requirements.txt")

        if not setup_file.exists():
            self.errors.append("setup.py not found")

    def _validate_yaml_structure(self):
        """验证YAML文件结构"""
        yaml_files = list(self.project_root.rglob("*.yaml"))
        yaml_files = [f for f in yaml_files if "__pycache__" not in str(f)]

        for yaml_file in yaml_files:
            rel_path = yaml_file.relative_to(self.project_root)

            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # 基本YAML语法检查（缩进，冒号）
                self._check_yaml_basic_syntax(content, rel_path)

                self.results["yaml_syntax"].append({
                    "file": str(rel_path),
                    "status": "OK"
                })
            except Exception as e:
                self.warnings.append(f"Could not validate YAML {rel_path}: {e}")
                self.results["yaml_syntax"].append({
                    "file": str(rel_path),
                    "status": "WARNING",
                    "message": str(e)
                })

    def _check_yaml_basic_syntax(self, content: str, file_path: Path):
        """基本YAML语法检查"""
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # 检查制表符（YAML不允许）
            if "\t" in line:
                self.errors.append(f"YAML syntax error in {file_path}:{i} - Tabs not allowed in YAML")

            # 检查冒号后的空格
            if ":" in line and not line.strip().startswith("#"):
                colon_pos = line.find(":")
                if colon_pos < len(line) - 1 and line[colon_pos + 1] not in [" ", "\n", "#", ":"]:
                    # 可能是错误，但URL和时间可能包含冒号
                    if "://" not in line and not line.strip().startswith("$"):
                        self.warnings.append(f"YAML warning in {file_path}:{i} - Colon should be followed by space")

    def _generate_summary(self):
        """生成验证摘要"""
        python_files = [f for f in self.results["python_syntax"] if f["status"] == "OK"]
        python_errors = [f for f in self.results["python_syntax"] if f["status"] == "ERROR"]

        self.results["summary"] = {
            "total_python_files": len(self.results["python_syntax"]),
            "python_files_valid": len(python_files),
            "python_files_with_errors": len(python_errors),
            "total_yaml_files": len(self.results["yaml_syntax"]),
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "build_status": "SUCCESS" if len(self.errors) == 0 else "FAILED"
        }

    def _print_results(self):
        """打印验证结果"""
        print()
        print("=" * 60)
        print("VALIDATION RESULTS")
        print("=" * 60)

        summary = self.results["summary"]

        print(f"\nPython Files:")
        print(f"  Total: {summary['total_python_files']}")
        print(f"  Valid: {summary['python_files_valid']}")
        print(f"  Errors: {summary['python_files_with_errors']}")

        print(f"\nYAML Files:")
        print(f"  Total: {summary['total_yaml_files']}")

        print(f"\nIssues:")
        print(f"  Errors: {summary['total_errors']}")
        print(f"  Warnings: {summary['total_warnings']}")

        print(f"\nBuild Status: {summary['build_status']}")

        if self.errors:
            print("\n--- ERRORS ---")
            for error in self.errors[:10]:  # 只显示前10个错误
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors")

        if self.warnings:
            print("\n--- WARNINGS ---")
            for warning in self.warnings[:5]:  # 只显示前5个警告
                print(f"  - {warning}")
            if len(self.warnings) > 5:
                print(f"  ... and {len(self.warnings) - 5} more warnings")

        print("\n" + "=" * 60)


def main():
    """主函数"""
    # 获取项目根目录
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1])
    else:
        project_root = Path(__file__).parent

    # 执行验证
    validator = ProjectValidator(project_root)
    success = validator.validate_all()

    # 保存验证报告
    report_file = project_root / "BUILD_REPORT.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# Power Platform Agent - Build Report\n\n")
        f.write(f"Generated: {__import__('datetime').datetime.now().isoformat()}\n\n")

        f.write("## Summary\n\n")
        summary = validator.results["summary"]
        f.write(f"- **Build Status**: {summary['build_status']}\n")
        f.write(f"- **Python Files**: {summary['python_files_valid']}/{summary['total_python_files']} valid\n")
        f.write(f"- **YAML Files**: {summary['total_yaml_files']} checked\n")
        f.write(f"- **Errors**: {summary['total_errors']}\n")
        f.write(f"- **Warnings**: {summary['total_warnings']}\n\n")

        if validator.errors:
            f.write("## Errors\n\n")
            for error in validator.errors:
                f.write(f"- {error}\n")
            f.write("\n")

        if validator.warnings:
            f.write("## Warnings\n\n")
            for warning in validator.warnings[:20]:
                f.write(f"- {warning}\n")
            if len(validator.warnings) > 20:
                f.write(f"\n... and {len(validator.warnings) - 20} more warnings\n")
            f.write("\n")

        f.write("## Project Structure\n\n")
        structure = validator.results["project_structure"]
        for category, data in structure.get("required", {}).items():
            status = "OK" if data["exists"] else "MISSING"
            f.write(f"- {category}: {status}\n")
            for file_info in data.get("files", []):
                file_status = "OK" if file_info["exists"] else "MISSING"
                f.write(f"  - {file_info['name']}: {file_status}\n")

        f.write("\n## Dependencies\n\n")
        f.write("### Required\n\n")
        for dep in validator.results["dependencies"].get("required", []):
            f.write(f"- {dep}\n")
        f.write("\n### Optional\n\n")
        for dep in validator.results["dependencies"].get("optional", []):
            f.write(f"- {dep}\n")

    print(f"\nBuild report saved to: {report_file}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
