# 🚀 Salesforce MCP Server

> **The complete Model Context Protocol (MCP) server for Salesforce development**
> Deploy metadata, run SOQL, manage multiple orgs, and automate everything - all through Claude Desktop.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/release/python-31312/)
[![MCP](https://img.shields.io/badge/MCP-1.12.4-green.svg)](https://github.com/modelcontextprotocol)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**Created by Sameer** | [Report Issues](https://github.com/AethereusSF/SF-MCP-Server/issues) | [Complete Guide](COMPLETE_GUIDE.md)

---

## ✨ What is This?

Transform Claude Desktop into a **powerful Salesforce IDE** with 60 optimized tools for metadata management, testing, multi-org operations, and more. No manual API calls, no context switching - just natural language commands.

**NEW v2.0:** Tool consolidation reduces 106 tools → 57 tools (46% reduction) for better LLM performance!
**NEW v2.1:** Added comprehensive debugging tool - diagnose and fix any Salesforce defect!
**NEW v2.2:** Added `analyze_field_usage` - comprehensive field usage analysis across ALL metadata with CSV export!
**NEW v2.3:** API-only authentication - reliable username/password login for Claude Desktop!
**NEW v2.4:** Added `compare_page_layouts` - compare page layouts between orgs with full CSV diff report!

### Key Features

- 🔐 **API-Based Authentication** - Reliable username/password login that works perfectly in Claude Desktop
- 🛠️ **60 Optimized Tools** - Complete Salesforce API coverage with LLM-friendly design
- 🎯 **Smart Infrastructure** - Caching, connection pooling, pagination, and enhanced error handling
- 🔍 **Field Usage Analysis** - Analyze where 500+ fields are used across ALL metadata with CSV export
- 🐛 **Intelligent Debugging** - Diagnose and fix triggers, flows, validations, fields, permissions, and more
- 🌐 **Multi-Org Management** - Work with multiple orgs simultaneously and compare metadata
- 📦 **Bulk Operations** - Handle thousands of records with Bulk API 2.0
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
Use execute_soql_query to run: SELECT Id, Name FROM Account LIMIT 10
```

### License Key Setup

Before running the server, you need a valid license key from MCP Admin.

1. **Contact MCP Admin** to get your `APP_ENCRYPTION_KEY` and `APP_PASSWORD_ENC`
2. **Add to `.env` file:**
   ```env
   APP_ENCRYPTION_KEY=your-key-from-admin
   APP_PASSWORD_ENC=your-encrypted-password-from-admin
   ```
3. Keys are **rotated weekly** - contact MCP Admin for renewal when your key expires

> Without a valid license key, the server will display: *"You don't have an active key. Please connect with MCP Admin to get access."*

### Installation

#### Windows (Recommended - One Click Setup)

```bash
# Clone repository
git clone https://github.com/AethereusSF/SF-MCP-Server
cd Salesforce-MCP-Server

# Run setup script (creates venv, installs dependencies, tests installation)
.\setup.bat
```

That's it! `setup.bat` handles everything automatically - creates the virtual environment, installs all dependencies, and verifies the installation.

#### macOS / Linux (Recommended - One Click Setup)

```bash
# Clone repository
git clone https://github.com/AethereusSF/SF-MCP-Server
cd Salesforce-MCP-Server

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

## 🛠️ Tool Categories (58 Total - Optimized for LLMs!)

### ⭐ NEW: Consolidated Tools (Core Operations)
**Universal tools that replace 59 specialized tools:**

- `deploy_metadata` - Deploy any metadata type (Apex, LWC, Fields, etc.) with single tool
- `fetch_metadata` - Fetch any metadata type with consistent interface
- `list_metadata` - List metadata of any type with filtering
- `bulk_operation` - Unified bulk insert/update/delete operations
- `export_data` - Export data in CSV, JSON, or backup format
- `soql_query` - Build and execute queries with optional analysis
- `get_object_metadata` - Get fields, relationships, and metadata in one call
- `manage_user_permissions` - Manage profiles and permission sets

**Benefits:** Easier for LLMs to select, more consistent API, flexible parameters

### 🐛 Debugging & Defect-Solving (1)
- `diagnose_and_fix_issue` - Comprehensive debugging for triggers, flows, validations, fields, permissions, formulas, picklists, lookups, layouts, and reports

**Powered by 25 real-world QA scenario patterns:**
- Trigger recursion and SOQL limit issues
- Flow null handling and decision logic
- Validation rule date/required field errors
- Field-level security and permission issues
- Formula field calculations and references
- Page layout assignment problems
- Report field visibility issues
- Broken lookup relationships

**Handles 10+ issue types with intelligent diagnosis, root cause analysis, and actionable fix recommendations.**

### 🔐 Authentication & Sessions (6)
- `salesforce_production_login` - OAuth to production org
- `salesforce_sandbox_login` - OAuth to sandbox (test.salesforce.com)
- `salesforce_custom_login` - OAuth to custom domain
- `salesforce_login_username_password` - Login with username/password/token
- `salesforce_logout` - Clear all sessions
- `salesforce_auth_status` - Check authentication status

### 🌐 Multi-Org Management (5)
- `list_connected_orgs` - List all connected orgs
- `switch_active_org` - Switch between orgs
- `compare_metadata_between_orgs` - Compare Apex, Flows, etc.
- `compare_object_schemas` - Compare field schemas
- `get_org_differences_summary` - High-level org comparison

### 📝 Metadata Operations (60)
**16 Metadata Types** × 3 Operations (fetch, create, upsert):
- **Apex Classes** - Full CRUD operations
- **Apex Triggers** - Create and manage triggers
- **Validation Rules** - Deploy validation logic
- **LWC (Lightning Web Components)** - Complete bundle management
- **Custom Objects** - Create and configure objects
- **Custom Fields** - Add fields to any object
- **Flows** - Manage Flow definitions
- **Email Templates** - Create email templates
- **Permission Sets** - Configure permissions
- **Static Resources** - Upload JavaScript, CSS, etc.
- **Custom Metadata Types** - Configuration management
- **Aura Components** - Legacy Lightning components
- **Custom Labels** - Translation labels
- **Record Types** - Object record types
- **Quick Actions** - Create quick actions
- **Custom Tabs** - Configure custom tabs

### 🧪 Apex Testing & Debug (3)
- `run_apex_tests` - Run tests with coverage
- `get_apex_test_coverage` - Get code coverage details
- `list_apex_test_classes` - List all test classes

### 📦 Bulk Operations (4)
- `bulk_insert_records` - Insert thousands via Bulk API 2.0
- `bulk_update_records` - Update thousands of records
- `bulk_delete_records` - Delete thousands of records
- `get_bulk_job_status` - Check job progress

### 💾 Data Export & Backup (5)
- `export_data_to_csv` - Export SOQL results to CSV
- `export_object_data` - Export entire objects
- `backup_object_records` - Create timestamped backups
- `get_record_count` - Fast record counting
- `export_schema_to_json` - Export object schemas

### 🔍 Query Helpers (5)
- `build_soql_query` - Build queries from components
- `get_object_fields` - Get field metadata
- `get_field_relationships` - Get all relationships
- `explain_soql_query` - Analyze and optimize queries
- `query_with_related_records` - Query parent-child records

### 📊 Schema Analysis (6)
- `analyze_object_dependencies` - Full dependency analysis
- `find_unused_fields` - Identify unused fields
- `generate_object_diagram` - Generate ERD data
- `list_all_objects` - List all objects (custom/standard)
- `get_field_usage_stats` - Field population statistics
- **`analyze_field_usage`** - **NEW!** Comprehensive field usage analysis - find where fields are used across ALL metadata (Apex, Triggers, Flows, Validation Rules, Formulas, Page Layouts, Reports) with CSV export

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
- `execute_soql_query` - Run any SOQL query
- `get_metadata_deploy_status` - Check deployment status

### 👥 User Management & Permissions (6)
- `change_user_profile` - Change a user's profile
- `assign_permission_set` - Assign permission set to a user
- `remove_permission_set` - Remove permission set from a user
- `list_user_permissions` - List user's permission sets and profile
- `list_available_profiles` - List all profiles in the org
- `list_available_permission_sets` - List all permission sets in the org

### 🔄 Advanced Comparison Tools (6)
- `compare_profiles` - Compare two profiles side-by-side
- `compare_permission_sets` - Compare two permission sets
- `compare_object_field_counts` - Compare field counts between orgs
- `find_similar_fields_across_objects` - Find fields with similar names/types
- `compare_org_object_counts` - Compare total object counts between orgs
- **`compare_page_layouts`** - **NEW!** Compare page layouts between orgs — fields, sections, and related lists diff with CSV export

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
"Bulk insert 1000 Account records with this CSV data: [...]"

# Bulk Update
"Bulk update all Contacts where State is null to set State = 'Unknown'"

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

### Field Usage Analysis (API-Based)

```
# Analyze single field (fast - excludes reports by default)
"Where is the Case Status field used?"
"Analyze usage of Account.Customer_Type__c field"

# Analyze with reports included (slower but comprehensive)
"Check if Case Status field is used in any reports"
"Analyze Case.Priority including reports"

# Analyze ALL fields on an object (handles 500+ fields)
"Analyze all Case fields and show me where they are used"
"Create a field usage report for all Account fields"

# Analyze all fields including reports
"Analyze all Case fields and check reports too"

# Custom CSV output
"Analyze all Opportunity fields and export to opportunity_audit.csv"

# Results include usage in:
# - Apex Classes (with class names) ✅ Always checked
# - Apex Triggers (with trigger names) ✅ Always checked
# - Flows (with flow names) ✅ Always checked
# - Validation Rules (with rule names) ✅ Always checked
# - Formula Fields (with field names) ✅ Always checked
# - Workflow Rules ✅ Always checked
# - Page Layouts ✅ Always checked
# - Email Templates ✅ Always checked
# - Reports ⚡ Optional (only if you say "include reports" or "check reports")
```

### Automation & Jobs

```
# Batch Jobs
"Show all running batch jobs"
"Get details for batch job 7074x000000AbcD"
"Abort batch job 7074x000000AbcD"

# Scheduled Jobs
"List all scheduled Apex jobs"
"Delete scheduled job 0884x000000XyzA"
```

### User Management

```
# Change User Profiles
"Change profile for user john.doe@example.com to System Administrator"
"Assign Standard User profile to jane.smith@example.com"

# Manage Permission Sets
"Assign Sales_User permission set to john.doe@example.com"
"Remove Marketing_Access permission set from jane.smith@example.com"
"List all permission sets for user john.doe@example.com"

# Query Profiles and Permission Sets
"List all available profiles in the org"
"Show me all permission sets"
```

### Advanced Comparison

```
# Profile Comparison
"Compare System Administrator and Standard User profiles"
"What are the differences between Sales User and Service User profiles?"

# Permission Set Comparison
"Compare Marketing_Admin and Marketing_User permission sets"

# Cross-Org Comparison
"Compare Account object fields between my two connected orgs"
"Find similar fields across Account and Contact objects"
"Compare total object counts between production and sandbox"
```

### Page Layout Comparison (NEW in v2.4!)

```
# Compare one layout between two orgs
"Compare Account page layout between production and sandbox"
→ compare_page_layouts(
    layout_names="Account-Account Layout",
    source_org_user_id="0051a000001XyzABC",
    target_org_user_id="0051b000001DefGHI"
  )

# Compare multiple layouts at once
"Compare Account, Contact, and Case layouts between my two orgs"
→ compare_page_layouts(
    layout_names="Account-Account Layout,Contact-Contact Layout,Case-Case Layout",
    source_org_user_id="0051a000001XyzABC",
    target_org_user_id="0051b000001DefGHI"
  )

# Custom output filename
"Compare Opportunity layout and save report as opp_layout_audit.csv"
→ compare_page_layouts(
    layout_names="Opportunity-Opportunity Layout",
    source_org_user_id="0051a000001XyzABC",
    target_org_user_id="0051b000001DefGHI",
    output_filename="opp_layout_audit.csv"
  )
```

---

## 🎓 Advanced Features

### 🔍 Field Usage Analysis (NEW in v2.2!)

The **`analyze_field_usage`** tool provides comprehensive field usage analysis across your entire Salesforce org. Perfect for field audits, cleanup projects, and impact analysis before making changes.

#### What It Does

Analyzes where fields are used across **ALL metadata types**:
- ✅ **Apex Classes** - Shows which classes reference the field
- ✅ **Apex Triggers** - Identifies trigger dependencies
- ✅ **Flows** - Finds flows using the field (including Process Builder)
- ✅ **Validation Rules** - Checks validation rule formulas
- ✅ **Formula Fields** - Identifies formula field dependencies
- ✅ **Workflow Rules** - Finds workflow field criteria
- ✅ **Page Layouts** - Shows layout field placement
- ✅ **Reports** - Identifies reports using the field

#### Use Cases

1. **Field Cleanup** - Find unused fields before archiving
2. **Impact Analysis** - Understand dependencies before changes
3. **Compliance Audit** - Document field usage for auditors
4. **Migration Planning** - Map field usage across orgs
5. **Documentation** - Generate comprehensive field reference

#### How to Use

```
# Analyze a single field
"Where is the Case Status field used?"

# Analyze ALL fields on an object (handles 500+ fields efficiently)
"Analyze all Case fields and create a CSV report"

# Custom output filename
"Analyze Account fields and save to account_field_audit.csv"
```

#### CSV Output

The tool automatically generates a CSV file saved in the **`Documents/`** folder with these columns:
- Field Name, Label, Type
- Is Custom, Is Required
- Apex Classes Count + Names
- Triggers Count + Names
- Flows Count + Names
- Validation Rules Count + Names
- Formula Fields Count + Names
- Workflow Rules Count + Names
- Page Layouts Count + Names
- Reports Count + Names
- Total Usage Count
- Is Referenced (Yes/No)

**Storage Location:** `Documents/{ObjectName}_field_usage_{timestamp}.csv`

#### Performance

**NEW in v2.2 - MASSIVELY IMPROVED:**
- **5-6x faster** with intelligent batch processing
- **500 fields analyzed in 5-10 minutes** (was 30-45 minutes!)
- **99% fewer API calls** - Only ~15-20 calls for any field count
- **Smart caching** - Fetches ALL metadata once, checks all fields against it
- **Progress tracking** - Updates every 50 fields
- **Memory efficient** - Handles unlimited fields

**How it works:**
1. Fetches all Apex, Triggers, Flows, Validations, Workflows, Layouts, Reports ONCE
2. Caches everything in memory
3. Checks all fields against cached data (instant!)
4. Result: 500 fields in ~5-10 minutes instead of 45 minutes!

### Configuration

Create a `.env` file (copy from `.env.example`):

```env
# License Key (required - get from MCP Admin)
APP_ENCRYPTION_KEY=your-encryption-key-here
APP_PASSWORD_ENC=your-encrypted-password-here

# Server Configuration
SFMCP_MCP_SERVER_NAME=salesforce-mcp-server
SFMCP_LOG_LEVEL=INFO
SFMCP_DEBUG_MODE=false

# OAuth Configuration
SFMCP_OAUTH_CALLBACK_PORT=1717
SFMCP_OAUTH_TIMEOUT_SECONDS=300

# API Configuration
SFMCP_SALESFORCE_API_VERSION=59.0
SFMCP_MAX_RETRIES=3
SFMCP_REQUEST_TIMEOUT_SECONDS=120

# Deployment
SFMCP_DEPLOY_TIMEOUT_SECONDS=300
SFMCP_DEPLOY_POLL_INTERVAL_SECONDS=5
```

> **Note:** The `APP_ENCRYPTION_KEY` and `APP_PASSWORD_ENC` are required to run the server. Contact your MCP Admin to get a valid license key. Keys are rotated weekly for security.

### 📁 Project Structure

```
Salesforce-MCP-Server/
├── app/
│   ├── main.py                          # Entry point, tool imports
│   ├── config.py                        # Configuration management
│   │
│   ├── mcp/
│   │   ├── server.py                    # MCP server setup, tool registration
│   │   └── tools/                       # All 57 MCP tools
│   │       ├── __init__.py
│   │       ├── consolidated_metadata.py      # Unified metadata deploy/fetch/list
│   │       ├── consolidated_operations.py    # Bulk ops, export, queries, permissions
│   │       ├── oauth_auth.py                 # OAuth 2.0 authentication
│   │       ├── debugging.py                  # NEW: Issue diagnosis (25 QA patterns)
│   │       ├── dynamic_tools.py              # Apex, triggers, flows, etc.
│   │       ├── multi_org.py                  # Multi-org management
│   │       ├── advanced_comparison.py        # Profile/permset/schema comparison
│   │       ├── user_management.py            # User profile/permission management
│   │       ├── schema_analysis.py            # Dependencies, unused fields, ERDs
│   │       ├── org_management.py             # Health check, limits, org info
│   │       ├── automation.py                 # Batch jobs, scheduled jobs
│   │       ├── testing.py                    # Apex tests, coverage
│   │       ├── bulk_operations.py            # Bulk API operations
│   │       ├── data_export.py                # Export/backup tools
│   │       ├── query_helpers.py              # Query builders
│   │       └── utils.py                      # Response formatting, error handling
│   │
│   ├── services/
│   │   └── salesforce.py                # Salesforce connection management
│   │
│   └── utils/                           # Production-grade utilities
│       ├── __init__.py                  # Utility exports
│       ├── validators.py                # SOQL injection protection, input validation
│       ├── retry.py                     # Retry logic with exponential backoff
│       ├── logging.py                   # Structured logging
│       ├── cache.py                     # NEW: Caching system (LRU, metadata cache)
│       ├── errors.py                    # NEW: Enhanced error handling
│       ├── pagination.py                # NEW: Pagination utilities
│       └── connection_pool.py           # NEW: Connection pooling
│
├── requirements.txt                      # Dependencies
├── .env.example                          # Example configuration
├── README.md                             # Main documentation
├── test_all_mcp_tools.py                 # Comprehensive testing suite
├── setup.bat                             # Windows setup script (one-click install)
├── setup.sh                              # macOS/Linux setup script (one-click install)
├── start_mcp.bat                         # Windows startup script (stdio mode)
├── start_mcp.sh                          # macOS/Linux startup script (stdio mode)
├── start_http.bat                        # Windows HTTP/SSE server startup
├── start_http.sh                         # macOS/Linux HTTP/SSE server startup
└── Documents/                            # CSV exports and reports stored here
    ├── README.md                         # Documents folder info
    └── *.csv                             # Field usage reports, data exports
```

**Total Size:** 12,500+ lines of Python code (tools only)

### Retry Logic

All API calls automatically retry with exponential backoff:
- Max attempts: 3 (configurable)
- Backoff multiplier: 2.0
- Handles transient failures gracefully

### Input Validation

Built-in protection against:
- SOQL injection
- Invalid metadata names
- Malformed API requests
- Unsafe operations

### Structured Logging

Track all operations with correlation IDs:
- Request tracking
- Error debugging
- Performance monitoring
- Audit trails

### Advanced Infrastructure

Built-in production-grade utilities for optimal performance:

#### Caching System
- **LRU cache** for metadata and field definitions
- **Automatic cache invalidation** with TTL
- **Validation rule caching** for faster lookups
- Significant performance improvements for repeated queries

#### Enhanced Error Handling
- **Custom `SalesforceError` exception** with error categories
- **Error categories:** auth, query, deployment, bulk operations
- **Troubleshooting hints** embedded in error messages
- **Structured error responses** with actionable suggestions

#### Pagination Support
- **Cursor-based pagination** for large result sets
- **SOQL pagination helpers** with automatic batching
- **List pagination** for API responses
- Handle datasets of any size efficiently

#### Connection Pooling
- **Multi-org connection pooling** with state management
- **Thread-local storage** for connection isolation
- **Pool statistics** and monitoring
- **Automatic cleanup** of stale connections

---

## 🔧 Troubleshooting

### "You don't have an active key"
**Solution:** Contact MCP Admin to get your `APP_ENCRYPTION_KEY` and `APP_PASSWORD_ENC`, then add them to your `.env` file.

### "Invalid or expired license key"
**Solution:** Your weekly license key has expired. Contact MCP Admin for a new key.

### "No active Salesforce sessions found"
**Solution:** Login first: `"Login to Salesforce production"`

### "Token expired"
**Solution:** Logout and re-login:
```
"Logout from all Salesforce orgs"
"Login to Salesforce production"
```

### "Deployment timeout"
**Solution:** Increase timeout in `.env`:
```env
SFMCP_DEPLOY_TIMEOUT_SECONDS=600
```

### "API limit exceeded"
**Solution:** Check limits: `"Get org limits"`

### "Wrong org being used"
**Solution:**
```
"List connected orgs"
"Switch to org [user_id]"
```

### Tools not showing in Claude
**Solution:**
1. Check Claude Desktop config file
2. Verify absolute path is correct
3. Restart Claude Desktop
4. Check logs: `%APPDATA%\Claude\logs\`

---

## 🤝 Contributing

We welcome contributions! See our [Contributing Guide](CONTRIBUTING.md) for details.

### Adding New Tools

1. **Create tool function** in appropriate module under `app/mcp/tools/`
2. **Add `@register_tool` decorator**
3. **Write docstring** with examples
4. **Add attribution**: `"Added by Sameer"` in docstring
5. **Test thoroughly** before submitting PR
6. **Update documentation** in `COMPLETE_GUIDE.md`

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

## 🌟 Star History

If this project saved you time, please star the repository! ⭐

---

**Built with ☕, code, and curiosity by Sameer** 

