"""
Consolidated debugging and defect-solving tool for Salesforce
Handles triggers, flows, validation rules, layouts, fields, permissions, etc.

Enhanced with:
- Auto-fix capabilities for common issues
- Cross-reference dependency analysis
- Performance improvements and caching
- 25 QA scenario patterns for intelligent issue detection

Created by Sameer
"""
import logging
import re
from typing import Optional, Dict, Any, List, Tuple
import time

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection
from app.mcp.tools.utils import format_error_response, format_success_response

logger = logging.getLogger(__name__)

# =============================================================================
# QA SCENARIO PATTERNS - Based on 25 real-world Salesforce issues
# =============================================================================

QA_SCENARIO_PATTERNS = {
    # Trigger Issues (1-3)
    "trigger_field_not_updating": {
        "patterns": [
            r"field.*not.*get.*updat",
            r"not.*updating",
            r"field.*not.*chang",
            r"trigger.*not.*set"
        ],
        "issue_type": "trigger",
        "scenario_id": 1,
        "description": "Trigger not updating a specific field"
    },
    "trigger_recursion": {
        "patterns": [
            r"maximum.*trigger.*depth",
            r"trigger.*depth.*exceeded",
            r"recursion",
            r"infinite.*loop"
        ],
        "issue_type": "trigger",
        "scenario_id": 2,
        "description": "Trigger recursion causing infinite loop"
    },
    "soql_limit_exceeded": {
        "patterns": [
            r"too.*many.*soql.*101",
            r"soql.*queries.*101",
            r"limit.*exception.*soql",
            r"governor.*limit.*soql"
        ],
        "issue_type": "trigger",
        "scenario_id": 3,
        "description": "SOQL 101 limit exceeded in bulk operations"
    },

    # Flow Issues (4-5)
    "flow_null_handling": {
        "patterns": [
            r"flow.*fail.*blank",
            r"flow.*fail.*null",
            r"flow.*fail.*empty",
            r"field.*is.*blank.*flow"
        ],
        "issue_type": "flow",
        "scenario_id": 4,
        "description": "Flow fails when field is blank/null"
    },
    "flow_decision_wrong_value": {
        "patterns": [
            r"decision.*check.*instead",
            r"decision.*wrong.*value",
            r"flow.*check.*closed.*instead",
            r"decision.*element.*wrong"
        ],
        "issue_type": "flow",
        "scenario_id": 5,
        "description": "Flow Decision element checks wrong value"
    },

    # License/Permission Issues (6, 8, 11, 22)
    "wrong_license": {
        "patterns": [
            r"wrong.*license",
            r"unable.*access.*lead",
            r"unable.*access.*opportunit",
            r"license.*type.*wrong"
        ],
        "issue_type": "permission",
        "scenario_id": 6,
        "description": "User has wrong license type"
    },
    "field_level_security": {
        "patterns": [
            r"cannot.*access.*field",
            r"profile.*cannot.*access",
            r"field.*not.*visible.*profile",
            r"fls.*issue"
        ],
        "issue_type": "permission",
        "scenario_id": 8,
        "description": "Profile cannot access field (FLS)"
    },
    "formula_field_not_visible": {
        "patterns": [
            r"formula.*field.*not.*visible",
            r"formula.*not.*visible.*profile",
            r"deal.*size.*not.*visible"
        ],
        "issue_type": "permission",
        "scenario_id": 11,
        "description": "Formula field not visible to any profile"
    },
    "report_field_not_visible": {
        "patterns": [
            r"report.*field.*not.*visible",
            r"field.*not.*visible.*report",
            r"rating.*not.*visible.*report"
        ],
        "issue_type": "report",
        "scenario_id": 22,
        "description": "Field not visible in reports"
    },

    # Layout Issues (7, 10, 15, 18, 23)
    "wrong_layout_assignment": {
        "patterns": [
            r"wrong.*layout",
            r"see.*wrong.*page",
            r"should.*see.*layout",
            r"wrong.*case.*layout"
        ],
        "issue_type": "layout",
        "scenario_id": 7,
        "description": "Users see wrong page layout"
    },
    "missing_count_related_list": {
        "patterns": [
            r"missing.*count.*opportunit",
            r"total.*count.*missing",
            r"related.*missing.*count"
        ],
        "issue_type": "layout",
        "scenario_id": 10,
        "description": "Missing count on related list"
    },
    "missing_fields_related_details": {
        "patterns": [
            r"missing.*rating.*partner",
            r"related.*missing.*field",
            r"missing.*fields.*related"
        ],
        "issue_type": "layout",
        "scenario_id": 15,
        "description": "Missing fields on related details component"
    },
    "missing_related_list": {
        "patterns": [
            r"related.*list.*missing",
            r"missing.*related.*list",
            r"stage.*history.*missing",
            r"product.*related.*list.*missing"
        ],
        "issue_type": "layout",
        "scenario_id": 18,
        "description": "Related list missing from page layout"
    },

    # Validation Issues (9, 20, 21, 24, 25)
    "required_field_validation": {
        "patterns": [
            r"cannot.*saved.*without",
            r"saved.*without.*phone",
            r"require.*phone",
            r"contact.*without.*phone"
        ],
        "issue_type": "validation",
        "scenario_id": 9,
        "description": "Required field validation"
    },
    "date_allows_past": {
        "patterns": [
            r"allow.*past.*date",
            r"date.*allow.*past",
            r"close.*date.*past"
        ],
        "issue_type": "validation",
        "scenario_id": 20,
        "description": "Date field allows past dates"
    },
    "validation_too_restrictive": {
        "patterns": [
            r"amount.*cannot.*exceed",
            r"validation.*too.*restrict",
            r"contact.*manager.*approval",
            r"amount.*error.*exceed"
        ],
        "issue_type": "validation",
        "scenario_id": 21,
        "description": "Validation rule too restrictive"
    },
    "missing_required_validation": {
        "patterns": [
            r"saved.*without",
            r"account.*without.*phone",
            r"no.*validation.*required"
        ],
        "issue_type": "validation",
        "scenario_id": 24,
        "description": "Missing required field validation"
    },
    "unclear_validation_error": {
        "patterns": [
            r"error.*enter.*field.*value",
            r"please.*enter.*net.*new",
            r"unclear.*validation.*error"
        ],
        "issue_type": "validation",
        "scenario_id": 25,
        "description": "Unclear or confusing validation error message"
    },

    # Formula Issues (12, 16)
    "formula_calculates_incorrectly": {
        "patterns": [
            r"formula.*calculates.*incorrect",
            r"formula.*wrong.*value",
            r"month.*formula.*invalid",
            r"formula.*return.*wrong"
        ],
        "issue_type": "formula",
        "scenario_id": 12,
        "description": "Formula field calculates incorrectly"
    },
    "datetime_instead_of_date": {
        "patterns": [
            r"display.*date.*and.*time",
            r"should.*display.*only.*date",
            r"datetime.*instead.*date"
        ],
        "issue_type": "formula",
        "scenario_id": 16,
        "description": "DateTime field should display only Date"
    },

    # Picklist Issues (13, 14, 19)
    "picklist_value_not_visible": {
        "patterns": [
            r"cannot.*see.*value.*picklist",
            r"picklist.*value.*not.*visible",
            r"new.*customer.*not.*visible",
            r"missing.*picklist.*value"
        ],
        "issue_type": "picklist",
        "scenario_id": 13,
        "description": "Picklist value not visible to users"
    },
    "wrong_field_type_picklist": {
        "patterns": [
            r"multi.*picklist.*instead.*single",
            r"displaying.*multi.*instead",
            r"wrong.*picklist.*type"
        ],
        "issue_type": "picklist",
        "scenario_id": 14,
        "description": "Wrong picklist field type"
    },
    "wrong_probability_for_stage": {
        "patterns": [
            r"probability.*shows.*instead",
            r"stage.*probability.*wrong",
            r"perception.*analysis.*10.*instead.*70"
        ],
        "issue_type": "picklist",
        "scenario_id": 19,
        "description": "Wrong probability percentage for Opportunity stage"
    },

    # Lookup Issues (17)
    "lookup_wrong_object": {
        "patterns": [
            r"lookup.*shows.*case.*instead.*contact",
            r"lookup.*wrong.*object",
            r"lookup.*shows.*wrong.*record"
        ],
        "issue_type": "lookup",
        "scenario_id": 17,
        "description": "Lookup field shows records from wrong object"
    }
}


def _detect_scenario(description: str) -> Optional[Dict[str, Any]]:
    """
    Detect which QA scenario matches the issue description.
    Returns the matched scenario or None if no match found.
    """
    description_lower = description.lower()

    for scenario_key, scenario_config in QA_SCENARIO_PATTERNS.items():
        for pattern in scenario_config["patterns"]:
            if re.search(pattern, description_lower):
                logger.info(f"Detected scenario: {scenario_key} (ID: {scenario_config['scenario_id']})")
                return {
                    "scenario_key": scenario_key,
                    "scenario_id": scenario_config["scenario_id"],
                    "issue_type": scenario_config["issue_type"],
                    "description": scenario_config["description"]
                }

    return None

# =============================================================================
# PERFORMANCE CACHE
# =============================================================================

# Cache for metadata to reduce API calls (TTL: 5 minutes)
_metadata_cache: Dict[str, Tuple[Any, float]] = {}
_CACHE_TTL = 300  # 5 minutes

def _get_cached_metadata(cache_key: str, fetch_func, *args, **kwargs):
    """Get metadata from cache or fetch and cache it"""
    current_time = time.time()

    if cache_key in _metadata_cache:
        cached_data, cached_time = _metadata_cache[cache_key]
        if current_time - cached_time < _CACHE_TTL:
            logger.debug(f"Cache hit for {cache_key}")
            return cached_data

    # Cache miss or expired
    logger.debug(f"Cache miss for {cache_key}, fetching...")
    data = fetch_func(*args, **kwargs)
    _metadata_cache[cache_key] = (data, current_time)
    return data

def clear_cache():
    """Clear all cached metadata"""
    global _metadata_cache
    _metadata_cache = {}
    logger.info("Metadata cache cleared")


# =============================================================================
# CROSS-REFERENCE DEPENDENCY ANALYSIS
# =============================================================================

