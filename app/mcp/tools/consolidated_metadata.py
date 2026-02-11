"""
Consolidated metadata tools - reduces 48 tools to 6 manageable tools
Each tool is focused and not too complex for LLMs to handle

Created by Sameer
"""
import json
import logging
from typing import Optional, Dict, Any, List

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection
from app.utils.validators import validate_api_name, ValidationError
from app.mcp.tools.utils import format_error_response, format_success_response

# Import existing implementation functions to reuse logic
from app.mcp.tools import dynamic_tools

logger = logging.getLogger(__name__)

# Metadata type mappings
METADATA_TYPE_ALIASES = {
    "apex": "ApexClass",
    "apexclass": "ApexClass",
    "class": "ApexClass",
    "trigger": "ApexTrigger",
    "apextrigger": "ApexTrigger",
    "validation": "ValidationRule",
    "validationrule": "ValidationRule",
    "lwc": "LightningComponentBundle",
    "lightningwebcomponent": "LightningComponentBundle",
    "aura": "AuraDefinitionBundle",
    "auracomponent": "AuraDefinitionBundle",
    "object": "CustomObject",
    "customobject": "CustomObject",
    "field": "CustomField",
    "customfield": "CustomField",
    "flow": "Flow",
    "email": "EmailTemplate",
    "emailtemplate": "EmailTemplate",
    "permset": "PermissionSet",
    "permissionset": "PermissionSet",
    "static": "StaticResource",
    "staticresource": "StaticResource",
    "custommetadata": "CustomMetadataType",
    "custommetadatatype": "CustomMetadataType",
    "label": "CustomLabel",
    "customlabel": "CustomLabel",
    "recordtype": "RecordType",
    "quickaction": "QuickAction",
    "tab": "CustomTab",
    "customtab": "CustomTab"
}


def _normalize_metadata_type(metadata_type: str) -> str:
    """Normalize metadata type to standard format"""
    normalized = metadata_type.lower().replace(" ", "").replace("_", "")
    return METADATA_TYPE_ALIASES.get(normalized, metadata_type)


