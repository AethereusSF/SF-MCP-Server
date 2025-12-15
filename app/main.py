# app/main.py
import sys
import logging
from app.config import get_config
from app.mcp.server import mcp_server, tool_registry

# IMPORTANT: import tool modules so @register_tool executes.
# If you add more tool files later, import them here too.

# Consolidated tools (NEW - reduces 106 tools to ~40 tools)
from app.mcp.tools import consolidated_metadata as _consolidated_metadata  # noqa: F401
from app.mcp.tools import consolidated_operations as _consolidated_operations  # noqa: F401

# Original tools (still available for backward compatibility)
from app.mcp.tools import oauth_auth as _oauth_auth  # noqa: F401
from app.mcp.tools import dynamic_tools as _dynamic_tools  # noqa: F401
from app.mcp.tools import user_management as _user_management  # noqa: F401
from app.mcp.tools import advanced_comparison as _advanced_comparison  # noqa: F401

# Debugging and defect-solving tools (NEW - comprehensive debugging capabilities)
from app.mcp.tools import debugging as _debugging  # noqa: F401

# Schema analysis tools (field usage analysis)
from app.mcp.tools import schema_analysis as _schema_analysis  # noqa: F401

if __name__ == "__main__":
    config = get_config()
    logging.basicConfig(stream=sys.stderr, level=getattr(logging, config.log_level.upper()))

    # Check for HTTP/SSE mode
    if "--http" in sys.argv or "--sse" in sys.argv:
        logging.info("MCP starting (HTTP/SSE)")
        logging.info("Host: %s", config.http_host)
        logging.info("Port: %s", config.http_port)
        logging.info("API Key: %s", config.api_key[:8] + "..." if len(config.api_key) > 8 else "***")
        logging.info("Tools: %s", ", ".join(tool_registry.keys()) or "(none)")
        mcp_server.run(transport="sse")
    elif "--mcp-stdio" in sys.argv:
        logging.info("MCP starting (stdio)")
        logging.info("Tools: %s", ", ".join(tool_registry.keys()) or "(none)")
        mcp_server.run(transport="stdio")
    else:
        # Default to stdio for backward compatibility
        logging.info("MCP starting (stdio - default)")
        logging.info("Tools: %s", ", ".join(tool_registry.keys()) or "(none)")
        mcp_server.run(transport="stdio")
