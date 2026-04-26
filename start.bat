@echo off
REM Power Platform Agent Start Script
REM 启动 MCP 服务器

echo ========================================
echo Power Platform Agent - Starting MCP Server
echo ========================================
echo.

if "%1"=="" set MODE=stdio
if "%1"=="stdio" set MODE=stdio
if "%1"=="--stdio" set MODE=stdio
if "%1"=="sse" set MODE=sse
if "%1"=="--sse" set MODE=sse
if "%1"=="--port" set MODE=sse
if "%1"=="help" goto :help
if "%1"=="--help" goto :help
if "%1"=="-h" goto :help

if "%MODE%"=="stdio" (
    echo Starting in STDIO mode ^(for Claude Code / Cursor^)...
    echo Press Ctrl+C to stop
    echo.
    python framework\mcp_serve.py --stdio
    goto :end
)

if "%MODE%"=="sse" (
    if "%2"=="" set PORT=8000
    if not "%2"=="" set PORT=%2
    echo Starting in SSE mode on port %PORT%...
    echo Access at: http://localhost:%PORT%
    echo Press Ctrl+C to stop
    echo.
    python framework\mcp_serve.py --port %PORT%
    goto :end
)

echo Unknown mode: %1
echo Run '%0 help' for usage information
exit /b 1

:help
echo Usage: %0 [mode] [port]
echo.
echo Modes:
echo   stdio       STDIO mode ^(default^) - for Claude Code / Cursor
echo   sse         SSE mode - HTTP server with port
echo.
echo Examples:
echo   %0              # Start in STDIO mode
echo   %0 stdio        # Start in STDIO mode
echo   %0 sse 8000     # Start in SSE mode on port 8000

:end