@register_tool
def deploy_metadata(
    metadata_type: str,
    name: str,
    content: str,
    operation: str = "upsert"
) -> str:
    """
    Deploy Salesforce metadata (create or update). Supports 16 metadata types.

    This is a unified tool that replaces 32 separate create/upsert tools.
    Keeps the simplicity while reducing tool count.

    Supported metadata types (case-insensitive):
    - ApexClass/apex/class: Apex classes
    - ApexTrigger/trigger: Apex triggers
    - ValidationRule/validation: Validation rules
    - LWC: Lightning Web Components
    - AuraComponent/aura: Aura components
    - CustomObject/object: Custom objects
    - CustomField/field: Custom fields
    - Flow: Flows
    - EmailTemplate/email: Email templates
    - PermissionSet/permset: Permission sets
    - StaticResource/static: Static resources
    - CustomMetadataType/custommetadata: Custom metadata types
    - CustomLabel/label: Custom labels
    - RecordType: Record types
    - QuickAction: Quick actions
    - CustomTab/tab: Custom tabs

    Args:
        metadata_type: Type of metadata (see supported types above)
        name: API name (e.g., "AccountService", "Account.Customer_Code__c")
        content: JSON string with metadata definition (varies by type)
        operation: "create" (fail if exists), "update" (fail if missing), "upsert" (default)

    Content format by type:
    - ApexClass: {"body": "public class...", "apiVersion": "59.0"}
    - ApexTrigger: {"body": "trigger...", "tableName": "Account", "apiVersion": "59.0"}
    - CustomField (Text): {"label": "Customer Code", "type": "Text", "length": 50}
    - CustomField (Picklist):
        Format 1: {"label": "Status", "type": "Picklist", "picklistValues": ["New", "In Progress", "Done"]}
        Format 2: {"label": "Status", "type": "Picklist", "valueSet": {"valueSetDefinition": {"value": [{"fullName": "New"}, {"fullName": "Done"}]}}}
    - CustomObject: {"label": "My Object", "pluralLabel": "My Objects"}
    - LWC: {"html": "<template>...", "js": "import...", "css": "..."}

    Returns:
        JSON response with deployment status

    Example:
        # Deploy Apex Class
        deploy_metadata(
            "ApexClass",
            "AccountService",
            '{"body": "public class AccountService {...}", "apiVersion": "59.0"}',
            "upsert"
        )

        # Deploy Custom Field
        deploy_metadata(
            "CustomField",
            "Account.Customer_Code__c",
            '{"label": "Customer Code", "type": "Text", "length": 50}',
            "create"
        )
    """
    try:
        # Normalize metadata type
        normalized_type = _normalize_metadata_type(metadata_type)

        # Parse content
        try:
            content_dict = json.loads(content)
        except json.JSONDecodeError as e:
            return format_error_response(
                Exception(f"Invalid JSON in content parameter: {str(e)}"),
                context="deploy_metadata"
            )

        # Route to appropriate handler based on metadata type
        if normalized_type in ["ApexClass", "apex", "class"]:
            if operation == "create":
                return dynamic_tools.create_apex_class(
                    class_name=name,
                    body=content_dict.get("body", ""),
                    api_version=content_dict.get("apiVersion", "59.0")
                )
            else:  # update or upsert
                return dynamic_tools.upsert_apex_class(
                    class_name=name,
                    body=content_dict.get("body", ""),
                    api_version=content_dict.get("apiVersion", "59.0")
                )

        elif normalized_type in ["ApexTrigger", "trigger"]:
            if operation == "create":
                return dynamic_tools.create_apex_trigger(
                    trigger_name=name,
                    body=content_dict.get("body", ""),
                    table_name=content_dict.get("tableName", content_dict.get("objectName", "")),
                    api_version=content_dict.get("apiVersion", "59.0")
                )
            else:
                return dynamic_tools.upsert_apex_trigger(
                    trigger_name=name,
                    body=content_dict.get("body", ""),
                    table_name=content_dict.get("tableName", content_dict.get("objectName", "")),
                    api_version=content_dict.get("apiVersion", "59.0")
                )

        elif normalized_type in ["ValidationRule", "validation"]:
            # ⚠️ CANNOT DEPLOY VALIDATION RULES VIA API
            object_name, rule_name = name.split(".", 1) if "." in name else (content_dict.get("objectName"), name)

            return json.dumps({
                "success": False,
                "error": "⚠️ MCP CANNOT deploy ValidationRules due to Salesforce API limitations",
                "validation_rule_definition": {
                    "Rule Name": rule_name,
                    "Object": object_name,
                    "Active": content_dict.get("active", True),
                    "Description": content_dict.get("description", ""),
                    "Error Condition Formula": content_dict.get("formula", content_dict.get("errorConditionFormula", "")),
                    "Error Message": content_dict.get("errorMessage", ""),
                    "Error Location": content_dict.get("errorDisplayField", "Top of Page")
                },
                "copy_paste_formula": {
                    "title": "📝 COPY THIS FORMULA",
                    "formula": content_dict.get("formula", content_dict.get("errorConditionFormula", ""))
                },
                "manual_deployment_required": {
                    "title": "📋 MANUAL DEPLOYMENT REQUIRED",
                    "warning": "This MCP server CANNOT deploy validation rules via API",
                    "steps": [
                        f"1. Open Salesforce Setup",
                        f"2. Navigate to: Object Manager → {object_name} → Validation Rules",
                        f"3. Click 'Edit' on: {rule_name}" if operation == "update" else f"3. Click 'New' button",
                        f"4. Copy the values from 'validation_rule_definition' above",
                        f"5. Paste into Salesforce UI fields",
                        f"6. Click 'Save'",
                        f"7. Test the validation rule"
                    ]
                },
                "why_this_fails": "ValidationRules cannot be modified via REST/Tooling API. Only Metadata API (ZIP file), SFDX CLI, or manual UI update work.",
                "alternatives": [
                    "Manual UI update (2 minutes, 100% reliable)",
                    "SFDX CLI: sf project deploy start -m 'ValidationRule:Object.RuleName'",
                    "Metadata API ZIP deployment"
                ]
            }, indent=2)

        elif normalized_type in ["LightningComponentBundle", "LWC", "lwc"]:
            if operation == "create":
                return dynamic_tools.create_lwc_component(
                    component_name=name,
                    html_content=content_dict.get("html", ""),
                    js_content=content_dict.get("js", ""),
                    css_content=content_dict.get("css", "")
                )
            else:
                return dynamic_tools.upsert_lwc_component(
                    component_name=name,
                    html_content=content_dict.get("html", ""),
                    js_content=content_dict.get("js", ""),
                    css_content=content_dict.get("css", "")
                )

        elif normalized_type in ["CustomObject", "object"]:
            return dynamic_tools.upsert_custom_object(
                object_name=name,
                label=content_dict.get("label", name),
                plural_label=content_dict.get("pluralLabel", name + "s"),
                description=content_dict.get("description", ""),
                sharing_model=content_dict.get("sharingModel", "ReadWrite")
            )

        elif normalized_type in ["CustomField", "field"]:
            # Extract object and field name
            if "." in name:
                object_name, field_name = name.rsplit(".", 1)
            else:
                object_name = content_dict.get("objectName")
                field_name = name

            # Build type_params string based on field type
            field_type = content_dict.get("type", "Text")
            type_params = ""
            if field_type in ["Text", "LongTextArea"]:
                length = content_dict.get("length", 255)
                type_params = f"length={length}"
            elif field_type in ["Number", "Currency", "Percent"]:
                precision = content_dict.get("precision", 18)
                scale = content_dict.get("scale", 0)
                type_params = f"precision={precision};scale={scale}"
            elif field_type == "Picklist":
                # Support multiple formats for picklist values
                picklist_values = []

                # Format 1: Simple list ["Value1", "Value2"]
                if "picklistValues" in content_dict:
                    picklist_values = content_dict["picklistValues"]

                # Format 2: Metadata API format with valueSet
                elif "valueSet" in content_dict:
                    value_set = content_dict["valueSet"]
                    if "valueSetDefinition" in value_set:
                        values_list = value_set["valueSetDefinition"].get("value", [])
                        # Extract fullName from each value object
                        picklist_values = [v.get("fullName", v.get("label", "")) for v in values_list if isinstance(v, dict)]

                # Format 3: Simple values list
                elif "values" in content_dict:
                    picklist_values = content_dict["values"]

                if picklist_values:
                    # Join with pipe (|) separator as expected by underlying function
                    type_params = f"values={'|'.join(picklist_values)}"

            elif field_type in ["Lookup", "MasterDetail"]:
                reference_to = content_dict.get("referenceTo", "")
                relationship_name = content_dict.get("relationshipName", "")
                relationship_label = content_dict.get("relationshipLabel", relationship_name)
                type_params = f"referenceTo={reference_to};relationshipName={relationship_name};relationshipLabel={relationship_label}"
                if field_type == "MasterDetail":
                    delete_constraint = content_dict.get("deleteConstraint", "Cascade")
                    type_params += f";deleteConstraint={delete_constraint}"

            return dynamic_tools.upsert_custom_field(
                object_name=object_name,
                field_api_name=field_name,
                label=content_dict.get("label", field_name),
                field_type=field_type,
                type_params=type_params,
                required=content_dict.get("required", False),
                description=content_dict.get("description", "")
            )

        elif normalized_type in ["Flow", "flow"]:
            if operation == "create":
                return dynamic_tools.create_flow(
                    flow_name=name,
                    label=content_dict.get("label", name),
                    description=content_dict.get("description", ""),
                    process_type=content_dict.get("processType", "AutoLaunchedFlow")
                )
            else:
                return dynamic_tools.upsert_flow(
                    flow_name=name,
                    label=content_dict.get("label", name),
                    description=content_dict.get("description", ""),
                    process_type=content_dict.get("processType", "AutoLaunchedFlow")
                )

        elif normalized_type in ["EmailTemplate", "email"]:
            if operation == "create":
                return dynamic_tools.create_email_template(
                    template_name=name,
                    name=content_dict.get("name", name),
                    subject=content_dict.get("subject", ""),
                    body=content_dict.get("body", ""),
                    folder_name=content_dict.get("folderName", "Unfiled Public Email Templates")
                )
            else:
                return dynamic_tools.upsert_email_template(
                    template_name=name,
                    name=content_dict.get("name", name),
                    subject=content_dict.get("subject", ""),
                    body=content_dict.get("body", ""),
                    folder_name=content_dict.get("folderName", "Unfiled Public Email Templates")
                )

        elif normalized_type in ["PermissionSet", "permset"]:
            if operation == "create":
                return dynamic_tools.create_permission_set(
                    permission_set_name=name,
                    label=content_dict.get("label", name),
                    description=content_dict.get("description", "")
                )
            else:
                return dynamic_tools.upsert_permission_set(
                    permission_set_name=name,
                    label=content_dict.get("label", name),
                    description=content_dict.get("description", "")
                )

        elif normalized_type in ["StaticResource", "static"]:
            if operation == "create":
                return dynamic_tools.create_static_resource(
                    resource_name=name,
                    content=content_dict.get("content", ""),
                    content_type=content_dict.get("contentType", "text/plain"),
                    description=content_dict.get("description", ""),
                    cache_control=content_dict.get("cacheControl", "Private")
                )
            else:
                return dynamic_tools.upsert_static_resource(
                    resource_name=name,
                    content=content_dict.get("content", ""),
                    content_type=content_dict.get("contentType", "text/plain"),
                    description=content_dict.get("description", ""),
                    cache_control=content_dict.get("cacheControl", "Private")
                )

        elif normalized_type in ["CustomMetadataType", "custommetadata"]:
            if operation == "create":
                return dynamic_tools.create_custom_metadata_type(
                    type_name=name,
                    label=content_dict.get("label", name),
                    plural_label=content_dict.get("pluralLabel", name + "s")
                )
            else:
                return dynamic_tools.upsert_custom_metadata_type(
                    type_name=name,
                    label=content_dict.get("label", name),
                    plural_label=content_dict.get("pluralLabel", name + "s")
                )

        elif normalized_type in ["AuraDefinitionBundle", "aura"]:
            if operation == "create":
                return dynamic_tools.create_aura_component(
                    component_name=name,
                    description=content_dict.get("description", "")
                )
            else:
                return dynamic_tools.upsert_aura_component(
                    component_name=name,
                    description=content_dict.get("description", "")
                )

        elif normalized_type in ["CustomLabel", "label"]:
            if operation == "create":
                return dynamic_tools.create_custom_label(
                    label_name=name,
                    value=content_dict.get("value", ""),
                    category=content_dict.get("category", ""),
                    language=content_dict.get("language", "en_US")
                )
            else:
                return dynamic_tools.upsert_custom_label(
                    label_name=name,
                    value=content_dict.get("value", ""),
                    category=content_dict.get("category", ""),
                    language=content_dict.get("language", "en_US")
                )

        elif normalized_type in ["RecordType", "recordtype"]:
            object_name, rt_name = name.split(".", 1) if "." in name else (content_dict.get("objectName"), name)
            if operation == "create":
                return dynamic_tools.create_record_type(
                    object_name=object_name,
                    record_type_name=rt_name,
                    label=content_dict.get("label", rt_name),
                    description=content_dict.get("description", "")
                )
            else:
                return dynamic_tools.upsert_record_type(
                    object_name=object_name,
                    record_type_name=rt_name,
                    label=content_dict.get("label", rt_name),
                    description=content_dict.get("description", "")
                )

        elif normalized_type in ["QuickAction", "quickaction"]:
            if operation == "create":
                return dynamic_tools.create_quick_action(
                    action_name=name,
                    label=content_dict.get("label", name),
                    action_type=content_dict.get("type", content_dict.get("actionType", "Create")),
                    target_object=content_dict.get("targetObject", ""),
                    description=content_dict.get("description", ""),
                    icon=content_dict.get("icon", "custom:custom1")
                )
            else:
                return dynamic_tools.upsert_quick_action(
                    action_name=name,
                    label=content_dict.get("label", name),
                    action_type=content_dict.get("type", content_dict.get("actionType", "Create")),
                    target_object=content_dict.get("targetObject", ""),
                    description=content_dict.get("description", "")
                )

        elif normalized_type in ["CustomTab", "tab"]:
            if operation == "create":
                return dynamic_tools.create_custom_tab(
                    tab_name=name,
                    label=content_dict.get("label", name),
                    tab_style=content_dict.get("tabStyle", content_dict.get("motif", "Custom1: Airplane")),
                    sobject=content_dict.get("customObject", content_dict.get("sobject", "")),
                    url=content_dict.get("url", ""),
                    description=content_dict.get("description", "")
                )
            else:
                return dynamic_tools.upsert_custom_tab(
                    tab_name=name,
                    label=content_dict.get("label", name),
                    tab_style=content_dict.get("tabStyle", content_dict.get("motif", "Custom1: Airplane")),
                    sobject=content_dict.get("customObject", content_dict.get("sobject", "")),
                    url=content_dict.get("url", ""),
                    description=content_dict.get("description", "")
                )
        else:
            return format_error_response(
                Exception(f"Unsupported metadata type: {metadata_type}"),
                context="deploy_metadata"
            )

    except Exception as e:
        logger.exception("deploy_metadata failed")
        return format_error_response(e, context="deploy_metadata")


