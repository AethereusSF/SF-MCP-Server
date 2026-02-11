"""SOQL query builder and helper tools

Created by Sameer
"""
import logging
import json
from typing import List, Optional, Dict, Any

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection
from app.mcp.tools.utils import (
    format_error_response,
    format_success_response,
    ResponseSizeManager
)

logger = logging.getLogger(__name__)


# DEPRECATED: Use consolidated tool instead
# @register_tool
def build_soql_query(
    object_name: str,
    fields: List[str],
    where_clause: str = "",
    order_by: str = "",
    limit: int = 200
) -> str:
    """Build a valid SOQL query from components.

    Added by Sameer

    Args:
        object_name: Salesforce object API name
        fields: List of field names to select
        where_clause: WHERE condition (without WHERE keyword)
        order_by: ORDER BY field(s) (without ORDER BY keyword)
        limit: Maximum records to return

    Returns:
        JSON with generated query and optional execution results
    """
    try:
        # Build query
        fields_str = ", ".join(fields) if fields else "Id"
        query = f"SELECT {fields_str} FROM {object_name}"

        if where_clause:
            query += f" WHERE {where_clause}"

        if order_by:
            query += f" ORDER BY {order_by}"

        if limit:
            query += f" LIMIT {limit}"

        return json.dumps({
            "success": True,
            "query": query,
            "components": {
                "object": object_name,
                "fields": fields,
                "where": where_clause,
                "order_by": order_by,
                "limit": limit
            }
        }, indent=2)

    except Exception as e:
        logger.exception("build_soql_query failed")
        return json.dumps({"success": False, "error": str(e)})


# DEPRECATED: Use consolidated tool instead
# @register_tool
def get_object_fields(object_name: str, field_type: str = "all", max_fields: int = 100, field_offset: int = 0) -> str:
    """Get all fields for an object with their metadata.

    Added by Sameer

    Args:
        object_name: Object API name
        field_type: Filter by field type (all, custom, standard, required, updateable)
        max_fields: Maximum number of fields to return (default: 100, use 0 for all)
        field_offset: Starting position for field pagination (default: 0)

    Returns:
        JSON with field list and metadata
    """
    try:
        sf = get_salesforce_connection()

        # Describe object
        describe = sf.__getattr__(object_name).describe()
        all_fields = describe['fields']

        # Filter fields based on type
        filtered_fields = []
        for field in all_fields:
            include = False

            if field_type == "all":
                include = True
            elif field_type == "custom" and field.get("custom"):
                include = True
            elif field_type == "standard" and not field.get("custom"):
                include = True
            elif field_type == "required" and not field.get("nillable") and field.get("createable"):
                include = True
            elif field_type == "updateable" and field.get("updateable"):
                include = True

            if include:
                filtered_fields.append({
                    "name": field["name"],
                    "label": field["label"],
                    "type": field["type"],
                    "length": field.get("length"),
                    "custom": field.get("custom", False),
                    "required": not field.get("nillable", True),
                    "updateable": field.get("updateable", False),
                    "referenced_to": field.get("referenceTo", [])
                })

        # Apply pagination
        total_filtered = len(filtered_fields)
        if max_fields > 0:
            paginated_fields = filtered_fields[field_offset:field_offset + max_fields]
        else:
            paginated_fields = filtered_fields[field_offset:]

        response = {
            "success": True,
            "object": object_name,
            "field_type_filter": field_type,
            "total_fields": total_filtered,
            "returned_fields": len(paginated_fields),
            "field_offset": field_offset,
            "has_more_fields": (field_offset + len(paginated_fields)) < total_filtered,
            "fields": paginated_fields
        }

        # Check response size and add warnings if needed
        response = ResponseSizeManager.check_response_size(response)
        return json.dumps(response, indent=2)

    except Exception as e:
        logger.exception("get_object_fields failed")
        return format_error_response(e, context="get_object_fields")


