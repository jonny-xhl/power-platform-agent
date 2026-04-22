#!/usr/bin/env python3
"""
Power Platform Agent Setup
Power Platform MCP Server安装脚本
"""

from pathlib import Path
from setuptools import setup, find_packages

# 读取项目根目录
project_root = Path(__file__).parent

# 读取README
readme_file = project_root / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# 读取版本号
version = "1.0.0"

setup(
    name="power-platform-agent",
    version=version,
    description="MCP Server for Microsoft Power Platform - Dataverse metadata management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Power Platform Agent Team",
    author_email="",
    url="https://github.com/your-org/power-platform-agent",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="power-platform dataverse mcp microsoft dynamics crm",
    python_requires=">=3.9",

    # 包发现
    packages=find_packages(exclude=["tests*", "docs*", ".pp-local*", "metadata*", "config*", "plugins*"]),

    # 入口点
    entry_points={
        "console_scripts": [
            "power-platform-mcp=framework.mcp_serve:main",
            "pp-mcp=framework.mcp_serve:main",
        ],
    },

    # 包含非Python文件
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.md", "*.json"],
    },

    # 依赖项
    install_requires=[
        # MCP Server
        "mcp>=0.1.0",

        # YAML Processing
        "PyYAML>=6.0",
        "jsonschema>=4.0.0",

        # Microsoft Authentication
        "msal>=1.20.0",

        # HTTP Client
        "requests>=2.28.0",
        "urllib3>=1.26.0",

        # Data Processing
        "python-dateutil>=2.8.0",
    ],

    # 可选依赖
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.20.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
            "types-PyYAML",
            "types-requests",
            "types-dateutil",
        ],
        "cli": [
            "click>=8.0.0",
            "rich>=12.0.0",
        ],
    },

    # 项目URL
    project_urls={
        "Bug Reports": "https://github.com/your-org/power-platform-agent/issues",
        "Source": "https://github.com/your-org/power-platform-agent",
        "Documentation": "https://github.com/your-org/power-platform-agent/wiki",
    },
)
