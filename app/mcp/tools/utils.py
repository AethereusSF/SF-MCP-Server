"""Utility functions for MCP tools - error handling and response management

Created by Sameer
"""
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Token limits
TOKEN_LIMIT = 25000
TOKEN_WARNING_THRESHOLD = 20000  # 80% of limit


class MCPError:
    """Enhanced error handling with troubleshooting hints"""

    # Common error patterns and their solutions
    ERROR_PATTERNS = {
        "MALFORMED_QUERY": {
            "hint": "SOQL query syntax error. Check for unsupported keywords like 'AS' or dynamic functions.",
            "suggestions": [
                "Remove 'AS' keyword from field aliases",
                "Replace dynamic functions like UserInfo.getUserId() with actual values",
                "Verify field names and relationships are correct"
            ]
        },
        "INVALID_FIELD": {
            "hint": "Field does not exist on this object or is not accessible.",
            "suggestions": [
                "Verify the field API name is correct (check spelling and __c suffix)",
                "Ensure the field exists on the object",
                "Check field-level security permissions"
            ]
        },
        "INVALID_TYPE": {
            "hint": "Object type not found or not accessible.",
            "suggestions": [
                "Verify the object API name is correct",
                "Check object exists in the org",
                "Ensure you have read access to this object"
            ]
        },
        "NOT_FOUND": {
            "hint": "Requested resource not found.",
            "suggestions": [
                "Verify the ID or name is correct",
                "Check if the resource exists in this org",
                "Ensure you have access permissions"
            ]
        },
        "INSUFFICIENT_ACCESS": {
            "hint": "You don't have permission to perform this operation.",
            "suggestions": [
                "Contact your Salesforce administrator",
                "Check your profile and permission sets",
                "Verify object and field-level security settings"
            ]
        },
        "INVALID_SESSION_ID": {
            "hint": "Your session has expired or is invalid.",
            "suggestions": [
                "Re-authenticate to Salesforce",
                "Use salesforce_sandbox_login or salesforce_production_login",
                "Check your .env configuration"
            ]
        },
        "REQUEST_LIMIT_EXCEEDED": {
            "hint": "API request limit exceeded.",
            "suggestions": [
                "Wait and retry later",
                "Check org limits with get_org_limits()",
                "Consider using Bulk API for large operations"
            ]
        },
        "QUERY_TIMEOUT": {
            "hint": "Query took too long to execute.",
            "suggestions": [
                "Add more specific WHERE conditions",
                "Reduce the number of fields selected",
                "Add LIMIT clause to restrict results"
            ]
        }
    }

    @classmethod
    def enhance_error(cls, error_msg: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Enhance error message with troubleshooting hints

        Args:
            error_msg: Original error message
            context: Additional context (e.g., function name, object name)

        Returns:
            Enhanced error dict with hints and suggestions
        """
        enhanced = {
            "error": error_msg,
            "success": False
        }

        # Add context if provided
        if context:
            enhanced["context"] = context

        # Find matching error pattern
        for error_code, info in cls.ERROR_PATTERNS.items():
            if error_code.lower() in error_msg.lower():
                enhanced["hint"] = info["hint"]
                enhanced["suggestions"] = info["suggestions"]
                enhanced["error_type"] = error_code
                break

        # If no pattern matched, provide generic help
        if "hint" not in enhanced:
            enhanced["hint"] = "An unexpected error occurred."
            enhanced["suggestions"] = [
                "Check the error message for details",
                "Verify your Salesforce connection",
                "Consult Salesforce API documentation"
            ]
            enhanced["error_type"] = "UNKNOWN"

        return enhanced


class ResponseSizeManager:
    """Manage response sizes and provide warnings"""

    @staticmethod
    def estimate_token_count(text: str) -> int:
        """Estimate token count for a string

        Rough estimation: 1 token ≈ 4 characters
        """
        return len(text) // 4

    @staticmethod
    def check_response_size(response_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Check response size and add warnings if needed

        Args:
            response_dict: Response dictionary to check

        Returns:
            Response dict with size warnings if applicable
        """
        response_json = json.dumps(response_dict, indent=2)
        estimated_tokens = ResponseSizeManager.estimate_token_count(response_json)

        # Add size metadata
        response_dict["_metadata"] = response_dict.get("_metadata", {})
        response_dict["_metadata"]["estimated_tokens"] = estimated_tokens
        response_dict["_metadata"]["response_size_bytes"] = len(response_json)

        # Add warning if approaching limit
        if estimated_tokens > TOKEN_WARNING_THRESHOLD:
            response_dict["_metadata"]["size_warning"] = {
                "message": f"Response size ({estimated_tokens} tokens) is approaching the limit ({TOKEN_LIMIT} tokens)",
                "level": "warning" if estimated_tokens < TOKEN_LIMIT else "error",
                "recommendations": [
                    "Use pagination parameters to reduce response size",
                    "Filter results with WHERE conditions",
                    "Select only necessary fields",
                    "Use offset/limit parameters if available"
                ]
            }

            logger.warning(
                f"Response size warning: {estimated_tokens} tokens "
                f"(threshold: {TOKEN_WARNING_THRESHOLD}, limit: {TOKEN_LIMIT})"
            )

        return response_dict

    @staticmethod
    def truncate_if_needed(
        data: list,
        max_items: int,
        message: str = "Results truncated due to size limit"
    ) -> tuple:
        """Truncate data if it exceeds max_items

        Args:
            data: List of items to potentially truncate
            max_items: Maximum number of items to return
            message: Message to include if truncated

        Returns:
            Tuple of (truncated_data, was_truncated, truncation_info)
        """
        if len(data) > max_items:
            return (
                data[:max_items],
                True,
                {
                    "truncated": True,
                    "message": message,
                    "original_count": len(data),
                    "returned_count": max_items,
                    "omitted_count": len(data) - max_items
                }
            )
        return data, False, None


def format_success_response(
    data: Any,
    context: Optional[Dict[str, Any]] = None,
    check_size: bool = True
) -> str:
    """Format a success response with optional size checking

    Args:
        data: Main data to return
        context: Additional context (metadata, counts, etc.)
        check_size: Whether to check response size and add warnings

    Returns:
        JSON string with formatted response
    """
    response = {
        "success": True,
        **data
    }

    # Add context if provided
    if context:
        response.update(context)

    # Check size if requested
    if check_size:
        response = ResponseSizeManager.check_response_size(response)

    return json.dumps(response, indent=2)


def format_error_response(
    error: Exception,
    context: Optional[str] = None,
    include_hints: bool = True
) -> str:
    """Format an error response with troubleshooting hints

    Args:
        error: Exception object
        context: Additional context about the operation
        include_hints: Whether to include troubleshooting hints

    Returns:
        JSON string with formatted error response
    """
    error_msg = str(error)

    if include_hints:
        response = MCPError.enhance_error(error_msg, context)
    else:
        response = {
            "success": False,
            "error": error_msg
        }
        if context:
            response["context"] = context

    return json.dumps(response, indent=2)


# Convenience functions for common operations
def safe_execute(
    operation_name: str,
    operation_func,
    *args,
    **kwargs
) -> str:
    """Safely execute an operation with enhanced error handling

    Args:
        operation_name: Name of the operation for context
        operation_func: Function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        JSON string with result or enhanced error
    """
    try:
        result = operation_func(*args, **kwargs)
        return result
    except Exception as e:
        logger.exception(f"{operation_name} failed")
        return format_error_response(e, context=operation_name)
