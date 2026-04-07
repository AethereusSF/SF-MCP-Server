"""
Advanced Comparison Tools for Salesforce MCP Server
Compares profiles, permission sets, objects, and fields across orgs

Created by Sameer
"""
import json
import logging
from typing import Dict, List, Set, Any, Optional
from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection
from app.mcp.tools.oauth_auth import get_stored_tokens
from app.utils.validators import escape_soql_string

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _query_all(sf, query: str) -> List[Dict]:
    """Execute SOQL and follow every nextRecordsUrl page — returns all records."""
    result = sf.query(query)
    records = list(result.get('records', []))
    while not result.get('done', True) and result.get('nextRecordsUrl'):
        result = sf.query_more(result['nextRecordsUrl'], identifier_is_url=True)
        records.extend(result.get('records', []))
    return records


def _get_system_perm_fields(sf) -> List[str]:
    """Return every boolean Permissions* field name on the PermissionSet object."""
    try:
        desc = sf.PermissionSet.describe()
        return [f['name'] for f in desc['fields']
                if f['name'].startswith('Permissions') and f['type'] == 'boolean']
    except Exception:
        logger.debug("Could not describe PermissionSet", exc_info=True)
        return []


def _get_system_permissions(sf, parent_id: str) -> Dict[str, bool]:
    """Query all system permission boolean fields for a Profile/PermissionSet id."""
    fields = _get_system_perm_fields(sf)
    if not fields:
        return {}
    result: Dict[str, bool] = {}
    safe_id = escape_soql_string(parent_id)
    # SOQL SELECT has no hard cap on columns but batching at 150 keeps query strings safe
    for i in range(0, len(fields), 150):
        batch = fields[i:i + 150]
        q = f"SELECT {', '.join(batch)} FROM PermissionSet WHERE Id = '{safe_id}' LIMIT 1"
        try:
            recs = sf.query(q).get('records', [])
            if recs:
                result.update({k: v for k, v in recs[0].items()
                                if k.startswith('Permissions') and isinstance(v, bool)})
        except Exception:
            logger.debug("Batch system-perm query failed (batch %d)", i, exc_info=True)
    return result


def _get_permset_id_for_profile(sf, profile_id: str) -> str:
    """Return the PermissionSet.Id that backs a Profile (IsOwnedByProfile=true).
    SetupEntityAccess and PermissionSetTabSetting require the PermissionSet Id,
    not the Profile Id."""
    safe_id = escape_soql_string(profile_id)
    q = (f"SELECT Id FROM PermissionSet "
         f"WHERE ProfileId = '{safe_id}' AND IsOwnedByProfile = true LIMIT 1")
    try:
        recs = sf.query(q).get('records', [])
        return recs[0]['Id'] if recs else profile_id
    except Exception:
        logger.debug("Could not resolve PermissionSet for profile %s", profile_id, exc_info=True)
        return profile_id


def _get_tab_settings(sf, parent_id: str) -> Dict[str, str]:
    """Return {tab_name: visibility} for a Profile/PermissionSet.
    parent_id must be the PermissionSet.Id (not Profile.Id) for profiles."""
    safe_id = escape_soql_string(parent_id)
    q = f"SELECT Name, Visibility FROM PermissionSetTabSetting WHERE ParentId = '{safe_id}'"
    try:
        records = _query_all(sf, q)
        return {r['Name']: r['Visibility'] for r in records}
    except Exception:
        logger.debug("Tab settings query failed", exc_info=True)
        return {}


def _get_entity_access(sf, parent_id: str, entity_types: tuple = ('ApexClass', 'ApexPage', 'CustomPermission')) -> Dict[str, List[str]]:
    """Return {entity_type: [entity_names]} for enabled access on a Profile/PermissionSet.
    parent_id must be the PermissionSet.Id (not Profile.Id) for profiles."""
    safe_id = escape_soql_string(parent_id)
    types_in = ", ".join(f"'{t}'" for t in entity_types)
    q = (f"SELECT SetupEntityId, SetupEntityType FROM SetupEntityAccess "
         f"WHERE ParentId = '{safe_id}' AND SetupEntityType IN ({types_in})")
    result: Dict[str, List[str]] = {t: [] for t in entity_types}
    try:
        for r in _query_all(sf, q):
            t = r.get('SetupEntityType', '')
            if t in result:
                result[t].append(r['SetupEntityId'])
    except Exception:
        logger.debug("SetupEntityAccess query failed", exc_info=True)
    return result


