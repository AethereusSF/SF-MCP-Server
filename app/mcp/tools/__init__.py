import pkgutil
import importlib
import sys

# This code dynamically finds and imports all Python modules in this
# directory. When each module is imported, any functions decorated with
# @register_tool will be automatically added to the mcp_server instance.
print("--- [MCP] Discovering and loading tools ---", file=sys.stderr)
for _, name, _ in pkgutil.iter_modules(__path__):
    importlib.import_module(f".{name}", __package__)
    print(f"  -> [MCP] Loaded tools from: {name}.py", file=sys.stderr)
print("--- [MCP] Tool loading complete ---", file=sys.stderr)