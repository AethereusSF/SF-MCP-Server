"""Enhanced error handling with actionable suggestions for Salesforce MCP Server.

Provides:
- Salesforce error code mapping to friendly messages
- Actionable suggestions for common errors
- Error categorization (auth, permissions, validation, limits, etc.)
- Structured error responses

Created by Sameer
"""
import re
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of Salesforce errors for better handling"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    API_LIMIT = "api_limit"
    DATA_INTEGRITY = "data_integrity"
    NOT_FOUND = "not_found"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    SYNTAX = "syntax"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class SalesforceError:
    """Structured Salesforce error with suggestions"""
    error_code: str
    message: str
    category: ErrorCategory
    suggestions: List[str] = field(default_factory=list)
    documentation_link: Optional[str] = None
    original_error: Optional[str] = None
    field_name: Optional[str] = None
    object_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "suggestions": self.suggestions,
            "documentation_link": self.documentation_link,
            "original_error": self.original_error,
            "field_name": self.field_name,
            "object_name": self.object_name
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


# =============================================================================
# SALESFORCE ERROR PATTERNS AND SUGGESTIONS
# =============================================================================

SALESFORCE_ERROR_PATTERNS: Dict[str, Dict[str, Any]] = {
    # Authentication Errors
    "INVALID_SESSION_ID": {
        "category": ErrorCategory.AUTHENTICATION,
        "message": "Your Salesforce session has expired or is invalid.",
        "suggestions": [
            "Re-authenticate using salesforce_sandbox_login or salesforce_production_login",
            "Check if your access token has expired",
            "Verify your connected app settings in Salesforce Setup",
            "Ensure IP restrictions are not blocking your connection"
        ],
        "doc_link": "https://help.salesforce.com/s/articleView?id=sf.connected_app_overview.htm"
    },
    "INVALID_LOGIN": {
        "category": ErrorCategory.AUTHENTICATION,
        "message": "Login credentials are invalid.",
        "suggestions": [
            "Verify your username and password are correct",
            "Check if your account is locked or requires password reset",
            "Ensure you're using the correct login URL (test.salesforce.com for sandbox)",
            "Verify security token is appended to password if required"
        ]
    },
    "INVALID_GRANT": {
        "category": ErrorCategory.AUTHENTICATION,
        "message": "OAuth grant is invalid or expired.",
        "suggestions": [
            "Re-authenticate using the login tools",
            "Check if refresh token has been revoked",
            "Verify Connected App permissions in Salesforce",
            "Clear stored tokens using salesforce_logout and re-login"
        ]
    },

    # Authorization/Permission Errors
    "INSUFFICIENT_ACCESS": {
        "category": ErrorCategory.AUTHORIZATION,
        "message": "You don't have permission to access this resource.",
        "suggestions": [
            "Check user profile permissions for the object",
            "Verify field-level security settings",
            "Ensure user has appropriate permission sets assigned",
            "Check sharing rules and record ownership",
            "Use list_user_permissions to see current user access"
        ]
    },
    "INSUFFICIENT_ACCESS_OR_READONLY": {
        "category": ErrorCategory.AUTHORIZATION,
        "message": "Insufficient access rights or the record is read-only.",
        "suggestions": [
            "Check if user has Edit permission on the object",
            "Verify the record is not locked by an approval process",
            "Check for validation rules preventing the edit",
            "Ensure the record type allows modifications"
        ]
    },
    "FIELD_CUSTOM_VALIDATION_EXCEPTION": {
        "category": ErrorCategory.VALIDATION,
        "message": "A validation rule is preventing this operation.",
        "suggestions": [
            "Use diagnose_and_fix_issue with issue_type='validation' to identify the rule",
            "Check active validation rules on the object",
            "Review the error message for specific field requirements",
            "Ensure all required fields have valid values"
        ]
    },
    "CANNOT_INSERT_UPDATE_ACTIVATE_ENTITY": {
        "category": ErrorCategory.VALIDATION,
        "message": "A trigger or process is preventing this operation.",
        "suggestions": [
            "Check for triggers on the object that may be failing",
            "Review Process Builder or Flow automations",
            "Look for recursion issues in triggers",
            "Use diagnose_and_fix_issue with issue_type='trigger' for analysis"
        ]
    },

    # Data Integrity Errors
    "REQUIRED_FIELD_MISSING": {
        "category": ErrorCategory.DATA_INTEGRITY,
        "message": "A required field is missing.",
        "suggestions": [
            "Use fetch_object_metadata to see all required fields",
            "Check page layout for required field indicators",
            "Ensure all fields marked as required have values",
            "Review field-level security to ensure fields are visible"
        ]
    },
    "DUPLICATE_VALUE": {
        "category": ErrorCategory.DATA_INTEGRITY,
        "message": "A duplicate value was found for a unique field.",
        "suggestions": [
            "Query existing records to find the duplicate",
            "Check for duplicate rules on the object",
            "Verify the unique field value is actually unique",
            "Consider using upsert with an external ID instead"
        ]
    },
    "DELETE_FAILED": {
        "category": ErrorCategory.DATA_INTEGRITY,
        "message": "Cannot delete this record.",
        "suggestions": [
            "Check for child records that reference this record",
            "Verify the record is not referenced by lookup relationships",
            "Ensure no workflows or processes depend on this record",
            "Check if deletion is blocked by triggers or validation rules"
        ]
    },
    "ENTITY_IS_DELETED": {
        "category": ErrorCategory.DATA_INTEGRITY,
        "message": "The record has been deleted.",
        "suggestions": [
            "Check if the record is in the Recycle Bin",
            "Query the record with ALL ROWS to find deleted records",
            "Undelete the record if needed using the Salesforce UI",
            "Verify you're using the correct record ID"
        ]
    },

    # API Limit Errors
    "REQUEST_LIMIT_EXCEEDED": {
        "category": ErrorCategory.API_LIMIT,
        "message": "API request limit has been exceeded.",
        "suggestions": [
            "Use get_org_limits to check current API usage",
            "Implement bulk operations instead of individual calls",
            "Add caching to reduce redundant API calls",
            "Consider upgrading org edition for higher limits",
            "Wait for the limit to reset (usually 24 hours)"
        ]
    },
    "QUERY_TIMEOUT": {
        "category": ErrorCategory.API_LIMIT,
        "message": "The query took too long to execute.",
        "suggestions": [
            "Add selective filters to reduce result set",
            "Create custom indexes on frequently queried fields",
            "Use LIMIT clause to reduce returned records",
            "Break complex queries into smaller parts",
            "Avoid querying non-selective fields"
        ]
    },
    "TOO_MANY_SOQL_QUERIES": {
        "category": ErrorCategory.API_LIMIT,
        "message": "Too many SOQL queries in a single transaction.",
        "suggestions": [
            "Combine multiple queries into one using subqueries",
            "Use batch processing for large operations",
            "Review triggers for inefficient query patterns",
            "Cache query results when possible"
        ]
    },

    # Not Found Errors
    "NOT_FOUND": {
        "category": ErrorCategory.NOT_FOUND,
        "message": "The requested resource was not found.",
        "suggestions": [
            "Verify the record ID or API name is correct",
            "Check if the object/field exists in the org",
            "Use list_all_objects or list_metadata to find available resources",
            "Ensure you have visibility to the resource"
        ]
    },
    "INVALID_FIELD": {
        "category": ErrorCategory.NOT_FOUND,
        "message": "One or more field names are invalid.",
        "suggestions": [
            "Use fetch_object_metadata to see valid field names",
            "Check field API names (not labels) - usually ends with __c for custom",
            "Verify field-level security allows access to the field",
            "Ensure custom field deployment is complete"
        ]
    },
    "INVALID_TYPE": {
        "category": ErrorCategory.NOT_FOUND,
        "message": "The object type is invalid or doesn't exist.",
        "suggestions": [
            "Use list_all_objects to see available objects",
            "Check the object API name (not label)",
            "Verify custom object deployment is complete",
            "Ensure object is enabled for your user profile"
        ]
    },

    # SOQL Syntax Errors
    "MALFORMED_QUERY": {
        "category": ErrorCategory.SYNTAX,
        "message": "The SOQL query has a syntax error.",
        "suggestions": [
            "Check for missing or misplaced keywords (SELECT, FROM, WHERE)",
            "Verify all field names are valid",
            "Ensure string values are properly quoted with single quotes",
            "Use soql_query tool with explain=True for query analysis",
            "Check parentheses are balanced in complex conditions"
        ]
    },
    "INVALID_QUERY_FILTER_OPERATOR": {
        "category": ErrorCategory.SYNTAX,
        "message": "Invalid operator used in query filter.",
        "suggestions": [
            "Valid operators: =, !=, <, >, <=, >=, LIKE, IN, NOT IN",
            "Use LIKE with % wildcard for partial matching",
            "Use IN for multiple value matching",
            "Ensure operator is appropriate for field type"
        ]
    },

    # Configuration Errors
    "UNABLE_TO_LOCK_ROW": {
        "category": ErrorCategory.CONFIGURATION,
        "message": "Unable to obtain exclusive access to this record.",
        "suggestions": [
            "Another transaction is currently modifying this record",
            "Retry the operation after a brief delay",
            "Check for long-running batch jobs that may lock records",
            "Review triggers that might cause lock contention"
        ]
    },
    "STORAGE_LIMIT_EXCEEDED": {
        "category": ErrorCategory.CONFIGURATION,
        "message": "Organization storage limit has been exceeded.",
        "suggestions": [
            "Delete unnecessary records from the org",
            "Archive old data to external storage",
            "Check Recycle Bin for records to permanently delete",
            "Contact Salesforce to increase storage limits"
        ]
    },

    # Network Errors
    "CONNECTION_RESET": {
        "category": ErrorCategory.NETWORK,
        "message": "Connection to Salesforce was reset.",
        "suggestions": [
            "Check your internet connection",
            "Retry the request after a moment",
            "Verify Salesforce services are operational at status.salesforce.com",
            "Check if corporate firewall is blocking connections"
        ]
    },
    "TIMEOUT": {
        "category": ErrorCategory.NETWORK,
        "message": "Request timed out.",
        "suggestions": [
            "Retry the request",
            "Reduce the complexity of the operation",
            "Check Salesforce Trust site for service issues",
            "Consider breaking the operation into smaller parts"
        ]
    }
}