def _resolve_entity_names(sf, ids: List[str], object_type: str) -> Dict[str, str]:
    """Batch-resolve {Id: DeveloperName/Name} for a list of Salesforce Ids.
    Batches in chunks of 200 to stay within SOQL query length limits."""
    if not ids:
        return {}
    # ApexClass and ApexPage use 'Name' in regular SOQL (DeveloperName is Tooling API only)
    # CustomPermission uses 'DeveloperName' via regular SOQL
    name_field = 'DeveloperName' if object_type == 'CustomPermission' else 'Name'
    from app.utils.validators import build_safe_soql_in_clause
    result: Dict[str, str] = {}
    for i in range(0, len(ids), 200):
        batch = ids[i:i + 200]
        in_clause = build_safe_soql_in_clause(batch)
        q = f"SELECT Id, {name_field} FROM {object_type} WHERE Id IN {in_clause}"
        try:
            records = _query_all(sf, q)
            result.update({r['Id']: r.get(name_field, r['Id']) for r in records})
        except Exception:
            logger.debug("Entity name resolution failed for %s (batch %d)", object_type, i, exc_info=True)
            result.update({eid: eid for eid in batch})
    return result


def _diff_dicts(d1: Dict, d2: Dict, key1: str = 'profile1', key2: str = 'profile2') -> List[Dict]:
    """Return list of {key, <key1>_value, <key2>_value} where values differ."""
    all_keys = set(d1) | set(d2)
    return [
        {'key': k, f'{key1}_value': d1.get(k), f'{key2}_value': d2.get(k)}
        for k in sorted(all_keys) if d1.get(k) != d2.get(k)
    ]


