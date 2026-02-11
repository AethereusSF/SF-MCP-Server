"""
User Management Tools for Salesforce MCP Server
Handles user profile changes and permission set assignments

Created by Sameer
"""
import json
from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection

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


# DEPRECATED: Use consolidated tool instead
# @register_tool
def change_user_profile(username: str, profile_name: str) -> str:
    """
    Change a user's profile.

    Args:
        username: Salesforce username (email) of the user to update
        profile_name: Name of the profile to assign (e.g., "System Administrator", "Standard User")

    Returns:
        JSON response with operation status

    Example:
        change_user_profile(
            username="sameer.shrivastava@salesforce.com",
            profile_name="Standard User"
        )

    Common Profiles:
        - System Administrator
        - Standard User
        - Read Only
        - Minimum Access - Salesforce
        - Contract Manager
        - Marketing User
        - Solution Manager
        - Standard Platform User

    Added by Sameer
    """
    try:
        # Get Salesforce connection
        sf = get_salesforce_connection()

        # Find the user by username
        user_query = f"SELECT Id, Username, Name, ProfileId, Profile.Name FROM User WHERE Username = '{username}' LIMIT 1"
        user_result = sf.query(user_query)

        if not user_result.get('records'):
            return _create_json_response(
                False,
                error=f"User not found with username: {username}",
                suggestion="Check the username spelling and try again"
            )

        user = user_result['records'][0]
        current_profile = user['Profile']['Name']

        # Find the target profile by name
        profile_query = f"SELECT Id, Name FROM Profile WHERE Name = '{profile_name}' LIMIT 1"
        profile_result = sf.query(profile_query)

        if not profile_result.get('records'):
            return _create_json_response(
                False,
                error=f"Profile not found: {profile_name}",
                suggestion="Use one of the common profiles like 'System Administrator' or 'Standard User'"
            )

        profile = profile_result['records'][0]
        new_profile_id = profile['Id']

        # Check if user already has this profile
        if user['ProfileId'] == new_profile_id:
            return _create_json_response(
                True,
                message=f"User already has the '{profile_name}' profile",
                username=username,
                user_name=user['Name'],
                profile=profile_name,
                no_change_needed=True
            )

        # Update the user's profile
        result = sf.User.update(user['Id'], {'ProfileId': new_profile_id})

        return _create_json_response(
            True,
            message=f"Successfully changed user profile from '{current_profile}' to '{profile_name}'",
            username=username,
            user_name=user['Name'],
            user_id=user['Id'],
            old_profile=current_profile,
            new_profile=profile_name,
            profile_id=new_profile_id
        )

    except Exception as e:
        return _create_json_response(
            False,
            error=f"Failed to change user profile: {str(e)}"
        )


