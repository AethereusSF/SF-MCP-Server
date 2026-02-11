"""
Consolidated operation tools - bulk ops, data export, queries, and user management
Reduces ~25 tools to ~10 manageable tools

Created by Sameer
"""
import json
import logging
import csv
import io
from typing import Optional, List, Dict, Any

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection
from app.utils.validators import validate_soql_query, ValidationError
from app.mcp.tools.utils import format_error_response, format_success_response

# Import existing implementations to reuse logic
from app.mcp.tools import bulk_operations, data_export, query_helpers, user_management

logger = logging.getLogger(__name__)


# ============================================================================
# BULK OPERATIONS (4 → 2 tools)
# ============================================================================

@register_tool
def bulk_operation(
    object_name: str,
    operation: str,
    records: str,
    external_id_field: str = None
) -> str:
    """
    Perform bulk operations on Salesforce records using Bulk API 2.0.

    Consolidates: bulk_insert_records, bulk_update_records, bulk_delete_records

    Supports operations:
    - insert: Create new records
    - update: Update existing records (requires Id field)
    - delete: Delete records (requires Id field)
    - upsert: Insert or update based on external ID

    Args:
        object_name: Salesforce object (e.g., "Account", "Contact")
        operation: "insert", "update", "delete", or "upsert"
        records: JSON array of records or CSV string
        external_id_field: Required for upsert operation (e.g., "Email__c")

    Returns:
        JSON response with job ID and status

    Example:
        # Bulk insert accounts
        bulk_operation(
            "Account",
            "insert",
            '[{"Name": "Acme Corp", "Industry": "Technology"}, {"Name": "TechCo"}]'
        )

        # Bulk update contacts
        bulk_operation(
            "Contact",
            "update",
            '[{"Id": "003xxx", "Email": "new@email.com"}]'
        )

        # Bulk upsert with external ID
        bulk_operation(
            "Lead",
            "upsert",
            '[{"Email__c": "test@example.com", "LastName": "Doe"}]',
            external_id_field="Email__c"
        )
    """
    try:
        operation = operation.lower()

        # Validate operation
        if operation not in ["insert", "update", "delete", "upsert"]:
            return format_error_response(
                Exception(f"Invalid operation: {operation}. Must be: insert, update, delete, or upsert"),
                context="bulk_operation"
            )

        # Validate external_id_field for upsert
        if operation == "upsert" and not external_id_field:
            return format_error_response(
                Exception("external_id_field is required for upsert operation"),
                context="bulk_operation"
            )

        # Route to appropriate handler
        if operation == "insert":
            return bulk_operations.bulk_insert_records(object_name, records)

        elif operation == "update":
            return bulk_operations.bulk_update_records(object_name, records)

        elif operation == "delete":
            return bulk_operations.bulk_delete_records(object_name, records)

        elif operation == "upsert":
            # Note: Original bulk_operations may not have upsert, so we'll use insert for now
            # You can enhance this later
            return format_error_response(
                Exception("Upsert operation not yet implemented. Use insert or update."),
                context="bulk_operation"
            )

    except Exception as e:
        logger.exception("bulk_operation failed")
        return format_error_response(e, context="bulk_operation")


# Keep existing get_bulk_job_status - it's already a single focused tool


# ============================================================================
# DATA EXPORT (5 → 2 tools)
# ============================================================================

