"""Apex testing and code coverage tools

Created by Sameer
"""
import logging
import json
import time
from typing import List, Optional, Dict, Any

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection
from app.mcp.tools.utils import (
    format_error_response,
    format_success_response,
    ResponseSizeManager
)

logger = logging.getLogger(__name__)


@register_tool
def run_apex_tests(
    class_names: Optional[List[str]] = None,
    test_level: str = "RunLocalTests",
    max_wait_seconds: int = 300
) -> str:
    """Run Apex tests and return results with code coverage.

    Added by Sameer

    Args:
        class_names: List of test class names to run (None = all tests)
        test_level: Test level (RunSpecifiedTests, RunLocalTests, RunAllTestsInOrg)
        max_wait_seconds: Maximum time to wait for test completion

    Returns:
        JSON string with test results and coverage data
    """
    try:
        sf = get_salesforce_connection()

        # Build test request
        test_request = {
            "testLevel": test_level
        }

        if class_names and test_level == "RunSpecifiedTests":
            test_request["tests"] = [{"classId": cls} for cls in class_names]

        # Start async test execution via Tooling API
        endpoint = f"{sf.base_url}tooling/runTestsAsynchronous"
        headers = {
            "Authorization": f"Bearer {sf.session_id}",
            "Content-Type": "application/json"
        }

        import requests
        response = requests.post(endpoint, headers=headers, json=test_request, timeout=30)
        response.raise_for_status()
        test_run_id = response.text.strip('"')

        logger.info(f"Started test run: {test_run_id}")

        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            # Query test run status
            query = f"SELECT Id, Status, ClassesCompleted, ClassesEnqueued, MethodsEnqueued, MethodsCompleted FROM ApexTestRunResult WHERE AsyncApexJobId = '{test_run_id}'"
            result = sf.toolingexecute(f"query/?q={query}")

            if result.get("records"):
                test_run = result["records"][0]
                status = test_run.get("Status")

                logger.info(
                    f"Test run status: {status} - "
                    f"Classes: {test_run.get('ClassesCompleted', 0)}/{test_run.get('ClassesEnqueued', 0)}, "
                    f"Methods: {test_run.get('MethodsCompleted', 0)}/{test_run.get('MethodsEnqueued', 0)}"
                )

                if status == "Completed":
                    # Get detailed test results
                    results_query = f"""
                        SELECT Id, ApexClassId, ApexClass.Name, MethodName, Outcome,
                               Message, StackTrace, RunTime
                        FROM ApexTestResult
                        WHERE AsyncApexJobId = '{test_run_id}'
                    """
                    test_results = sf.toolingexecute(f"query/?q={results_query}")

                    # Get code coverage
                    coverage_query = f"""
                        SELECT ApexClassOrTriggerId, ApexClassOrTrigger.Name,
                               NumLinesCovered, NumLinesUncovered, Coverage
                        FROM ApexCodeCoverageAggregate
                    """
                    coverage_results = sf.toolingexecute(f"query/?q={coverage_query}")

                    # Calculate summary
                    test_records = test_results.get("records", [])
                    passed = sum(1 for t in test_records if t.get("Outcome") == "Pass")
                    failed = sum(1 for t in test_records if t.get("Outcome") == "Fail")
                    skipped = sum(1 for t in test_records if t.get("Outcome") in ["Skip", "CompileFail"])

                    # Calculate overall coverage
                    coverage_records = coverage_results.get("records", [])
                    total_lines = sum(
                        r.get("NumLinesCovered", 0) + r.get("NumLinesUncovered", 0)
                        for r in coverage_records
                    )
                    covered_lines = sum(r.get("NumLinesCovered", 0) for r in coverage_records)
                    coverage_percent = (covered_lines / total_lines * 100) if total_lines > 0 else 0

                    return json.dumps({
                        "success": True,
                        "test_run_id": test_run_id,
                        "summary": {
                            "total": len(test_records),
                            "passed": passed,
                            "failed": failed,
                            "skipped": skipped,
                            "pass_rate": f"{(passed / len(test_records) * 100):.1f}%" if test_records else "0%"
                        },
                        "coverage": {
                            "overall_percentage": f"{coverage_percent:.1f}%",
                            "total_lines": total_lines,
                            "covered_lines": covered_lines,
                            "uncovered_lines": total_lines - covered_lines
                        },
                        "test_results": test_records,
                        "coverage_details": coverage_records
                    }, indent=2)

                elif status in ["Failed", "Aborted"]:
                    return json.dumps({
                        "success": False,
                        "error": f"Test run {status.lower()}",
                        "test_run_id": test_run_id
                    })

            time.sleep(5)

        # Timeout
        return json.dumps({
            "success": False,
            "error": f"Test run timed out after {max_wait_seconds} seconds",
            "test_run_id": test_run_id
        })

    except Exception as e:
        logger.exception("run_apex_tests failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def get_apex_test_coverage(class_name: Optional[str] = None) -> str:
    """Get code coverage for Apex classes.

    Added by Sameer

    Args:
        class_name: Specific class name (None = all classes)

    Returns:
        JSON string with coverage data
    """
    try:
        sf = get_salesforce_connection()

        # Build query
        query = """
            SELECT ApexClassOrTriggerId, ApexClassOrTrigger.Name,
                   NumLinesCovered, NumLinesUncovered, Coverage
            FROM ApexCodeCoverageAggregate
        """

        if class_name:
            query += f" WHERE ApexClassOrTrigger.Name = '{class_name}'"

        result = sf.toolingexecute(f"query/?q={query}")
        records = result.get("records", [])

        # Calculate summary
        total_lines = sum(
            r.get("NumLinesCovered", 0) + r.get("NumLinesUncovered", 0)
            for r in records
        )
        covered_lines = sum(r.get("NumLinesCovered", 0) for r in records)
        coverage_percent = (covered_lines / total_lines * 100) if total_lines > 0 else 0

        return json.dumps({
            "success": True,
            "overall_coverage": {
                "coverage_percent": round(coverage_percent, 1),
                "coverage_string": f"{coverage_percent:.1f}%"
            },
            "total_lines": total_lines,
            "covered_lines": covered_lines,
            "uncovered_lines": total_lines - covered_lines,
            "classes": records
        }, indent=2)

    except Exception as e:
        logger.exception("get_apex_test_coverage failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def list_apex_test_classes(max_results: int = 100, offset: int = 0) -> str:
    """List all Apex test classes in the org.

    Added by Sameer

    Args:
        max_results: Maximum number of test classes to return (default: 100, use 0 for all)
        offset: Starting position for pagination (default: 0)

    Returns:
        JSON string with list of test classes
    """
    try:
        sf = get_salesforce_connection()

        # Build query with pagination
        query = """
            SELECT Id, Name, ApiVersion, Status, LengthWithoutComments
            FROM ApexClass
            WHERE Name LIKE '%Test%'
            ORDER BY Name
        """

        if max_results > 0:
            query += f" LIMIT {max_results} OFFSET {offset}"
        elif offset > 0:
            query += f" OFFSET {offset}"

        result = sf.toolingexecute(f"query/?q={query}")
        test_classes = result.get("records", [])

        # Get total count without limit
        count_query = """
            SELECT COUNT()
            FROM ApexClass
            WHERE Name LIKE '%Test%'
        """
        count_result = sf.toolingexecute(f"query/?q={count_query}")
        total_count = count_result.get("totalSize", len(test_classes))

        response = {
            "success": True,
            "total_count": total_count,
            "returned_count": len(test_classes),
            "offset": offset,
            "has_more": (offset + len(test_classes)) < total_count if max_results > 0 else False,
            "test_classes": test_classes
        }

        # Check response size and add warnings if needed
        response = ResponseSizeManager.check_response_size(response)
        return json.dumps(response, indent=2)

    except Exception as e:
        logger.exception("list_apex_test_classes failed")
        return format_error_response(e, context="list_apex_test_classes")