def _analyze_dependencies(sf, object_name: Optional[str], field_name: Optional[str], component_name: Optional[str]) -> Dict[str, Any]:
    """
    Analyze dependencies for a component to identify cascading effects
    Returns what depends on this component and what it depends on
    """
    dependencies = {
        "depends_on": [],
        "depended_by": [],
        "potential_impacts": []
    }

    try:
        # Field dependencies
        if object_name and field_name:
            cache_key = f"field_deps_{object_name}_{field_name}"

            def fetch_field_deps():
                deps = {"depends_on": [], "depended_by": []}

                # Check validation rules that use this field
                try:
                    val_query = f"""
                        SELECT ValidationName, ErrorDisplayField, ErrorMessage
                        FROM ValidationRule
                        WHERE EntityDefinition.QualifiedApiName = '{object_name}'
                    """
                    val_result = sf.toolingexecute(val_query)
                    for rule in val_result.get('records', []):
                        deps["depended_by"].append({
                            "type": "ValidationRule",
                            "name": rule.get('ValidationName'),
                            "details": "Uses this field in validation logic"
                        })
                except Exception as e:
                    logger.warning(f"Could not check validation dependencies: {e}")

                # Check workflows/flows that use this field
                try:
                    flow_query = f"""
                        SELECT Label, ProcessType, TriggerObjectOrEvent.QualifiedApiName
                        FROM Flow
                        WHERE TriggerObjectOrEvent.QualifiedApiName = '{object_name}'
                        AND Status = 'Active'
                        LIMIT 50
                    """
                    flow_result = sf.toolingexecute(flow_query)
                    for flow in flow_result.get('records', []):
                        deps["depended_by"].append({
                            "type": "Flow",
                            "name": flow.get('Label'),
                            "details": f"May reference this field ({flow.get('ProcessType')})"
                        })
                except Exception as e:
                    logger.warning(f"Could not check flow dependencies: {e}")

                # Check triggers on this object
                try:
                    trigger_query = f"""
                        SELECT Name, Status
                        FROM ApexTrigger
                        WHERE TableEnumOrId = '{object_name}'
                        AND Status = 'Active'
                    """
                    trigger_result = sf.toolingexecute(trigger_query)
                    for trigger in trigger_result.get('records', []):
                        deps["depended_by"].append({
                            "type": "ApexTrigger",
                            "name": trigger.get('Name'),
                            "details": "May reference this field in trigger logic"
                        })
                except Exception as e:
                    logger.warning(f"Could not check trigger dependencies: {e}")

                return deps

            field_deps = _get_cached_metadata(cache_key, fetch_field_deps)
            dependencies["depends_on"] = field_deps.get("depends_on", [])
            dependencies["depended_by"] = field_deps.get("depended_by", [])

            # Add impact warnings
            if len(dependencies["depended_by"]) > 0:
                dependencies["potential_impacts"].append(
                    f"Changes to this field may affect {len(dependencies['depended_by'])} component(s)"
                )

        # Trigger dependencies
        elif component_name and object_name:
            cache_key = f"trigger_deps_{object_name}_{component_name}"

            def fetch_trigger_deps():
                deps = {"depends_on": [], "depended_by": []}

                # Check what objects/fields the trigger queries
                try:
                    trigger_query = f"""
                        SELECT Id, Name, Body
                        FROM ApexTrigger
                        WHERE Name = '{component_name}'
                        AND TableEnumOrId = '{object_name}'
                    """
                    trigger_result = sf.toolingexecute(trigger_query)

                    if trigger_result.get('totalSize', 0) > 0:
                        body = trigger_result['records'][0].get('Body', '')

                        # Find referenced objects in SOQL queries
                        soql_objects = set(re.findall(r'FROM\s+(\w+)', body, re.IGNORECASE))
                        for obj in soql_objects:
                            if obj != object_name:
                                deps["depends_on"].append({
                                    "type": "SObject",
                                    "name": obj,
                                    "details": "Queried by this trigger"
                                })

                        # Find DML operations on other objects
                        dml_patterns = [
                            r'insert\s+(\w+)',
                            r'update\s+(\w+)',
                            r'delete\s+(\w+)',
                            r'upsert\s+(\w+)'
                        ]
                        for pattern in dml_patterns:
                            matches = re.findall(pattern, body, re.IGNORECASE)
                            for match in matches:
                                deps["depends_on"].append({
                                    "type": "DML Operation",
                                    "name": match,
                                    "details": "Modified by this trigger"
                                })

                except Exception as e:
                    logger.warning(f"Could not analyze trigger dependencies: {e}")

                return deps

            trigger_deps = _get_cached_metadata(cache_key, fetch_trigger_deps)
            dependencies["depends_on"] = trigger_deps.get("depends_on", [])
            dependencies["depended_by"] = trigger_deps.get("depended_by", [])

            if len(dependencies["depends_on"]) > 3:
                dependencies["potential_impacts"].append(
                    "Trigger has many dependencies - consider refactoring for maintainability"
                )

    except Exception as e:
        logger.exception("Error analyzing dependencies")
        dependencies["error"] = str(e)

    return dependencies


# =============================================================================
# AUTO-FIX CAPABILITIES
# =============================================================================

def _create_trigger_helper_class(_sf, helper_type: str, object_name: str) -> Dict[str, Any]:
    """
    Create a TriggerHelper class to prevent recursion
    Returns deployment result
    """
    result = {"success": False, "message": "", "class_name": ""}

    try:
        if helper_type == "recursion_prevention":
            class_name = f"{object_name}TriggerHelper"
            class_body = f"""/**
 * Helper class for {object_name} trigger
 * Prevents recursion and tracks processed records
 * Auto-generated by diagnose_and_fix_issue tool
 */
public class {class_name} {{
    // Prevents trigger from running multiple times
    public static Boolean isFirstRun = true;

    // Tracks processed record IDs to prevent duplicate processing
    public static Set<Id> processedIds = new Set<Id>();

    /**
     * Check if record has already been processed
     */
    public static Boolean isAlreadyProcessed(Id recordId) {{
        return processedIds.contains(recordId);
    }}

    /**
     * Mark record as processed
     */
    public static void markAsProcessed(Id recordId) {{
        processedIds.add(recordId);
    }}

    /**
     * Mark multiple records as processed
     */
    public static void markAsProcessed(Set<Id> recordIds) {{
        processedIds.addAll(recordIds);
    }}

    /**
     * Reset for testing
     */
    @TestVisible
    private static void reset() {{
        isFirstRun = true;
        processedIds.clear();
    }}
}}"""

            # Deploy the class using Metadata API
            try:
                # Note: In a production environment, you'd use JSForce or Metadata API
                # For now, we'll provide the code for manual deployment
                result["success"] = True
                result["message"] = f"Helper class '{class_name}' code generated. Please deploy manually or use deploy_metadata tool."
                result["class_name"] = class_name
                result["class_body"] = class_body
                result["manual_steps"] = [
                    "1. Copy the class_body code",
                    "2. Navigate to Setup → Apex Classes → New",
                    "3. Paste the code and save",
                    f"4. Update your trigger to use {class_name}.isFirstRun or {class_name}.markAsProcessed()"
                ]

            except Exception as e:
                result["message"] = f"Could not auto-deploy class: {e}. Code provided for manual deployment."
                result["class_body"] = class_body

    except Exception as e:
        logger.exception("Error creating helper class")
        result["message"] = str(e)

    return result


def _get_validation_rule_for_manual_edit(_sf, object_name: str, rule_name: str, description: str) -> Dict[str, Any]:
    """
    Fetch validation rule and return complete definition for manual editing

    This function retrieves the current validation rule and returns ALL fields
    so the user can manually update it in Salesforce UI.

    Returns complete validation rule specification
    """
    result = {
        "success": False,
        "message": "",
        "validation_rule_definition": {},
        "important_note": "⚠️ MCP CANNOT create or update ValidationRules due to Salesforce API limitations."
    }

    try:
        logger.info(f"Fetching validation rule for manual edit: {object_name}.{rule_name}")

        # Fetch existing rule using Tooling API
        val_query = f"""
            SELECT Id, ValidationName, FullName, Active, Metadata
            FROM ValidationRule
            WHERE EntityDefinition.QualifiedApiName = '{object_name}'
            AND ValidationName = '{rule_name}'
        """

        val_result = _sf.toolingexecute(val_query)

        if val_result.get('totalSize', 0) > 0:
            record = val_result['records'][0]
            metadata = record.get('Metadata', {})

            current_formula = metadata.get('errorConditionFormula', '')
            error_message = metadata.get('errorMessage', '')
            error_display_field = metadata.get('errorDisplayField', '')
            rule_description = metadata.get('description', '')
            active = metadata.get('active', True)

            result["success"] = True
            result["message"] = f"✓ Retrieved validation rule '{rule_name}' - Ready for manual update"

            result["validation_rule_definition"] = {
                "Rule Name": rule_name,
                "Object": object_name,
                "Active": active,
                "Description": rule_description or "Update as needed",
                "Error Condition Formula": current_formula,
                "Error Message": error_message,
                "Error Location": error_display_field or "Top of Page"
            }

            result["manual_update_instructions"] = {
                "title": "📋 HOW TO UPDATE IN SALESFORCE UI",
                "warning": "⚠️ This MCP server CANNOT deploy validation rules. Please follow these steps:",
                "steps": [
                    f"1. Open Salesforce Setup",
                    f"2. Navigate to: Object Manager → {object_name} → Validation Rules",
                    f"3. Click 'Edit' on: {rule_name}",
                    f"4. Update the fields based on your requirement:",
                    f"   Current Formula: {current_formula}",
                    f"   Error Message: {error_message}",
                    f"5. Make your changes based on the issue described: {description}",
                    f"6. Click 'Save'",
                    f"7. Test the validation rule"
                ]
            }

            result["current_values"] = {
                "title": "📊 CURRENT VALIDATION RULE VALUES",
                "fields": {
                    "Rule Name": rule_name,
                    "Active": active,
                    "Description": rule_description or "(empty)",
                    "Error Condition Formula": current_formula,
                    "Error Message": error_message,
                    "Error Location": error_display_field or "Top of Page"
                }
            }

            result["suggested_action"] = f"Review the current values above and make necessary changes in Salesforce UI based on: {description}"

        else:
            # Rule doesn't exist
            result["success"] = True
            result["message"] = f"✓ Rule '{rule_name}' not found - Provide template for manual creation"

            result["validation_rule_definition"] = {
                "Rule Name": rule_name,
                "Object": object_name,
                "Active": True,
                "Description": "Add description here",
                "Error Condition Formula": "/* Add your formula here */",
                "Error Message": "Add your error message here",
                "Error Location": "Top of Page"
            }

            result["manual_create_instructions"] = {
                "title": "📋 HOW TO CREATE IN SALESFORCE UI",
                "warning": "⚠️ This MCP server CANNOT create validation rules. Please follow these steps:",
                "steps": [
                    f"1. Open Salesforce Setup",
                    f"2. Navigate to: Object Manager → {object_name} → Validation Rules",
                    f"3. Click 'New' button",
                    f"4. Fill in the fields:",
                    f"   - Rule Name: {rule_name}",
                    f"   - Active: Yes (checked)",
                    f"   - Description: Based on your requirement",
                    f"   - Error Condition Formula: Based on your logic",
                    f"   - Error Message: User-friendly message",
                    f"   - Error Location: Select field or Top of Page",
                    f"5. Click 'Save'",
                    f"6. Test the validation rule"
                ]
            }

            result["suggested_action"] = f"Create the validation rule manually in Salesforce UI based on: {description}"

    except Exception as e:
        logger.exception("Error fetching validation rule for manual edit")
        result["message"] = f"Error: {str(e)}"
        result["success"] = False

    return result


