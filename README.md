# 🚀 Salesforce MCP Server

> **The complete Model Context Protocol (MCP) server for Salesforce development**
> Deploy metadata, run SOQL, manage multiple orgs, and automate everything - all through Claude Desktop.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/release/python-31312/)
[![MCP](https://img.shields.io/badge/MCP-1.12.4-green.svg)](https://github.com/modelcontextprotocol)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**Created by Sameer** | [Report Issues](https://github.com/AethereusSF/SF-MCP-Server/issues)

---

## ✨ What is This?

Transform Claude Desktop into a **powerful Salesforce IDE** with optimized tools for metadata management, testing, multi-org operations, and more. No manual API calls, no context switching - just natural language commands.

**v2.0:** Tool consolidation reduces 106 tools → 57 tools (46% reduction) for better LLM performance!  
**v2.1:** Added comprehensive debugging tool - diagnose and fix any Salesforce defect!  
**v2.2:** Added `analyze_field_usage` - comprehensive field usage analysis across ALL metadata with CSV export!  
**v2.3:** API-only authentication - reliable username/password login for Claude Desktop!  
**v2.4:** Added `compare_page_layouts` - compare page layouts between orgs with full CSV diff report!  
**v2.5:** Security hardening - SOQL injection protection across all tools, bulk upsert implemented, thread-local connection cache staleness fix!  
**v2.6:** Enhanced `compare_profiles` and `compare_permission_sets` - now covers object, field, tab, app, Apex/VF page, and system permissions with full pagination!

### Key Features

- 🔐 **API-Based Authentication** - Reliable username/password login that works perfectly in Claude Desktop
- 🛠️ **57 Optimized Tools** - Complete Salesforce API coverage with LLM-friendly design
- 🔒 **SOQL Injection Protection** - All user inputs escaped via `escape_soql_string()` throughout
- 🎯 **Smart Infrastructure** - Caching, connection pooling, pagination, and enhanced error handling
- 🔍 **Field Usage Analysis** - Analyze where 500+ fields are used across ALL metadata with CSV export
- 🐛 **Intelligent Debugging** - Diagnose and fix triggers, flows, validations, fields, permissions, and more
- 🌐 **Multi-Org Management** - Work with multiple orgs simultaneously and compare metadata
- 📦 **Bulk Operations** - Handle thousands of records with Bulk API 2.0 (insert/update/delete/upsert)
- 🧪 **Apex Testing** - Run tests, get coverage, debug with full logs
- 🔍 **Schema Analysis** - Analyze dependencies, find unused fields, generate ERDs
- 📊 **Health Monitoring** - Check org limits, API usage, and system health
- 🚦 **Production-Ready** - Retry logic, input validation, structured logging

---

## 🎯 Quick Start

### Prerequisites

- **Python 3.13** ([Download](https://www.python.org/downloads/release/python-31312/))
- **Git** ([Download](https://git-scm.com/downloads))
- **VS Code** ([Download](https://code.visualstudio.com/download))
- **Claude Desktop** ([Download](https://claude.ai/download))
- **Salesforce Org** (Production, Sandbox, or Developer)

### ⚡ Quick Authentication (Claude Desktop)

**Recommended:** Use username/password authentication (most reliable for MCP servers)

```
Step 1: Get domain from your org URL
Use salesforce_get_domain_from_url with: https://your-org.salesforce.com

Step 2: Login
Use salesforce_login_username_password with:
- username: your.email@company.com
- password: YourPassword
- security_token: [Get from Salesforce Settings → Reset Security Token]
- domain: [from step 1]

Step 3: Start using tools!
Use soql_query to run: SELECT Id, Name FROM Account LIMIT 10
```

### Installation

#### Windows (Recommended - One Click Setup)

```bash
# Clone repository
git clone https://github.com/AethereusSF/SF-MCP-Server
cd SF-MCP-Server

# Run setup script (creates venv, installs dependencies, tests installation)
.\setup.bat
```

That's it! `setup.bat` handles everything automatically - creates the virtual environment, installs all dependencies, and verifies the installation.

#### macOS / Linux (Recommended - One Click Setup)

```bash
# Clone repository
git clone https://github.com/AethereusSF/SF-MCP-Server
cd SF-MCP-Server

# Make scripts executable
chmod +x setup.sh start_mcp.sh start_http.sh

# Run setup script (creates venv, installs dependencies, tests installation)
./setup.sh
```

### Configure Claude Desktop

#### Windows

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "salesforce-mcp-server": {
      "command": "C:\\path\\to\\Salesforce-MCP-Server\\start_mcp.bat"
    }
  }
}
```

#### macOS / Linux

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "salesforce-mcp-server": {
      "command": "/bin/bash",
      "args": [
        "-c",
        "cd '/absolute/path/to/Salesforce-MCP-Server' && venv/bin/python -m app.main --mcp-stdio"
      ]
    }
  }
}
```

**Important:** Replace `/absolute/path/to/Salesforce-MCP-Server` with your actual absolute path!

### First Use

1. **Restart Claude Desktop**
2. **Login:** Type `"Login to Salesforce production"` in a new Claude chat
3. **Authenticate:** Browser window opens → Login → Allow access
4. **Start Using:** Try `"Check my Salesforce org health"`

---

## 🛠️ Tool Categories (57 Total)

### ⭐ Consolidated Tools (Core Operations)
**Universal tools that replace many specialized tools:**

- `deploy_metadata` - Deploy any metadata type (Apex, LWC, Fields, etc.) with a single tool
- `fetch_metadata` - Fetch any metadata type with consistent interface
- `list_metadata` - List metadata of any type with wildcard filtering
- `bulk_operation` - Unified bulk insert / update / delete / **upsert** via Bulk API 2.0
- `export_data` - Export data in CSV, JSON, or backup format
- `soql_query` - Build and execute SOQL queries with optional analysis
- `get_object_metadata` - Get fields, relationships, and metadata in one call
- `manage_user_permissions` - Manage profiles and permission sets (set_profile / assign_permset / remove_permset / list)

### 🐛 Debugging & Defect-Solving (1)
- `diagnose_and_fix_issue` - Comprehensive debugging for triggers, flows, validations, fields, permissions, formulas, picklists, lookups, layouts, and reports

**Powered by 26 real-world QA scenario patterns:**
- Trigger recursion and SOQL limit issues
- Flow null handling and decision logic
- Validation rule date/required field errors
- Field-level security and permission issues
- Formula field calculations and references
- Page layout assignment problems
- Report field visibility issues
- Broken lookup relationships

### 🔐 Authentication & Sessions (7)
- `salesforce_production_login` - OAuth to production org
- `salesforce_sandbox_login` - OAuth to sandbox (test.salesforce.com)
- `salesforce_custom_login` - OAuth to custom domain
- `salesforce_login_username_password` - Login with username/password/token *(recommended)*
- `salesforce_logout` - Clear all sessions
- `salesforce_auth_status` - Check authentication status
- `salesforce_get_domain_from_url` - Extract domain parameter from any Salesforce URL

### 🌐 Multi-Org Management (5)
- `list_connected_orgs` - List all connected orgs
- `switch_active_org` - Switch between orgs
- `compare_metadata_between_orgs` - Compare Apex, Flows, etc. across orgs
- `compare_object_schemas` - Compare field schemas across orgs
- `get_org_differences_summary` - High-level org comparison

### 📝 Metadata Operations (3 unified tools)
**One tool handles all 16 metadata types:**

| Tool | Supported Types |
|------|----------------|
| `deploy_metadata` | ApexClass, ApexTrigger, LWC, AuraComponent, CustomObject, CustomField, Flow, EmailTemplate, PermissionSet, StaticResource, CustomMetadataType, CustomLabel, RecordType, QuickAction, CustomTab *(ValidationRule — manual only)* |
| `fetch_metadata` | All 16 types above |
| `list_metadata` | ApexClass, ApexTrigger, CustomObject, Flow, PermissionSet, StaticResource |

### 🧪 Apex Testing & Debug (3)
- `run_apex_tests` - Run tests with coverage
- `get_apex_test_coverage` - Get code coverage details
- `list_apex_test_classes` - List all test classes

### 📦 Bulk Operations
- `bulk_operation` - Insert / update / delete / **upsert** (Bulk API 2.0, fully async with polling)
- `get_bulk_job_status` - Check job progress

### 💾 Data Export & Backup (3)
- `export_data` - Export as CSV / JSON / timestamped backup
- `get_record_count` - Fast record counting with optional WHERE filter
- `export_schema_to_json` - Export object schemas to JSON

### 🔍 SOQL & Query Helpers (2)
- `soql_query` - Execute or auto-build SOQL; optional query analysis
- `query_with_related_records` - Query parent + child records in one call

### 📊 Schema Analysis (7)
- `analyze_object_dependencies` - Full dependency analysis (lookups, triggers, flows, VRs)
- `find_unused_fields` - Identify fields with no Apex/trigger references
- `generate_object_diagram` - Generate ERD data
- `export_object_relationships` - Export relationship map
- `extract_metadata_relationships` - Cross-metadata relationship analysis
- `analyze_field_usage` - Where a field is used across ALL metadata with CSV export
- `compare_field_presence` - Compare field presence across objects

### 🤖 Process Automation (8)
- `list_batch_jobs` - List Batch Apex jobs
- `get_batch_job_details` - Get detailed job info
- `list_scheduled_jobs` - List scheduled Apex
- `abort_batch_job` - Stop running batch
- `delete_scheduled_job` - Delete scheduled job
- `execute_anonymous_apex` - Execute Apex instantly
- `get_debug_logs` - Retrieve debug logs
- `get_debug_log_body` - Get full log content

### 🏥 Org Health & Limits (6)
- `salesforce_health_check` - Comprehensive health check
- `get_org_limits` - API/storage limits
- `get_org_info` - Organization details
- `get_current_user_info` - Current user profile
- `list_installed_packages` - List managed packages
- `get_api_usage_stats` - API usage statistics

### 🎯 Core Operations (2)
- `execute_soql_query` - Low-level SOQL execution
- `get_metadata_deploy_status` - Check deployment status

### 👥 User Management (backing functions)
Exposed through `manage_user_permissions` consolidated tool:
- set_profile, assign_permset, remove_permset, list
- `list_available_profiles` - List all profiles in the org
- `list_available_permission_sets` - List all permission sets in the org

### 🔄 Advanced Comparison Tools (6)
- `compare_profiles` - **Full comparison**: object, field, tab, app, Apex/VF page, and system permissions; `sections` parameter for targeted queries
- `compare_permission_sets` - **Full comparison**: same coverage as profiles, fully paginated (no LIMIT caps); `sections` parameter
- `compare_object_field_counts` - Compare field counts/types between orgs
- `find_similar_fields_across_objects` - Find fields with similar names/types
- `compare_org_object_counts` - Compare total object counts between orgs
- `compare_page_layouts` - Compare page layouts between orgs — fields, sections, related lists diff with CSV export

### 📄 Documentation Tools (4)
- `generate_brd_document` - Generate Business Requirements Document
- `generate_design_document` - Generate Technical Design Document
- `generate_test_document` - Generate Test Plan document
- `generate_sf_object_documentation` - Generate object documentation

---

## 📚 Usage Examples

### Basic Operations

```
# Authentication
"Login to Salesforce production"
"Login to Salesforce sandbox"
"Check my login status"

# Health Check
"Check my Salesforce org health"
"Show me my API limits"

# Run Query
"Run SOQL: SELECT Id, Name FROM Account WHERE Industry = 'Technology' LIMIT 10"

# Get Information
"Show me all custom fields on the Account object"
"List all Apex classes in the org"
```

### Metadata Management

```
# Create Apex Class
"Create an Apex class called AccountService with this code:
public class AccountService {
    public static List<Account> getHighValueAccounts() {
        return [SELECT Id, Name, AnnualRevenue FROM Account WHERE AnnualRevenue > 1000000];
    }
}"

# Create Custom Field
"Create a text field called Customer_Code__c on Account with length 50"

# Create Validation Rule
"Create a validation rule on Opportunity that requires Amount when Stage is Closed Won"

# Deploy LWC Component
"Create an LWC component called accountCard"
```

### Testing & Debugging

```
# Run Tests
"Run all Apex tests and show me the code coverage"
"Run tests from AccountServiceTest class"
"Show me code coverage for AccountService"

# Debug
"Get my last 10 debug logs"
"Show me the full log for 07L4x000000AbcD"
"Execute this Apex: System.debug('Test message');"
```

### Multi-Org Operations

```
# Connect Multiple Orgs
"Login to Salesforce production"
"Login to Salesforce sandbox"

# List & Switch
"List all my connected orgs"
"Switch to org 00D4x000000XyzE"

# Compare
"Compare Apex classes between production and sandbox"
"Compare Account schema between the two orgs"
"Get differences summary between my orgs"
```

### Bulk Operations

```
# Bulk Insert
"Bulk insert these Account records: [...]"

# Bulk Upsert (NEW - uses external ID field)
"Bulk upsert Contacts using Email__c as the external ID: [...]"

# Check Status
"Check status of bulk job 7504x000000AbcD"
```

### Data Export

```
# Export to CSV
"Export all Opportunities from Q4 2024 to CSV"

# Backup
"Backup all Account records"

# Count Records
"How many Leads were created today?"

# Export Schema
"Export Account, Contact, and Opportunity schemas to JSON"
```

### Advanced Comparison (v2.6)

```
# Full profile comparison (all sections)
"Compare System Administrator and Standard User profiles"

# Targeted comparison (faster)
"Compare object and field permissions between Sales User and Service User"
→ compare_profiles("Sales User", "Service User", sections="objects,fields")

# Permission set comparison
"Compare Marketing_Admin and Marketing_User permission sets"

# Cross-org profile comparison
"Compare System Administrator profile between production and sandbox"
→ compare_profiles("System Administrator", "System Administrator", org2_user_id="005xx...", sections="all")

# Compare object fields across orgs
"Compare Account object fields between my two connected orgs"

# Compare page layouts
"Compare Account page layout between production and sandbox"
→ compare_page_layouts(
    layout_names="Account-Account Layout",
    source_org_user_id="005xx...",
    target_org_user_id="005yy..."
  )
```

### Field Usage Analysis

```
# Analyze single field
"Where is the Case Status field used?"

# Analyze ALL fields on an object
"Analyze all Case fields and create a CSV report"

# Include reports
"Analyze Account.Customer_Type__c including reports"

# Custom output filename
"Analyze Opportunity fields and save to opp_field_audit.csv"
```

---

## 🎓 Advanced Features

### 🔄 Advanced Profile & Permission Set Comparison (v2.6)

Both `compare_profiles` and `compare_permission_sets` now provide **full coverage** across all permission dimensions:

| Section | What it checks |
|---------|---------------|
| `objects` | CRUD + ViewAll + ModifyAll per SObject |
| `fields` | Read + Edit per field (fully paginated, no caps) |
| `tabs` | Tab visibility (DefaultOn / DefaultOff / Hidden) |
| `apps` | Apex class, VF page, custom permission access |
| `system` | All ~150 boolean user permissions (PermissionsApiEnabled, PermissionsModifyAllData, etc.) |

Use the `sections` parameter to run only the checks you need:

```
# Only object + field permissions (fast)
compare_profiles("Admin", "Standard", sections="objects,fields")

# Only system permissions
compare_profiles("Admin", "Standard", sections="system")

# Everything (default)
compare_profiles("Admin", "Standard")
```

### 🔍 Field Usage Analysis

The `analyze_field_usage` tool provides comprehensive field usage analysis. Perfect for field audits, cleanup projects, and impact analysis.

Checks usage in: Apex Classes, Apex Triggers, Flows, Validation Rules, Formula Fields, Workflow Rules, Page Layouts, Email Templates, Reports (optional).

CSV output saved to `Documents/{ObjectName}_field_usage_{timestamp}.csv`.

### Configuration

Create a `.env` file (copy from `.env.example`):

```env
# Server Configuration
SFMCP_MCP_SERVER_NAME=salesforce-mcp-server
SFMCP_LOG_LEVEL=INFO
SFMCP_DEBUG_MODE=false

# OAuth Configuration
SFMCP_OAUTH_CALLBACK_PORT=1717
SFMCP_OAUTH_TIMEOUT_SECONDS=300

# API Configuration
SFMCP_SALESFORCE_API_VERSION=62.0
SFMCP_MAX_RETRIES=3
SFMCP_REQUEST_TIMEOUT_SECONDS=120

# Deployment
SFMCP_DEPLOY_TIMEOUT_SECONDS=300
SFMCP_DEPLOY_POLL_INTERVAL_SECONDS=5

# HTTP/SSE mode (optional)
SFMCP_HTTP_HOST=0.0.0.0
SFMCP_HTTP_PORT=8000
SFMCP_API_KEY=change-this-before-deploying
```

### 📁 Project Structure

```
SF-MCP-Server/
├── app/
│   ├── main.py                          # Entry point, tool imports
│   ├── config.py                        # Configuration management
│   │
│   ├── mcp/
│   │   ├── server.py                    # MCP server setup, tool registration
│   │   └── tools/                       # All MCP tools
│   │       ├── consolidated_metadata.py      # Unified deploy/fetch/list
│   │       ├── consolidated_operations.py    # Bulk ops, export, queries, permissions
│   │       ├── oauth_auth.py                 # OAuth 2.0 + username/password auth
│   │       ├── debugging.py                  # Issue diagnosis (26 QA patterns)
│   │       ├── dynamic_tools.py              # Low-level Metadata API helpers
│   │       ├── multi_org.py                  # Multi-org management
│   │       ├── advanced_comparison.py        # Full profile/permset/schema comparison
│   │       ├── user_management.py            # Backing user permission functions
│   │       ├── schema_analysis.py            # Dependencies, unused fields, ERDs
│   │       ├── org_management.py             # Health check, limits, org info
│   │       ├── automation.py                 # Batch jobs, scheduled jobs
│   │       ├── testing.py                    # Apex tests, coverage
│   │       ├── bulk_operations.py            # Bulk API backing functions
│   │       ├── data_export.py                # Export/backup backing functions
│   │       ├── query_helpers.py              # Query builder backing functions
│   │       ├── documentation.py              # BRD/TDD/Test document generation
│   │       ├── page_layout_comparison.py     # Page layout diff tool
│   │       └── utils.py                      # Response formatting, error handling
│   │
│   ├── services/
│   │   └── salesforce.py                # Connection management, token refresh
│   │
│   └── utils/
│       ├── validators.py                # SOQL injection protection, SafeSOQLBuilder
│       ├── retry.py                     # Retry with exponential backoff
│       ├── logging.py                   # Structured logging
│       ├── cache.py                     # LRU caching system
│       ├── errors.py                    # Enhanced error handling
│       ├── pagination.py                # Pagination utilities
│       └── connection_pool.py           # Connection pooling
│
├── requirements.txt                      # Dependencies
├── .env.example                          # Example configuration
├── CLAUDE.md                             # Developer guide for Claude Code
├── README.md                             # This file
├── setup.bat / setup.sh                  # One-click setup scripts
├── start_mcp.bat / start_mcp.sh          # stdio mode startup
└── start_http.bat / start_http.sh        # HTTP/SSE mode startup
```

### Retry Logic

All API calls automatically retry with exponential backoff:
- Max attempts: 3 (configurable via `SFMCP_MAX_RETRIES`)
- Backoff multiplier: 2.0
- Handles transient failures gracefully

### Security

- **SOQL injection protection** — all user-supplied values wrapped with `escape_soql_string()` / `escape_soql_like()` before query interpolation
- **SafeSOQLBuilder** available for programmatic query construction
- **OAuth tokens** stored in-memory only — cleared on process restart
- **HTTPS required** for custom domain OAuth flows

---

## 🔧 Troubleshooting

### "No active Salesforce sessions found"
Login first:
```
"Login to Salesforce production"
```
Or use username/password: `salesforce_login_username_password`

### "Token expired"
Logout and re-login:
```
"Logout from all Salesforce orgs"
"Login to Salesforce production"
```

### "Deployment timeout"
Increase timeout in `.env`:
```env
SFMCP_DEPLOY_TIMEOUT_SECONDS=600
```

### "API limit exceeded"
Check limits: `"Get org limits"`

### "Wrong org being used"
```
"List connected orgs"
"Switch to org [user_id]"
```

### Tools not showing in Claude
1. Check Claude Desktop config file path
2. Verify absolute path is correct
3. Restart Claude Desktop
4. Check logs: `%APPDATA%\Claude\logs\` (Windows)

---

## 🤝 Contributing

We welcome contributions! See our [Contributing Guide](CONTRIBUTING.md) for details.

### Adding New Tools

1. Create tool function in the appropriate module under `app/mcp/tools/`
2. Add `@register_tool` decorator
3. Write a clear docstring — first line is the tool description, then `Args:` section
4. Import the module in `app/main.py`
5. Return a JSON string using `format_success_response()` / `format_error_response()`
6. Always escape user inputs: `escape_soql_string(value)` before SOQL interpolation

### Testing Requirements

Before submitting PRs:
- ✅ All existing tests must pass
- ✅ New tools must include test scenarios
- ✅ Test in sandbox environment first
- ✅ Document any API limit implications

## ⚖️ License

MIT License - See [LICENSE](LICENSE) for details

**Created by Sameer** | Built with [Model Context Protocol](https://github.com/modelcontextprotocol)

---

## 🆘 Support

- **Issues:** [GitHub Issues](https://github.com/AethereusSF/SF-MCP-Server/issues)
- **Discussions:** [GitHub Discussions](https://github.com/AethereusSF/SF-MCP-Server/discussions)

---

**Built with ☕, code, and curiosity by Sameer**
