"""Schema analysis and dependency tools

Created by Sameer
"""
import logging
import json
import csv
import os
from typing import List, Optional
from datetime import datetime

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection

logger = logging.getLogger(__name__)


@register_tool
def analyze_object_dependencies(object_name: str) -> str:
    """Analyze dependencies for an object.

    Added by Sameer

    Args:
        object_name: Object API name

    Returns:
        JSON with dependency information
    """
    try:
        sf = get_salesforce_connection()

        dependencies = {
            "object": object_name,
            "lookup_fields": [],
            "referenced_by": [],
            "child_objects": [],
            "validation_rules": [],
            "triggers": [],
            "workflows": [],
            "flows": []
        }

        # Get lookup/master-detail relationships
        describe = sf.__getattr__(object_name).describe()
        for field in describe["fields"]:
            if field.get("type") in ["reference", "lookup", "masterdetail"]:
                dependencies["lookup_fields"].append({
                    "field": field["name"],
                    "references": field.get("referenceTo", []),
                    "required": not field.get("nillable", True)
                })

        # Get child relationships
        for child_rel in describe.get("childRelationships", []):
            if child_rel.get("relationshipName"):
                dependencies["child_objects"].append({
                    "object": child_rel["childSObject"],
                    "relationship": child_rel["relationshipName"],
                    "field": child_rel["field"]
                })

        # Get validation rules
        vr_query = f"""
            SELECT Id, ValidationName, Active, ErrorDisplayField, ErrorMessage
            FROM ValidationRule
            WHERE EntityDefinition.QualifiedApiName = '{object_name}'
        """
        try:
            vr_result = sf.toolingexecute(f"query/?q={vr_query}")
            dependencies["validation_rules"] = vr_result.get("records", [])
        except:
            pass

        # Get triggers
        trigger_query = f"""
            SELECT Id, Name, Status, UsageAfterInsert, UsageAfterUpdate,
                   UsageAfterDelete, UsageBeforeInsert, UsageBeforeUpdate, UsageBeforeDelete
            FROM ApexTrigger
            WHERE TableEnumOrId = '{object_name}'
        """
        try:
            trigger_result = sf.toolingexecute(f"query/?q={trigger_query}")
            dependencies["triggers"] = trigger_result.get("records", [])
        except:
            pass

        return json.dumps({
            "success": True,
            "dependencies": dependencies,
            "summary": {
                "lookup_count": len(dependencies["lookup_fields"]),
                "child_count": len(dependencies["child_objects"]),
                "validation_rules": len(dependencies["validation_rules"]),
                "triggers": len(dependencies["triggers"])
            }
        }, indent=2)

    except Exception as e:
        logger.exception("analyze_object_dependencies failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def find_unused_fields(object_name: str, days: int = 90) -> str:
    """Find potentially unused fields on an object.

    Added by Sameer

    Args:
        object_name: Object API name
        days: Look back period for usage

    Returns:
        JSON with unused field candidates
    """
    try:
        sf = get_salesforce_connection()

        # Get all custom fields
        describe = sf.__getattr__(object_name).describe()
        custom_fields = [f for f in describe["fields"] if f.get("custom")]

        # For each field, check if it appears in SOQL queries, Apex, etc.
        # This is a simplified version - full implementation would need Field History
        unused_candidates = []

        for field in custom_fields:
            field_name = field["name"]

            # Try to find references in Apex classes
            apex_query = f"""
                SELECT Id, Name
                FROM ApexClass
                WHERE Body LIKE '%{field_name}%'
                LIMIT 1
            """

            try:
                apex_result = sf.toolingexecute(f"query/?q={apex_query}")
                has_apex_reference = len(apex_result.get("records", [])) > 0
            except:
                has_apex_reference = False

            # Try to find in triggers
            trigger_query = f"""
                SELECT Id, Name
                FROM ApexTrigger
                WHERE Body LIKE '%{field_name}%'
                LIMIT 1
            """

            try:
                trigger_result = sf.toolingexecute(f"query/?q={trigger_query}")
                has_trigger_reference = len(trigger_result.get("records", [])) > 0
            except:
                has_trigger_reference = False

            if not has_apex_reference and not has_trigger_reference:
                unused_candidates.append({
                    "field_name": field_name,
                    "label": field["label"],
                    "type": field["type"],
                    "created_date": field.get("calculatedFormula", "Unknown"),
                    "reason": "No references found in Apex or Triggers"
                })

        return json.dumps({
            "success": True,
            "object": object_name,
            "total_custom_fields": len(custom_fields),
            "unused_candidates": unused_candidates,
            "unused_count": len(unused_candidates),
            "note": "Manual verification recommended before deletion"
        }, indent=2)

    except Exception as e:
        logger.exception("find_unused_fields failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def generate_object_diagram(object_names: List[str]) -> str:
    """Generate entity relationship diagram data for objects.

    Added by Sameer

    Args:
        object_names: List of object API names

    Returns:
        JSON with ERD data (nodes and edges)
    """
    try:
        sf = get_salesforce_connection()

        nodes = []
        edges = []

        for obj_name in object_names:
            describe = sf.__getattr__(obj_name).describe()

            # Add object as node
            nodes.append({
                "id": obj_name,
                "label": describe["label"],
                "type": "custom" if describe.get("custom") else "standard",
                "field_count": len(describe["fields"])
            })

            # Add relationships as edges
            for field in describe["fields"]:
                if field.get("type") in ["reference", "lookup", "masterdetail"]:
                    for ref_obj in field.get("referenceTo", []):
                        if ref_obj in object_names:
                            edges.append({
                                "from": obj_name,
                                "to": ref_obj,
                                "field": field["name"],
                                "type": "Master-Detail" if not field.get("nillable") else "Lookup"
                            })

        return json.dumps({
            "success": True,
            "diagram": {
                "nodes": nodes,
                "edges": edges
            },
            "summary": {
                "object_count": len(nodes),
                "relationship_count": len(edges)
            }
        }, indent=2)

    except Exception as e:
        logger.exception("generate_object_diagram failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def list_all_objects(filter_type: str = "all") -> str:
    """List all objects in the org.

    Added by Sameer

    Args:
        filter_type: Filter (all, custom, standard, queryable, createable)

    Returns:
        JSON with object list
    """
    try:
        sf = get_salesforce_connection()

        describe_global = sf.describe()
        all_objects = describe_global["sobjects"]

        # Filter objects
        filtered = []
        for obj in all_objects:
            include = False

            if filter_type == "all":
                include = True
            elif filter_type == "custom" and obj.get("custom"):
                include = True
            elif filter_type == "standard" and not obj.get("custom"):
                include = True
            elif filter_type == "queryable" and obj.get("queryable"):
                include = True
            elif filter_type == "createable" and obj.get("createable"):
                include = True

            if include:
                filtered.append({
                    "name": obj["name"],
                    "label": obj["label"],
                    "custom": obj.get("custom", False),
                    "queryable": obj.get("queryable", False),
                    "createable": obj.get("createable", False),
                    "updateable": obj.get("updateable", False),
                    "deletable": obj.get("deletable", False)
                })

        return json.dumps({
            "success": True,
            "filter": filter_type,
            "total_count": len(filtered),
            "objects": filtered
        }, indent=2)

    except Exception as e:
        logger.exception("list_all_objects failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def get_field_usage_stats(object_name: str) -> str:
    """Get statistics about field usage (null values, etc.).

    Added by Sameer

    Args:
        object_name: Object API name

    Returns:
        JSON with field usage statistics
    """
    try:
        sf = get_salesforce_connection()

        # Get total record count
        count_query = f"SELECT COUNT() FROM {object_name}"
        count_result = sf.query(count_query)
        total_records = count_result.get("totalSize", 0)

        if total_records == 0:
            return json.dumps({
                "success": True,
                "object": object_name,
                "total_records": 0,
                "message": "No records to analyze"
            })

        # Get fields
        describe = sf.__getattr__(object_name).describe()
        field_stats = []

        # Sample first 1000 records for analysis
        sample_query = f"SELECT FIELDS(ALL) FROM {object_name} LIMIT 1000"

        try:
            sample_result = sf.query(sample_query)
            records = sample_result.get("records", [])

            for field in describe["fields"]:
                if not field.get("custom"):
                    continue  # Only analyze custom fields

                field_name = field["name"]
                null_count = sum(1 for r in records if not r.get(field_name))
                populated_count = len(records) - null_count

                field_stats.append({
                    "field": field_name,
                    "label": field["label"],
                    "type": field["type"],
                    "null_count": null_count,
                    "populated_count": populated_count,
                    "population_rate": f"{(populated_count / len(records) * 100):.1f}%" if records else "0%"
                })

        except Exception as e:
            # Fallback to individual field queries
            logger.warning(f"FIELDS(ALL) not supported, using individual queries: {e}")

        return json.dumps({
            "success": True,
            "object": object_name,
            "total_records": total_records,
            "sample_size": len(records) if 'records' in locals() else 0,
            "field_stats": field_stats
        }, indent=2)

    except Exception as e:
        logger.exception("get_field_usage_stats failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def test_field_analysis(object_name: str, field_name: str) -> str:
    """Quick test version of field analysis - analyzes ONE field only (for testing).

    Added by Sameer

    Args:
        object_name: Object API name (e.g., "Case", "Account")
        field_name: Field API name (e.g., "Status", "Name")

    Returns:
        JSON with field usage results

    Example:
        test_field_analysis("Case", "Status")
    """
    try:
        sf = get_salesforce_connection()

        result = {
            "success": True,
            "field": f"{object_name}.{field_name}",
            "usage": {
                "apex_classes": [],
                "apex_triggers": []
            }
        }

        # Simple Apex class check
        try:
            apex_query = f"SELECT Id, Name FROM ApexClass WHERE Body LIKE '%{field_name}%' LIMIT 10"
            apex_result = sf.query_all(apex_query)
            result["usage"]["apex_classes"] = [r["Name"] for r in apex_result.get("records", [])]
        except Exception as e:
            result["usage"]["apex_classes_error"] = str(e)

        # Simple trigger check
        try:
            trigger_query = f"SELECT Id, Name FROM ApexTrigger WHERE Body LIKE '%{field_name}%' LIMIT 10"
            trigger_result = sf.query_all(trigger_query)
            result["usage"]["apex_triggers"] = [r["Name"] for r in trigger_result.get("records", [])]
        except Exception as e:
            result["usage"]["apex_triggers_error"] = str(e)

        return json.dumps(result, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }, indent=2)


@register_tool
def analyze_field_usage(
    object_name: str,
    field_name: Optional[str] = None,
    export_to_csv: bool = True,
    output_file: Optional[str] = None,
    include_reports: bool = False
) -> str:
    """Comprehensive field usage analysis - find where fields are used across all metadata.

    This tool analyzes field usage across Apex Classes, Triggers, Flows, Validation Rules,
    Formula Fields, Workflow Rules, Page Layouts, Email Templates, and optionally Reports.
    Perfect for field audit, cleanup, and impact analysis.

    Added by Sameer

    Args:
        object_name: Object API name (e.g., "Case", "Account", "CustomObject__c")
        field_name: Specific field to analyze (e.g., "Status", "Custom_Field__c").
                   If None, analyzes ALL CUSTOM fields on the object (standard fields excluded).
        export_to_csv: Whether to export results to CSV file (default: True)
        output_file: Custom CSV filename. If None, auto-generates:
                    "{object_name}_field_usage_{timestamp}.csv"
        include_reports: Whether to check Reports (default: False for performance).
                        Set to True only when you need report analysis.
                        Reports can slow down analysis significantly.

    Returns:
        JSON with detailed field usage analysis and CSV file path (if exported)

    Example:
        # Analyze single field (fast - no reports)
        analyze_field_usage("Case", "Status")

        # Analyze with reports
        analyze_field_usage("Case", "Status", include_reports=True)

        # Analyze ALL CUSTOM fields on Case object (standard fields excluded)
        analyze_field_usage("Case")

        # Analyze all custom fields with reports included
        analyze_field_usage("Case", include_reports=True)

        # Custom CSV output
        analyze_field_usage("Account", export_to_csv=True, output_file="account_audit.csv")

    CSV Columns:
        - Field Name
        - Field Label
        - Field Type
        - Used in Apex Classes (count + names)
        - Used in Triggers (count + names)
        - Used in Flows (count + names)
        - Used in Validation Rules (count + names)
        - Used in Formula Fields (count + names)
        - Used in Workflow Rules (count + names)
        - Used in Page Layouts (count + names)
        - Used in Email Templates (count + names)
        - Used in Reports (count + names)
        - Total Usage Count
        - Is Referenced (Yes/No)
    """
    try:
        sf = get_salesforce_connection()
        logger.info(f"Starting field usage analysis for {object_name}.{field_name or 'ALL'}")

        # Get object metadata
        describe = sf.__getattr__(object_name).describe()

        # Determine which fields to analyze
        if field_name:
            # Single field analysis
            fields_to_analyze = [f for f in describe["fields"] if f["name"] == field_name]
            if not fields_to_analyze:
                return json.dumps({
                    "success": False,
                    "error": f"Field '{field_name}' not found on object '{object_name}'"
                })
        else:
            # All fields analysis - only analyze custom fields (not standard fields)
            fields_to_analyze = [f for f in describe["fields"] if f.get("custom", False)]

        logger.info(f"Analyzing {len(fields_to_analyze)} fields (custom fields only)...")
        logger.info("PERFORMANCE MODE: Fetching all metadata in batches first (much faster!)...")

        # ===================================================================
        # PERFORMANCE OPTIMIZATION: Fetch ALL metadata ONCE, then check fields
        # This reduces API calls from (fields × 8) to just ~8 total queries!
        # ===================================================================

        # Cache storage for all metadata
        metadata_cache = {
            "apex_classes": {},
            "apex_triggers": {},
            "flows": {},
            "validation_rules": {},
            "workflow_rules": {},
            "layouts": {},
            "reports": {},
            "email_templates": {}
        }

        # 1. Fetch ALL Apex Classes (ONCE)
        try:
            logger.info("Fetching all Apex Classes...")
            apex_query = "SELECT Id, Name, Body FROM ApexClass"
            apex_result = sf.query_all(apex_query)
            for apex in apex_result.get("records", []):
                metadata_cache["apex_classes"][apex["Name"]] = apex.get("Body", "")
            logger.info(f"  ✓ Cached {len(metadata_cache['apex_classes'])} Apex classes")
        except Exception as e:
            logger.warning(f"Error fetching Apex Classes: {e}")

        # 2. Fetch ALL Apex Triggers (ONCE)
        try:
            logger.info("Fetching all Apex Triggers...")
            trigger_query = "SELECT Id, Name, Body FROM ApexTrigger"
            trigger_result = sf.query_all(trigger_query)
            for trigger in trigger_result.get("records", []):
                metadata_cache["apex_triggers"][trigger["Name"]] = trigger.get("Body", "")
            logger.info(f"  ✓ Cached {len(metadata_cache['apex_triggers'])} triggers")
        except Exception as e:
            logger.warning(f"Error fetching Triggers: {e}")

        # 3. Fetch ALL Active Flows (ONCE) - Get actual flow content via Tooling API
        try:
            logger.info("Fetching all active Flows via Tooling API...")
            # Query Flow objects to get latest active versions
            flow_query = "SELECT Id, Definition.DeveloperName, Status FROM Flow WHERE Status = 'Active'"
            flow_result = sf.restful("tooling/query", params={'q': flow_query})

            for flow in flow_result.get("records", []):
                flow_id = flow.get("Id", "")
                # Get DeveloperName from Definition object
                definition = flow.get("Definition", {})
                flow_api_name = definition.get("DeveloperName", "") if definition else ""

                # Try to get flow metadata to check for field references
                try:
                    # Fetch the flow's full definition which contains field references
                    flow_detail = sf.restful(f"tooling/sobjects/Flow/{flow_id}")
                    metadata = flow_detail.get("Metadata", {})
                    flow_label = metadata.get("label", flow_api_name)

                    # Combine all searchable content including metadata
                    metadata_str = str(metadata)
                    flow_content = f"{flow_label} {flow_api_name} {metadata_str}"

                except Exception:
                    # If metadata fetch fails, use basic info
                    logger.debug(f"Could not fetch full metadata for flow {flow_api_name}, using basic info")
                    flow_content = flow_api_name
                    flow_label = flow_api_name

                metadata_cache["flows"][flow_label or flow_api_name] = flow_content
                logger.debug(f"Cached flow: {flow_label}")

            logger.info(f"  ✓ Cached {len(metadata_cache['flows'])} active flows")
        except Exception as e:
            logger.warning(f"Error fetching Flows: {e}")

        # 4. Fetch ALL Validation Rules for this object (ONCE)
        try:
            logger.info("Fetching all Validation Rules...")
            # First query: Get ValidationName and Id only (ErrorConditionFormula is not directly queryable)
            vr_query = f"""
                SELECT ValidationName, Id
                FROM ValidationRule
                WHERE EntityDefinition.QualifiedApiName = '{object_name}' AND Active = true
            """
            vr_result = sf.restful("tooling/query", params={'q': vr_query})

            # Second step: Fetch full record with Metadata for each validation rule
            for rec in vr_result.get("records", []):
                vr_id = rec.get("Id")
                vr_name = rec.get("ValidationName")

                # Get full record with Metadata
                try:
                    detail = sf.restful(f"tooling/sobjects/ValidationRule/{vr_id}")
                    metadata = detail.get("Metadata") or {}
                    formula = metadata.get("errorConditionFormula", "")
                    error_msg = metadata.get("errorMessage", "")

                    metadata_cache["validation_rules"][vr_name] = {
                        "formula": formula,
                        "error_msg": error_msg,
                        "name": vr_name
                    }
                except Exception as detail_error:
                    logger.warning(f"Error fetching details for validation rule {vr_name}: {detail_error}")

            logger.info(f"  ✓ Cached {len(metadata_cache['validation_rules'])} validation rules")
        except Exception as e:
            logger.warning(f"Error fetching Validation Rules: {e}")

        # 5. Fetch ALL Workflow Rules for this object (ONCE)
        try:
            logger.info("Fetching all Workflow Rules...")
            # First query: Get Id and Name only (Formula is not directly queryable)
            wf_query = f"""
                SELECT Id, Name
                FROM WorkflowRule
                WHERE TableEnumOrId = '{object_name}' AND IsActive = true
            """
            wf_result = sf.restful("tooling/query", params={'q': wf_query})

            # Second step: Fetch full record with Metadata for each workflow rule
            for rec in wf_result.get("records", []):
                wf_id = rec.get("Id")
                wf_name = rec.get("Name")

                # Get full record with Metadata
                try:
                    detail = sf.restful(f"tooling/sobjects/WorkflowRule/{wf_id}")
                    metadata = detail.get("Metadata") or {}
                    formula = metadata.get("formula", "")

                    metadata_cache["workflow_rules"][wf_name] = formula
                except Exception as detail_error:
                    logger.warning(f"Error fetching details for workflow rule {wf_name}: {detail_error}")

            logger.info(f"  ✓ Cached {len(metadata_cache['workflow_rules'])} workflow rules")
        except Exception as e:
            logger.warning(f"Error fetching Workflow Rules: {e}")

        # 6. Fetch ALL Page Layouts for this object (ONCE)
        try:
            logger.info(f"Fetching all Page Layouts for {object_name}...")
            # First query: Get Id, Name, and EntityDefinitionId
            # Note: We'll filter by object after fetching to ensure we only get layouts for this object
            layout_query = f"""
                SELECT Id, Name, EntityDefinitionId, EntityDefinition.QualifiedApiName
                FROM Layout
                WHERE EntityDefinition.QualifiedApiName = '{object_name}'
            """
            layout_result = sf.restful("tooling/query", params={'q': layout_query})

            layouts_for_object = layout_result.get("records", [])
            logger.info(f"Found {len(layouts_for_object)} layouts for {object_name}")

            # Second step: Fetch full record with Metadata for each layout
            for layout in layouts_for_object:
                layout_id = layout.get("Id")
                layout_name = layout.get("Name")

                try:
                    # Get full record with Metadata
                    layout_detail = sf.restful(f"tooling/sobjects/Layout/{layout_id}")
                    metadata = layout_detail.get("Metadata", {})

                    # Extract field names from layout sections
                    field_names = []
                    layout_sections = metadata.get("layoutSections", [])
                    for section in layout_sections:
                        layout_columns = section.get("layoutColumns", [])
                        for column in layout_columns:
                            layout_items = column.get("layoutItems", [])
                            for item in layout_items:
                                field_name = item.get("field")
                                if field_name:
                                    field_names.append(field_name.strip())

                    metadata_cache["layouts"][layout_name] = field_names
                    logger.debug(f"Cached layout '{layout_name}' with {len(field_names)} fields")
                except Exception as layout_err:
                    logger.debug(f"Error fetching metadata for layout {layout_name}: {layout_err}")
                    metadata_cache["layouts"][layout_name] = []

            logger.info(f"  ✓ Cached {len(metadata_cache['layouts'])} page layouts for {object_name}")
        except Exception as e:
            logger.warning(f"Error fetching Page Layouts: {e}")

        # 7. Fetch ALL Reports (LIMITED) (ONCE) - OPTIONAL (only if requested)
        if include_reports:
            try:
                logger.info("Fetching reports (limited to 50 for performance)...")
                report_query = "SELECT Id, Name FROM Report LIMIT 50"
                report_result = sf.query_all(report_query)

                report_count = 0
                for report in report_result.get("records", []):
                    if report_count >= 50:  # Hard limit to prevent timeout
                        break

                    report_id = report["Id"]
                    report_name = report["Name"]

                    try:
                        # Get report metadata (with timeout protection)
                        report_describe = sf.restful(f'analytics/reports/{report_id}/describe')
                        if report_describe:
                            report_metadata = report_describe.get("reportMetadata", {})
                            # Store all columns/fields in this report
                            all_fields = []
                            all_fields.extend(report_metadata.get("detailColumns", []))

                            for agg in report_metadata.get("aggregates", []):
                                all_fields.append(str(agg))

                            for group in report_metadata.get("groupingsDown", []) + report_metadata.get("groupingsAcross", []):
                                all_fields.append(str(group))

                            for rf in report_metadata.get("reportFilters", []):
                                all_fields.append(rf.get("column", ""))

                            metadata_cache["reports"][report_name] = " ".join(all_fields)
                            report_count += 1
                    except Exception as e:
                        # Skip problematic reports
                        logger.debug(f"Skipping report {report_name}: {e}")
                        metadata_cache["reports"][report_name] = report_name

                logger.info(f"  ✓ Cached {len(metadata_cache['reports'])} reports")
            except Exception as e:
                logger.warning(f"Error fetching Reports (continuing without report analysis): {e}")
                # Continue without reports - don't fail the whole analysis
        else:
            logger.info("  ⊘ Skipping reports (include_reports=False) - use include_reports=True to analyze reports")

        # 8. Fetch ALL Email Templates (ONCE) - Always fetch
        try:
            logger.info("Fetching all Email Templates...")
            # Query EmailTemplate - check HtmlValue, Body, Subject, BrandTemplateId
            email_query = """
                SELECT Id, Name, DeveloperName, Subject, HtmlValue, Body
                FROM EmailTemplate
                WHERE IsActive = true
                LIMIT 500
            """
            email_result = sf.query_all(email_query)
            for email in email_result.get("records", []):
                email_name = email.get("Name") or email.get("DeveloperName", "Unknown")
                # Combine all searchable content
                email_content = " ".join([
                    email.get("Subject", ""),
                    email.get("HtmlValue", ""),
                    email.get("Body", ""),
                    email.get("DeveloperName", "")
                ])
                metadata_cache["email_templates"][email_name] = email_content
                logger.debug(f"Cached email template: {email_name}")
            logger.info(f"  ✓ Cached {len(metadata_cache['email_templates'])} email templates")
        except Exception as e:
            logger.warning(f"Error fetching Email Templates: {e}")

        logger.info(f"✓ All metadata cached! Now analyzing {len(fields_to_analyze)} fields against cached data...")

        # Results storage
        field_usage_results = []

        # Process each field (NOW FAST - just checking against cached data!)
        for idx, field in enumerate(fields_to_analyze, 1):
            field_api_name = field["name"]
            if idx % 50 == 0:  # Progress every 50 fields
                logger.info(f"Progress: [{idx}/{len(fields_to_analyze)}] fields analyzed")

            usage_data = {
                "field_name": field_api_name,
                "field_label": field["label"],
                "field_type": field["type"],
                "is_custom": field.get("custom", False),
                "is_required": not field.get("nillable", True),
                "apex_classes": [],
                "apex_triggers": [],
                "flows": [],
                "validation_rules": [],
                "formula_fields": [],
                "workflow_rules": [],
                "page_layouts": [],
                "email_templates": [],
                "reports": [],
                "total_usage": 0
            }

            # 1. Check Apex Classes (from cache)
            usage_data["apex_classes"] = [
                name for name, body in metadata_cache["apex_classes"].items()
                if field_api_name in body
            ]

            # 2. Check Apex Triggers (from cache)
            usage_data["apex_triggers"] = [
                name for name, body in metadata_cache["apex_triggers"].items()
                if field_api_name in body
            ]

            # 3. Check Flows (from cache)
            flows_with_field = []
            for flow_name, flow_data in metadata_cache["flows"].items():
                if field_api_name in flow_data or field_api_name.lower() in flow_name.lower():
                    flows_with_field.append(flow_name)
                    logger.debug(f"✓ Found {field_api_name} in Flow: {flow_name}")

            if not flows_with_field and metadata_cache["flows"]:
                logger.debug(f"✗ {field_api_name} not found in any of {len(metadata_cache['flows'])} flows")
                logger.debug(f"   Sample flow names: {list(metadata_cache['flows'].keys())[:3]}")

            usage_data["flows"] = flows_with_field

            # 4. Check Validation Rules (from cache)
            vr_using_field = []
            for vr_name, vr_data in metadata_cache["validation_rules"].items():
                if (field_api_name in vr_data["formula"] or
                    field_api_name in vr_data["error_msg"] or
                    field_api_name in vr_data["name"]):
                    vr_using_field.append(vr_name)
            usage_data["validation_rules"] = vr_using_field

            # 5. Check Formula Fields (fields that reference this field)
            try:
                formula_fields = [
                    f["name"] for f in describe["fields"]
                    if f.get("calculatedFormula") and field_api_name in f.get("calculatedFormula", "")
                ]
                usage_data["formula_fields"] = formula_fields
            except Exception as e:
                logger.warning(f"Error checking Formula Fields for {field_api_name}: {e}")

            # 6. Check Workflow Rules (from cache)
            usage_data["workflow_rules"] = [
                name for name, formula in metadata_cache["workflow_rules"].items()
                if field_api_name in formula or field_api_name in name
            ]

            # 7. Check Page Layouts (from cache) - IMPROVED MATCHING
            layouts_with_field = []
            for layout_name, field_list in metadata_cache["layouts"].items():
                # Check for exact match or case-insensitive match
                for field_in_layout in field_list:
                    if (field_api_name == field_in_layout or
                        field_api_name.lower() == field_in_layout.lower()):
                        layouts_with_field.append(layout_name)
                        logger.debug(f"✓ Found {field_api_name} in layout: {layout_name}")
                        break

            if not layouts_with_field and metadata_cache["layouts"]:
                logger.debug(f"✗ {field_api_name} not found in any of {len(metadata_cache['layouts'])} page layouts")
                # Show first layout's fields for debugging
                if metadata_cache["layouts"]:
                    first_layout = list(metadata_cache["layouts"].items())[0]
                    logger.debug(f"   Sample layout '{first_layout[0]}' has {len(first_layout[1])} fields: {first_layout[1][:5]}")

            usage_data["page_layouts"] = layouts_with_field

            # 8. Check Reports (from cache)
            usage_data["reports"] = [
                report_name for report_name, report_data in metadata_cache["reports"].items()
                if field_api_name in report_data or field_api_name.lower() in report_name.lower()
            ]

            # 9. Check Email Templates (from cache) - NEW!
            email_templates_with_field = []
            for email_name, email_content in metadata_cache["email_templates"].items():
                if field_api_name in email_content:
                    email_templates_with_field.append(email_name)
                    logger.debug(f"✓ Found {field_api_name} in Email Template: {email_name}")

            if not email_templates_with_field and metadata_cache["email_templates"]:
                logger.debug(f"✗ {field_api_name} not found in any of {len(metadata_cache['email_templates'])} email templates")

            usage_data["email_templates"] = email_templates_with_field

            # Calculate total usage
            usage_data["total_usage"] = (
                len(usage_data["apex_classes"]) +
                len(usage_data["apex_triggers"]) +
                len(usage_data["flows"]) +
                len(usage_data["validation_rules"]) +
                len(usage_data["formula_fields"]) +
                len(usage_data["workflow_rules"]) +
                len(usage_data["page_layouts"]) +
                len(usage_data["reports"]) +
                len(usage_data["email_templates"])
            )

            usage_data["is_referenced"] = usage_data["total_usage"] > 0

            field_usage_results.append(usage_data)

        logger.info(f"✓ Completed analysis of {len(field_usage_results)} fields!")

        # Generate CSV if requested
        csv_file_path = None
        if export_to_csv:
            # Create Documents folder if it doesn't exist
            docs_folder = os.path.join(os.getcwd(), "Documents")
            os.makedirs(docs_folder, exist_ok=True)

            if not output_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"{object_name}_field_usage_{timestamp}.csv"

            # If output_file is just a filename (no path), save to Documents folder
            if not os.path.dirname(output_file):
                csv_file_path = os.path.join(docs_folder, output_file)
            else:
                # If full path provided, use it as-is
                csv_file_path = os.path.abspath(output_file)

            with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'Field Name',
                    'Field Label',
                    'Field Type',
                    'Is Custom',
                    'Is Required',
                    'Apex Classes Count',
                    'Apex Classes',
                    'Triggers Count',
                    'Triggers',
                    'Flows Count',
                    'Flows',
                    'Validation Rules Count',
                    'Validation Rules',
                    'Formula Fields Count',
                    'Formula Fields',
                    'Workflow Rules Count',
                    'Workflow Rules',
                    'Page Layouts Count',
                    'Page Layouts',
                    'Email Templates Count',
                    'Email Templates',
                    'Reports Count',
                    'Reports',
                    'Total Usage Count',
                    'Is Referenced'
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for result in field_usage_results:
                    writer.writerow({
                        'Field Name': result['field_name'],
                        'Field Label': result['field_label'],
                        'Field Type': result['field_type'],
                        'Is Custom': 'Yes' if result['is_custom'] else 'No',
                        'Is Required': 'Yes' if result['is_required'] else 'No',
                        'Apex Classes Count': len(result['apex_classes']),
                        'Apex Classes': ', '.join(result['apex_classes']),
                        'Triggers Count': len(result['apex_triggers']),
                        'Triggers': ', '.join(result['apex_triggers']),
                        'Flows Count': len(result['flows']),
                        'Flows': ', '.join(result['flows']),
                        'Validation Rules Count': len(result['validation_rules']),
                        'Validation Rules': ', '.join(result['validation_rules']),
                        'Formula Fields Count': len(result['formula_fields']),
                        'Formula Fields': ', '.join(result['formula_fields']),
                        'Workflow Rules Count': len(result['workflow_rules']),
                        'Workflow Rules': ', '.join(result['workflow_rules']),
                        'Page Layouts Count': len(result['page_layouts']),
                        'Page Layouts': ', '.join(result['page_layouts']),
                        'Email Templates Count': len(result['email_templates']),
                        'Email Templates': ', '.join(result['email_templates']),
                        'Reports Count': len(result['reports']),
                        'Reports': ', '.join(result['reports']),
                        'Total Usage Count': result['total_usage'],
                        'Is Referenced': 'Yes' if result['is_referenced'] else 'No'
                    })

            logger.info(f"CSV exported to: {csv_file_path}")

        # Summary statistics
        total_referenced = sum(1 for r in field_usage_results if r['is_referenced'])
        total_unreferenced = len(field_usage_results) - total_referenced

        return json.dumps({
            "success": True,
            "object": object_name,
            "field_analyzed": field_name if field_name else "ALL",
            "total_fields_analyzed": len(field_usage_results),
            "summary": {
                "referenced_fields": total_referenced,
                "unreferenced_fields": total_unreferenced,
                "total_apex_classes": sum(len(r["apex_classes"]) for r in field_usage_results),
                "total_triggers": sum(len(r["apex_triggers"]) for r in field_usage_results),
                "total_flows": sum(len(r["flows"]) for r in field_usage_results),
                "total_validation_rules": sum(len(r["validation_rules"]) for r in field_usage_results),
                "total_formula_fields": sum(len(r["formula_fields"]) for r in field_usage_results),
                "total_workflow_rules": sum(len(r["workflow_rules"]) for r in field_usage_results),
                "total_page_layouts": sum(len(r["page_layouts"]) for r in field_usage_results),
                "total_email_templates": sum(len(r["email_templates"]) for r in field_usage_results),
                "total_reports": sum(len(r["reports"]) for r in field_usage_results)
            },
            "csv_file": csv_file_path,
            "field_usage_details": field_usage_results[:10] if len(field_usage_results) > 10 else field_usage_results,
            "note": "Full results exported to CSV. Only first 10 results shown in JSON to avoid token limits."
        }, indent=2)

    except Exception as e:
        logger.exception("analyze_field_usage failed")
        import traceback
        return json.dumps({
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }, indent=2)