@register_tool
def export_data(
    object_name: str,
    format: str = "csv",
    query: str = None,
    fields: str = None,
    where_clause: str = None,
    limit: int = None,
    include_timestamp: bool = False
) -> str:
    """
    Export Salesforce data in various formats.

    Consolidates: export_data_to_csv, export_object_data, backup_object_records

    Supported formats:
    - csv: Export as CSV file
    - json: Export as JSON
    - backup: Full timestamped backup of all records

    Args:
        object_name: Salesforce object (e.g., "Account")
        format: "csv", "json", or "backup"
        query: Custom SOQL query (overrides other parameters)
        fields: Comma-separated field list (e.g., "Id,Name,Email")
        where_clause: WHERE clause filter (e.g., "Industry = 'Technology'")
        limit: Maximum records to export
        include_timestamp: Add timestamp to backup filename

    Returns:
        JSON response with exported data or file path

    Example:
        # Export to CSV
        export_data("Account", format="csv", fields="Id,Name,Industry", limit=1000)

        # Full backup
        export_data("Contact", format="backup", include_timestamp=True)

        # Custom query
        export_data("Opportunity", query="SELECT Id, Name, Amount FROM Opportunity WHERE StageName = 'Closed Won'")

        # Export to JSON
        export_data("Lead", format="json", where_clause="Status = 'Open'", limit=500)
    """
    try:
        format = format.lower()

        # Validate format
        if format not in ["csv", "json", "backup"]:
            return format_error_response(
                Exception(f"Invalid format: {format}. Must be: csv, json, or backup"),
                context="export_data"
            )

        # Build query if not provided
        if not query:
            if not fields:
                # Get all fields for the object
                sf = get_salesforce_connection()
                describe = sf.__getattr__(object_name).describe()
                fields = ",".join([f["name"] for f in describe["fields"][:50]])  # Limit to 50 fields

            query = f"SELECT {fields} FROM {object_name}"
            if where_clause:
                query += f" WHERE {where_clause}"
            if limit:
                query += f" LIMIT {limit}"

        # Route to appropriate handler based on format
        if format == "csv":
            return data_export.export_data_to_csv(query)

        elif format == "json":
            # Execute query and return as JSON
            sf = get_salesforce_connection()
            result = sf.query(query)

            return format_success_response({
                "format": "json",
                "object_name": object_name,
                "total_size": result["totalSize"],
                "records": result["records"]
            })

        elif format == "backup":
            return data_export.backup_object_records(object_name)

    except Exception as e:
        logger.exception("export_data failed")
        return format_error_response(e, context="export_data")


# Keep existing get_record_count - it's already a single focused tool
# Keep existing export_schema_to_json - it's a unique capability


# ============================================================================
# QUERY OPERATIONS (5 → 3 tools)
# ============================================================================

@register_tool
def soql_query(
    query: str = None,
    object_name: str = None,
    fields: str = None,
    where_clause: str = None,
    order_by: str = None,
    limit: int = None,
    explain: bool = False
) -> str:
    """
    Execute SOQL query or build and execute using parameters.

    Consolidates: execute_soql_query, build_soql_query, explain_soql_query

    You can either:
    1. Provide a complete SOQL query string
    2. Use parameters to build a query automatically

    Args:
        query: Complete SOQL query (overrides other parameters)
        object_name: Object to query (if building query)
        fields: Comma-separated fields (e.g., "Id,Name,Email")
        where_clause: Filter conditions (e.g., "Industry = 'Technology' AND AnnualRevenue > 1000000")
        order_by: Sort order (e.g., "Name ASC", "CreatedDate DESC")
        limit: Maximum records to return
        explain: Include query analysis and optimization suggestions

    Returns:
        JSON response with query results and optional analysis

    Example:
        # Direct query
        soql_query(query="SELECT Id, Name FROM Account WHERE Industry = 'Technology' LIMIT 10")

        # Build query from parameters
        soql_query(
            object_name="Contact",
            fields="Id,Name,Email,Account.Name",
            where_clause="Email != null",
            order_by="CreatedDate DESC",
            limit=50
        )

        # Query with analysis
        soql_query(
            object_name="Opportunity",
            fields="Id,Name,Amount,StageName",
            where_clause="StageName = 'Closed Won'",
            explain=True
        )
    """
    try:
        # Build query if parameters provided
        if not query:
            if not object_name or not fields:
                return format_error_response(
                    Exception("Either 'query' or 'object_name' and 'fields' must be provided"),
                    context="soql_query"
                )

            # Build query
            built_query = query_helpers.build_soql_query(
                object_name=object_name,
                fields=fields.split(",") if isinstance(fields, str) else fields,
                where_clause=where_clause,
                order_by=order_by,
                limit=limit
            )

            # Extract query string from JSON response
            built_result = json.loads(built_query)
            if not built_result.get("success"):
                return built_query
            query = built_result["query"]

        # Execute query
        from app.mcp.tools.dynamic_tools import execute_soql_query
        result = execute_soql_query(query)

        # Add explanation if requested
        if explain:
            result_dict = json.loads(result)
            if result_dict.get("success"):
                explain_result = query_helpers.explain_soql_query(query)
                explain_dict = json.loads(explain_result)
                if explain_dict.get("success"):
                    result_dict["query_analysis"] = explain_dict.get("analysis")
                result = json.dumps(result_dict, indent=2)

        return result

    except Exception as e:
        logger.exception("soql_query failed")
        return format_error_response(e, context="soql_query")


