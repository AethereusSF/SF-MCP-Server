"""MCP Server definition and tool registration"""
import inspect
import pydantic
from mcp.server.fastmcp import FastMCP
import logging
import os

logger = logging.getLogger(__name__)

def parse_docstring(func):
    """A simple parser for a standard Python docstring."""
    docstring = inspect.getdoc(func)
    if not docstring:
        return "No description available.", {}
    
    lines = docstring.strip().split('\n')
    description = lines[0].strip()
    arg_descriptions = {}
    args_section = False
    
    for line in lines[1:]:
        line = line.strip()
        if line.lower() in ('args:', 'parameters:'):
            args_section = True
            continue
        if args_section and ':' in line:
            arg_name, arg_desc = line.split(':', 1)
            arg_descriptions[arg_name.strip()] = arg_desc.strip()
    
    return description, arg_descriptions

def create_model_from_func(func, arg_descriptions):
    """Creates a Pydantic model from a function's signature and descriptions."""
    fields = {}
    for param in inspect.signature(func).parameters.values():
        field_info = {
            "description": arg_descriptions.get(param.name, ""),
        }
        if param.default is not inspect.Parameter.empty:
            field_info["default"] = param.default
        fields[param.name] = (param.annotation, pydantic.Field(**field_info))
    
    return pydantic.create_model(f"{func.__name__}Schema", **fields)

# ✅ FIXED: Removed version parameter
# Configure for both stdio and HTTP/SSE modes
# Read from environment variables (set by config)
http_host = os.getenv("SFMCP_HTTP_HOST", "0.0.0.0")
http_port = int(os.getenv("PORT", os.getenv("SFMCP_HTTP_PORT", "8000")))

mcp_server = FastMCP(
    name="salesforce-production-server",
    host=http_host,
    port=http_port
)

tool_registry = {}

def add_tool_to_registry(func):
    """
    Parses a function, generates its schema, and adds it to the global tool_registry.
    """
    tool_name = func.__name__
    
    try:
        # Get tool metadata
        description, arg_descriptions = parse_docstring(func)
        schema = create_model_from_func(func, arg_descriptions)
        
        # Add to registry
        tool_registry[tool_name] = {
            "name": tool_name,
            "description": description,
            "schema": schema,
            "function": func
        }
        
        # Register with MCP
        mcp_server.tool()(func)
        logger.info(f"✅ Registered tool: '{tool_name}'")
        
    except Exception as e:
        logger.error(f"❌ Failed to register tool '{tool_name}': {e}")

def register_tool(func):
    """A decorator that registers a function as a tool."""
    add_tool_to_registry(func)
    return func

# Export for other modules
__all__ = ['mcp_server', 'register_tool', 'tool_registry']