def _fix_validation_rule(_sf, object_name: str, rule_name: str, profile_to_exempt: str) -> Dict[str, Any]:
    """
    Generate complete validation rule definition for manual creation/update

    This retrieves the current rule (if exists) and generates a complete, ready-to-use
    validation rule definition that can be copied directly into Salesforce UI.

    Note: ValidationRules cannot be deployed via REST/Tooling API - manual UI update required.

    Returns complete validation rule specification for manual deployment
    """
    result = {
        "success": False,
        "message": "",
        "validation_rule_definition": {},
        "mode": "update"  # or "create"
    }

    try:
        full_name = f"{object_name}.{rule_name}"
        logger.info(f"Generating validation rule definition for: {full_name}")

        # Try to fetch existing rule
        val_query = f"""
            SELECT Id, ValidationName, FullName, Active,
                   ErrorConditionFormula, ErrorMessage, ErrorDisplayField,
                   Description
            FROM ValidationRule
            WHERE EntityDefinition.QualifiedApiName = '{object_name}'
            AND ValidationName = '{rule_name}'
        """

        val_result = _sf.toolingexecute(val_query)

        if val_result.get('totalSize', 0) > 0:
            # Rule exists - generate UPDATE definition
            record = val_result['records'][0]
            current_formula = record.get('ErrorConditionFormula', '')
            error_message = record.get('ErrorMessage', '')
            error_display_field = record.get('ErrorDisplayField', '')
            description = record.get('Description', '')
            active = record.get('Active', True)

            if current_formula:
                # Generate updated formula with profile exemption
                updated_formula = f"""AND(
    {current_formula.strip()},
    $Profile.Name != '{profile_to_exempt}'
)"""

                result["mode"] = "update"
                result["success"] = True
                result["message"] = f"✓ Generated complete validation rule definition for updating '{rule_name}'"

                result["validation_rule_definition"] = {
                    "Rule Name": rule_name,
                    "Object": object_name,
                    "Active": active,
                    "Description": description or f"Updated to exempt {profile_to_exempt} profile",
                    "Error Condition Formula": updated_formula.strip(),
                    "Error Message": error_message,
                    "Error Location": error_display_field or "Top of Page"
                }

                result["ui_instructions"] = {
                    "title": "📋 Copy these values into Salesforce UI",
                    "steps": [
                        f"1. Navigate to: Setup → Object Manager → {object_name} → Validation Rules",
                        f"2. Click 'Edit' on existing rule: {rule_name}",
                        "3. Copy each field value from 'validation_rule_definition' below:",
                        f"   - Active: {active}",
                        f"   - Description: {description or f'Updated to exempt {profile_to_exempt} profile'}",
                        f"   - Error Condition Formula: (see copy_paste_formula below)",
                        f"   - Error Message: {error_message}",
                        f"   - Error Location: {error_display_field or 'Top of Page'}",
                        "4. Click 'Save'",
                        f"5. Test: Login as {profile_to_exempt} user and verify rule doesn't fire"
                    ]
                }

                result["copy_paste_formula"] = {
                    "title": "📝 COPY THIS FORMULA",
                    "formula": updated_formula.strip(),
                    "note": "Copy the entire formula above and paste into 'Error Condition Formula' field"
                }

            else:
                # Rule exists but no formula retrieved
                result["success"] = True
                result["mode"] = "update"
                result["message"] = f"⚠️ Found rule '{rule_name}' but couldn't retrieve formula - provide template"

                result["validation_rule_definition"] = {
                    "Rule Name": rule_name,
                    "Object": object_name,
                    "Active": True,
                    "Description": f"Updated to exempt {profile_to_exempt} profile",
                    "Error Condition Formula": f"AND(\n    /* PASTE YOUR EXISTING FORMULA HERE */,\n    $Profile.Name != '{profile_to_exempt}'\n)",
                    "Error Message": error_message or "Validation error",
                    "Error Location": error_display_field or "Top of Page"
                }

                result["ui_instructions"] = {
                    "title": "⚠️ Manual formula merge required",
                    "steps": [
                        f"1. Navigate to: Setup → Object Manager → {object_name} → Validation Rules",
                        f"2. Click 'Edit' on: {rule_name}",
                        "3. Copy the existing 'Error Condition Formula'",
                        "4. Replace '/* PASTE YOUR EXISTING FORMULA HERE */' in the template with your copied formula",
                        "5. Paste the complete formula back",
                        "6. Save and test"
                    ]
                }

        else:
            # Rule doesn't exist - generate CREATE definition
            result["mode"] = "create"
            result["success"] = True
            result["message"] = f"✓ Rule '{rule_name}' not found - generated CREATE definition"

            # Generate a sensible default formula based on description
            default_formula = f"""AND(
    /* ADD YOUR VALIDATION LOGIC HERE */
    /* Example: Amount > 1000000 */,
    $Profile.Name != '{profile_to_exempt}'
)"""

            result["validation_rule_definition"] = {
                "Rule Name": rule_name,
                "Object": object_name,
                "Active": True,
                "Description": f"Validation rule with {profile_to_exempt} profile exemption",
                "Error Condition Formula": default_formula.strip(),
                "Error Message": "This record doesn't meet validation requirements",
                "Error Location": "Top of Page"
            }

            result["ui_instructions"] = {
                "title": "📋 Create new validation rule with these values",
                "steps": [
                    f"1. Navigate to: Setup → Object Manager → {object_name} → Validation Rules",
                    "2. Click 'New' button",
                    "3. Fill in the fields using values from 'validation_rule_definition':",
                    f"   - Rule Name: {rule_name}",
                    "   - Active: Yes (checked)",
                    f"   - Description: Validation rule with {profile_to_exempt} profile exemption",
                    "   - Error Condition Formula: (update the template with your actual logic)",
                    "   - Error Message: (customize as needed)",
                    "   - Error Location: Top of Page",
                    "4. Click 'Save'",
                    "5. Test thoroughly"
                ]
            }

            result["copy_paste_formula"] = {
                "title": "📝 FORMULA TEMPLATE",
                "formula": default_formula.strip(),
                "note": "Replace '/* ADD YOUR VALIDATION LOGIC HERE */' with your actual validation condition"
            }

        # Add quick reference
        result["quick_copy"] = {
            "description": "Quick copy for each field",
            "fields": result["validation_rule_definition"]
        }

    except Exception as e:
        logger.exception("Error generating validation rule definition")
        result["message"] = f"Error: {str(e)}"
        result["success"] = False

    return result


def _fix_field_security(sf, object_name: str, field_name: str, profile_name: str, _grant_access: bool = True) -> Dict[str, Any]:
    """
    Fix field-level security for a profile
    Returns fix result
    """
    result = {"success": False, "message": ""}

    try:
        # Get profile ID
        profile_query = f"SELECT Id, Name FROM Profile WHERE Name = '{profile_name}'"
        profile_result = sf.query(profile_query)

        if profile_result['totalSize'] == 0:
            result["message"] = f"Profile '{profile_name}' not found"
            return result

        # Provide manual steps (FLS changes via API are complex and require Metadata API)
        result["success"] = True
        result["message"] = f"Field security fix instructions generated for {field_name}"
        result["manual_steps"] = [
            f"1. Navigate to Setup → Profiles → {profile_name}",
            f"2. Click 'Object Settings' and find {object_name}",
            f"3. Click 'Edit' next to {object_name}",
            f"4. Find field '{field_name}' in the Field Permissions section",
            f"5. Check 'Read' and 'Edit' (if needed) for the field",
            "6. Click Save"
        ]
        result["alternative_approach"] = {
            "method": "Permission Set (Recommended)",
            "steps": [
                "1. Create a new Permission Set",
                f"2. Add field permissions for {object_name}.{field_name}",
                f"3. Assign permission set to users with {profile_name} profile"
            ]
        }

    except Exception as e:
        logger.exception("Error fixing field security")
        result["message"] = str(e)

    return result


@register_tool
def diagnose_and_fix_issue(
    issue_type: str,
    description: str,
    object_name: Optional[str] = None,
    field_name: Optional[str] = None,
    component_name: Optional[str] = None,
    auto_fix: bool = False
) -> str:
    """
    Diagnose and optionally fix Salesforce issues including triggers, flows, validation rules,
    layouts, fields, permissions, formulas, and more.

    This unified tool analyzes issues and provides detailed diagnostics with fix recommendations
    or automatic fixes.

    Args:
        issue_type: Type of issue (trigger, flow, validation, layout, field, permission, formula, picklist, lookup, page_layout, report)
        description: Description of the issue/error
        object_name: Object API name (e.g., "Account", "Opportunity")
        field_name: Field API name if issue is field-related (e.g., "Amount", "Stage")
        component_name: Name of the component (trigger, flow, validation rule, etc.)
        auto_fix: Whether to attempt automatic fix (default: False, only provides diagnosis)

    Returns:
        JSON response with diagnosis, root cause analysis, and fix recommendations or applied fixes

    Example:
        # Diagnose trigger recursion issue
        diagnose_and_fix_issue(
            "trigger",
            "System.DmlException: Update failed due to maximum trigger depth exceeded",
            object_name="Opportunity",
            component_name="TriggerOnOpportunity"
        )

        # Diagnose flow issue
        diagnose_and_fix_issue(
            "flow",
            "Flow fails when Account Revenue field is blank",
            object_name="Account",
            component_name="Update Field On Account"
        )

        # Diagnose field visibility issue
        diagnose_and_fix_issue(
            "permission",
            "Standard User profile cannot access Partner_Type__c field",
            object_name="Account",
            field_name="Partner_Type__c"
        )

        # Diagnose formula field issue
        diagnose_and_fix_issue(
            "formula",
            "Close_Month__c formula field calculates incorrectly",
            object_name="Opportunity",
            field_name="Close_Month__c"
        )

    Added by Sameer
    """
    try:
        sf = get_salesforce_connection()
        issue_type = issue_type.lower().strip()

        # ENHANCED: Detect specific QA scenario from description
        detected_scenario = _detect_scenario(description)
        if detected_scenario:
            logger.info(f"Auto-detected scenario: {detected_scenario['scenario_key']} (QA Issue #{detected_scenario['scenario_id']})")
            # Override issue_type if scenario detection gives us a better match
            if issue_type == "auto" or issue_type == "detect":
                issue_type = detected_scenario["issue_type"]

        # Route to appropriate diagnostic function
        if issue_type in ["trigger", "apex_trigger", "apextrigger"]:
            result = _diagnose_trigger_issue(sf, description, object_name, component_name, auto_fix, detected_scenario)
        elif issue_type in ["flow", "process_builder", "workflow"]:
            result = _diagnose_flow_issue(sf, description, object_name, component_name, auto_fix, detected_scenario)
        elif issue_type in ["validation", "validation_rule", "validationrule"]:
            result = _diagnose_validation_issue(sf, description, object_name, component_name, auto_fix, detected_scenario)
        elif issue_type in ["field", "custom_field", "customfield"]:
            result = _diagnose_field_issue(sf, description, object_name, field_name, auto_fix, detected_scenario)
        elif issue_type in ["permission", "profile", "permset", "field_security", "license"]:
            result = _diagnose_permission_issue(sf, description, object_name, field_name, auto_fix, detected_scenario)
        elif issue_type in ["formula", "formula_field"]:
            result = _diagnose_formula_issue(sf, description, object_name, field_name, auto_fix, detected_scenario)
        elif issue_type in ["picklist", "picklist_value", "stage"]:
            result = _diagnose_picklist_issue(sf, description, object_name, field_name, auto_fix, detected_scenario)
        elif issue_type in ["lookup", "relationship", "master_detail"]:
            result = _diagnose_lookup_issue(sf, description, object_name, field_name, auto_fix, detected_scenario)
        elif issue_type in ["layout", "page_layout", "pagelayout", "related_list"]:
            result = _diagnose_layout_issue(sf, description, object_name, component_name, auto_fix, detected_scenario)
        elif issue_type in ["report", "report_field"]:
            result = _diagnose_report_issue(sf, description, object_name, field_name, auto_fix, detected_scenario)
        else:
            # Generic diagnosis for unknown types
            result = _generic_diagnosis(sf, issue_type, description, object_name, field_name, component_name, detected_scenario)

        # Add detected scenario info to result
        if detected_scenario:
            result["detected_scenario"] = detected_scenario

        # Add cross-reference dependency analysis
        if object_name or component_name:
            logger.info("Analyzing dependencies...")
            dependencies = _analyze_dependencies(sf, object_name, field_name, component_name)
            if dependencies["depends_on"] or dependencies["depended_by"]:
                result["dependency_analysis"] = dependencies

        return format_success_response(result)

    except Exception as e:
        logger.exception(f"Error diagnosing {issue_type} issue")
        return format_error_response(e, context=f"diagnose_and_fix_issue ({issue_type})")


# =============================================================================
# TRIGGER DIAGNOSTICS (QA Issues 1, 2, 3)
# =============================================================================

def _diagnose_trigger_issue(sf, description: str, object_name: Optional[str], trigger_name: Optional[str], _auto_fix: bool, _detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Diagnose trigger-related issues.

    Handles QA Scenarios:
    - #1: Trigger not updating specific field (e.g., Industry field not getting updated)
    - #2: Maximum trigger depth exceeded (recursion)
    - #3: Too many SOQL queries: 101 (governor limits in bulk)
    """
    diagnosis = {
        "issue_type": "trigger",
        "object": object_name,
        "trigger_name": trigger_name,
        "description": description,
        "root_causes": [],
        "recommendations": [],
        "fixes_applied": []
    }

    scenario_id = _detected_scenario.get("scenario_id") if _detected_scenario else None

    # ==========================================================================
    # QA SCENARIO #1: Field not updating in trigger
    # ==========================================================================
    if scenario_id == 1 or ("not" in description.lower() and "updating" in description.lower()):
        # Extract the field name from description
        field_match = re.search(r'(\w+(?:__c)?)\s+(?:field\s+)?(?:is\s+)?not\s+(?:getting\s+)?updat', description.lower())
        problematic_field = field_match.group(1) if field_match else None

        diagnosis["root_causes"].append({
            "cause": "Field Not Updating in Trigger",
            "explanation": f"The trigger is not correctly updating the '{problematic_field or 'specified'}' field. This typically happens when:\n1. The field assignment is in wrong trigger context (before vs after)\n2. The field is being set but DML is not being called\n3. The condition to update the field is not being met\n4. The field is on a different object and needs explicit DML",
            "severity": "high",
            "qa_scenario": 1
        })

        # Fetch trigger body to analyze
        if trigger_name and object_name:
            try:
                trigger_query = f"SELECT Id, Name, Body FROM ApexTrigger WHERE Name = '{trigger_name}' LIMIT 1"
                trigger_result = sf.toolingexecute(trigger_query)

                if trigger_result.get('totalSize', 0) > 0:
                    trigger_body = trigger_result['records'][0].get('Body', '')

                    # Check if field is being assigned
                    if problematic_field:
                        field_pattern = rf'{problematic_field}\s*='
                        if not re.search(field_pattern, trigger_body, re.IGNORECASE):
                            diagnosis["root_causes"].append({
                                "cause": "Field Assignment Missing",
                                "explanation": f"Field '{problematic_field}' is NOT being assigned in the trigger code",
                                "severity": "critical"
                            })
                        else:
                            # Field is being assigned - check context
                            if 'after update' in trigger_body.lower() or 'after insert' in trigger_body.lower():
                                # Check if updating same object in after trigger
                                if f"update {object_name.lower()}" not in trigger_body.lower() and "update " not in trigger_body.lower():
                                    diagnosis["root_causes"].append({
                                        "cause": "Missing DML in After Trigger",
                                        "explanation": f"Field '{problematic_field}' is assigned but update DML may be missing. In 'after' triggers, you must explicitly call update on related records.",
                                        "severity": "high"
                                    })

                    diagnosis["trigger_analysis"] = {
                        "trigger_name": trigger_name,
                        "body_length": len(trigger_body),
                        "has_before_insert": "before insert" in trigger_body.lower(),
                        "has_after_insert": "after insert" in trigger_body.lower(),
                        "has_before_update": "before update" in trigger_body.lower(),
                        "has_after_update": "after update" in trigger_body.lower()
                    }

            except Exception as e:
                logger.warning(f"Could not fetch trigger for analysis: {e}")

        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Verify trigger context (before vs after)",
                "details": "For updating fields on the SAME record, use 'before insert' or 'before update' - no DML needed.\nFor updating RELATED records, use 'after' trigger with explicit DML.",
                "code_example": f"""// For updating same record (use BEFORE trigger):
trigger {trigger_name or 'MyTrigger'} on {object_name or 'Account'} (before insert, before update) {{
    for ({object_name or 'Account'} record : Trigger.new) {{
        if (/* your condition */) {{
            record.{problematic_field or 'Industry'} = 'Banking';  // Direct assignment, no DML needed
        }}
    }}
}}"""
            },
            {
                "priority": 2,
                "action": "For related object updates, use explicit DML",
                "code_example": f"""// For updating related record (use AFTER trigger):
trigger {trigger_name or 'MyTrigger'} on Opportunity (after insert, after update) {{
    List<Account> accountsToUpdate = new List<Account>();
    Set<Id> accountIds = new Set<Id>();

    for (Opportunity opp : Trigger.new) {{
        accountIds.add(opp.AccountId);
    }}

    Map<Id, Account> accountMap = new Map<Id, Account>(
        [SELECT Id, {problematic_field or 'Industry'} FROM Account WHERE Id IN :accountIds]
    );

    for (Opportunity opp : Trigger.new) {{
        Account acc = accountMap.get(opp.AccountId);
        if (acc != null && /* your condition */) {{
            acc.{problematic_field or 'Industry'} = 'Banking';
            accountsToUpdate.add(acc);
        }}
    }}

    if (!accountsToUpdate.isEmpty()) {{
        update accountsToUpdate;
    }}
}}"""
            }
        ])

    # ==========================================================================
    # QA SCENARIO #2: Trigger Recursion
    # ==========================================================================
    elif scenario_id == 2 or "maximum trigger depth exceeded" in description.lower() or "recursion" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "Trigger Recursion",
            "explanation": "Trigger is calling itself repeatedly causing infinite loop",
            "severity": "high"
        })
        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Add static variable to prevent recursion",
                "code_example": """public class TriggerHelper {
    public static Boolean isFirstRun = true;
}

// In trigger:
if (TriggerHelper.isFirstRun) {
    TriggerHelper.isFirstRun = false;
    // Your trigger logic here
}"""
            },
            {
                "priority": 2,
                "action": "Use Set<Id> to track processed records",
                "code_example": """public class TriggerHelper {
    public static Set<Id> processedIds = new Set<Id>();
}

// In trigger:
for (SObject record : Trigger.new) {
    if (!TriggerHelper.processedIds.contains(record.Id)) {
        TriggerHelper.processedIds.add(record.Id);
        // Your trigger logic here
    }
}"""
            }
        ])

        # AUTO-FIX: Generate helper class
        if _auto_fix and object_name:
            logger.info(f"Auto-fix enabled: Creating recursion prevention helper class for {object_name}")
            fix_result = _create_trigger_helper_class(sf, "recursion_prevention", object_name)
            diagnosis["fixes_applied"].append({
                "fix_type": "Recursion Prevention Helper Class",
                "status": "Generated" if fix_result["success"] else "Failed",
                "details": fix_result
            })

    # ==========================================================================
    # QA SCENARIO #3: SOQL 101 Limit Exceeded
    # ==========================================================================
    elif scenario_id == 3 or "too many soql queries" in description.lower() or "101" in description:
        diagnosis["root_causes"].append({
            "cause": "SOQL Query Limit Exceeded (Governor Limit)",
            "explanation": "Trigger is executing more than 100 SOQL queries. This typically happens when:\n1. SOQL query is inside a for/while loop\n2. Trigger is not bulkified for handling multiple records\n3. Helper methods are querying inside loops",
            "severity": "critical",
            "qa_scenario": 3
        })

        # Analyze trigger body for SOQL in loops if available (with caching)
        if trigger_name and object_name:
            try:
                cache_key = f"trigger_body_{trigger_name}_{object_name}"
                trigger_result = _get_cached_metadata(
                    cache_key,
                    lambda: sf.toolingexecute(
                        f"SELECT Id, Name, Body FROM ApexTrigger WHERE Name = '{trigger_name}' AND TableEnumOrId = '{object_name}'"
                    )
                )

                if trigger_result['totalSize'] > 0:
                    trigger_body = trigger_result['records'][0].get('Body', '')
                    body_lines = len(trigger_body.split('\n'))
                    logger.info(f"Analyzing large trigger: {body_lines} lines")

                    # Detect SOQL in loops - even in large files
                    soql_in_loop_patterns = [
                        (r'for\s*\(.*?\)\s*\{[^}]*\[SELECT', 'SOQL inside for loop'),
                        (r'while\s*\(.*?\)\s*\{[^}]*\[SELECT', 'SOQL inside while loop'),
                        (r'for\s*\(.*?\)\s*\{[^}]*Database\.query', 'Dynamic SOQL inside for loop')
                    ]

                    detected_issues = []
                    for pattern, issue_desc in soql_in_loop_patterns:
                        matches = re.finditer(pattern, trigger_body, re.DOTALL | re.IGNORECASE)
                        for match in matches:
                            # Find line number
                            line_num = trigger_body[:match.start()].count('\n') + 1
                            detected_issues.append({
                                "issue": issue_desc,
                                "line": line_num,
                                "snippet": trigger_body[max(0, match.start()-50):match.end()+50]
                            })

                    if detected_issues:
                        diagnosis["detected_soql_issues"] = detected_issues
                        diagnosis["recommendations"].insert(0, {
                            "priority": 0,
                            "action": f"CRITICAL: Found {len(detected_issues)} SOQL queries in loops",
                            "locations": [f"Line {issue['line']}: {issue['issue']}" for issue in detected_issues]
                        })
            except Exception as e:
                logger.warning(f"Could not analyze trigger for SOQL patterns: {e}")

        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Bulkify trigger - query outside loop",
                "code_example": """// ❌ BAD - Query in loop
for (Opportunity opp : Trigger.new) {
    Account acc = [SELECT Id, Name FROM Account WHERE Id = :opp.AccountId];
}

// ✅ GOOD - Query once, use Map
Set<Id> accountIds = new Set<Id>();
for (Opportunity opp : Trigger.new) {
    accountIds.add(opp.AccountId);
}
Map<Id, Account> accountMap = new Map<Id, Account>(
    [SELECT Id, Name FROM Account WHERE Id IN :accountIds]
);
for (Opportunity opp : Trigger.new) {
    Account acc = accountMap.get(opp.AccountId);
}"""
            },
            {
                "priority": 2,
                "action": "Use Trigger.newMap and Trigger.oldMap for efficient lookups"
            }
        ])

    elif "field is not writable" in description.lower() or "field not updating" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "Field Not Updateable",
            "explanation": "Attempting to update a read-only, formula, or system field",
            "severity": "medium"
        })

        # Check if trigger is trying to update specific fields (with caching)
        if object_name and trigger_name:
            try:
                # Get trigger body to analyze
                cache_key = f"trigger_body_{trigger_name}_{object_name}"
                trigger_result = _get_cached_metadata(
                    cache_key,
                    lambda: sf.toolingexecute(
                        f"SELECT Id, Name, Body FROM ApexTrigger WHERE Name = '{trigger_name}' AND TableEnumOrId = '{object_name}'"
                    )
                )

                if trigger_result['totalSize'] > 0:
                    trigger_body = trigger_result['records'][0].get('Body', '')
                    body_lines = len(trigger_body.split('\n'))

                    # Log size info
                    logger.info(f"Analyzing trigger body: {body_lines} lines, {len(trigger_body)} characters")

                    # Get object metadata to check field types
                    obj_metadata = sf.__getattr__(object_name).describe()

                    # Analyze which fields are being updated
                    fields_being_updated = re.findall(r'\.(\w+)\s*=\s*', trigger_body)
                    problematic_fields = []

                    for field_name in set(fields_being_updated):
                        for field in obj_metadata['fields']:
                            if field['name'].lower() == field_name.lower():
                                if not field['updateable'] or field['calculated']:
                                    problematic_fields.append({
                                        "field": field['name'],
                                        "reason": "Formula field" if field['calculated'] else "Not updateable",
                                        "type": field['type']
                                    })

                    if problematic_fields:
                        diagnosis["problematic_fields"] = problematic_fields
                        diagnosis["recommendations"].append({
                            "priority": 1,
                            "action": f"Remove updates to read-only fields: {', '.join([f['field'] for f in problematic_fields])}"
                        })

            except Exception as e:
                logger.warning(f"Could not analyze trigger body: {e}")

    # Get trigger details if name provided
    if trigger_name and object_name:
        try:
            trigger_query = f"SELECT Id, Name, Status, UsageBeforeInsert, UsageAfterInsert, UsageBeforeUpdate, UsageAfterUpdate, UsageBeforeDelete, UsageAfterDelete FROM ApexTrigger WHERE Name = '{trigger_name}'"
            trigger_result = sf.query(trigger_query)

            if trigger_result['totalSize'] > 0:
                trigger_info = trigger_result['records'][0]
                diagnosis["trigger_details"] = {
                    "status": trigger_info.get('Status'),
                    "events": []
                }

                # List active events
                events = []
                if trigger_info.get('UsageBeforeInsert'): events.append('before insert')
                if trigger_info.get('UsageAfterInsert'): events.append('after insert')
                if trigger_info.get('UsageBeforeUpdate'): events.append('before update')
                if trigger_info.get('UsageAfterUpdate'): events.append('after update')
                if trigger_info.get('UsageBeforeDelete'): events.append('before delete')
                if trigger_info.get('UsageAfterDelete'): events.append('after delete')

                diagnosis["trigger_details"]["events"] = events

        except Exception as e:
            logger.warning(f"Could not fetch trigger details: {e}")

    return diagnosis


# =============================================================================
# FLOW DIAGNOSTICS (QA Issues 4, 5)
# =============================================================================

def _diagnose_flow_issue(sf, description: str, object_name: Optional[str], flow_name: Optional[str], _auto_fix: bool, _detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Diagnose flow-related issues.

    Handles QA Scenarios:
    - #4: Flow fails when field is blank/null (e.g., Account Revenue field is blank)
    - #5: Flow Decision element checks wrong value (e.g., checks "Closed" instead of "Closed Won")
    """
    diagnosis = {
        "issue_type": "flow",
        "object": object_name,
        "flow_name": flow_name,
        "description": description,
        "root_causes": [],
        "recommendations": []
    }

    scenario_id = _detected_scenario.get("scenario_id") if _detected_scenario else None

    # ==========================================================================
    # QA SCENARIO #4: Flow fails when field is blank/null
    # ==========================================================================
    if scenario_id == 4 or ("fails when" in description.lower() and "blank" in description.lower()):
        # Extract field name from description
        field_match = re.search(r'(\w+(?:\s+\w+)?)\s+field\s+is\s+blank', description.lower())
        problematic_field = field_match.group(1).title().replace(' ', '') if field_match else "Revenue"

        diagnosis["root_causes"].append({
            "cause": "Missing Null/Blank Value Handling",
            "explanation": f"Flow fails when the '{problematic_field}' field is blank. Record-triggered flows must handle null values explicitly.",
            "severity": "high",
            "qa_scenario": 4
        })
        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Add null check BEFORE using the field value",
                "details": f"Add a Decision element at the start of your flow to check: NOT(ISBLANK({{!$Record.{problematic_field}}}))",
                "flow_steps": [
                    "1. Open Flow Builder",
                    f"2. Add a Decision element BEFORE the Update element",
                    f"3. Create outcome 'Field Has Value' with condition:",
                    f"   - Resource: {{!$Record.{problematic_field}}}",
                    f"   - Operator: Is Null = False",
                    f"4. Route 'Field Has Value' to your Update element",
                    f"5. Route 'Default Outcome' to End (skip update)"
                ]
            },
            {
                "priority": 2,
                "action": "Alternative: Use formula with BLANKVALUE()",
                "details": f"In formulas, use: BLANKVALUE({{!$Record.{problematic_field}}}, 0) to provide default value",
                "formula_example": f"IF(BLANKVALUE({{!$Record.{problematic_field}}}, 0) > 1000000, 'Hot', 'Cold')"
            },
            {
                "priority": 3,
                "action": "Add Entry Conditions to prevent flow from running on blank values",
                "details": f"In Flow entry conditions, add: {{!$Record.{problematic_field}}} Is Null = False"
            }
        ])

    # ==========================================================================
    # QA SCENARIO #5: Flow Decision checks wrong picklist value
    # ==========================================================================
    elif scenario_id == 5 or ("decision" in description.lower() and "instead" in description.lower()):
        diagnosis["root_causes"].append({
            "cause": "Incorrect Decision Logic",
            "explanation": "Decision element has wrong condition or comparison",
            "severity": "medium"
        })
        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Review Decision element conditions",
                "details": "Common issues: Using 'Closed' instead of 'Closed Won', using Contains instead of Equals"
            },
            {
                "priority": 2,
                "action": "Check for exact field API names and values",
                "details": "Verify picklist values match exactly (case-sensitive)"
            }
        ])

    # Get flow details
    if flow_name:
        try:
            flow_query = f"SELECT Id, Label, ProcessType, Status, TriggerType FROM Flow WHERE Label = '{flow_name}' OR ApiName = '{flow_name}' ORDER BY VersionNumber DESC LIMIT 1"
            flow_result = sf.query(flow_query)

            if flow_result['totalSize'] > 0:
                flow_info = flow_result['records'][0]
                diagnosis["flow_details"] = {
                    "label": flow_info.get('Label'),
                    "type": flow_info.get('ProcessType'),
                    "status": flow_info.get('Status'),
                    "trigger_type": flow_info.get('TriggerType')
                }

                if flow_info.get('Status') != 'Active':
                    diagnosis["root_causes"].append({
                        "cause": "Flow Not Active",
                        "explanation": f"Flow status is '{flow_info.get('Status')}' - needs to be activated",
                        "severity": "high"
                    })
                    diagnosis["recommendations"].append({
                        "priority": 1,
                        "action": "Activate the flow in Flow Builder"
                    })

        except Exception as e:
            logger.warning(f"Could not fetch flow details: {e}")

    return diagnosis


# =============================================================================
# VALIDATION RULE DIAGNOSTICS
# =============================================================================

def _fetch_validation_rules(sf, object_name: str, rule_name: Optional[str] = None) -> List[Dict]:
    """
    Fetch validation rules from the org for analysis.
    Returns list of validation rules with their metadata.
    """
    validation_rules = []
    try:
        # Query validation rules via Tooling API
        query = f"""
            SELECT Id, ValidationName, Active, Description, ErrorConditionFormula,
                   ErrorDisplayField, ErrorMessage, FullName, Metadata
            FROM ValidationRule
            WHERE EntityDefinition.QualifiedApiName = '{object_name}'
        """
        if rule_name:
            query += f" AND ValidationName = '{rule_name}'"
        query += " LIMIT 50"

        result = sf.toolingexecute(query)

        for rule in result.get('records', []):
            validation_rules.append({
                "id": rule.get('Id'),
                "name": rule.get('ValidationName'),
                "full_name": rule.get('FullName'),
                "active": rule.get('Active'),
                "description": rule.get('Description'),
                "formula": rule.get('ErrorConditionFormula'),
                "error_message": rule.get('ErrorMessage'),
                "error_field": rule.get('ErrorDisplayField'),
                "metadata": rule.get('Metadata')
            })

    except Exception as e:
        logger.warning(f"Could not fetch validation rules: {e}")

    return validation_rules


def _diagnose_validation_issue(sf, description: str, object_name: Optional[str], rule_name: Optional[str], _auto_fix: bool, _detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Diagnose validation rule issues.

    Handles QA Scenarios:
    - #9: Contact cannot be saved without Phone (existing validation needs review)
    - #20: Opportunity Close Date allows past dates (missing validation)
    - #21: Amount validation too restrictive (needs profile exemption)
    - #24: Accounts saved without Phone (missing validation)
    - #25: Unclear validation error message

    NOTE: Validation rules CANNOT be deployed via API. This tool fetches, analyzes,
    and provides corrected code with manual instructions.
    """
    diagnosis = {
        "issue_type": "validation_rule",
        "object": object_name,
        "rule_name": rule_name,
        "description": description,
        "root_causes": [],
        "recommendations": [],
        "existing_rules": [],
        "manual_update_required": True
    }

    scenario_id = _detected_scenario.get("scenario_id") if _detected_scenario else None

    # ==========================================================================
    # FETCH EXISTING VALIDATION RULES FOR ANALYSIS
    # ==========================================================================
    if object_name:
        existing_rules = _fetch_validation_rules(sf, object_name, rule_name)
        if existing_rules:
            diagnosis["existing_rules"] = existing_rules
            logger.info(f"Found {len(existing_rules)} validation rule(s) on {object_name}")

    # ==========================================================================
    # QA SCENARIO #20: Date allows past dates
    # ==========================================================================
    if scenario_id == 20 or "allows past dates" in description.lower():
        # Extract field name
        field_match = re.search(r'(\w+)\s+(?:date\s+)?allows?\s+past', description.lower())
        date_field = field_match.group(1).title() + "Date" if field_match else "CloseDate"

        diagnosis["root_causes"].append({
            "cause": "Missing Date Validation Rule",
            "explanation": f"The '{date_field}' field allows past dates, which can cause data quality issues.",
            "severity": "high",
            "qa_scenario": 20
        })

        formula = f"{date_field} < TODAY()"
        error_msg = f"{date_field.replace('Date', ' Date')} cannot be in the past. Please select today or a future date."

        diagnosis["recommendations"].append({
            "priority": 1,
            "action": f"Create validation rule to prevent past dates on {date_field}",
            "validation_rule": {
                "Rule Name": f"Prevent_Past_{date_field}",
                "Object": object_name or "Opportunity",
                "Active": True,
                "Error Condition Formula": formula,
                "Error Message": error_msg,
                "Error Location": date_field
            },
            "manual_steps": [
                f"1. Go to Setup → Object Manager → {object_name or 'Opportunity'} → Validation Rules",
                "2. Click 'New'",
                f"3. Rule Name: Prevent_Past_{date_field}",
                f"4. Error Condition Formula: {formula}",
                f"5. Error Message: {error_msg}",
                "6. Error Location: Field → " + date_field,
                "7. Save"
            ]
        })

    # ==========================================================================
    # QA SCENARIO #21: Validation too restrictive (amount limit)
    # ==========================================================================
    elif scenario_id == 21 or "cannot exceed" in description.lower():
        # Extract amount from description
        amount_match = re.search(r'\$?([\d,]+)', description)
        current_limit = amount_match.group(1).replace(',', '') if amount_match else "5000"

        diagnosis["root_causes"].append({
            "cause": "Overly Restrictive Validation Rule",
            "explanation": f"Validation rule is blocking amounts over ${current_limit}. This may be too restrictive for legitimate business cases.",
            "severity": "medium",
            "qa_scenario": 21
        })

        # Analyze existing rules to find the problematic one
        problematic_rule = None
        if diagnosis.get("existing_rules"):
            for rule in diagnosis["existing_rules"]:
                formula = rule.get("formula", "").lower()
                if "amount" in formula and (">" in formula or ">=" in formula):
                    problematic_rule = rule
                    break

        if problematic_rule:
            diagnosis["current_rule_analysis"] = {
                "rule_name": problematic_rule["name"],
                "current_formula": problematic_rule["formula"],
                "current_error_message": problematic_rule["error_message"],
                "is_active": problematic_rule["active"]
            }

            # Generate corrected formula with profile exemption
            original_formula = problematic_rule["formula"]
            corrected_formula = f"""AND(
    {original_formula},
    $Profile.Name <> "System Administrator",
    $Profile.Name <> "Sales Manager"
)"""
            diagnosis["corrected_code"] = {
                "formula": corrected_formula,
                "error_message": f"Opportunity amount exceeds ${current_limit}. Please contact your manager for approval or use the Approval Process for larger opportunities."
            }

        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Add profile exemption to validation rule",
                "corrected_formula": diagnosis.get("corrected_code", {}).get("formula", f"""AND(
    Amount > {current_limit},
    $Profile.Name <> "System Administrator",
    $Profile.Name <> "Sales Manager"
)"""),
                "manual_steps": [
                    f"1. Go to Setup → Object Manager → {object_name or 'Opportunity'} → Validation Rules",
                    f"2. Find and Edit the rule: {rule_name or problematic_rule['name'] if problematic_rule else '[Amount Validation Rule]'}",
                    "3. Update the Error Condition Formula with the corrected formula above",
                    "4. Update the Error Message to be more helpful",
                    "5. Save the rule"
                ]
            },
            {
                "priority": 2,
                "action": "Alternative: Increase the threshold",
                "details": f"Change the amount limit from ${current_limit} to a higher value if business requirements have changed"
            },
            {
                "priority": 3,
                "action": "Alternative: Use Approval Process instead",
                "details": "Create an approval process for amounts over the threshold instead of blocking them entirely"
            }
        ])

    # ==========================================================================
    # QA SCENARIO #9, #24: Missing required field validation (Contact/Account Phone)
    # ==========================================================================
    elif scenario_id in [9, 24] or "saved without" in description.lower() or "without a phone" in description.lower():
        # Extract which field and object
        field_match = re.search(r'without\s+(?:a\s+)?(\w+)', description.lower())
        required_field = field_match.group(1).title() if field_match else "Phone"
        target_object = object_name or ("Contact" if "contact" in description.lower() else "Account")

        diagnosis["root_causes"].append({
            "cause": "Missing Required Field Validation",
            "explanation": f"{target_object} records can be saved without a {required_field} number. A validation rule needs to be created.",
            "severity": "high",
            "qa_scenario": scenario_id or 24
        })

        formula = f"ISBLANK({required_field})"
        error_msg = f"Please enter a {required_field} number before saving."

        diagnosis["recommendations"].append({
            "priority": 1,
            "action": f"Create validation rule to require {required_field} field",
            "validation_rule": {
                "Rule Name": f"Require_{required_field}",
                "Object": target_object,
                "Active": True,
                "Error Condition Formula": formula,
                "Error Message": error_msg,
                "Error Location": required_field
            },
            "manual_steps": [
                f"1. Go to Setup → Object Manager → {target_object} → Validation Rules",
                "2. Click 'New'",
                f"3. Rule Name: Require_{required_field}",
                f"4. Error Condition Formula: {formula}",
                f"5. Error Message: {error_msg}",
                f"6. Error Location: Field → {required_field}",
                "7. Save"
            ]
        })

    # ==========================================================================
    # QA SCENARIO #25: Unclear validation error message
    # ==========================================================================
    elif scenario_id == 25 or "unclear" in description.lower() or "enter.*field.*value" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "Confusing Validation Error Message",
            "explanation": "The validation rule error message is not clear to users. Error messages should be specific and actionable.",
            "severity": "medium",
            "qa_scenario": 25
        })

        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Update validation rule error message to be clear and actionable",
                "best_practices": [
                    "State what the user needs to do, not just what's wrong",
                    "Be specific about which field needs attention",
                    "Provide the valid values or format if applicable",
                    "Avoid technical jargon"
                ],
                "examples": {
                    "bad": "Please enter net new Type field value",
                    "good": "Please select a Type value for this Opportunity. Valid options are: New Customer, Existing Customer - Upgrade, Existing Customer - Add-On"
                }
            },
            {
                "priority": 2,
                "action": "Set Error Location to the specific field",
                "details": "This highlights the problematic field for the user"
            }
        ])

    # Get validation rule details using Tooling API
    if object_name:
        try:
            # Cache key for validation rules
            cache_key = f"validation_rules_{object_name}_{rule_name or 'all'}"

            def fetch_validation_rules():
                # Query validation rules for the object via Tooling API
                val_query = f"""
                    SELECT Id, ValidationName, Active, ErrorDisplayField, ErrorMessage, FullName
                    FROM ValidationRule
                    WHERE EntityDefinition.QualifiedApiName = '{object_name}'
                """
                if rule_name:
                    val_query += f" AND ValidationName = '{rule_name}'"

                val_query += " LIMIT 50"

                return sf.toolingexecute(val_query)

            validation_result = _get_cached_metadata(cache_key, fetch_validation_rules)

            if validation_result.get('totalSize', 0) > 0:
                diagnosis["validation_rules"] = []
                for rule in validation_result['records']:
                    diagnosis["validation_rules"].append({
                        "name": rule.get('ValidationName'),
                        "full_name": rule.get('FullName'),
                        "active": rule.get('Active'),
                        "error_field": rule.get('ErrorDisplayField'),
                        "error_message": rule.get('ErrorMessage')
                    })

        except Exception as e:
            logger.warning(f"Could not fetch validation rules via Tooling API: {e}")

    return diagnosis


# =============================================================================
# FIELD DIAGNOSTICS
# =============================================================================

def _diagnose_field_issue(sf, description: str, object_name: Optional[str], field_name: Optional[str], _auto_fix: bool, _detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """Diagnose field-related issues (QA scenarios 14, 16, 17)"""
    diagnosis = {
        "issue_type": "field",
        "object": object_name,
        "field_name": field_name,
        "description": description,
        "root_causes": [],
        "recommendations": []
    }

    if not object_name or not field_name:
        diagnosis["root_causes"].append({
            "cause": "Insufficient Information",
            "explanation": "Need both object_name and field_name to diagnose field issues"
        })
        return diagnosis

    try:
        # Get field metadata with caching
        cache_key = f"obj_describe_{object_name}"
        obj_describe = _get_cached_metadata(
            cache_key,
            lambda: sf.__getattr__(object_name).describe()
        )
        field_info = None

        for field in obj_describe['fields']:
            if field['name'].lower() == field_name.lower():
                field_info = field
                break

        if not field_info:
            diagnosis["root_causes"].append({
                "cause": "Field Not Found",
                "explanation": f"Field '{field_name}' does not exist on '{object_name}'",
                "severity": "high"
            })
            diagnosis["recommendations"].append({
                "priority": 1,
                "action": f"Verify field API name (should it be {field_name}__c?)"
            })
            return diagnosis

        diagnosis["field_details"] = {
            "label": field_info['label'],
            "type": field_info['type'],
            "required": not field_info['nillable'],
            "updateable": field_info['updateable'],
            "calculated": field_info['calculated'],
            "visible": not field_info['deprecatedAndHidden']
        }

        # Analyze based on description
        if "not visible" in description.lower() or "cannot see" in description.lower():
            diagnosis["root_causes"].append({
                "cause": "Field Level Security",
                "explanation": "Field may not be visible to user's profile",
                "severity": "high"
            })
            diagnosis["recommendations"].extend([
                {
                    "priority": 1,
                    "action": "Check field-level security settings",
                    "details": f"Setup → Object Manager → {object_name} → Fields → {field_name} → Set Field-Level Security"
                },
                {
                    "priority": 2,
                    "action": "Check page layout",
                    "details": "Field must be added to page layout AND have FLS access"
                }
            ])

        elif "displays as multi-picklist" in description.lower() or "wrong field type" in description.lower():
            diagnosis["root_causes"].append({
                "cause": "Incorrect Field Type",
                "explanation": f"Field is configured as {field_info['type']} but should be different type",
                "severity": "medium"
            })
            diagnosis["recommendations"].append({
                "priority": 1,
                "action": "Field type cannot be changed directly",
                "details": "Create new field with correct type and migrate data"
            })

        elif "shows wrong records" in description.lower():
            if field_info['type'] in ['reference', 'lookup']:
                diagnosis["root_causes"].append({
                    "cause": "Incorrect Lookup Configuration",
                    "explanation": "Lookup field is pointing to wrong object",
                    "severity": "high"
                })
                diagnosis["recommendations"].append({
                    "priority": 1,
                    "action": "Recreate lookup field pointing to correct object",
                    "details": f"Current reference: {field_info.get('referenceTo', 'Unknown')}"
                })

        elif "displays date and time" in description.lower() and field_info['type'] == 'datetime':
            diagnosis["root_causes"].append({
                "cause": "Wrong Field Type",
                "explanation": "Using DateTime field instead of Date field",
                "severity": "low"
            })
            diagnosis["recommendations"].append({
                "priority": 1,
                "action": "Change field type from DateTime to Date",
                "details": "This requires creating a new field and migrating data"
            })

    except Exception as e:
        logger.exception("Error diagnosing field issue")
        diagnosis["root_causes"].append({
            "cause": "Diagnosis Error",
            "explanation": str(e)
        })

    return diagnosis


# =============================================================================
# PERMISSION DIAGNOSTICS
# =============================================================================

def _diagnose_permission_issue(sf, description: str, object_name: Optional[str], field_name: Optional[str], _auto_fix: bool, _detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Diagnose permission and security issues.

    Handles QA Scenarios:
    - #6: Wrong license, unable to access Leads/Opportunities
    - #8: Profile cannot access field (FLS)
    - #11: Formula field not visible to any profile
    """
    diagnosis = {
        "issue_type": "permission",
        "object": object_name,
        "field_name": field_name,
        "description": description,
        "root_causes": [],
        "recommendations": []
    }

    # Extract profile name from description
    profile_match = re.search(r'([\w\s]+)\s+profile', description.lower())
    profile_name = profile_match.group(1).strip().title() if profile_match else None

    if "cannot access" in description.lower() and field_name:
        diagnosis["root_causes"].append({
            "cause": "Field Level Security",
            "explanation": f"Profile does not have access to field '{field_name}'",
            "severity": "high"
        })
        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Grant field access to profile",
                "details": f"Setup → Profiles → {profile_name or '[Profile Name]'} → Field-Level Security → {object_name} → {field_name} → Set to Visible"
            },
            {
                "priority": 2,
                "action": "Alternatively, use Permission Set",
                "details": "Create Permission Set with field access and assign to users"
            }
        ])

        # AUTO-FIX: Generate field security fix instructions
        if _auto_fix and profile_name and object_name and field_name:
            logger.info(f"Auto-fix enabled: Generating FLS fix for {object_name}.{field_name}")
            fix_result = _fix_field_security(sf, object_name, field_name, profile_name)
            diagnosis["fixes_applied"] = diagnosis.get("fixes_applied", [])
            diagnosis["fixes_applied"].append({
                "fix_type": "Field-Level Security Access",
                "status": "Generated" if fix_result["success"] else "Failed",
                "details": fix_result
            })

    elif "wrong license" in description.lower() or "unable to access" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "User License Issue",
            "explanation": "User has wrong license type for required access",
            "severity": "high"
        })
        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Verify user license type",
                "details": "Setup → Users → [User] → Check License field"
            },
            {
                "priority": 2,
                "action": "Change profile or assign correct license",
                "details": "Some objects require Salesforce or Sales Cloud license"
            }
        ])

    elif "wrong layout" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "Page Layout Assignment",
            "explanation": "Profile is assigned to wrong page layout",
            "severity": "medium"
        })
        diagnosis["recommendations"].append({
            "priority": 1,
            "action": "Reassign page layout to profile",
            "details": f"Setup → Object Manager → {object_name} → Page Layouts → Page Layout Assignment → Assign correct layout to profile"
        })

    return diagnosis


# =============================================================================
# FORMULA FIELD DIAGNOSTICS
# =============================================================================

def _diagnose_formula_issue(sf, description: str, object_name: Optional[str], field_name: Optional[str], _auto_fix: bool, _detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Diagnose formula field issues.

    Handles QA Scenarios:
    - #12: Formula calculates incorrectly (e.g., Close_Month__c returns invalid month)
    - #16: DateTime field displays time, should be Date only
    """
    diagnosis = {
        "issue_type": "formula",
        "object": object_name,
        "field_name": field_name,
        "description": description,
        "root_causes": [],
        "recommendations": []
    }

    if not object_name or not field_name:
        diagnosis["root_causes"].append({
            "cause": "Insufficient Information",
            "explanation": "Need both object_name and field_name"
        })
        return diagnosis

    try:
        # Get field details with caching
        cache_key = f"obj_describe_{object_name}"
        obj_describe = _get_cached_metadata(
            cache_key,
            lambda: sf.__getattr__(object_name).describe()
        )
        field_info = None

        for field in obj_describe['fields']:
            if field['name'].lower() == field_name.lower():
                field_info = field
                break

        if field_info and field_info['calculated']:
            diagnosis["field_details"] = {
                "label": field_info['label'],
                "type": field_info['type'],
                "formula": field_info.get('calculatedFormula', 'N/A')
            }

            if "incorrect" in description.lower() or "wrong value" in description.lower():
                diagnosis["root_causes"].append({
                    "cause": "Formula Logic Error",
                    "explanation": "Formula has incorrect logic or calculation",
                    "severity": "high"
                })
                diagnosis["recommendations"].extend([
                    {
                        "priority": 1,
                        "action": "Review formula syntax",
                        "current_formula": field_info.get('calculatedFormula', 'N/A')
                    },
                    {
                        "priority": 2,
                        "action": "Check for null value handling",
                        "details": "Use ISBLANK() to handle null values"
                    },
                    {
                        "priority": 3,
                        "action": "Test formula with sample data"
                    }
                ])

            # Specific issue: month calculation
            if "month" in field_name.lower() and "invalid" in description.lower():
                diagnosis["recommendations"].append({
                    "priority": 1,
                    "action": "Fix month calculation formula",
                    "correct_formula": "TEXT(MONTH(CloseDate))",
                    "details": "Use MONTH() function which returns 1-12, then TEXT() to convert to string"
                })

    except Exception as e:
        logger.exception("Error diagnosing formula")
        diagnosis["error"] = str(e)

    return diagnosis


# =============================================================================
# PICKLIST DIAGNOSTICS
# =============================================================================

def _diagnose_picklist_issue(sf, description: str, object_name: Optional[str], field_name: Optional[str], _auto_fix: bool, _detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Diagnose picklist field issues.

    Handles QA Scenarios:
    - #13: Picklist value not visible (e.g., New Customer not visible in Type)
    - #14: Wrong field type (multi-picklist instead of single)
    - #19: Wrong probability for Opportunity stage
    """
    diagnosis = {
        "issue_type": "picklist",
        "object": object_name,
        "field_name": field_name,
        "description": description,
        "root_causes": [],
        "recommendations": []
    }

    if not object_name or not field_name:
        return diagnosis

    try:
        # Get object metadata with caching
        cache_key = f"obj_describe_{object_name}"
        obj_describe = _get_cached_metadata(
            cache_key,
            lambda: sf.__getattr__(object_name).describe()
        )
        field_info = None

        for field in obj_describe['fields']:
            if field['name'].lower() == field_name.lower():
                field_info = field
                break

        if field_info and field_info['type'] in ['picklist', 'multipicklist']:
            picklist_values = [pv['value'] for pv in field_info.get('picklistValues', [])]
            active_values = [pv['value'] for pv in field_info.get('picklistValues', []) if pv.get('active', False)]

            diagnosis["field_details"] = {
                "type": field_info['type'],
                "all_values": picklist_values,
                "active_values": active_values,
                "record_type_specific": len([pv for pv in field_info.get('picklistValues', []) if pv.get('validFor')]) > 0
            }

            if "cannot see" in description.lower() or "missing" in description.lower():
                # Extract the value they're looking for
                value_match = re.search(r'value[:\s]+([^\s,\.]+)', description, re.IGNORECASE)
                missing_value = value_match.group(1) if value_match else None

                diagnosis["root_causes"].append({
                    "cause": "Picklist Value Not Available",
                    "explanation": f"Value '{missing_value}' is either inactive or not visible to this record type",
                    "severity": "medium"
                })

                if missing_value and missing_value not in active_values:
                    if missing_value in picklist_values:
                        diagnosis["recommendations"].append({
                            "priority": 1,
                            "action": f"Activate picklist value '{missing_value}'",
                            "details": f"Setup → Object Manager → {object_name} → Fields → {field_name} → Activate value"
                        })
                    else:
                        diagnosis["recommendations"].append({
                            "priority": 1,
                            "action": f"Add picklist value '{missing_value}'",
                            "details": f"Setup → Object Manager → {object_name} → Fields → {field_name} → New"
                        })

                diagnosis["recommendations"].append({
                    "priority": 2,
                    "action": "Check record type picklist value assignments",
                    "details": "Value may be available but not assigned to current record type"
                })

    except Exception as e:
        logger.exception("Error diagnosing picklist")
        diagnosis["error"] = str(e)

    return diagnosis


# =============================================================================
# LOOKUP/RELATIONSHIP DIAGNOSTICS
# =============================================================================

def _diagnose_lookup_issue(_sf, description: str, object_name: Optional[str], field_name: Optional[str], _auto_fix: bool, _detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Diagnose lookup/relationship field issues.

    Handles QA Scenarios:
    - #17: Lookup shows wrong object records (e.g., Case instead of Contact)
    """
    diagnosis = {
        "issue_type": "lookup",
        "object": object_name,
        "field_name": field_name,
        "description": description,
        "root_causes": [],
        "recommendations": []
    }

    if "shows wrong records" in description.lower() or "shows" in description.lower() and "instead of" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "Incorrect Lookup Object",
            "explanation": "Lookup field is pointing to wrong object",
            "severity": "high"
        })
        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Verify lookup field configuration",
                "details": "Check which object the lookup field references"
            },
            {
                "priority": 2,
                "action": "Delete and recreate lookup field",
                "details": "Lookup target object cannot be changed after creation"
            }
        ])

    return diagnosis


# =============================================================================
# PAGE LAYOUT DIAGNOSTICS
# =============================================================================

def _diagnose_layout_issue(_sf, description: str, object_name: Optional[str], layout_name: Optional[str], _auto_fix: bool, _detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Diagnose page layout issues.

    Handles QA Scenarios:
    - #7: Users see wrong layout (e.g., Service users see wrong Case layout)
    - #10: Missing count on related list
    - #15: Missing fields on related details component
    - #18: Related list missing from page layout (Stage History)
    - #23: Related list missing (Opportunity Products)
    """
    diagnosis = {
        "issue_type": "page_layout",
        "object": object_name,
        "layout_name": layout_name,
        "description": description,
        "root_causes": [],
        "recommendations": []
    }

    scenario_id = _detected_scenario.get("scenario_id") if _detected_scenario else None

    # ==========================================================================
    # QA SCENARIO #7: Users see wrong layout
    # ==========================================================================
    if scenario_id == 7 or "wrong layout" in description.lower() or "wrong page" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "Incorrect Layout Assignment",
            "explanation": "Users are seeing a different page layout than expected. This is controlled by profile/record type assignment.",
            "severity": "high",
            "qa_scenario": 7
        })
        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Check Layout Assignment by Profile and Record Type",
                "manual_steps": [
                    f"1. Go to Setup → Object Manager → {object_name or 'Case'} → Page Layouts",
                    "2. Click 'Page Layout Assignment'",
                    "3. Find the Profile for affected users",
                    "4. Check which Record Type row they use",
                    "5. Change the layout assignment to the correct layout",
                    "6. Save"
                ]
            },
            {
                "priority": 2,
                "action": "Verify user's Profile and Record Type access",
                "details": "Users may be getting a different record type than expected"
            }
        ])

    # ==========================================================================
    # QA SCENARIO #18, #23: Missing related list
    # ==========================================================================
    elif scenario_id in [18, 23] or "related list" in description.lower() and "missing" in description.lower():
        # Extract which related list
        related_list_match = re.search(r'(\w+(?:\s+\w+)?)\s+related\s+list', description.lower())
        related_list = related_list_match.group(1).title() if related_list_match else "Related Records"

        diagnosis["root_causes"].append({
            "cause": f"Missing Related List: {related_list}",
            "explanation": f"The '{related_list}' related list is not displayed on the page layout.",
            "severity": "medium",
            "qa_scenario": scenario_id or 18
        })
        diagnosis["recommendations"].append({
            "priority": 1,
            "action": f"Add '{related_list}' related list to page layout",
            "manual_steps": [
                f"1. Go to Setup → Object Manager → {object_name or 'Opportunity'} → Page Layouts",
                "2. Click on the layout being used (check Layout Assignment if unsure)",
                "3. Scroll to 'Related Lists' section",
                f"4. Drag '{related_list}' from the palette to Related Lists section",
                "5. Click 'Save'"
            ],
            "lightning_steps": [
                f"1. Go to the {object_name or 'Opportunity'} record page",
                "2. Click gear icon → Edit Page",
                "3. Add 'Related List - Single' component",
                f"4. Configure it to show '{related_list}'",
                "5. Save and Activate"
            ]
        })

    # ==========================================================================
    # QA SCENARIO #10: Missing count on related list
    # ==========================================================================
    elif scenario_id == 10 or "count" in description.lower() and "missing" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "Related List Count Not Displayed",
            "explanation": "The record count is not configured to display on the related list component.",
            "severity": "low",
            "qa_scenario": 10
        })
        diagnosis["recommendations"].append({
            "priority": 1,
            "action": "Configure Related List component to show count",
            "lightning_steps": [
                "1. Go to the record page in Lightning",
                "2. Click gear icon → Edit Page",
                "3. Click on the Related List component",
                "4. In the properties panel, enable 'Show row count'",
                "5. Save and Activate"
            ]
        })

    # ==========================================================================
    # QA SCENARIO #15: Missing fields on related details
    # ==========================================================================
    elif scenario_id == 15 or "missing" in description.lower() and "field" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "Fields Missing from Related Record Component",
            "explanation": "The Related Record component is not configured to display the required fields.",
            "severity": "medium",
            "qa_scenario": 15
        })
        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Configure Related Record component fields",
                "lightning_steps": [
                    "1. Go to the record page in Lightning",
                    "2. Click gear icon → Edit Page",
                    "3. Click on the Related Record component",
                    "4. Configure 'Fields to Display'",
                    "5. Add the missing fields (Rating, Partner Type, etc.)",
                    "6. Save and Activate"
                ]
            },
            {
                "priority": 2,
                "action": "Check Field-Level Security",
                "details": "Ensure the user's profile has read access to these fields"
            }
        ])

    # Generic missing/not visible handling
    elif "missing" in description.lower() or "not visible" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "Component Not on Layout",
            "explanation": "The requested component is not added to the page layout",
            "severity": "medium"
        })
        diagnosis["recommendations"].append({
            "priority": 1,
            "action": "Add component to page layout",
            "details": f"Setup → Object Manager → {object_name} → Page Layouts → Add component"
        })

    return diagnosis


# =============================================================================
# REPORT DIAGNOSTICS
# =============================================================================

def _diagnose_report_issue(_sf, description: str, object_name: Optional[str], field_name: Optional[str], _auto_fix: bool, _detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Diagnose report field issues.

    Handles QA Scenarios:
    - #22: Field not visible in reports (e.g., Rating field in Account reports)
    """
    diagnosis = {
        "issue_type": "report",
        "object": object_name,
        "field_name": field_name,
        "description": description,
        "root_causes": [],
        "recommendations": []
    }

    if "field is not visible" in description.lower() or "missing" in description.lower():
        diagnosis["root_causes"].append({
            "cause": "Field Not Available in Reports",
            "explanation": "Field may not be visible due to FLS or field settings",
            "severity": "medium"
        })
        diagnosis["recommendations"].extend([
            {
                "priority": 1,
                "action": "Check field-level security for report runner's profile"
            },
            {
                "priority": 2,
                "action": "Verify field is not hidden from reports",
                "details": "Some formula fields can be set to 'Hidden' in reports"
            }
        ])

    return diagnosis


# =============================================================================
# GENERIC DIAGNOSIS
# =============================================================================

def _generic_diagnosis(sf, issue_type: str, description: str, object_name: Optional[str], field_name: Optional[str], component_name: Optional[str], detected_scenario: Optional[Dict] = None) -> Dict[str, Any]:
    """Generic diagnosis for unknown issue types"""
    return {
        "issue_type": issue_type,
        "description": description,
        "object": object_name,
        "field": field_name,
        "component": component_name,
        "root_causes": [{
            "cause": "Unknown Issue Type",
            "explanation": f"Issue type '{issue_type}' is not specifically handled. Provide more details or use: trigger, flow, validation, field, permission, formula, picklist, lookup, layout, report"
        }],
        "recommendations": [{
            "priority": 1,
            "action": "Use more specific issue_type",
            "supported_types": ["trigger", "flow", "validation", "field", "permission", "formula", "picklist", "lookup", "layout", "report"]
        }]
    }