# DEPRECATED: Use consolidated tool instead
# @register_tool
def assign_permission_set(username: str, permission_set_name: str) -> str:
    """
    Assign a permission set to a user.

    Args:
        username: Salesforce username (email) of the user
        permission_set_name: API Name or Label of the permission set to assign

    Returns:
        JSON response with operation status

    Example:
        assign_permission_set(
            username="sameer.shrivastava@salesforce.com",
            permission_set_name="Advanced_User_Access"
        )

    Note: This function will check if the user already has the permission set
    before attempting to assign it.

    Added by Sameer
    """
    try:
        # Get Salesforce connection
        sf = get_salesforce_connection()

        # Find the user by username
        user_query = f"SELECT Id, Username, Name FROM User WHERE Username = '{username}' LIMIT 1"
        user_result = sf.query(user_query)

        if not user_result.get('records'):
            return _create_json_response(
                False,
                error=f"User not found with username: {username}",
                suggestion="Check the username spelling and try again"
            )

        user = user_result['records'][0]
        user_id = user['Id']

        # Find the permission set by Name or Label
        ps_query = f"""
        SELECT Id, Name, Label
        FROM PermissionSet
        WHERE Name = '{permission_set_name}' OR Label = '{permission_set_name}'
        LIMIT 1
        """
        ps_result = sf.query(ps_query)

        if not ps_result.get('records'):
            return _create_json_response(
                False,
                error=f"Permission set not found: {permission_set_name}",
                suggestion="Check the permission set name/label and try again"
            )

        permission_set = ps_result['records'][0]
        permission_set_id = permission_set['Id']

        # Check if user already has this permission set
        existing_query = f"""
        SELECT Id
        FROM PermissionSetAssignment
        WHERE AssigneeId = '{user_id}' AND PermissionSetId = '{permission_set_id}'
        LIMIT 1
        """
        existing_result = sf.query(existing_query)

        if existing_result.get('records'):
            return _create_json_response(
                True,
                message=f"User already has the '{permission_set['Label']}' permission set",
                username=username,
                user_name=user['Name'],
                permission_set_label=permission_set['Label'],
                permission_set_name=permission_set['Name'],
                already_assigned=True
            )

        # Create permission set assignment
        assignment_data = {
            'AssigneeId': user_id,
            'PermissionSetId': permission_set_id
        }

        result = sf.PermissionSetAssignment.create(assignment_data)

        return _create_json_response(
            True,
            message=f"Successfully assigned '{permission_set['Label']}' permission set to user",
            username=username,
            user_name=user['Name'],
            user_id=user_id,
            permission_set_label=permission_set['Label'],
            permission_set_name=permission_set['Name'],
            permission_set_id=permission_set_id,
            assignment_id=result.get('id')
        )

    except Exception as e:
        return _create_json_response(
            False,
            error=f"Failed to assign permission set: {str(e)}"
        )


# DEPRECATED: Use consolidated tool instead
# @register_tool
def remove_permission_set(username: str, permission_set_name: str) -> str:
    """
    Remove a permission set from a user.

    Args:
        username: Salesforce username (email) of the user
        permission_set_name: API Name or Label of the permission set to remove

    Returns:
        JSON response with operation status

    Example:
        remove_permission_set(
            username="sameer.shrivastava@salesforce.com",
            permission_set_name="Advanced_User_Access"
        )

    Added by Sameer
    """
    try:
        # Get Salesforce connection
        sf = get_salesforce_connection()

        # Find the user by username
        user_query = f"SELECT Id, Username, Name FROM User WHERE Username = '{username}' LIMIT 1"
        user_result = sf.query(user_query)

        if not user_result.get('records'):
            return _create_json_response(
                False,
                error=f"User not found with username: {username}",
                suggestion="Check the username spelling and try again"
            )

        user = user_result['records'][0]
        user_id = user['Id']

        # Find the permission set by Name or Label
        ps_query = f"""
        SELECT Id, Name, Label
        FROM PermissionSet
        WHERE Name = '{permission_set_name}' OR Label = '{permission_set_name}'
        LIMIT 1
        """
        ps_result = sf.query(ps_query)

        if not ps_result.get('records'):
            return _create_json_response(
                False,
                error=f"Permission set not found: {permission_set_name}",
                suggestion="Check the permission set name/label and try again"
            )

        permission_set = ps_result['records'][0]
        permission_set_id = permission_set['Id']

        # Find the permission set assignment
        assignment_query = f"""
        SELECT Id
        FROM PermissionSetAssignment
        WHERE AssigneeId = '{user_id}' AND PermissionSetId = '{permission_set_id}'
        LIMIT 1
        """
        assignment_result = sf.query(assignment_query)

        if not assignment_result.get('records'):
            return _create_json_response(
                True,
                message=f"User does not have the '{permission_set['Label']}' permission set",
                username=username,
                user_name=user['Name'],
                permission_set_label=permission_set['Label'],
                not_assigned=True
            )

        # Delete the permission set assignment
        assignment_id = assignment_result['records'][0]['Id']
        result = sf.PermissionSetAssignment.delete(assignment_id)

        return _create_json_response(
            True,
            message=f"Successfully removed '{permission_set['Label']}' permission set from user",
            username=username,
            user_name=user['Name'],
            user_id=user_id,
            permission_set_label=permission_set['Label'],
            permission_set_name=permission_set['Name'],
            removed=True
        )

    except Exception as e:
        return _create_json_response(
            False,
            error=f"Failed to remove permission set: {str(e)}"
        )


