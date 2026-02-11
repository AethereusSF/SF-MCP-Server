"""Multi-org management and metadata comparison tools

Created by Sameer
"""
import logging
import json
import time
from typing import Optional, List, Dict, Any
from simple_salesforce import Salesforce

from app.config import get_config
from app.mcp.server import register_tool
from app.mcp.tools.oauth_auth import get_stored_tokens, refresh_salesforce_token

logger = logging.getLogger(__name__)

# Active org context
_active_org = {"user_id": None}


@register_tool
def list_connected_orgs() -> str:
    """List all connected Salesforce orgs.

    Added by Sameer

    Returns:
        JSON with list of connected orgs and their details
    """
    try:
        stored_tokens = get_stored_tokens()

        if not stored_tokens:
            return json.dumps({
                "success": True,
                "total_count": 0,
                "orgs": [],
                "message": "No orgs connected. Use login commands to connect."
            })

        orgs = []
        for user_id, token_data in stored_tokens.items():
            orgs.append({
                "user_id": user_id,
                "instance_url": token_data['instance_url'],
                "org_type": token_data.get('org_type', 'unknown'),
                "login_timestamp": token_data['login_timestamp'],
                "is_active": user_id == _active_org["user_id"]
            })

        return json.dumps({
            "success": True,
            "total_count": len(orgs),
            "active_org": _active_org["user_id"],
            "orgs": orgs
        }, indent=2)

    except Exception as e:
        logger.exception("list_connected_orgs failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def switch_active_org(user_id: str) -> str:
    """Switch to a different connected org.

    Added by Sameer

    Args:
        user_id: User ID of the org to switch to

    Returns:
        JSON with switch status
    """
    try:
        stored_tokens = get_stored_tokens()

        if user_id not in stored_tokens:
            available_orgs = list(stored_tokens.keys())
            return json.dumps({
                "success": False,
                "error": f"Org '{user_id}' not connected",
                "available_orgs": available_orgs
            })

        # Set active org
        _active_org["user_id"] = user_id
        token_data = stored_tokens[user_id]

        # Clear connection cache to force new connection
        from app.services.salesforce import clear_connection_cache
        clear_connection_cache()

        return json.dumps({
            "success": True,
            "active_org": user_id,
            "instance_url": token_data['instance_url'],
            "org_type": token_data.get('org_type', 'unknown'),
            "message": f"Switched to org: {token_data['instance_url']}"
        }, indent=2)

    except Exception as e:
        logger.exception("switch_active_org failed")
        return json.dumps({"success": False, "error": str(e)})


def _get_connection_for_org(user_id: str) -> Salesforce:
    """Get Salesforce connection for specific org.

    Added by Sameer
    """
    stored_tokens = get_stored_tokens()

    if user_id not in stored_tokens:
        raise ValueError(f"Org '{user_id}' not connected")

    token_data = stored_tokens[user_id]

    # Check if token needs refresh
    config = get_config()
    token_age = time.time() - token_data['login_timestamp']
    if token_age > config.token_refresh_threshold_seconds:
        if not refresh_salesforce_token(user_id):
            raise Exception(f"Failed to refresh token for {user_id}")
        token_data = get_stored_tokens()[user_id]

    # Create connection
    return Salesforce(
        instance_url=token_data['instance_url'],
        session_id=token_data['access_token']
    )


@register_tool
def compare_metadata_between_orgs(
    source_org: str,
    target_org: str,
    metadata_type: str,
    metadata_names: Optional[List[str]] = None
) -> str:
    """Compare metadata between two connected orgs.

    Added by Sameer

    Args:
        source_org: Source org user ID
        target_org: Target org user ID
        metadata_type: Type of metadata (ApexClass, ApexTrigger, Flow, etc.)
        metadata_names: Specific metadata names to compare (None = all)

    Returns:
        JSON with comparison results
    """
    try:
        sf_source = _get_connection_for_org(source_org)
        sf_target = _get_connection_for_org(target_org)

        comparison = {
            "source_org": source_org,
            "target_org": target_org,
            "metadata_type": metadata_type,
            "only_in_source": [],
            "only_in_target": [],
            "in_both": [],
            "differences": []
        }

        # Query metadata based on type
        if metadata_type == "ApexClass":
            source_query = "SELECT Id, Name, ApiVersion, Status, LengthWithoutComments FROM ApexClass"
            target_query = source_query
        elif metadata_type == "ApexTrigger":
            source_query = "SELECT Id, Name, TableEnumOrId, Status, ApiVersion FROM ApexTrigger"
            target_query = source_query
        elif metadata_type == "Flow":
            source_query = "SELECT ApiName, Label, ProcessType, Status FROM FlowDefinition"
            target_query = source_query
        elif metadata_type == "ValidationRule":
            source_query = "SELECT Id, ValidationName, EntityDefinition.QualifiedApiName, Active FROM ValidationRule"
            target_query = source_query
        else:
            return json.dumps({
                "success": False,
                "error": f"Metadata type '{metadata_type}' not yet supported for comparison",
                "supported_types": ["ApexClass", "ApexTrigger", "Flow", "ValidationRule"]
            })

        # Filter by names if provided
        if metadata_names:
            names_str = "', '".join(metadata_names)
            source_query += f" WHERE Name IN ('{names_str}')" if "ApexClass" in metadata_type or "ApexTrigger" in metadata_type else ""

        # Execute queries
        if metadata_type in ["ApexClass", "ApexTrigger"]:
            source_result = sf_source.toolingexecute(f"query/?q={source_query}")
            target_result = sf_target.toolingexecute(f"query/?q={target_query}")
        else:
            source_result = sf_source.query(source_query)
            target_result = sf_target.query(source_query)

        source_items = {item.get("Name") or item.get("ApiName"): item for item in source_result.get("records", [])}
        target_items = {item.get("Name") or item.get("ApiName"): item for item in target_result.get("records", [])}

        # Compare
        source_names = set(source_items.keys())
        target_names = set(target_items.keys())

        comparison["only_in_source"] = list(source_names - target_names)
        comparison["only_in_target"] = list(target_names - source_names)
        comparison["in_both"] = list(source_names & target_names)

        # Check for differences in items that exist in both
        for name in comparison["in_both"]:
            source_item = source_items[name]
            target_item = target_items[name]

            diffs = []

            # Compare key fields
            if metadata_type == "ApexClass":
                if source_item.get("ApiVersion") != target_item.get("ApiVersion"):
                    diffs.append(f"API Version: {source_item.get('ApiVersion')} vs {target_item.get('ApiVersion')}")
                if source_item.get("Status") != target_item.get("Status"):
                    diffs.append(f"Status: {source_item.get('Status')} vs {target_item.get('Status')}")

            elif metadata_type == "Flow":
                if source_item.get("Status") != target_item.get("Status"):
                    diffs.append(f"Status: {source_item.get('Status')} vs {target_item.get('Status')}")

            elif metadata_type == "ValidationRule":
                if source_item.get("Active") != target_item.get("Active"):
                    diffs.append(f"Active: {source_item.get('Active')} vs {target_item.get('Active')}")

            if diffs:
                comparison["differences"].append({
                    "name": name,
                    "differences": diffs
                })

        return json.dumps({
            "success": True,
            "comparison": comparison,
            "summary": {
                "total_in_source": len(source_names),
                "total_in_target": len(target_names),
                "only_in_source_count": len(comparison["only_in_source"]),
                "only_in_target_count": len(comparison["only_in_target"]),
                "in_both_count": len(comparison["in_both"]),
                "differences_count": len(comparison["differences"])
            }
        }, indent=2)

    except Exception as e:
        logger.exception("compare_metadata_between_orgs failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def compare_object_schemas(
    source_org: str,
    target_org: str,
    object_names: List[str]
) -> str:
    """Compare object schemas between two orgs.

    Added by Sameer

    Args:
        source_org: Source org user ID
        target_org: Target org user ID
        object_names: List of object API names to compare

    Returns:
        JSON with schema comparison
    """
    try:
        sf_source = _get_connection_for_org(source_org)
        sf_target = _get_connection_for_org(target_org)

        comparison = {}

        for obj_name in object_names:
            try:
                source_describe = sf_source.__getattr__(obj_name).describe()
                target_describe = sf_target.__getattr__(obj_name).describe()

                # Get field names
                source_fields = {f["name"]: f for f in source_describe["fields"]}
                target_fields = {f["name"]: f for f in target_describe["fields"]}

                source_field_names = set(source_fields.keys())
                target_field_names = set(target_fields.keys())

                field_diffs = []
                for field_name in source_field_names & target_field_names:
                    src_field = source_fields[field_name]
                    tgt_field = target_fields[field_name]

                    if src_field["type"] != tgt_field["type"]:
                        field_diffs.append({
                            "field": field_name,
                            "difference": "type",
                            "source": src_field["type"],
                            "target": tgt_field["type"]
                        })

                    if src_field.get("length") != tgt_field.get("length"):
                        field_diffs.append({
                            "field": field_name,
                            "difference": "length",
                            "source": src_field.get("length"),
                            "target": tgt_field.get("length")
                        })

                comparison[obj_name] = {
                    "fields_only_in_source": list(source_field_names - target_field_names),
                    "fields_only_in_target": list(target_field_names - source_field_names),
                    "common_fields": list(source_field_names & target_field_names),
                    "field_differences": field_diffs,
                    "source_recordtype_count": len(source_describe.get("recordTypeInfos", [])),
                    "target_recordtype_count": len(target_describe.get("recordTypeInfos", []))
                }

            except Exception as e:
                comparison[obj_name] = {
                    "error": str(e),
                    "message": "Failed to compare this object"
                }

        return json.dumps({
            "success": True,
            "source_org": source_org,
            "target_org": target_org,
            "object_comparisons": comparison
        }, indent=2)

    except Exception as e:
        logger.exception("compare_object_schemas failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def get_org_differences_summary(source_org: str, target_org: str) -> str:
    """Get a high-level summary of differences between two orgs.

    Added by Sameer

    Args:
        source_org: Source org user ID
        target_org: Target org user ID

    Returns:
        JSON with summary of major differences
    """
    try:
        sf_source = _get_connection_for_org(source_org)
        sf_target = _get_connection_for_org(target_org)

        summary = {
            "source_org": source_org,
            "target_org": target_org,
            "differences": {}
        }

        # Compare org info
        source_org_query = "SELECT Name, OrganizationType, IsSandbox, InstanceName FROM Organization LIMIT 1"
        target_org_query = source_org_query

        source_org_info = sf_source.query(source_org_query).get("records", [{}])[0]
        target_org_info = sf_target.query(target_org_query).get("records", [{}])[0]

        summary["source_org_info"] = source_org_info
        summary["target_org_info"] = target_org_info

        # Compare object counts
        source_global = sf_source.describe()
        target_global = sf_target.describe()

        source_custom_objects = [o["name"] for o in source_global["sobjects"] if o.get("custom")]
        target_custom_objects = [o["name"] for o in target_global["sobjects"] if o.get("custom")]

        summary["differences"]["custom_objects"] = {
            "source_count": len(source_custom_objects),
            "target_count": len(target_custom_objects),
            "only_in_source": list(set(source_custom_objects) - set(target_custom_objects)),
            "only_in_target": list(set(target_custom_objects) - set(source_custom_objects))
        }

        # Compare Apex classes
        source_apex = sf_source.toolingexecute("query/?q=SELECT Id, Name FROM ApexClass")
        target_apex = sf_target.toolingexecute("query/?q=SELECT Id, Name FROM ApexClass")

        source_apex_names = {a["Name"] for a in source_apex.get("records", [])}
        target_apex_names = {a["Name"] for a in target_apex.get("records", [])}

        summary["differences"]["apex_classes"] = {
            "source_count": len(source_apex_names),
            "target_count": len(target_apex_names),
            "only_in_source_count": len(source_apex_names - target_apex_names),
            "only_in_target_count": len(target_apex_names - source_apex_names)
        }

        return json.dumps({
            "success": True,
            "summary": summary
        }, indent=2)

    except Exception as e:
        logger.exception("get_org_differences_summary failed")
        return json.dumps({"success": False, "error": str(e)})
