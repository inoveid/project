"""MCP Server для Agent Console.

Запуск из директории api/:
  python -m mcp.server

Или как скрипт (тогда внешний mcp пакет доступен напрямую):
  python api/mcp/server.py
"""
import sys
import os

# При запуске как скрипт добавляем api/ в path для доступа к нашему mcp пакету
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from mcp.server.fastmcp import FastMCP  # type: ignore[import]
from mcp.tools.platform import register_platform_tools

mcp = FastMCP("agent-console")

register_platform_tools(mcp)

if __name__ == "__main__":
    mcp.run()