def _diff_sets(s1: set, s2: set, key1: str = 'profile1', key2: str = 'profile2') -> Dict:
    return {
        f'only_in_{key1}': sorted(s1 - s2),
        f'only_in_{key2}': sorted(s2 - s1),
        'in_both': sorted(s1 & s2),
    }

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
def compare_profiles(
    profile1_name: str,
    profile2_name: str,
    org2_user_id: str = None,
    sections: str = "all"
) -> str:
    """
    Compare two Salesforce profiles across all permission dimensions.

    Compares object permissions, field permissions, tab visibility, app/Apex/VF
    page access, and system (user) permissions. Fully paginated — works on large orgs
    with thousands of field permissions.

    Args:
        profile1_name: Name of first profile (e.g. "System Administrator")
        profile2_name: Name of second profile (e.g. "Standard User")
        org2_user_id: Optional user ID for second org (cross-org comparison)
        sections: Comma-separated list of sections to include.
                  Options: objects, fields, tabs, apps, system, all
                  Default: all

    Returns:
        JSON response with per-section diff results

    Example:
        # Full comparison
        compare_profiles("System Administrator", "Standard User")

        # Objects + fields only (faster)
        compare_profiles("System Administrator", "Standard User", sections="objects,fields")

        # Cross-org
        compare_profiles("Sales User", "Sales User", org2_user_id="005xx000001abc")
    """
    try:
        want = {s.strip().lower() for s in sections.split(',')}
        all_sections = want == {'all'}

        sf1 = get_salesforce_connection()
        sf2 = get_salesforce_connection(org2_user_id) if org2_user_id else sf1

        # ── Fetch profile records ──────────────────────────────────────────
        def _fetch_profile(sf, name):
            q = (f"SELECT Id, Name, Description, UserLicense.Name "
                 f"FROM Profile WHERE Name = '{escape_soql_string(name)}' LIMIT 1")
            recs = sf.query(q).get('records', [])
            return recs[0] if recs else None

        p1 = _fetch_profile(sf1, profile1_name)
        if not p1:
            return _create_json_response(False, error=f"Profile '{profile1_name}' not found")
        p2 = _fetch_profile(sf2, profile2_name)
        if not p2:
            return _create_json_response(False, error=f"Profile '{profile2_name}' not found")

        p1_id, p2_id = p1['Id'], p2['Id']
        # SetupEntityAccess and PermissionSetTabSetting require PermissionSet.Id,
        # not Profile.Id — resolve the backing PermissionSet for each profile.
        p1_ps_id = _get_permset_id_for_profile(sf1, p1_id)
        p2_ps_id = _get_permset_id_for_profile(sf2, p2_id)

        OBJ_PERM_FIELDS = ['PermissionsRead', 'PermissionsCreate', 'PermissionsEdit',
                           'PermissionsDelete', 'PermissionsViewAllRecords', 'PermissionsModifyAllRecords']

        response = {
            'profile1': {'name': p1['Name'],
                         'license': p1.get('UserLicense', {}).get('Name', ''),
                         'description': p1.get('Description', '')},
            'profile2': {'name': p2['Name'],
                         'license': p2.get('UserLicense', {}).get('Name', ''),
                         'description': p2.get('Description', '')},
            'cross_org_comparison': org2_user_id is not None,
            'sections_compared': sections,
        }

        # ── Object Permissions ────────────────────────────────────────────
        if all_sections or 'objects' in want:
            q_obj = ("SELECT SobjectType, PermissionsRead, PermissionsCreate, PermissionsEdit, "
                     "PermissionsDelete, PermissionsViewAllRecords, PermissionsModifyAllRecords "
                     "FROM ObjectPermissions WHERE ParentId = '{}'")
            op1 = {r['SobjectType']: r for r in _query_all(sf1, q_obj.format(escape_soql_string(p1_id)))}
            op2 = {r['SobjectType']: r for r in _query_all(sf2, q_obj.format(escape_soql_string(p2_id)))}
            all_objs = set(op1) | set(op2)
            obj_diffs, obj_same = [], []
            only_p1_objs, only_p2_objs = [], []
            for obj in sorted(all_objs):
                r1, r2 = op1.get(obj), op2.get(obj)
                if r1 and not r2:
                    only_p1_objs.append(obj)
                elif r2 and not r1:
                    only_p2_objs.append(obj)
                else:
                    diff = {f: {'profile1': r1.get(f), 'profile2': r2.get(f)}
                            for f in OBJ_PERM_FIELDS if r1.get(f) != r2.get(f)}
                    if diff:
                        obj_diffs.append({'object': obj, 'differences': diff})
                    else:
                        obj_same.append(obj)
            response['object_permissions'] = {
                'summary': {
                    'total': len(all_objs),
                    'with_differences': len(obj_diffs),
                    'identical': len(obj_same),
                    'only_in_profile1': len(only_p1_objs),
                    'only_in_profile2': len(only_p2_objs),
                },
                'differences': obj_diffs,
                'only_in_profile1': only_p1_objs,
                'only_in_profile2': only_p2_objs,
            }

        # ── Field Permissions ─────────────────────────────────────────────
        if all_sections or 'fields' in want:
            q_fp = ("SELECT Field, PermissionsRead, PermissionsEdit "
                    "FROM FieldPermissions WHERE ParentId = '{}'")
            fp1 = {r['Field']: r for r in _query_all(sf1, q_fp.format(escape_soql_string(p1_id)))}
            fp2 = {r['Field']: r for r in _query_all(sf2, q_fp.format(escape_soql_string(p2_id)))}
            all_fields = set(fp1) | set(fp2)
            field_diffs = []
            for field in sorted(all_fields):
                f1, f2 = fp1.get(field), fp2.get(field)
                p1_read  = f1.get('PermissionsRead',  False) if f1 else False
                p1_edit  = f1.get('PermissionsEdit',  False) if f1 else False
                p2_read  = f2.get('PermissionsRead',  False) if f2 else False
                p2_edit  = f2.get('PermissionsEdit',  False) if f2 else False
                if p1_read != p2_read or p1_edit != p2_edit:
                    field_diffs.append({
                        'field': field,
                        'profile1_read': p1_read, 'profile1_edit': p1_edit,
                        'profile2_read': p2_read, 'profile2_edit': p2_edit,
                    })
            response['field_permissions'] = {
                'summary': {
                    'total_fields': len(all_fields),
                    'fields_with_differences': len(field_diffs),
                },
                'differences': field_diffs,
            }

        # ── Tab Visibility ────────────────────────────────────────────────
        if all_sections or 'tabs' in want:
            tabs1 = _get_tab_settings(sf1, p1_ps_id)
            tabs2 = _get_tab_settings(sf2, p2_ps_id)
            all_tabs = set(tabs1) | set(tabs2)
            tab_diffs = [
                {'tab': t, 'profile1': tabs1.get(t, 'Hidden'), 'profile2': tabs2.get(t, 'Hidden')}
                for t in sorted(all_tabs) if tabs1.get(t, 'Hidden') != tabs2.get(t, 'Hidden')
            ]
            response['tab_visibility'] = {
                'summary': {
                    'total_tabs': len(all_tabs),
                    'tabs_with_differences': len(tab_diffs),
                },
                'differences': tab_diffs,
                'only_in_profile1': sorted(set(tabs1) - set(tabs2)),
                'only_in_profile2': sorted(set(tabs2) - set(tabs1)),
            }

        # ── App / Apex Class / VF Page / Custom Permission Access ─────────
        if all_sections or 'apps' in want:
            entity_types = ('ApexClass', 'ApexPage', 'CustomPermission')
            ea1 = _get_entity_access(sf1, p1_ps_id, entity_types)
            ea2 = _get_entity_access(sf2, p2_ps_id, entity_types)
            app_section = {}
            for etype in entity_types:
                ids1 = set(ea1.get(etype, []))
                ids2 = set(ea2.get(etype, []))
                # Resolve names per-org to avoid cross-org ID mismatches
                names1 = _resolve_entity_names(sf1, list(ids1), etype)
                names2 = _resolve_entity_names(sf2, list(ids2), etype)
                names1_set = set(names1.values())
                names2_set = set(names2.values())
                app_section[etype] = {
                    'only_in_profile1': sorted(names1_set - names2_set),
                    'only_in_profile2': sorted(names2_set - names1_set),
                    'in_both': sorted(names1_set & names2_set),
                    'in_both_count': len(names1_set & names2_set),
                    'only_in_profile1_count': len(names1_set - names2_set),
                    'only_in_profile2_count': len(names2_set - names1_set),
                }
            response['entity_access'] = app_section

        # ── System / User Permissions ─────────────────────────────────────
        if all_sections or 'system' in want:
            sys1 = _get_system_permissions(sf1, p1_id)
            sys2 = _get_system_permissions(sf2, p2_id)
            sys_diffs = _diff_dicts(sys1, sys2, 'profile1', 'profile2')
            response['system_permissions'] = {
                'summary': {
                    'total_permissions': len(set(sys1) | set(sys2)),
                    'permissions_with_differences': len(sys_diffs),
                    'profile1_enabled_count': sum(1 for v in sys1.values() if v),
                    'profile2_enabled_count': sum(1 for v in sys2.values() if v),
                },
                'differences': sys_diffs,
            }

        return _create_json_response(True, **response)

    except Exception as e:
        return _create_json_response(False, error=f"Failed to compare profiles: {str(e)}")