# DEPRECATED: Use consolidated tool instead
# @register_tool
def get_field_relationships(object_name: str) -> str:
    """Get all relationship fields and their targets.

    Added by Sameer

    Args:
        object_name: Object API name

    Returns:
        JSON with relationship field details
    """
    try:
        sf = get_salesforce_connection()

        describe = sf.__getattr__(object_name).describe()
        relationships = []

        for field in describe['fields']:
            if field.get('type') in ['reference', 'lookup', 'masterdetail']:
                relationships.append({
                    "field_name": field["name"],
                    "relationship_name": field.get("relationshipName"),
                    "reference_to": field.get("referenceTo", []),
                    "type": "Master-Detail" if not field.get("nillable") else "Lookup",
                    "cascade_delete": field.get("cascadeDelete", False)
                })

        # Get child relationships
        child_relationships = []
        for child_rel in describe.get('childRelationships', []):
            if child_rel.get('relationshipName'):
                child_relationships.append({
                    "relationship_name": child_rel["relationshipName"],
                    "child_object": child_rel["childSObject"],
                    "field": child_rel["field"],
                    "cascade_delete": child_rel.get("cascadeDelete", False)
                })

        return json.dumps({
            "success": True,
            "object": object_name,
            "parent_relationships": relationships,
            "child_relationships": child_relationships,
            "total_relationships": len(relationships) + len(child_relationships)
        }, indent=2)

    except Exception as e:
        logger.exception("get_field_relationships failed")
        return json.dumps({"success": False, "error": str(e)})


# DEPRECATED: Use consolidated tool instead
# @register_tool
def explain_soql_query(query: str) -> str:
    """Analyze a SOQL query and provide optimization suggestions.

    Added by Sameer

    Args:
        query: SOQL query to analyze

    Returns:
        JSON with analysis and suggestions
    """
    try:
        analysis = {
            "success": True,
            "query": query,
            "analysis": {},
            "suggestions": []
        }

        query_upper = query.upper()

        # Check for SELECT *
        if "SELECT *" in query_upper:
            analysis["suggestions"].append({
                "type": "performance",
                "message": "Avoid SELECT * - explicitly list needed fields",
                "impact": "high"
            })

        # Check for LIMIT
        if "LIMIT" not in query_upper:
            analysis["suggestions"].append({
                "type": "performance",
                "message": "Add LIMIT clause to prevent large result sets",
                "impact": "medium"
            })

        # Check for WHERE clause
        if "WHERE" not in query_upper:
            analysis["analysis"]["has_filter"] = False
            analysis["suggestions"].append({
                "type": "performance",
                "message": "Consider adding WHERE clause to filter results",
                "impact": "medium"
            })
        else:
            analysis["analysis"]["has_filter"] = True

        # Check for indexed fields in WHERE
        if "ID =" in query_upper or "NAME =" in query_upper:
            analysis["analysis"]["uses_indexed_field"] = True
        else:
            analysis["suggestions"].append({
                "type": "performance",
                "message": "Consider filtering on indexed fields (Id, Name, etc.)",
                "impact": "low"
            })

        # Check for relationship queries
        relationship_count = query.count('.')
        analysis["analysis"]["relationship_depth"] = relationship_count
        if relationship_count > 2:
            analysis["suggestions"].append({
                "type": "complexity",
                "message": "Deep relationship queries may impact performance",
                "impact": "medium"
            })

        # Check for subqueries
        subquery_count = query.count("(SELECT")
        analysis["analysis"]["subquery_count"] = subquery_count
        if subquery_count > 2:
            analysis["suggestions"].append({
                "type": "complexity",
                "message": "Multiple subqueries may slow down query execution",
                "impact": "high"
            })

        return json.dumps(analysis, indent=2)

    except Exception as e:
        logger.exception("explain_soql_query failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def query_with_related_records(
    parent_object: str,
    parent_fields: List[str],
    child_relationship: str,
    child_fields: List[str],
    where_clause: str = "",
    limit: int = 100
) -> str:
    """Query parent records with related child records.

    Added by Sameer

    Args:
        parent_object: Parent object API name
        parent_fields: Fields to select from parent
        child_relationship: Child relationship name
        child_fields: Fields to select from children
        where_clause: WHERE condition for parent (without WHERE)
        limit: Maximum parent records

    Returns:
        JSON with query and results
    """
    try:
        sf = get_salesforce_connection()

        # Build parent fields
        parent_fields_str = ", ".join(parent_fields)

        # Build child subquery
        child_fields_str = ", ".join(child_fields)
        subquery = f"(SELECT {child_fields_str} FROM {child_relationship})"

        # Build main query
        query = f"SELECT {parent_fields_str}, {subquery} FROM {parent_object}"

        if where_clause:
            query += f" WHERE {where_clause}"

        query += f" LIMIT {limit}"

        # Execute query
        result = sf.query(query)

        return json.dumps({
            "success": True,
            "query": query,
            "total_size": result.get("totalSize", 0),
            "records": result.get("records", [])
        }, indent=2)

    except Exception as e:
        logger.exception("query_with_related_records failed")
        return json.dumps({"success": False, "error": str(e)})
