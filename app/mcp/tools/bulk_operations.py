"""Bulk data operations using Salesforce Bulk API 2.0

Created by Sameer
"""
import logging
import json
import time
import io
import csv
from typing import List, Dict, Any, Optional

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection

logger = logging.getLogger(__name__)


# DEPRECATED: Use consolidated tool instead
# @register_tool
def bulk_insert_records(
    object_name: str,
    records: List[Dict[str, Any]],
    wait_for_completion: bool = True,
    timeout_seconds: int = 300
) -> str:
    """Insert multiple records using Bulk API 2.0.

    Added by Sameer

    Args:
        object_name: Salesforce object API name
        records: List of dictionaries with record data
        wait_for_completion: Wait for job to complete
        timeout_seconds: Maximum wait time

    Returns:
        JSON string with job status and results
    """
    try:
        sf = get_salesforce_connection()

        if not records:
            return json.dumps({"success": False, "error": "No records provided"})

        # Convert records to CSV
        csv_buffer = io.StringIO()
        if records:
            writer = csv.DictWriter(csv_buffer, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
            csv_data = csv_buffer.getvalue()
        else:
            return json.dumps({"success": False, "error": "Empty records list"})

        # Create bulk job
        import requests
        job_endpoint = f"{sf.base_url}jobs/ingest"
        headers = {
            "Authorization": f"Bearer {sf.session_id}",
            "Content-Type": "application/json"
        }

        job_data = {
            "object": object_name,
            "operation": "insert",
            "lineEnding": "CRLF"
        }

        response = requests.post(job_endpoint, headers=headers, json=job_data, timeout=30)
        response.raise_for_status()
        job_info = response.json()
        job_id = job_info["id"]

        logger.info(f"Created bulk insert job: {job_id}")

        # Upload CSV data
        upload_endpoint = f"{job_endpoint}/{job_id}/batches"
        upload_headers = {
            "Authorization": f"Bearer {sf.session_id}",
            "Content-Type": "text/csv"
        }

        response = requests.put(upload_endpoint, headers=upload_headers, data=csv_data, timeout=60)
        response.raise_for_status()

        # Close job to start processing
        close_endpoint = f"{job_endpoint}/{job_id}"
        close_data = {"state": "UploadComplete"}

        response = requests.patch(close_endpoint, headers=headers, json=close_data, timeout=30)
        response.raise_for_status()

        logger.info(f"Started processing bulk job: {job_id}")

        if not wait_for_completion:
            return json.dumps({
                "success": True,
                "job_id": job_id,
                "status": "processing",
                "message": "Job started, use get_bulk_job_status to check progress"
            }, indent=2)

        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            status_response = requests.get(close_endpoint, headers=headers, timeout=30)
            status_response.raise_for_status()
            job_status = status_response.json()

            state = job_status["state"]
            logger.info(f"Bulk job {job_id} status: {state}")

            if state in ["JobComplete", "Failed", "Aborted"]:
                # Get results
                results = {
                    "success": state == "JobComplete",
                    "job_id": job_id,
                    "state": state,
                    "records_processed": job_status.get("numberRecordsProcessed", 0),
                    "records_failed": job_status.get("numberRecordsFailed", 0),
                    "total_processing_time_ms": job_status.get("totalProcessingTime", 0)
                }

                # Get failed records if any
                if job_status.get("numberRecordsFailed", 0) > 0:
                    failed_endpoint = f"{job_endpoint}/{job_id}/failedResults"
                    failed_response = requests.get(failed_endpoint, headers={"Authorization": f"Bearer {sf.session_id}"}, timeout=30)
                    if failed_response.status_code == 200:
                        results["failed_records"] = failed_response.text

                return json.dumps(results, indent=2)

            time.sleep(5)

        return json.dumps({
            "success": False,
            "job_id": job_id,
            "error": f"Job timed out after {timeout_seconds} seconds"
        })

    except Exception as e:
        logger.exception("bulk_insert_records failed")
        return json.dumps({"success": False, "error": str(e)})


# DEPRECATED: Use consolidated tool instead
# @register_tool
def bulk_update_records(
    object_name: str,
    records: List[Dict[str, Any]],
    wait_for_completion: bool = True,
    timeout_seconds: int = 300
) -> str:
    """Update multiple records using Bulk API 2.0.

    Added by Sameer

    Args:
        object_name: Salesforce object API name
        records: List of dictionaries with record data (must include Id field)
        wait_for_completion: Wait for job to complete
        timeout_seconds: Maximum wait time

    Returns:
        JSON string with job status and results
    """
    try:
        # Validate records have Id field
        if not all("Id" in record for record in records):
            return json.dumps({
                "success": False,
                "error": "All records must have 'Id' field for update operation"
            })

        sf = get_salesforce_connection()

        # Convert records to CSV
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
        csv_data = csv_buffer.getvalue()

        # Create bulk job
        import requests
        job_endpoint = f"{sf.base_url}jobs/ingest"
        headers = {
            "Authorization": f"Bearer {sf.session_id}",
            "Content-Type": "application/json"
        }

        job_data = {
            "object": object_name,
            "operation": "update",
            "lineEnding": "CRLF"
        }

        response = requests.post(job_endpoint, headers=headers, json=job_data, timeout=30)
        response.raise_for_status()
        job_info = response.json()
        job_id = job_info["id"]

        # Upload and process (same as insert)
        upload_endpoint = f"{job_endpoint}/{job_id}/batches"
        upload_headers = {
            "Authorization": f"Bearer {sf.session_id}",
            "Content-Type": "text/csv"
        }

        response = requests.put(upload_endpoint, headers=upload_headers, data=csv_data, timeout=60)
        response.raise_for_status()

        close_endpoint = f"{job_endpoint}/{job_id}"
        close_data = {"state": "UploadComplete"}
        response = requests.patch(close_endpoint, headers=headers, json=close_data, timeout=30)
        response.raise_for_status()

        if not wait_for_completion:
            return json.dumps({
                "success": True,
                "job_id": job_id,
                "status": "processing"
            }, indent=2)

        # Poll for completion (similar to insert)
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            status_response = requests.get(close_endpoint, headers=headers, timeout=30)
            status_response.raise_for_status()
            job_status = status_response.json()

            if job_status["state"] in ["JobComplete", "Failed", "Aborted"]:
                return json.dumps({
                    "success": job_status["state"] == "JobComplete",
                    "job_id": job_id,
                    "state": job_status["state"],
                    "records_processed": job_status.get("numberRecordsProcessed", 0),
                    "records_failed": job_status.get("numberRecordsFailed", 0)
                }, indent=2)

            time.sleep(5)

        return json.dumps({"success": False, "job_id": job_id, "error": "Timeout"})

    except Exception as e:
        logger.exception("bulk_update_records failed")
        return json.dumps({"success": False, "error": str(e)})


# DEPRECATED: Use consolidated tool instead
# @register_tool
def bulk_delete_records(
    object_name: str,
    record_ids: List[str],
    wait_for_completion: bool = True,
    timeout_seconds: int = 300
) -> str:
    """Delete multiple records using Bulk API 2.0.

    Added by Sameer

    Args:
        object_name: Salesforce object API name
        record_ids: List of record IDs to delete
        wait_for_completion: Wait for job to complete
        timeout_seconds: Maximum wait time

    Returns:
        JSON string with job status and results
    """
    try:
        if not record_ids:
            return json.dumps({"success": False, "error": "No record IDs provided"})

        # Convert to records format
        records = [{"Id": record_id} for record_id in record_ids]

        sf = get_salesforce_connection()

        # Create CSV
        csv_buffer = io.StringIO()
        csv_buffer.write("Id\n")
        for rid in record_ids:
            csv_buffer.write(f"{rid}\n")
        csv_data = csv_buffer.getvalue()

        # Create delete job
        import requests
        job_endpoint = f"{sf.base_url}jobs/ingest"
        headers = {
            "Authorization": f"Bearer {sf.session_id}",
            "Content-Type": "application/json"
        }

        job_data = {
            "object": object_name,
            "operation": "delete",
            "lineEnding": "CRLF"
        }

        response = requests.post(job_endpoint, headers=headers, json=job_data, timeout=30)
        response.raise_for_status()
        job_id = response.json()["id"]

        # Upload and process
        upload_endpoint = f"{job_endpoint}/{job_id}/batches"
        upload_headers = {
            "Authorization": f"Bearer {sf.session_id}",
            "Content-Type": "text/csv"
        }

        response = requests.put(upload_endpoint, headers=upload_headers, data=csv_data, timeout=60)
        response.raise_for_status()

        close_endpoint = f"{job_endpoint}/{job_id}"
        response = requests.patch(close_endpoint, headers=headers, json={"state": "UploadComplete"}, timeout=30)
        response.raise_for_status()

        if not wait_for_completion:
            return json.dumps({"success": True, "job_id": job_id, "status": "processing"}, indent=2)

        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            status_response = requests.get(close_endpoint, headers=headers, timeout=30)
            job_status = status_response.json()

            if job_status["state"] in ["JobComplete", "Failed", "Aborted"]:
                return json.dumps({
                    "success": job_status["state"] == "JobComplete",
                    "job_id": job_id,
                    "state": job_status["state"],
                    "records_processed": job_status.get("numberRecordsProcessed", 0),
                    "records_failed": job_status.get("numberRecordsFailed", 0)
                }, indent=2)

            time.sleep(5)

        return json.dumps({"success": False, "job_id": job_id, "error": "Timeout"})

    except Exception as e:
        logger.exception("bulk_delete_records failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def get_bulk_job_status(job_id: str) -> str:
    """Get status of a bulk API job.

    Added by Sameer

    Args:
        job_id: Bulk job ID

    Returns:
        JSON string with job status
    """
    try:
        sf = get_salesforce_connection()

        import requests
        endpoint = f"{sf.base_url}jobs/ingest/{job_id}"
        headers = {"Authorization": f"Bearer {sf.session_id}"}

        response = requests.get(endpoint, headers=headers, timeout=30)
        response.raise_for_status()
        job_status = response.json()

        return json.dumps({
            "success": True,
            "job_status": job_status
        }, indent=2)

    except Exception as e:
        logger.exception("get_bulk_job_status failed")
        return json.dumps({"success": False, "error": str(e)})