@register_tool
def fetch_metadata(
    metadata_type: str,
    name: str,
    include_body: bool = True
) -> str:
    """
    Fetch Salesforce metadata by type and name. Supports 16 metadata types.

    This is a unified tool that replaces 16 separate fetch tools.

    Supported metadata types (case-insensitive):
    - ApexClass/apex/class: Apex classes
    - ApexTrigger/trigger: Apex triggers
    - ValidationRule/validation: Validation rules (use "Object.RuleName" format)
    - LWC: Lightning Web Components
    - AuraComponent/aura: Aura components
    - CustomObject/object: Custom objects
    - CustomField/field: Custom fields (use "Object.FieldName" format)
    - Flow: Flows
    - EmailTemplate/email: Email templates
    - PermissionSet/permset: Permission sets
    - StaticResource/static: Static resources
    - CustomMetadataType/custommetadata: Custom metadata types
    - CustomLabel/label: Custom labels
    - RecordType: Record types (use "Object.RecordTypeName" format)
    - QuickAction: Quick actions
    - CustomTab/tab: Custom tabs

    Args:
        metadata_type: Type of metadata (see supported types)
        name: API name (e.g., "AccountService", "Account.Customer_Code__c")
        include_body: Include full source code/body (for Apex/LWC)

    Returns:
        JSON response with metadata details

    Example:
        # Fetch Apex Class
        fetch_metadata("ApexClass", "AccountService")

        # Fetch Custom Field
        fetch_metadata("CustomField", "Account.Customer_Code__c")

        # Fetch without body (faster)
        fetch_metadata("ApexClass", "AccountService", include_body=False)
    """
    try:
        # Normalize metadata type
        normalized_type = _normalize_metadata_type(metadata_type)

        # Route to appropriate handler
        if normalized_type in ["ApexClass", "apex", "class"]:
            return dynamic_tools.fetch_apex_class(name)

        elif normalized_type in ["ApexTrigger", "trigger"]:
            return dynamic_tools.fetch_apex_trigger(name)

        elif normalized_type in ["ValidationRule", "validation"]:
            object_name, rule_name = name.split(".", 1) if "." in name else (None, name)
            if not object_name:
                return format_error_response(
                    Exception("ValidationRule name must be in format 'ObjectName.RuleName'"),
                    context="fetch_metadata"
                )
            return dynamic_tools.fetch_validation_rule(object_name, rule_name)

        elif normalized_type in ["LightningComponentBundle", "LWC", "lwc"]:
            return dynamic_tools.fetch_lwc_component(name)

        elif normalized_type in ["CustomObject", "object"]:
            return dynamic_tools.fetch_object_metadata(name)

        elif normalized_type in ["CustomField", "field"]:
            object_name, field_name = name.split(".", 1) if "." in name else (None, name)
            if not object_name:
                return format_error_response(
                    Exception("CustomField name must be in format 'ObjectName.FieldName'"),
                    context="fetch_metadata"
                )
            return dynamic_tools.fetch_custom_field(object_name, field_name)

        elif normalized_type in ["Flow", "flow"]:
            return dynamic_tools.fetch_flow(name)

        elif normalized_type in ["EmailTemplate", "email"]:
            return dynamic_tools.fetch_email_template(name)

        elif normalized_type in ["PermissionSet", "permset"]:
            return dynamic_tools.fetch_permission_set(name)

        elif normalized_type in ["StaticResource", "static"]:
            return dynamic_tools.fetch_static_resource(name)

        elif normalized_type in ["CustomMetadataType", "custommetadata"]:
            return dynamic_tools.fetch_custom_metadata_type(name)

        elif normalized_type in ["AuraDefinitionBundle", "aura"]:
            return dynamic_tools.fetch_aura_component(name)

        elif normalized_type in ["CustomLabel", "label"]:
            return dynamic_tools.fetch_custom_label(name)

        elif normalized_type in ["RecordType", "recordtype"]:
            object_name, rt_name = name.split(".", 1) if "." in name else (None, name)
            if not object_name:
                return format_error_response(
                    Exception("RecordType name must be in format 'ObjectName.RecordTypeName'"),
                    context="fetch_metadata"
                )
            return dynamic_tools.fetch_record_type(object_name, rt_name)

        elif normalized_type in ["QuickAction", "quickaction"]:
            return dynamic_tools.fetch_quick_action(name)

        elif normalized_type in ["CustomTab", "tab"]:
            return dynamic_tools.fetch_custom_tab(name)

        else:
            return format_error_response(
                Exception(f"Unsupported metadata type: {metadata_type}"),
                context="fetch_metadata"
            )

    except Exception as e:
        logger.exception("fetch_metadata failed")
        return format_error_response(e, context="fetch_metadata")