# =============================================================================
# ERROR MESSAGE ENHANCEMENT FUNCTIONS
# =============================================================================

def parse_salesforce_error(error_message: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Parse a Salesforce error message to extract error code and details.

    Args:
        error_message: Raw error message from Salesforce

    Returns:
        Tuple of (error_code, field_name, object_name)
    """
    error_code = "UNKNOWN_ERROR"
    field_name = None
    object_name = None

    # Try to extract error code from common patterns
    patterns = [
        r"\[(\w+)\]",  # [ERROR_CODE]
        r"errorCode['\"]?\s*[:=]\s*['\"]?(\w+)",  # errorCode: ERROR_CODE
        r"^(\w+_\w+):",  # ERROR_CODE: message
        r"exception.*?(\w+Exception)",  # SomeException
    ]

    for pattern in patterns:
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            error_code = match.group(1).upper()
            break

    # Extract field name if present
    field_patterns = [
        r"field[:\s]+['\"]?(\w+)['\"]?",
        r"(\w+__c)\s+(?:is|does|cannot)",
        r"(?:on|for)\s+field\s+['\"]?(\w+)"
    ]
    for pattern in field_patterns:
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            field_name = match.group(1)
            break

    # Extract object name if present
    object_patterns = [
        r"object[:\s]+['\"]?(\w+)['\"]?",
        r"(?:on|from|to)\s+(\w+__c)",
        r"(?:Account|Contact|Lead|Opportunity|Case|(\w+__c))"
    ]
    for pattern in object_patterns:
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            object_name = match.group(1)
            break

    return error_code, field_name, object_name


def enhance_error_message(
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> SalesforceError:
    """
    Enhance a raw error into a structured error with suggestions.

    Args:
        error: The original exception
        context: Optional context (object_name, field_name, operation, etc.)

    Returns:
        SalesforceError with detailed message and suggestions
    """
    error_message = str(error)
    error_code, field_name, object_name = parse_salesforce_error(error_message)

    # Check context for additional info
    if context:
        field_name = field_name or context.get("field_name")
        object_name = object_name or context.get("object_name")

    # Look up error pattern
    error_info = SALESFORCE_ERROR_PATTERNS.get(error_code, {})

    # Build enhanced error
    category = error_info.get("category", ErrorCategory.UNKNOWN)
    message = error_info.get("message", f"An error occurred: {error_message}")
    suggestions = error_info.get("suggestions", [])
    doc_link = error_info.get("doc_link")

    # Add context-specific suggestions
    if not suggestions:
        suggestions = _generate_contextual_suggestions(error_message, context)

    return SalesforceError(
        error_code=error_code,
        message=message,
        category=category,
        suggestions=suggestions,
        documentation_link=doc_link,
        original_error=error_message,
        field_name=field_name,
        object_name=object_name
    )


def _generate_contextual_suggestions(
    error_message: str,
    context: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Generate suggestions based on error message content"""
    suggestions = []
    error_lower = error_message.lower()

    # Authentication related
    if any(term in error_lower for term in ["session", "token", "login", "auth"]):
        suggestions.extend([
            "Check authentication status using salesforce_auth_status",
            "Try logging out and back in using salesforce_logout then salesforce_login",
            "Verify your session hasn't timed out"
        ])

    # Permission related
    if any(term in error_lower for term in ["permission", "access", "denied", "insufficient"]):
        suggestions.extend([
            "Use list_available_profiles and list_available_permission_sets to check access",
            "Verify field-level security and object permissions",
            "Check sharing rules and ownership"
        ])

    # Query related
    if any(term in error_lower for term in ["query", "soql", "select", "from"]):
        suggestions.extend([
            "Check field and object API names are correct",
            "Use fetch_object_metadata to verify available fields",
            "Ensure WHERE clause values are properly formatted"
        ])

    # Trigger/Flow related
    if any(term in error_lower for term in ["trigger", "flow", "process", "workflow"]):
        suggestions.extend([
            "Use diagnose_and_fix_issue to analyze automation issues",
            "Check for recursion in triggers",
            "Review Flow and Process Builder for failing automations"
        ])

    # Validation related
    if any(term in error_lower for term in ["validation", "required", "invalid"]):
        suggestions.extend([
            "Check validation rules on the object",
            "Ensure all required fields have values",
            "Review field data types and format requirements"
        ])

    # If no specific suggestions, add generic ones
    if not suggestions:
        suggestions = [
            "Check the Salesforce debug logs for more details",
            "Verify the operation and data are correct",
            "Consult Salesforce documentation for the specific error",
            "Use salesforce_health_check to verify connection"
        ]

    return suggestions


def create_error_response(
    success: bool = False,
    error: Optional[Exception] = None,
    error_message: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    include_suggestions: bool = True
) -> str:
    """
    Create a standardized JSON error response with suggestions.

    Args:
        success: Operation success status
        error: Optional exception object
        error_message: Optional error message string
        context: Optional context for better suggestions
        include_suggestions: Whether to include suggestions

    Returns:
        JSON string with error details and suggestions
    """
    response: Dict[str, Any] = {"success": success}

    if error or error_message:
        if error:
            enhanced = enhance_error_message(error, context)
        else:
            # Create a mock exception for the message
            enhanced = enhance_error_message(Exception(error_message), context)

        response["error"] = enhanced.message
        response["error_code"] = enhanced.error_code
        response["category"] = enhanced.category.value

        if include_suggestions and enhanced.suggestions:
            response["suggestions"] = enhanced.suggestions

        if enhanced.documentation_link:
            response["documentation"] = enhanced.documentation_link

        if enhanced.original_error and enhanced.original_error != enhanced.message:
            response["original_error"] = enhanced.original_error

        if enhanced.field_name:
            response["field"] = enhanced.field_name
        if enhanced.object_name:
            response["object"] = enhanced.object_name

    return json.dumps(response, indent=2)


# =============================================================================
# COMMON ERROR HANDLERS FOR SPECIFIC SCENARIOS
# =============================================================================

def handle_authentication_error(error: Exception) -> str:
    """Handle authentication-specific errors"""
    return create_error_response(
        success=False,
        error=error,
        context={"operation": "authentication"}
    )


def handle_query_error(
    error: Exception,
    query: Optional[str] = None,
    object_name: Optional[str] = None
) -> str:
    """Handle SOQL query errors with query-specific suggestions"""
    context = {
        "operation": "query",
        "object_name": object_name
    }

    response_data = json.loads(create_error_response(
        success=False,
        error=error,
        context=context
    ))

    # Add query-specific suggestions
    if query:
        response_data["failed_query"] = query

        # Analyze query for common issues
        query_suggestions = []

        if "'" not in query and any(kw in query.upper() for kw in ["WHERE", "LIKE"]):
            query_suggestions.append("String values in WHERE clause must be wrapped in single quotes")

        if query.count("(") != query.count(")"):
            query_suggestions.append("Check for unbalanced parentheses in the query")

        if "SELECT *" in query.upper():
            query_suggestions.append("Salesforce doesn't support SELECT * - specify field names explicitly")

        if query_suggestions:
            response_data["query_analysis"] = query_suggestions

    return json.dumps(response_data, indent=2)


def handle_deployment_error(
    error: Exception,
    metadata_type: Optional[str] = None,
    component_name: Optional[str] = None
) -> str:
    """Handle metadata deployment errors"""
    context = {
        "operation": "deployment",
        "metadata_type": metadata_type,
        "component_name": component_name
    }

    response_data = json.loads(create_error_response(
        success=False,
        error=error,
        context=context
    ))

    # Add deployment-specific suggestions
    error_lower = str(error).lower()
    deployment_suggestions = []

    if "apex" in error_lower:
        deployment_suggestions.extend([
            "Check Apex syntax and compile errors",
            "Ensure all referenced classes and methods exist",
            "Verify API version compatibility"
        ])

    if "test" in error_lower or "coverage" in error_lower:
        deployment_suggestions.extend([
            "Run run_apex_tests to check test coverage",
            "Ensure 75% code coverage for production deployment",
            "Check for failing test methods"
        ])

    if "component" in error_lower or "lwc" in error_lower:
        deployment_suggestions.extend([
            "Verify component bundle structure is correct",
            "Check for missing or invalid imports",
            "Ensure JavaScript/HTML syntax is valid"
        ])

    if deployment_suggestions:
        response_data["deployment_hints"] = deployment_suggestions

    return json.dumps(response_data, indent=2)


def handle_bulk_operation_error(
    error: Exception,
    object_name: Optional[str] = None,
    operation: Optional[str] = None,
    failed_records: Optional[List[Dict]] = None
) -> str:
    """Handle bulk operation errors with record-level details"""
    context = {
        "operation": f"bulk_{operation}" if operation else "bulk",
        "object_name": object_name
    }

    response_data = json.loads(create_error_response(
        success=False,
        error=error,
        context=context
    ))

    if failed_records:
        response_data["failed_record_count"] = len(failed_records)
        response_data["failed_records_sample"] = failed_records[:5]  # Show first 5

        # Analyze common failure patterns
        error_patterns = {}
        for record in failed_records:
            err = record.get("error", "Unknown")
            error_patterns[err] = error_patterns.get(err, 0) + 1

        if error_patterns:
            response_data["error_pattern_summary"] = [
                {"error": k, "count": v} for k, v in
                sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:5]
            ]

    return json.dumps(response_data, indent=2)


# =============================================================================
# ERROR LOGGING UTILITY
# =============================================================================

def log_and_return_error(
    error: Exception,
    operation: str,
    context: Optional[Dict[str, Any]] = None,
    log_level: str = "error"
) -> str:
    """
    Log error with context and return enhanced error response.

    Args:
        error: The exception that occurred
        operation: Name of the operation that failed
        context: Additional context for the error
        log_level: Log level (debug, info, warning, error, critical)

    Returns:
        JSON error response string
    """
    # Log the error
    log_func = getattr(logger, log_level, logger.error)
    log_func(f"Error in {operation}: {error}", exc_info=True, extra={
        "operation": operation,
        "context": context
    })

    # Return enhanced error response
    return create_error_response(
        success=False,
        error=error,
        context=context
    )
