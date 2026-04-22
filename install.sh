#!/bin/bash
# Power Platform Agent Installation Script
# 使用pip安装依赖

echo "========================================"
echo "Power Platform Agent - Installation"
echo "========================================"
echo

echo "Installing Python dependencies..."
pip install mcp
pip install PyYAML
pip install jsonschema
pip install msal
pip install requests
pip install urllib3
pip install python-dateutil

echo
echo "Installing optional dependencies..."
pip install click rich
pip install pytest pytest-asyncio pytest-cov
pip install black flake8 mypy
pip install types-PyYAML types-requests types-dateutil

echo
echo "========================================"
echo "Installation completed!"
echo "========================================"
echo
echo "To run the MCP server:"
echo "  python framework/mcp_serve.py"
echo
echo "Or install as package:"
echo "  pip install -e ."
echo "  pp-mcp"
echo