@register_tool
def list_metadata(
    metadata_type: str,
    name_pattern: str = "*",
    limit: int = 100
) -> str:
    """
    List metadata of a specific type with optional filtering.

    This tool helps discover what metadata exists in your org.

    Supported metadata types (case-insensitive):
    - ApexClass/apex: List Apex classes
    - ApexTrigger/trigger: List Apex triggers
    - CustomObject/object: List custom objects
    - CustomField: List custom fields (requires name_pattern like "Account.*")
    - Flow: List flows
    - PermissionSet/permset: List permission sets
    - StaticResource/static: List static resources
    - And more...

    Args:
        metadata_type: Type of metadata to list
        name_pattern: Name filter (supports wildcards: "*", "?")
        limit: Maximum results (default 100)

    Returns:
        JSON list of metadata matching the criteria

    Example:
        # List all Apex classes
        list_metadata("ApexClass")

        # List Apex classes matching pattern
        list_metadata("ApexClass", "*Service*", 50)

        # List Account custom fields
        list_metadata("CustomField", "Account.*__c")
    """
    try:
        normalized_type = _normalize_metadata_type(metadata_type)
        sf = get_salesforce_connection()

        # Handle different metadata types
        if normalized_type in ["ApexClass", "apex", "class"]:
            query = f"SELECT Id, Name, ApiVersion, Status, LengthWithoutComments FROM ApexClass LIMIT {limit}"
            if name_pattern != "*":
                pattern = name_pattern.replace("*", "%").replace("?", "_")
                query = f"SELECT Id, Name, ApiVersion, Status, LengthWithoutComments FROM ApexClass WHERE Name LIKE '{pattern}' LIMIT {limit}"
            result = sf.query(query)

        elif normalized_type in ["ApexTrigger", "trigger"]:
            query = f"SELECT Id, Name, TableEnumOrId, Status, ApiVersion FROM ApexTrigger LIMIT {limit}"
            if name_pattern != "*":
                pattern = name_pattern.replace("*", "%").replace("?", "_")
                query = f"SELECT Id, Name, TableEnumOrId, Status, ApiVersion FROM ApexTrigger WHERE Name LIKE '{pattern}' LIMIT {limit}"
            result = sf.query(query)

        elif normalized_type in ["CustomObject", "object"]:
            query = f"SELECT QualifiedApiName, Label, PluralLabel FROM EntityDefinition WHERE IsCustomizable = true LIMIT {limit}"
            if name_pattern != "*":
                pattern = name_pattern.replace("*", "%").replace("?", "_")
                query = f"SELECT QualifiedApiName, Label, PluralLabel FROM EntityDefinition WHERE IsCustomizable = true AND QualifiedApiName LIKE '{pattern}' LIMIT {limit}"
            result = sf.query(query)

        elif normalized_type in ["Flow", "flow"]:
            query = f"SELECT Id, ApiName, Label, ProcessType, Status FROM FlowDefinitionView LIMIT {limit}"
            if name_pattern != "*":
                pattern = name_pattern.replace("*", "%").replace("?", "_")
                query = f"SELECT Id, ApiName, Label, ProcessType, Status FROM FlowDefinitionView WHERE ApiName LIKE '{pattern}' LIMIT {limit}"
            result = sf.query(query)

        elif normalized_type in ["PermissionSet", "permset"]:
            query = f"SELECT Id, Name, Label, Description, IsOwnedByProfile FROM PermissionSet WHERE IsOwnedByProfile = false LIMIT {limit}"
            if name_pattern != "*":
                pattern = name_pattern.replace("*", "%").replace("?", "_")
                query = f"SELECT Id, Name, Label, Description FROM PermissionSet WHERE IsOwnedByProfile = false AND Name LIKE '{pattern}' LIMIT {limit}"
            result = sf.query(query)

        elif normalized_type in ["StaticResource", "static"]:
            query = f"SELECT Id, Name, ContentType, BodyLength FROM StaticResource LIMIT {limit}"
            if name_pattern != "*":
                pattern = name_pattern.replace("*", "%").replace("?", "_")
                query = f"SELECT Id, Name, ContentType, BodyLength FROM StaticResource WHERE Name LIKE '{pattern}' LIMIT {limit}"
            result = sf.query(query)

        else:
            return format_error_response(
                Exception(f"List operation not yet supported for metadata type: {metadata_type}"),
                context="list_metadata"
            )

        return format_success_response({
            "metadata_type": normalized_type,
            "records": result["records"],
            "total_size": result["totalSize"],
            "pattern": name_pattern,
            "limit": limit
        })

    except Exception as e:
        logger.exception("list_metadata failed")
        return format_error_response(e, context="list_metadata")
