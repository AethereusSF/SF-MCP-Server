import pkgutil
import importlib

# This code dynamically finds and imports all Python modules in this
# directory. When each module is imported, any functions decorated with
# @register_tool will be automatically added to the mcp_server instance.
print("--- [MCP] Discovering and loading tools ---")
for _, name, _ in pkgutil.iter_modules(__path__):
    importlib.import_module(f".{name}", __package__)
    print(f"  -> [MCP] Loaded tools from: {name}.py")
print("--- [MCP] Tool loading complete ---")