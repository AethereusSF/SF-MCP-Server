"""Process automation and job monitoring tools

Created by Sameer
"""
import logging
import json
from typing import Optional

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection

logger = logging.getLogger(__name__)


@register_tool
def list_batch_jobs(status: str = "all", max_results: int = 100) -> str:
    """List Batch Apex jobs.

    Added by Sameer

    Args:
        status: Filter by status (all, queued, processing, completed, failed, aborted)
        max_results: Maximum jobs to return

    Returns:
        JSON with batch job list
    """
    try:
        sf = get_salesforce_connection()

        query = f"""
            SELECT Id, JobType, Status, TotalJobItems, JobItemsProcessed,
                   NumberOfErrors, CreatedDate, CompletedDate,
                   CreatedBy.Name, ApexClass.Name
            FROM AsyncApexJob
        """

        if status.lower() != "all":
            query += f" WHERE Status = '{status.title()}'"

        query += f" ORDER BY CreatedDate DESC LIMIT {max_results}"

        result = sf.query(query)
        jobs = result.get("records", [])

        return json.dumps({
            "success": True,
            "total_count": len(jobs),
            "status_filter": status,
            "jobs": jobs
        }, indent=2)

    except Exception as e:
        logger.exception("list_batch_jobs failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def get_batch_job_details(job_id: str) -> str:
    """Get detailed information about a batch job.

    Added by Sameer

    Args:
        job_id: Async Apex Job ID

    Returns:
        JSON with job details and batch items
    """
    try:
        sf = get_salesforce_connection()

        # Get job details
        job_query = f"""
            SELECT Id, JobType, Status, TotalJobItems, JobItemsProcessed,
                   NumberOfErrors, CreatedDate, CompletedDate, MethodName,
                   ExtendedStatus, CreatedBy.Name, ApexClass.Name
            FROM AsyncApexJob
            WHERE Id = '{job_id}'
        """

        job_result = sf.query(job_query)
        if not job_result.get("records"):
            return json.dumps({"success": False, "error": f"Job {job_id} not found"})

        job = job_result["records"][0]

        # Get batch items if available
        items_query = f"""
            SELECT Id, Status, NumberOfErrors, TotalJobItems, JobItemsProcessed,
                   ExtendedStatus, CreatedDate, CompletedDate
            FROM AsyncApexJob
            WHERE ParentJobId = '{job_id}'
        """

        items_result = sf.query(items_query)
        batch_items = items_result.get("records", [])

        return json.dumps({
            "success": True,
            "job": job,
            "batch_items": batch_items,
            "batch_count": len(batch_items)
        }, indent=2)

    except Exception as e:
        logger.exception("get_batch_job_details failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def list_scheduled_jobs(job_type: str = "all") -> str:
    """List scheduled Apex jobs.

    Added by Sameer

    Args:
        job_type: Filter by type (all, scheduled, cron)

    Returns:
        JSON with scheduled jobs
    """
    try:
        sf = get_salesforce_connection()

        query = """
            SELECT Id, CronJobDetail.Name, CronJobDetail.JobType, State,
                   CronExpression, PreviousFireTime, NextFireTime,
                   StartTime, EndTime, CreatedBy.Name, CreatedDate
            FROM CronTrigger
            WHERE CronJobDetail.JobType IN ('ScheduledApex', '7')
            ORDER BY NextFireTime
        """

        result = sf.query(query)
        jobs = result.get("records", [])

        return json.dumps({
            "success": True,
            "total_count": len(jobs),
            "scheduled_jobs": jobs
        }, indent=2)

    except Exception as e:
        logger.exception("list_scheduled_jobs failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def abort_batch_job(job_id: str) -> str:
    """Abort a running batch job.

    Added by Sameer

    Args:
        job_id: Async Apex Job ID

    Returns:
        JSON with abort status
    """
    try:
        sf = get_salesforce_connection()

        # Abort the job via Tooling API
        import requests
        endpoint = f"{sf.base_url}tooling/sobjects/AsyncApexJob/{job_id}"
        headers = {
            "Authorization": f"Bearer {sf.session_id}",
            "Content-Type": "application/json"
        }

        # Update job status to Aborted
        update_data = {"Status": "Aborted"}

        response = requests.patch(endpoint, headers=headers, json=update_data, timeout=30)
        response.raise_for_status()

        return json.dumps({
            "success": True,
            "job_id": job_id,
            "message": "Job aborted successfully"
        }, indent=2)

    except Exception as e:
        logger.exception("abort_batch_job failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def delete_scheduled_job(job_id: str) -> str:
    """Delete a scheduled job.

    Added by Sameer

    Args:
        job_id: CronTrigger ID

    Returns:
        JSON with deletion status
    """
    try:
        sf = get_salesforce_connection()

        # Delete via Tooling API
        import requests
        endpoint = f"{sf.base_url}tooling/sobjects/CronTrigger/{job_id}"
        headers = {"Authorization": f"Bearer {sf.session_id}"}

        response = requests.delete(endpoint, headers=headers, timeout=30)
        response.raise_for_status()

        return json.dumps({
            "success": True,
            "job_id": job_id,
            "message": "Scheduled job deleted successfully"
        }, indent=2)

    except Exception as e:
        logger.exception("delete_scheduled_job failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def execute_anonymous_apex(apex_code: str) -> str:
    """Execute anonymous Apex code.

    Added by Sameer

    Args:
        apex_code: Apex code to execute

    Returns:
        JSON with execution results
    """
    try:
        sf = get_salesforce_connection()

        # Execute via REST API
        import requests
        import urllib.parse

        endpoint = f"{sf.base_url}tooling/executeAnonymous"
        headers = {"Authorization": f"Bearer {sf.session_id}"}

        params = {"anonymousBody": apex_code}
        response = requests.get(endpoint, headers=headers, params=params, timeout=60)
        response.raise_for_status()

        result = response.json()

        return json.dumps({
            "success": result.get("success", False),
            "compiled": result.get("compiled", False),
            "compile_problem": result.get("compileProblem"),
            "exception_message": result.get("exceptionMessage"),
            "exception_stack_trace": result.get("exceptionStackTrace"),
            "line": result.get("line"),
            "column": result.get("column")
        }, indent=2)

    except Exception as e:
        logger.exception("execute_anonymous_apex failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def get_debug_logs(
    user_name: Optional[str] = None,
    max_logs: int = 10,
    limit: Optional[int] = None
) -> str:
    """Retrieve recent debug logs.

    Added by Sameer

    Args:
        user_name: Filter by username (None = current user)
        max_logs: Maximum logs to retrieve (deprecated, use limit)
        limit: Maximum logs to retrieve (preferred parameter name)

    Returns:
        JSON with debug log list
    """
    # Support both max_logs and limit parameters
    actual_limit = limit if limit is not None else max_logs
    try:
        sf = get_salesforce_connection()

        query = f"""
            SELECT Id, Application, DurationMilliseconds, Location,
                   LogLength, LogUser.Name, Operation, Request, StartTime, Status
            FROM ApexLog
        """

        if user_name:
            query += f" WHERE LogUser.Name = '{user_name}'"

        query += f" ORDER BY StartTime DESC LIMIT {actual_limit}"

        result = sf.toolingexecute(f"query/?q={query}")
        logs = result.get("records", [])

        return json.dumps({
            "success": True,
            "total_count": len(logs),
            "logs": logs,
            "message": "Use log ID to fetch full log content"
        }, indent=2)

    except Exception as e:
        logger.exception("get_debug_logs failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def get_debug_log_body(log_id: str) -> str:
    """Get the full body of a debug log.

    Added by Sameer

    Args:
        log_id: ApexLog ID

    Returns:
        JSON with log body
    """
    try:
        sf = get_salesforce_connection()

        # Fetch log body via Tooling API
        import requests
        endpoint = f"{sf.base_url}tooling/sobjects/ApexLog/{log_id}/Body"
        headers = {"Authorization": f"Bearer {sf.session_id}"}

        response = requests.get(endpoint, headers=headers, timeout=30)
        response.raise_for_status()

        log_body = response.text

        return json.dumps({
            "success": True,
            "log_id": log_id,
            "log_body": log_body,
            "size_bytes": len(log_body)
        }, indent=2)

    except Exception as e:
        logger.exception("get_debug_log_body failed")
        return json.dumps({"success": False, "error": str(e)})
