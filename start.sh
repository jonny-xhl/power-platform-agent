#!/bin/bash
# Power Platform Agent Start Script
# 启动 MCP 服务器

echo "========================================"
echo "Power Platform Agent - Starting MCP Server"
echo "========================================"
echo

# 默认使用 stdio 模式
MODE="${1:-stdio}"

case "$MODE" in
    "stdio"|"--stdio")
        echo "Starting in STDIO mode (for Claude Code / Cursor)..."
        echo "Press Ctrl+C to stop"
        echo
        python framework/mcp_serve.py --stdio
        ;;
    "sse"|"--sse"|"--port")
        PORT="${2:-8000}"
        echo "Starting in SSE mode on port $PORT..."
        echo "Access at: http://localhost:$PORT"
        echo "Press Ctrl+C to stop"
        echo
        python framework/mcp_serve.py --port "$PORT"
        ;;
    "help"|"--help"|"-h")
        echo "Usage: $0 [mode] [port]"
        echo
        echo "Modes:"
        echo "  stdio       STDIO mode (default) - for Claude Code / Cursor"
        echo "  sse         SSE mode - HTTP server with port"
        echo
        echo "Examples:"
        echo "  $0              # Start in STDIO mode"
        echo "  $0 stdio        # Start in STDIO mode"
        echo "  $0 sse 8000     # Start in SSE mode on port 8000"
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac
