"""
Advanced Comparison Tools for Salesforce MCP Server
Compares profiles, permission sets, objects, and fields across orgs

Created by Sameer
"""
import json
from typing import Dict, List, Set, Any
from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection
from app.mcp.tools.oauth_auth import get_stored_tokens

def _create_json_response(success, **kwargs):
    """Create guaranteed valid JSON response"""
    result = {"success": success}
    for key, value in kwargs.items():
        if value is None:
            result[key] = None
        elif isinstance(value, (str, int, float, bool)):
            result[key] = value
        elif isinstance(value, (list, dict)):
            result[key] = value
        else:
            result[key] = str(value)
    return json.dumps(result, indent=2)


@register_tool
def compare_profiles(profile1_name: str, profile2_name: str, org2_user_id: str = None) -> str:
    """
    Compare two Salesforce profiles and show their differences.

    Args:
        profile1_name: Name of first profile
        profile2_name: Name of second profile
        org2_user_id: Optional user ID for second org (if comparing across orgs)

    Returns:
        JSON response with detailed comparison

    Example:
        # Compare within same org
        compare_profiles(
            profile1_name="System Administrator",
            profile2_name="Standard User"
        )

        # Compare across orgs
        compare_profiles(
            profile1_name="System Administrator",
            profile2_name="System Administrator",
            org2_user_id="00D4x000000XyzE"
        )

    Added by Sameer
    """
    try:
        # Get first org connection
        sf1 = get_salesforce_connection()

        # Get second org connection if specified
        sf2 = get_salesforce_connection(org2_user_id) if org2_user_id else sf1

        # Query profile 1
        profile1_query = f"""
        SELECT Id, Name, Description, UserLicenseId, UserLicense.Name
        FROM Profile
        WHERE Name = '{profile1_name}'
        LIMIT 1
        """
        profile1_result = sf1.query(profile1_query)

        if not profile1_result.get('records'):
            return _create_json_response(False, error=f"Profile '{profile1_name}' not found in first org")

        profile1 = profile1_result['records'][0]

        # Query profile 2
        profile2_query = f"""
        SELECT Id, Name, Description, UserLicenseId, UserLicense.Name
        FROM Profile
        WHERE Name = '{profile2_name}'
        LIMIT 1
        """
        profile2_result = sf2.query(profile2_query)

        if not profile2_result.get('records'):
            return _create_json_response(False, error=f"Profile '{profile2_name}' not found in second org")

        profile2 = profile2_result['records'][0]

        # Get object permissions for profile 1
        obj_perms1_query = f"""
        SELECT SobjectType, PermissionsRead, PermissionsCreate, PermissionsEdit, PermissionsDelete, PermissionsViewAllRecords, PermissionsModifyAllRecords
        FROM ObjectPermissions
        WHERE ParentId = '{profile1['Id']}'
        """
        obj_perms1 = sf1.query(obj_perms1_query)['records']

        # Get object permissions for profile 2
        obj_perms2_query = f"""
        SELECT SobjectType, PermissionsRead, PermissionsCreate, PermissionsEdit, PermissionsDelete, PermissionsViewAllRecords, PermissionsModifyAllRecords
        FROM ObjectPermissions
        WHERE ParentId = '{profile2['Id']}'
        """
        obj_perms2 = sf2.query(obj_perms2_query)['records']

        # Create permission maps
        perms1_map = {p['SobjectType']: p for p in obj_perms1}
        perms2_map = {p['SobjectType']: p for p in obj_perms2}

        all_objects = set(perms1_map.keys()) | set(perms2_map.keys())

        # Compare permissions
        differences = []
        similarities = []
        only_in_profile1 = []
        only_in_profile2 = []

        for obj in sorted(all_objects):
            p1 = perms1_map.get(obj)
            p2 = perms2_map.get(obj)

            if p1 and not p2:
                only_in_profile1.append(obj)
            elif p2 and not p1:
                only_in_profile2.append(obj)
            elif p1 and p2:
                # Compare permissions
                perm_diff = {}
                for perm_field in ['PermissionsRead', 'PermissionsCreate', 'PermissionsEdit', 'PermissionsDelete', 'PermissionsViewAllRecords', 'PermissionsModifyAllRecords']:
                    if p1.get(perm_field) != p2.get(perm_field):
                        perm_diff[perm_field] = {
                            'profile1': p1.get(perm_field),
                            'profile2': p2.get(perm_field)
                        }

                if perm_diff:
                    differences.append({
                        'object': obj,
                        'differences': perm_diff
                    })
                else:
                    similarities.append(obj)

        return _create_json_response(
            True,
            profile1={
                'name': profile1['Name'],
                'license': profile1['UserLicense']['Name'],
                'description': profile1.get('Description', '')
            },
            profile2={
                'name': profile2['Name'],
                'license': profile2['UserLicense']['Name'],
                'description': profile2.get('Description', '')
            },
            comparison_summary={
                'total_objects_compared': len(all_objects),
                'objects_with_differences': len(differences),
                'objects_with_same_permissions': len(similarities),
                'only_in_profile1': len(only_in_profile1),
                'only_in_profile2': len(only_in_profile2)
            },
            objects_with_permission_differences=differences[:20],  # Limit to first 20
            objects_only_in_profile1=only_in_profile1[:10],
            objects_only_in_profile2=only_in_profile2[:10],
            objects_with_identical_permissions_count=len(similarities),
            cross_org_comparison=org2_user_id is not None
        )

    except Exception as e:
        return _create_json_response(False, error=f"Failed to compare profiles: {str(e)}")


@register_tool
def compare_permission_sets(permset1_name: str, permset2_name: str, org2_user_id: str = None) -> str:
    """
    Compare two permission sets and show their differences.

    Args:
        permset1_name: Name or Label of first permission set
        permset2_name: Name or Label of second permission set
        org2_user_id: Optional user ID for second org (if comparing across orgs)

    Returns:
        JSON response with detailed comparison

    Example:
        compare_permission_sets(
            permset1_name="API_User",
            permset2_name="Advanced_User"
        )

    Added by Sameer
    """
    try:
        sf1 = get_salesforce_connection()
        sf2 = get_salesforce_connection(org2_user_id) if org2_user_id else sf1

        # Find permission set 1
        ps1_query = f"""
        SELECT Id, Name, Label, Description
        FROM PermissionSet
        WHERE Name = '{permset1_name}' OR Label = '{permset1_name}'
        LIMIT 1
        """
        ps1_result = sf1.query(ps1_query)
        if not ps1_result.get('records'):
            return _create_json_response(False, error=f"Permission set '{permset1_name}' not found in first org")
        ps1 = ps1_result['records'][0]

        # Find permission set 2
        ps2_query = f"""
        SELECT Id, Name, Label, Description
        FROM PermissionSet
        WHERE Name = '{permset2_name}' OR Label = '{permset2_name}'
        LIMIT 1
        """
        ps2_result = sf2.query(ps2_query)
        if not ps2_result.get('records'):
            return _create_json_response(False, error=f"Permission set '{permset2_name}' not found in second org")
        ps2 = ps2_result['records'][0]

        # Get object permissions
        obj_perms1 = sf1.query(f"SELECT SobjectType, PermissionsRead, PermissionsCreate, PermissionsEdit, PermissionsDelete FROM ObjectPermissions WHERE ParentId = '{ps1['Id']}'")['records']
        obj_perms2 = sf2.query(f"SELECT SobjectType, PermissionsRead, PermissionsCreate, PermissionsEdit, PermissionsDelete FROM ObjectPermissions WHERE ParentId = '{ps2['Id']}'")['records']

        # Get field permissions
        field_perms1 = sf1.query(f"SELECT Field, PermissionsRead, PermissionsEdit FROM FieldPermissions WHERE ParentId = '{ps1['Id']}' LIMIT 200")['records']
        field_perms2 = sf2.query(f"SELECT Field, PermissionsRead, PermissionsEdit FROM FieldPermissions WHERE ParentId = '{ps2['Id']}' LIMIT 200")['records']

        # Get user permissions
        user_perms1_query = f"SELECT Id FROM PermissionSet WHERE Id = '{ps1['Id']}'"
        # Note: User permissions are stored as boolean fields on PermissionSet object

        # Compare object permissions
        perms1_map = {p['SobjectType']: p for p in obj_perms1}
        perms2_map = {p['SobjectType']: p for p in obj_perms2}
        all_objects = set(perms1_map.keys()) | set(perms2_map.keys())

        object_differences = []
        for obj in sorted(all_objects):
            p1 = perms1_map.get(obj)
            p2 = perms2_map.get(obj)
            if not p1 or not p2:
                object_differences.append({
                    'object': obj,
                    'in_permset1': p1 is not None,
                    'in_permset2': p2 is not None
                })

        # Compare field permissions
        fields1_map = {f['Field']: f for f in field_perms1}
        fields2_map = {f['Field']: f for f in field_perms2}
        all_fields = set(fields1_map.keys()) | set(fields2_map.keys())

        field_differences = []
        for field in sorted(all_fields):
            f1 = fields1_map.get(field)
            f2 = fields2_map.get(field)
            if not f1 or not f2 or f1.get('PermissionsRead') != f2.get('PermissionsRead') or f1.get('PermissionsEdit') != f2.get('PermissionsEdit'):
                field_differences.append({
                    'field': field,
                    'permset1_read': f1.get('PermissionsRead') if f1 else None,
                    'permset1_edit': f1.get('PermissionsEdit') if f1 else None,
                    'permset2_read': f2.get('PermissionsRead') if f2 else None,
                    'permset2_edit': f2.get('PermissionsEdit') if f2 else None
                })

        return _create_json_response(
            True,
            permset1={'name': ps1['Name'], 'label': ps1['Label'], 'description': ps1.get('Description', '')},
            permset2={'name': ps2['Name'], 'label': ps2['Label'], 'description': ps2.get('Description', '')},
            comparison_summary={
                'object_permissions_compared': len(all_objects),
                'object_differences': len(object_differences),
                'field_permissions_compared': len(all_fields),
                'field_differences': len(field_differences)
            },
            object_permission_differences=object_differences[:20],
            field_permission_differences=field_differences[:30],
            cross_org_comparison=org2_user_id is not None
        )

    except Exception as e:
        return _create_json_response(False, error=f"Failed to compare permission sets: {str(e)}")


@register_tool
def compare_object_field_counts(object_name: str, org2_user_id: str = None) -> str:
    """
    Compare field counts and field details for an object between same or different orgs.

    Args:
        object_name: API name of the object (e.g., 'Account', 'CustomObject__c')
        org2_user_id: Optional user ID for second org (if comparing across orgs)

    Returns:
        JSON response with field comparison

    Example:
        # Compare within same org against standard
        compare_object_field_counts(object_name="Account")

        # Compare across orgs
        compare_object_field_counts(
            object_name="Account",
            org2_user_id="00D4x000000XyzE"
        )

    Added by Sameer
    """
    try:
        sf1 = get_salesforce_connection()
        sf2 = get_salesforce_connection(org2_user_id) if org2_user_id else sf1

        # Get object description from org 1
        try:
            obj1 = getattr(sf1, object_name).describe()
        except Exception as e:
            return _create_json_response(False, error=f"Object '{object_name}' not found in first org: {str(e)}")

        # Get object description from org 2
        try:
            obj2 = getattr(sf2, object_name).describe()
        except Exception as e:
            return _create_json_response(False, error=f"Object '{object_name}' not found in second org: {str(e)}")

        # Get field names
        fields1 = {f['name']: f for f in obj1['fields']}
        fields2 = {f['name']: f for f in obj2['fields']}

        all_field_names = set(fields1.keys()) | set(fields2.keys())

        # Compare fields
        only_in_org1 = []
        only_in_org2 = []
        in_both = []
        type_differences = []

        for field_name in sorted(all_field_names):
            f1 = fields1.get(field_name)
            f2 = fields2.get(field_name)

            if f1 and not f2:
                only_in_org1.append({
                    'name': field_name,
                    'type': f1['type'],
                    'label': f1['label'],
                    'custom': f1['custom']
                })
            elif f2 and not f1:
                only_in_org2.append({
                    'name': field_name,
                    'type': f2['type'],
                    'label': f2['label'],
                    'custom': f2['custom']
                })
            elif f1 and f2:
                in_both.append(field_name)
                if f1['type'] != f2['type']:
                    type_differences.append({
                        'field': field_name,
                        'org1_type': f1['type'],
                        'org2_type': f2['type']
                    })

        # Count field types in each org
        org1_types = {}
        org2_types = {}
        for f in fields1.values():
            org1_types[f['type']] = org1_types.get(f['type'], 0) + 1
        for f in fields2.values():
            org2_types[f['type']] = org2_types.get(f['type'], 0) + 1

        return _create_json_response(
            True,
            object_name=object_name,
            org1_stats={
                'total_fields': len(fields1),
                'custom_fields': sum(1 for f in fields1.values() if f['custom']),
                'standard_fields': sum(1 for f in fields1.values() if not f['custom']),
                'field_types': org1_types
            },
            org2_stats={
                'total_fields': len(fields2),
                'custom_fields': sum(1 for f in fields2.values() if f['custom']),
                'standard_fields': sum(1 for f in fields2.values() if not f['custom']),
                'field_types': org2_types
            },
            comparison_summary={
                'fields_in_both': len(in_both),
                'fields_only_in_org1': len(only_in_org1),
                'fields_only_in_org2': len(only_in_org2),
                'fields_with_type_differences': len(type_differences)
            },
            fields_only_in_org1=only_in_org1[:20],
            fields_only_in_org2=only_in_org2[:20],
            fields_with_type_differences=type_differences,
            common_fields_sample=in_both[:20],
            cross_org_comparison=org2_user_id is not None
        )

    except Exception as e:
        return _create_json_response(False, error=f"Failed to compare object fields: {str(e)}")


@register_tool
def find_similar_fields_across_objects(object1_name: str, object2_name: str, org2_user_id: str = None) -> str:
    """
    Find similar or matching fields between two different objects.

    Args:
        object1_name: First object API name
        object2_name: Second object API name
        org2_user_id: Optional user ID if second object is in different org

    Returns:
        JSON response with field similarities

    Example:
        # Compare Account and Contact fields
        find_similar_fields_across_objects(
            object1_name="Account",
            object2_name="Contact"
        )

        # Compare custom objects across orgs
        find_similar_fields_across_objects(
            object1_name="CustomObject1__c",
            object2_name="CustomObject2__c",
            org2_user_id="00D4x000000XyzE"
        )

    Added by Sameer
    """
    try:
        sf1 = get_salesforce_connection()
        sf2 = get_salesforce_connection(org2_user_id) if org2_user_id else sf1

        # Get object descriptions
        obj1 = getattr(sf1, object1_name).describe()
        obj2 = getattr(sf2, object2_name).describe()

        fields1 = {f['name']: f for f in obj1['fields']}
        fields2 = {f['name']: f for f in obj2['fields']}

        # Find exact name matches
        exact_matches = []
        for name in set(fields1.keys()) & set(fields2.keys()):
            f1 = fields1[name]
            f2 = fields2[name]
            exact_matches.append({
                'field_name': name,
                'obj1_label': f1['label'],
                'obj2_label': f2['label'],
                'obj1_type': f1['type'],
                'obj2_type': f2['type'],
                'same_type': f1['type'] == f2['type'],
                'both_custom': f1['custom'] and f2['custom']
            })

        # Find similar labels (fuzzy matching)
        label_similarities = []
        for name1, f1 in fields1.items():
            label1_lower = f1['label'].lower()
            for name2, f2 in fields2.items():
                label2_lower = f2['label'].lower()
                # Check if labels are similar (not exact name match)
                if name1 != name2:
                    if label1_lower == label2_lower:
                        label_similarities.append({
                            'obj1_field': name1,
                            'obj1_label': f1['label'],
                            'obj1_type': f1['type'],
                            'obj2_field': name2,
                            'obj2_label': f2['label'],
                            'obj2_type': f2['type'],
                            'match_type': 'exact_label'
                        })
                    elif label1_lower in label2_lower or label2_lower in label1_lower:
                        label_similarities.append({
                            'obj1_field': name1,
                            'obj1_label': f1['label'],
                            'obj1_type': f1['type'],
                            'obj2_field': name2,
                            'obj2_label': f2['label'],
                            'obj2_type': f2['type'],
                            'match_type': 'partial_label'
                        })

        # Find fields with same type
        type_matches = {}
        for f1 in fields1.values():
            field_type = f1['type']
            if field_type not in type_matches:
                type_matches[field_type] = {'obj1': [], 'obj2': []}
            type_matches[field_type]['obj1'].append(f1['name'])

        for f2 in fields2.values():
            field_type = f2['type']
            if field_type not in type_matches:
                type_matches[field_type] = {'obj1': [], 'obj2': []}
            type_matches[field_type]['obj2'].append(f2['name'])

        return _create_json_response(
            True,
            object1=object1_name,
            object2=object2_name,
            exact_name_matches={
                'count': len(exact_matches),
                'fields': exact_matches[:30]
            },
            similar_labels={
                'count': len(label_similarities),
                'matches': label_similarities[:20]
            },
            type_distribution={
                field_type: {
                    'obj1_count': len(data['obj1']),
                    'obj2_count': len(data['obj2'])
                }
                for field_type, data in type_matches.items()
                if data['obj1'] or data['obj2']
            },
            cross_org_comparison=org2_user_id is not None
        )

    except Exception as e:
        return _create_json_response(False, error=f"Failed to find similar fields: {str(e)}")


@register_tool
def compare_org_object_counts(org2_user_id: str = None) -> str:
    """
    Compare total object counts and types between two orgs.

    Args:
        org2_user_id: Optional user ID for second org (compares first org with itself if not provided)

    Returns:
        JSON response with object count comparison

    Example:
        # Compare two different orgs
        compare_org_object_counts(org2_user_id="00D4x000000XyzE")

    Added by Sameer
    """
    try:
        sf1 = get_salesforce_connection()
        sf2 = get_salesforce_connection(org2_user_id) if org2_user_id else sf1

        # Get all objects from both orgs
        global_describe1 = sf1.describe()
        global_describe2 = sf2.describe()

        objects1 = {obj['name']: obj for obj in global_describe1['sobjects']}
        objects2 = {obj['name']: obj for obj in global_describe2['sobjects']}

        # Categorize objects
        def categorize_objects(objects_dict):
            custom = []
            standard = []
            custom_metadata = []
            custom_settings = []

            for name, obj in objects_dict.items():
                if name.endswith('__mdt'):
                    custom_metadata.append(name)
                elif name.endswith('__c'):
                    if obj.get('customSetting'):
                        custom_settings.append(name)
                    else:
                        custom.append(name)
                else:
                    standard.append(name)

            return {
                'custom': custom,
                'standard': standard,
                'custom_metadata': custom_metadata,
                'custom_settings': custom_settings
            }

        org1_categories = categorize_objects(objects1)
        org2_categories = categorize_objects(objects2)

        # Find differences
        all_object_names = set(objects1.keys()) | set(objects2.keys())
        only_in_org1 = [name for name in all_object_names if name in objects1 and name not in objects2]
        only_in_org2 = [name for name in all_object_names if name in objects2 and name not in objects1]
        in_both = [name for name in all_object_names if name in objects1 and name in objects2]

        return _create_json_response(
            True,
            org1_summary={
                'total_objects': len(objects1),
                'custom_objects': len(org1_categories['custom']),
                'standard_objects': len(org1_categories['standard']),
                'custom_metadata_types': len(org1_categories['custom_metadata']),
                'custom_settings': len(org1_categories['custom_settings'])
            },
            org2_summary={
                'total_objects': len(objects2),
                'custom_objects': len(org2_categories['custom']),
                'standard_objects': len(org2_categories['standard']),
                'custom_metadata_types': len(org2_categories['custom_metadata']),
                'custom_settings': len(org2_categories['custom_settings'])
            },
            comparison_summary={
                'objects_in_both': len(in_both),
                'objects_only_in_org1': len(only_in_org1),
                'objects_only_in_org2': len(only_in_org2)
            },
            objects_only_in_org1=only_in_org1[:30],
            objects_only_in_org2=only_in_org2[:30],
            common_custom_objects=[
                name for name in in_both
                if name in org1_categories['custom']
            ][:20],
            cross_org_comparison=org2_user_id is not None
        )

    except Exception as e:
        return _create_json_response(False, error=f"Failed to compare org objects: {str(e)}")