@register_tool
def compare_permission_sets(
    permset1_name: str,
    permset2_name: str,
    org2_user_id: str = None,
    sections: str = "all"
) -> str:
    """
    Compare two permission sets across all permission dimensions.

    Compares object permissions, field permissions, tab visibility, Apex class /
    VF page / custom permission access, and system user permissions.
    Fully paginated — no record count caps.

    Args:
        permset1_name: Name or Label of first permission set
        permset2_name: Name or Label of second permission set
        org2_user_id: Optional user ID for second org (cross-org comparison)
        sections: Comma-separated sections to include.
                  Options: objects, fields, tabs, apps, system, all
                  Default: all

    Returns:
        JSON response with per-section diff results

    Example:
        # Full comparison
        compare_permission_sets("API_User", "Advanced_User")

        # Fields + system permissions only
        compare_permission_sets("API_User", "Advanced_User", sections="fields,system")

        # Cross-org
        compare_permission_sets("Sales_PS", "Sales_PS", org2_user_id="005xx000001abc")
    """
    try:
        want = {s.strip().lower() for s in sections.split(',')}
        all_sections = want == {'all'}

        sf1 = get_salesforce_connection()
        sf2 = get_salesforce_connection(org2_user_id) if org2_user_id else sf1

        # ── Fetch permission sets ─────────────────────────────────────────
        def _fetch_ps(sf, name):
            n = escape_soql_string(name)
            q = (f"SELECT Id, Name, Label, Description FROM PermissionSet "
                 f"WHERE (Name = '{n}' OR Label = '{n}') AND IsOwnedByProfile = false LIMIT 1")
            recs = sf.query(q).get('records', [])
            return recs[0] if recs else None

        ps1 = _fetch_ps(sf1, permset1_name)
        if not ps1:
            return _create_json_response(False, error=f"Permission set '{permset1_name}' not found in first org")
        ps2 = _fetch_ps(sf2, permset2_name)
        if not ps2:
            return _create_json_response(False, error=f"Permission set '{permset2_name}' not found in second org")

        ps1_id, ps2_id = ps1['Id'], ps2['Id']
        OBJ_PERM_FIELDS = ['PermissionsRead', 'PermissionsCreate', 'PermissionsEdit',
                           'PermissionsDelete', 'PermissionsViewAllRecords', 'PermissionsModifyAllRecords']

        response = {
            'permset1': {'name': ps1['Name'], 'label': ps1['Label'], 'description': ps1.get('Description', '')},
            'permset2': {'name': ps2['Name'], 'label': ps2['Label'], 'description': ps2.get('Description', '')},
            'cross_org_comparison': org2_user_id is not None,
            'sections_compared': sections,
        }

        # ── Object Permissions ────────────────────────────────────────────
        if all_sections or 'objects' in want:
            q_obj = ("SELECT SobjectType, PermissionsRead, PermissionsCreate, PermissionsEdit, "
                     "PermissionsDelete, PermissionsViewAllRecords, PermissionsModifyAllRecords "
                     "FROM ObjectPermissions WHERE ParentId = '{}'")
            op1 = {r['SobjectType']: r for r in _query_all(sf1, q_obj.format(escape_soql_string(ps1_id)))}
            op2 = {r['SobjectType']: r for r in _query_all(sf2, q_obj.format(escape_soql_string(ps2_id)))}
            all_objs = set(op1) | set(op2)
            obj_diffs, only_ps1_objs, only_ps2_objs, same_count = [], [], [], 0
            for obj in sorted(all_objs):
                r1, r2 = op1.get(obj), op2.get(obj)
                if r1 and not r2:
                    only_ps1_objs.append(obj)
                elif r2 and not r1:
                    only_ps2_objs.append(obj)
                else:
                    diff = {f: {'permset1': r1.get(f), 'permset2': r2.get(f)}
                            for f in OBJ_PERM_FIELDS if r1.get(f) != r2.get(f)}
                    if diff:
                        obj_diffs.append({'object': obj, 'differences': diff})
                    else:
                        same_count += 1
            response['object_permissions'] = {
                'summary': {
                    'total': len(all_objs),
                    'with_differences': len(obj_diffs),
                    'identical': same_count,
                    'only_in_permset1': len(only_ps1_objs),
                    'only_in_permset2': len(only_ps2_objs),
                },
                'differences': obj_diffs,
                'only_in_permset1': only_ps1_objs,
                'only_in_permset2': only_ps2_objs,
            }

        # ── Field Permissions  (fully paginated — no LIMIT 200) ───────────
        if all_sections or 'fields' in want:
            q_fp = "SELECT Field, PermissionsRead, PermissionsEdit FROM FieldPermissions WHERE ParentId = '{}'"
            fp1 = {r['Field']: r for r in _query_all(sf1, q_fp.format(escape_soql_string(ps1_id)))}
            fp2 = {r['Field']: r for r in _query_all(sf2, q_fp.format(escape_soql_string(ps2_id)))}
            all_fields = set(fp1) | set(fp2)
            field_diffs = []
            for field in sorted(all_fields):
                f1, f2 = fp1.get(field), fp2.get(field)
                p1_read = f1.get('PermissionsRead',  False) if f1 else False
                p1_edit = f1.get('PermissionsEdit',  False) if f1 else False
                p2_read = f2.get('PermissionsRead',  False) if f2 else False
                p2_edit = f2.get('PermissionsEdit',  False) if f2 else False
                if p1_read != p2_read or p1_edit != p2_edit:
                    field_diffs.append({
                        'field': field,
                        'permset1_read': p1_read, 'permset1_edit': p1_edit,
                        'permset2_read': p2_read, 'permset2_edit': p2_edit,
                    })
            response['field_permissions'] = {
                'summary': {
                    'total_fields': len(all_fields),
                    'fields_with_differences': len(field_diffs),
                },
                'differences': field_diffs,
            }

        # ── Tab Visibility ────────────────────────────────────────────────
        if all_sections or 'tabs' in want:
            tabs1 = _get_tab_settings(sf1, ps1_id)
            tabs2 = _get_tab_settings(sf2, ps2_id)
            all_tabs = set(tabs1) | set(tabs2)
            tab_diffs = [
                {'tab': t, 'permset1': tabs1.get(t, 'Hidden'), 'permset2': tabs2.get(t, 'Hidden')}
                for t in sorted(all_tabs) if tabs1.get(t, 'Hidden') != tabs2.get(t, 'Hidden')
            ]
            response['tab_visibility'] = {
                'summary': {'total_tabs': len(all_tabs), 'tabs_with_differences': len(tab_diffs)},
                'differences': tab_diffs,
                'only_in_permset1': sorted(set(tabs1) - set(tabs2)),
                'only_in_permset2': sorted(set(tabs2) - set(tabs1)),
            }

        # ── App / Apex Class / VF Page / Custom Permission Access ─────────
        if all_sections or 'apps' in want:
            entity_types = ('ApexClass', 'ApexPage', 'CustomPermission')
            ea1 = _get_entity_access(sf1, ps1_id, entity_types)
            ea2 = _get_entity_access(sf2, ps2_id, entity_types)
            app_section = {}
            for etype in entity_types:
                ids1 = set(ea1.get(etype, []))
                ids2 = set(ea2.get(etype, []))
                # Resolve names per-org to avoid cross-org ID mismatches
                names1 = _resolve_entity_names(sf1, list(ids1), etype)
                names2 = _resolve_entity_names(sf2, list(ids2), etype)
                names1_set = set(names1.values())
                names2_set = set(names2.values())
                app_section[etype] = {
                    'only_in_permset1': sorted(names1_set - names2_set),
                    'only_in_permset2': sorted(names2_set - names1_set),
                    'in_both': sorted(names1_set & names2_set),
                    'in_both_count': len(names1_set & names2_set),
                    'only_in_permset1_count': len(names1_set - names2_set),
                    'only_in_permset2_count': len(names2_set - names1_set),
                }
            response['entity_access'] = app_section

        # ── System / User Permissions ─────────────────────────────────────
        if all_sections or 'system' in want:
            sys1 = _get_system_permissions(sf1, ps1_id)
            sys2 = _get_system_permissions(sf2, ps2_id)
            sys_diffs = _diff_dicts(sys1, sys2, 'permset1', 'permset2')
            response['system_permissions'] = {
                'summary': {
                    'total_permissions': len(set(sys1) | set(sys2)),
                    'permissions_with_differences': len(sys_diffs),
                    'permset1_enabled_count': sum(1 for v in sys1.values() if v),
                    'permset2_enabled_count': sum(1 for v in sys2.values() if v),
                },
                'differences': sys_diffs,
            }

        return _create_json_response(True, **response)

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
