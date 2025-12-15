"""Data export and backup tools

Created by Sameer
"""
import logging
import json
import csv
import io
from typing import Optional, List

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection

logger = logging.getLogger(__name__)


# DEPRECATED: Use consolidated tool instead
# @register_tool
def export_data_to_csv(
    soql_query: str,
    include_header: bool = True,
    max_records: int = 10000
) -> str:
    """Export SOQL query results to CSV format.

    Added by Sameer

    Args:
        soql_query: SOQL query to execute
        include_header: Include column headers
        max_records: Maximum records to export

    Returns:
        JSON with CSV data and metadata
    """
    try:
        sf = get_salesforce_connection()

        # Execute query
        result = sf.query_all(soql_query)
        records = result.get("records", [])

        if not records:
            return json.dumps({
                "success": True,
                "message": "No records found",
                "csv_data": "",
                "record_count": 0
            })

        # Limit records
        records = records[:max_records]

        # Remove attributes field from records
        clean_records = []
        for record in records:
            clean_record = {k: v for k, v in record.items() if k != 'attributes'}
            clean_records.append(clean_record)

        # Generate CSV
        output = io.StringIO()
        if clean_records:
            fieldnames = list(clean_records[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)

            if include_header:
                writer.writeheader()

            writer.writerows(clean_records)

        csv_data = output.getvalue()

        return json.dumps({
            "success": True,
            "record_count": len(clean_records),
            "fields": list(clean_records[0].keys()) if clean_records else [],
            "csv_data": csv_data,
            "truncated": len(result.get("records", [])) > max_records
        }, indent=2)

    except Exception as e:
        logger.exception("export_data_to_csv failed")
        return json.dumps({"success": False, "error": str(e)})


# DEPRECATED: Use consolidated tool instead
# @register_tool
def export_object_data(
    object_name: str,
    fields: Optional[List[str]] = None,
    where_clause: str = "",
    format: str = "json",
    max_records: int = 5000
) -> str:
    """Export all data from an object.

    Added by Sameer

    Args:
        object_name: Object API name
        fields: List of fields (None = all fields)
        where_clause: WHERE filter (without WHERE keyword)
        format: Output format (json or csv)
        max_records: Maximum records to export

    Returns:
        JSON with exported data
    """
    try:
        sf = get_salesforce_connection()

        # Get fields if not specified
        if not fields:
            describe = sf.__getattr__(object_name).describe()
            fields = [f["name"] for f in describe["fields"]]

        # Build query
        fields_str = ", ".join(fields)
        query = f"SELECT {fields_str} FROM {object_name}"

        if where_clause:
            query += f" WHERE {where_clause}"

        query += f" LIMIT {max_records}"

        # Execute query
        result = sf.query_all(query)
        records = result.get("records", [])

        # Clean records
        clean_records = []
        for record in records:
            clean_record = {k: v for k, v in record.items() if k != 'attributes'}
            clean_records.append(clean_record)

        if format.lower() == "csv":
            # Generate CSV
            output = io.StringIO()
            if clean_records:
                writer = csv.DictWriter(output, fieldnames=fields)
                writer.writeheader()
                writer.writerows(clean_records)
            data = output.getvalue()
        else:
            # JSON format
            data = clean_records

        return json.dumps({
            "success": True,
            "object": object_name,
            "record_count": len(clean_records),
            "fields": fields,
            "format": format,
            "data": data if format != "csv" else None,
            "csv_data": data if format == "csv" else None
        }, indent=2)

    except Exception as e:
        logger.exception("export_object_data failed")
        return json.dumps({"success": False, "error": str(e)})


# DEPRECATED: Use consolidated tool instead
# @register_tool
def backup_object_records(
    object_name: str,
    backup_name: str,
    where_clause: str = "",
    max_records: int = 10000
) -> str:
    """Create a backup of object records.

    Added by Sameer

    Args:
        object_name: Object API name
        backup_name: Name for this backup
        where_clause: Filter for records to backup
        max_records: Maximum records in backup

    Returns:
        JSON with backup metadata
    """
    try:
        sf = get_salesforce_connection()

        # Get all fields
        describe = sf.__getattr__(object_name).describe()
        fields = [f["name"] for f in describe["fields"]]
        fields_str = ", ".join(fields)

        # Build query
        query = f"SELECT {fields_str} FROM {object_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        query += f" LIMIT {max_records}"

        # Execute
        result = sf.query_all(query)
        records = result.get("records", [])

        # Clean and prepare backup
        clean_records = []
        for record in records:
            clean_record = {k: v for k, v in record.items() if k != 'attributes'}
            clean_records.append(clean_record)

        import datetime
        backup_metadata = {
            "backup_name": backup_name,
            "object": object_name,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "record_count": len(clean_records),
            "query": query,
            "fields": fields
        }

        return json.dumps({
            "success": True,
            "backup": backup_metadata,
            "records": clean_records,
            "message": f"Backed up {len(clean_records)} records from {object_name}"
        }, indent=2)

    except Exception as e:
        logger.exception("backup_object_records failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def get_record_count(object_name: str, where_clause: str = "") -> str:
    """Get count of records in an object.

    Added by Sameer

    Args:
        object_name: Object API name
        where_clause: WHERE filter (optional)

    Returns:
        JSON with count
    """
    try:
        sf = get_salesforce_connection()

        query = f"SELECT COUNT() FROM {object_name}"
        if where_clause:
            query += f" WHERE {where_clause}"

        result = sf.query(query)
        count = result.get("totalSize", 0)

        return json.dumps({
            "success": True,
            "object": object_name,
            "where_clause": where_clause,
            "count": count,
            "query": query
        }, indent=2)

    except Exception as e:
        logger.exception("get_record_count failed")
        return json.dumps({"success": False, "error": str(e)})


@register_tool
def export_schema_to_json(object_names: Optional[List[str]] = None) -> str:
    """Export object schema(s) to JSON.

    Added by Sameer

    Args:
        object_names: List of objects (None = all custom objects)

    Returns:
        JSON with schema definitions
    """
    try:
        sf = get_salesforce_connection()

        if not object_names:
            # Get all custom objects
            describe_global = sf.describe()
            object_names = [
                obj["name"] for obj in describe_global["sobjects"]
                if obj.get("custom") or obj["name"] in ["Account", "Contact", "Lead", "Opportunity"]
            ]

        schemas = {}
        for obj_name in object_names:
            try:
                describe = sf.__getattr__(obj_name).describe()
                schemas[obj_name] = {
                    "label": describe["label"],
                    "labelPlural": describe["labelPlural"],
                    "fields": [
                        {
                            "name": f["name"],
                            "label": f["label"],
                            "type": f["type"],
                            "length": f.get("length"),
                            "required": not f.get("nillable", True),
                            "unique": f.get("unique", False),
                            "custom": f.get("custom", False)
                        }
                        for f in describe["fields"]
                    ],
                    "recordTypes": describe.get("recordTypeInfos", [])
                }
            except Exception as e:
                logger.warning(f"Failed to describe {obj_name}: {e}")
                continue

        return json.dumps({
            "success": True,
            "object_count": len(schemas),
            "schemas": schemas
        }, indent=2)

    except Exception as e:
        logger.exception("export_schema_to_json failed")
        return json.dumps({"success": False, "error": str(e)})
