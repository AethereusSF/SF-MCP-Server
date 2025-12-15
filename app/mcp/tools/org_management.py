"""Org management tools: health checks, limits, and org info

Created by Sameer
"""
import logging
import json
from typing import Optional

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection
from app.mcp.tools.utils import (
    format_error_response,
    format_success_response,
    ResponseSizeManager
)

logger = logging.getLogger(__name__)


@register_tool
def salesforce_health_check() -> str:
    """Comprehensive health check for Salesforce connection and org status.

    Added by Sameer

    Checks:
    - Connection status
    - API availability
    - Org limits
    - User info

    Returns:
        JSON string with health check results
    """
    try:
        sf = get_salesforce_connection()
        health_status = {
            "success": True,
            "checks": {}
        }

        # 1. Connection check
        try:
            # Simple identity check
            identity_url = f"{sf.base_url}sobjects/"
            import requests
            response = requests.get(
                identity_url,
                headers={"Authorization": f"Bearer {sf.session_id}"},
                timeout=10
            )
            response.raise_for_status()
            health_status["checks"]["connection"] = {
                "status": "healthy",
                "message": "Successfully connected to Salesforce"
            }
        except Exception as e:
            health_status["checks"]["connection"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["success"] = False

        # 2. API limits check
        try:
            limits_result = json.loads(get_org_limits())
            if limits_result.get("success"):
                health_status["checks"]["api_limits"] = {
                    "status": "healthy",
                    "daily_api_usage": limits_result.get("DailyApiRequests", {})
                }
            else:
                health_status["checks"]["api_limits"] = {
                    "status": "warning",
                    "message": "Could not fetch API limits"
                }
        except Exception as e:
            health_status["checks"]["api_limits"] = {
                "status": "error",
                "error": str(e)
            }

        # 3. User info check
        try:
            user_result = json.loads(get_current_user_info())
            if user_result.get("success"):
                health_status["checks"]["user_session"] = {
                    "status": "healthy",
                    "user": user_result.get("user", {}).get("Username"),
                    "profile": user_result.get("user", {}).get("Profile", {}).get("Name")
                }
            else:
                health_status["checks"]["user_session"] = {
                    "status": "warning",
                    "message": "Could not fetch user info"
                }
        except Exception as e:
            health_status["checks"]["user_session"] = {
                "status": "error",
                "error": str(e)
            }

        # 4. Org info
        try:
            org_result = json.loads(get_org_info())
            if org_result.get("success"):
                health_status["checks"]["org_info"] = {
                    "status": "healthy",
                    "org_type": org_result.get("org", {}).get("OrganizationType"),
                    "instance": org_result.get("org", {}).get("InstanceName")
                }
        except Exception as e:
            health_status["checks"]["org_info"] = {
                "status": "error",
                "error": str(e)
            }

        # Overall health
        unhealthy_checks = [
            k for k, v in health_status["checks"].items()
            if v.get("status") in ["unhealthy", "error"]
        ]

        health_status["overall_status"] = "unhealthy" if unhealthy_checks else "healthy"
        health_status["timestamp"] = json.loads(get_current_user_info()).get("timestamp", "")

        return json.dumps(health_status, indent=2)

    except Exception as e:
        logger.exception("salesforce_health_check failed")
        return json.dumps({
            "success": False,
            "overall_status": "unhealthy",
            "error": str(e)
        })


@register_tool
def get_org_limits() -> str:
    """Get Salesforce org limits (API calls, storage, etc.).

    Added by Sameer

    Returns:
        JSON string with limit information
    """
    try:
        sf = get_salesforce_connection()

        # Query org limits via REST API
        endpoint = f"{sf.base_url}limits"
        import requests
        response = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {sf.session_id}"},
            timeout=30
        )
        response.raise_for_status()
        limits = response.json()

        # Extract key limits
        key_limits = {
            "DailyApiRequests": limits.get("DailyApiRequests"),
            "DailyBulkApiRequests": limits.get("DailyBulkApiRequests"),
            "DailyAsyncApexExecutions": limits.get("DailyAsyncApexExecutions"),
            "DataStorageMB": limits.get("DataStorageMB"),
            "FileStorageMB": limits.get("FileStorageMB"),
            "HourlyTimeBasedWorkflow": limits.get("HourlyTimeBasedWorkflow"),
        }

        return json.dumps({
            "success": True,
            "key_limits": key_limits,
            "all_limits": limits
        }, indent=2)

    except Exception as e:
        logger.exception("get_org_limits failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def get_org_info() -> str:
    """Get Salesforce org information.

    Added by Sameer

    Returns:
        JSON string with org details
    """
    try:
        sf = get_salesforce_connection()

        # Query Organization object
        query = """
            SELECT Id, Name, OrganizationType, InstanceName, IsSandbox,
                   TrialExpirationDate, NamespacePrefix, DefaultAccountAccess
            FROM Organization
            LIMIT 1
        """

        result = sf.query(query)
        org_info = result.get("records", [{}])[0]

        return json.dumps({
            "success": True,
            "org": org_info,
            "instance_url": sf.base_url
        }, indent=2)

    except Exception as e:
        logger.exception("get_org_info failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def get_current_user_info() -> str:
    """Get current user information.

    Added by Sameer

    Returns:
        JSON string with user details
    """
    try:
        sf = get_salesforce_connection()

        # Get current user ID from stored OAuth tokens
        from app.mcp.tools.oauth_auth import get_stored_tokens
        stored_tokens = get_stored_tokens()

        if not stored_tokens:
            raise Exception("No stored OAuth tokens found. Please login first.")

        # Get the first (or active) user's ID
        user_id = None
        for uid, token_data in stored_tokens.items():
            user_id = token_data.get('user_id')
            break

        if not user_id:
            # Fallback: Query current user via UserInfo
            query = """
                SELECT Id, Username, Name, Email, Profile.Name, UserRole.Name,
                       IsActive, UserType, LastLoginDate, CreatedDate
                FROM User
                WHERE Id = UserInfo.getUserId()
                LIMIT 1
            """
        else:
            # Query User object for current user using the stored user_id
            query = f"""
                SELECT Id, Username, Name, Email, Profile.Name, UserRole.Name,
                       IsActive, UserType, LastLoginDate, CreatedDate
                FROM User
                WHERE Id = '{user_id}'
                LIMIT 1
            """

        result = sf.query(query)
        user_info = result.get("records", [{}])[0]

        import datetime
        return json.dumps({
            "success": True,
            "user": user_info,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }, indent=2)

    except Exception as e:
        logger.exception("get_current_user_info failed")
        return format_error_response(e, context="get_current_user_info")


@register_tool
def list_installed_packages() -> str:
    """List all installed managed packages in the org.

    Added by Sameer

    Returns:
        JSON string with package list
    """
    try:
        sf = get_salesforce_connection()

        query = """
            SELECT Id, SubscriberPackageId, SubscriberPackage.Name,
                   SubscriberPackage.NamespacePrefix,
                   SubscriberPackageVersion.Name,
                   SubscriberPackageVersion.MajorVersion,
                   SubscriberPackageVersion.MinorVersion,
                   SubscriberPackageVersion.PatchVersion,
                   SubscriberPackageVersion.BuildNumber
            FROM InstalledSubscriberPackage
            ORDER BY SubscriberPackage.Name
        """

        result = sf.query(query)
        packages = result.get("records", [])

        response = {
            "total_count": len(packages),
            "packages": packages
        }

        # Check response size and add warnings if needed
        response = ResponseSizeManager.check_response_size(response)
        return json.dumps(response, indent=2)

    except Exception as e:
        logger.exception("list_installed_packages failed")
        return format_error_response(e, context="list_installed_packages")


@register_tool
def get_api_usage_stats(days: int = 7) -> str:
    """Get API usage statistics for recent days.

    Added by Sameer

    Args:
        days: Number of days to look back (max 30)

    Returns:
        JSON string with usage stats
    """
    try:
        sf = get_salesforce_connection()

        # Limit to 30 days
        days = min(days, 30)

        # Calculate date
        import datetime
        start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")

        # Query EventLogFile for API usage
        query = f"""
            SELECT LogDate, ApiType, ApiVersion, Method, COUNT(Id)
            FROM EventLogFile
            WHERE LogDate >= {start_date}
            AND EventType = 'API'
            GROUP BY LogDate, ApiType, ApiVersion, Method
            ORDER BY LogDate DESC
        """

        result = sf.query(query)
        usage_stats = result.get("records", [])

        response = {
            "days": days,
            "total_records": len(usage_stats),
            "usage_stats": usage_stats
        }

        # Check response size and add warnings if needed
        response = ResponseSizeManager.check_response_size(response)
        return json.dumps(response, indent=2)

    except Exception as e:
        logger.exception("get_api_usage_stats failed")
        return format_error_response(e, context="get_api_usage_stats")