# DEPRECATED: Use consolidated tool instead
# @register_tool
def list_user_permissions(username: str) -> str:
    """
    List all permission sets assigned to a user.

    Args:
        username: Salesforce username (email) of the user

    Returns:
        JSON response with user's profile and permission sets

    Example:
        list_user_permissions(username="sameer.shrivastava@salesforce.com")

    Added by Sameer
    """
    try:
        # Get Salesforce connection
        sf = get_salesforce_connection()

        # Find the user by username
        user_query = f"""
        SELECT Id, Username, Name, Profile.Name, IsActive
        FROM User
        WHERE Username = '{username}'
        LIMIT 1
        """
        user_result = sf.query(user_query)

        if not user_result.get('records'):
            return _create_json_response(
                False,
                error=f"User not found with username: {username}",
                suggestion="Check the username spelling and try again"
            )

        user = user_result['records'][0]
        user_id = user['Id']

        # Get all permission sets assigned to the user
        ps_query = f"""
        SELECT PermissionSet.Id, PermissionSet.Name, PermissionSet.Label,
               PermissionSet.Description, PermissionSet.Type
        FROM PermissionSetAssignment
        WHERE AssigneeId = '{user_id}'
        ORDER BY PermissionSet.Label
        """
        ps_result = sf.query(ps_query)

        permission_sets = []
        for record in ps_result.get('records', []):
            ps_info = record['PermissionSet']
            # Skip profile-based permission sets (they're automatic)
            if ps_info['Type'] != 'Profile':
                permission_sets.append({
                    'label': ps_info['Label'],
                    'name': ps_info['Name'],
                    'description': ps_info.get('Description', ''),
                    'id': ps_info['Id']
                })

        return _create_json_response(
            True,
            username=username,
            user_name=user['Name'],
            user_id=user_id,
            profile=user['Profile']['Name'],
            is_active=user['IsActive'],
            permission_sets=permission_sets,
            permission_set_count=len(permission_sets)
        )

    except Exception as e:
        return _create_json_response(
            False,
            error=f"Failed to list user permissions: {str(e)}"
        )


@register_tool
def list_available_profiles() -> str:
    """
    List all available profiles in the org.

    Returns:
        JSON response with list of profiles

    Example:
        list_available_profiles()

    Added by Sameer
    """
    try:
        # Get Salesforce connection
        sf = get_salesforce_connection()

        # Get all profiles
        query = "SELECT Id, Name, UserType, Description FROM Profile ORDER BY Name"
        result = sf.query(query)

        profiles = []
        for record in result.get('records', []):
            profiles.append({
                'name': record['Name'],
                'user_type': record.get('UserType', ''),
                'description': record.get('Description', ''),
                'id': record['Id']
            })

        return _create_json_response(
            True,
            profiles=profiles,
            total_count=len(profiles)
        )

    except Exception as e:
        return _create_json_response(
            False,
            error=f"Failed to list profiles: {str(e)}"
        )


@register_tool
def list_available_permission_sets() -> str:
    """
    List all available permission sets in the org (excluding profile-based ones).

    Returns:
        JSON response with list of permission sets

    Example:
        list_available_permission_sets()

    Added by Sameer
    """
    try:
        # Get Salesforce connection
        sf = get_salesforce_connection()

        # Get all permission sets (excluding profile-based ones)
        query = """
        SELECT Id, Name, Label, Description, Type
        FROM PermissionSet
        WHERE Type != 'Profile'
        ORDER BY Label
        """
        result = sf.query(query)

        permission_sets = []
        for record in result.get('records', []):
            permission_sets.append({
                'label': record['Label'],
                'name': record['Name'],
                'description': record.get('Description', ''),
                'type': record.get('Type', ''),
                'id': record['Id']
            })

        return _create_json_response(
            True,
            permission_sets=permission_sets,
            total_count=len(permission_sets)
        )

    except Exception as e:
        return _create_json_response(
            False,
            error=f"Failed to list permission sets: {str(e)}"
        )