@register_tool
def get_object_metadata(
    object_name: str,
    include_fields: bool = True,
    include_relationships: bool = True,
    field_types_filter: str = None
) -> str:
    """
    Get comprehensive object metadata including fields and relationships.

    Consolidates: get_object_fields, get_field_relationships

    Args:
        object_name: Salesforce object (e.g., "Account", "Contact")
        include_fields: Include field metadata
        include_relationships: Include relationship fields
        field_types_filter: Comma-separated field types to filter (e.g., "reference,text,number")

    Returns:
        JSON response with object metadata

    Example:
        # Get all metadata
        get_object_metadata("Account")

        # Get only relationships
        get_object_metadata("Contact", include_fields=False, include_relationships=True)

        # Get only specific field types
        get_object_metadata("Opportunity", field_types_filter="reference,picklist")
    """
    try:
        response_data = {
            "object_name": object_name
        }

        # Get fields
        if include_fields:
            fields_result = query_helpers.get_object_fields(object_name)
            fields_dict = json.loads(fields_result)
            if fields_dict.get("success"):
                fields = fields_dict.get("fields", [])

                # Apply field type filter if provided
                if field_types_filter:
                    filter_types = [t.strip().lower() for t in field_types_filter.split(",")]
                    fields = [f for f in fields if f.get("type", "").lower() in filter_types]

                response_data["fields"] = fields
                response_data["field_count"] = len(fields)

        # Get relationships
        if include_relationships:
            rel_result = query_helpers.get_field_relationships(object_name)
            rel_dict = json.loads(rel_result)
            if rel_dict.get("success"):
                response_data["relationships"] = rel_dict.get("relationships", [])
                response_data["relationship_count"] = len(rel_dict.get("relationships", []))

        return format_success_response(response_data)

    except Exception as e:
        logger.exception("get_object_metadata failed")
        return format_error_response(e, context="get_object_metadata")


# Keep query_with_related_records - it's a specialized capability


# ============================================================================
# USER MANAGEMENT (6 → 3 tools)
# ============================================================================

@register_tool
def manage_user_permissions(
    username: str,
    action: str,
    profile_name: str = None,
    permission_set_name: str = None
) -> str:
    """
    Manage user permissions, profiles, and permission sets.

    Consolidates: change_user_profile, assign_permission_set, remove_permission_set, list_user_permissions

    Supported actions:
    - set_profile: Change user's profile
    - assign_permset: Assign a permission set
    - remove_permset: Remove a permission set
    - list: List user's current permissions

    Args:
        username: Salesforce username (email)
        action: "set_profile", "assign_permset", "remove_permset", or "list"
        profile_name: Profile name (required for set_profile)
        permission_set_name: Permission set name (required for assign/remove_permset)

    Returns:
        JSON response with operation result

    Example:
        # Change user profile
        manage_user_permissions("user@example.com", "set_profile", profile_name="System Administrator")

        # Assign permission set
        manage_user_permissions("user@example.com", "assign_permset", permission_set_name="Sales_User")

        # Remove permission set
        manage_user_permissions("user@example.com", "remove_permset", permission_set_name="Marketing_Access")

        # List user permissions
        manage_user_permissions("user@example.com", "list")
    """
    try:
        action = action.lower()

        # Validate action
        valid_actions = ["set_profile", "assign_permset", "remove_permset", "list"]
        if action not in valid_actions:
            return format_error_response(
                Exception(f"Invalid action: {action}. Must be one of: {', '.join(valid_actions)}"),
                context="manage_user_permissions"
            )

        # Route to appropriate handler
        if action == "set_profile":
            if not profile_name:
                return format_error_response(
                    Exception("profile_name is required for set_profile action"),
                    context="manage_user_permissions"
                )
            return user_management.change_user_profile(username, profile_name)

        elif action == "assign_permset":
            if not permission_set_name:
                return format_error_response(
                    Exception("permission_set_name is required for assign_permset action"),
                    context="manage_user_permissions"
                )
            return user_management.assign_permission_set(username, permission_set_name)

        elif action == "remove_permset":
            if not permission_set_name:
                return format_error_response(
                    Exception("permission_set_name is required for remove_permset action"),
                    context="manage_user_permissions"
                )
            return user_management.remove_permission_set(username, permission_set_name)

        elif action == "list":
            return user_management.list_user_permissions(username)

    except Exception as e:
        logger.exception("manage_user_permissions failed")
        return format_error_response(e, context="manage_user_permissions")


# Keep list_available_profiles - distinct capability
# Keep list_available_permission_sets - distinct capability
