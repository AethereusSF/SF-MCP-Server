"""Input validation utilities for Salesforce metadata and data operations

Created by Sameer

Enhanced with:
- SOQL injection protection
- Safe string escaping functions
- Query builder helpers
"""
import re
from typing import Optional, List, Dict, Any


class ValidationError(Exception):
    """Custom exception for validation errors

    Added by Sameer
    """
    pass


# =============================================================================
# SOQL INJECTION PROTECTION
# =============================================================================

def escape_soql_string(value: str) -> str:
    """
    Escape a string value for safe use in SOQL queries.
    Prevents SOQL injection attacks.

    Args:
        value: The string value to escape

    Returns:
        Escaped string safe for SOQL

    Example:
        name = escape_soql_string("O'Reilly")  # Returns: O\'Reilly
        query = f"SELECT Id FROM Account WHERE Name = '{name}'"
    """
    if value is None:
        return ""

    # Convert to string if not already
    value = str(value)

    # Escape single quotes by doubling them (SOQL standard)
    value = value.replace("'", "\\'")

    # Escape backslashes
    value = value.replace("\\", "\\\\")

    # Remove null bytes
    value = value.replace("\x00", "")

    # Remove other potentially dangerous characters
    value = value.replace("\n", " ").replace("\r", " ")

    return value


def escape_soql_like(value: str) -> str:
    """
    Escape a string for use in SOQL LIKE clauses.
    Escapes wildcard characters in addition to standard escaping.

    Args:
        value: The string value to escape for LIKE

    Returns:
        Escaped string safe for SOQL LIKE clause

    Example:
        pattern = escape_soql_like("50%")  # Returns: 50\%
        query = f"SELECT Id FROM Account WHERE Name LIKE '%{pattern}%'"
    """
    if value is None:
        return ""

    # First apply standard escaping
    value = escape_soql_string(value)

    # Escape LIKE wildcards
    value = value.replace("%", "\\%")
    value = value.replace("_", "\\_")

    return value


def build_safe_soql_in_clause(values: List[str]) -> str:
    """
    Build a safe IN clause for SOQL queries.

    Args:
        values: List of string values for IN clause

    Returns:
        Safe IN clause string like ('val1','val2','val3')

    Example:
        ids = ["001xx", "001yy"]
        in_clause = build_safe_soql_in_clause(ids)
        query = f"SELECT Id FROM Account WHERE Id IN {in_clause}"
    """
    if not values:
        return "()"

    escaped_values = [f"'{escape_soql_string(v)}'" for v in values]
    return f"({','.join(escaped_values)})"


def build_safe_where_clause(field: str, operator: str, value: Any) -> str:
    """
    Build a safe WHERE clause condition.

    Args:
        field: Field API name
        operator: SOQL operator (=, !=, LIKE, IN, >, <, >=, <=)
        value: Value to compare (string, number, list, or boolean)

    Returns:
        Safe WHERE clause condition

    Example:
        condition = build_safe_where_clause("Name", "LIKE", "Acme%")
        query = f"SELECT Id FROM Account WHERE {condition}"
    """
    # Validate field name to prevent injection
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_\.]*$', field):
        raise ValidationError(f"Invalid field name: {field}")

    # Validate operator
    valid_operators = ['=', '!=', '<>', 'LIKE', 'IN', 'NOT IN', '>', '<', '>=', '<=', 'INCLUDES', 'EXCLUDES']
    if operator.upper() not in valid_operators:
        raise ValidationError(f"Invalid operator: {operator}")

    operator = operator.upper()

    # Handle different value types
    if value is None:
        return f"{field} = null"

    elif isinstance(value, bool):
        return f"{field} {operator} {str(value).lower()}"

    elif isinstance(value, (int, float)):
        return f"{field} {operator} {value}"

    elif isinstance(value, list):
        if operator in ['IN', 'NOT IN']:
            in_clause = build_safe_soql_in_clause(value)
            return f"{field} {operator} {in_clause}"
        else:
            raise ValidationError(f"List values only supported with IN/NOT IN operators")

    else:
        # String value
        if operator == 'LIKE':
            escaped = escape_soql_string(str(value))  # Don't escape wildcards for LIKE
        else:
            escaped = escape_soql_string(str(value))
        return f"{field} {operator} '{escaped}'"


class SafeSOQLBuilder:
    """
    Builder class for constructing safe SOQL queries.

    Example:
        query = (SafeSOQLBuilder()
            .select(['Id', 'Name', 'Industry'])
            .from_object('Account')
            .where('Name', 'LIKE', 'Acme%')
            .where('Industry', '=', 'Technology')
            .order_by('Name')
            .limit(100)
            .build())
    """

    def __init__(self):
        self._select_fields: List[str] = []
        self._from_object: str = ""
        self._where_conditions: List[str] = []
        self._order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None

    def select(self, fields: List[str]) -> 'SafeSOQLBuilder':
        """Add SELECT fields"""
        for field in fields:
            # Validate field name
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_\.]*$', field):
                raise ValidationError(f"Invalid field name: {field}")
            self._select_fields.append(field)
        return self

    def from_object(self, obj: str) -> 'SafeSOQLBuilder':
        """Set FROM object"""
        # Validate object name
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*(__c|__mdt|__e|__b|__x|__r)?$', obj):
            raise ValidationError(f"Invalid object name: {obj}")
        self._from_object = obj
        return self

    def where(self, field: str, operator: str, value: Any) -> 'SafeSOQLBuilder':
        """Add WHERE condition"""
        condition = build_safe_where_clause(field, operator, value)
        self._where_conditions.append(condition)
        return self

    def where_raw(self, condition: str) -> 'SafeSOQLBuilder':
        """Add raw WHERE condition (use with caution - must be pre-escaped)"""
        self._where_conditions.append(condition)
        return self

    def order_by(self, field: str, direction: str = 'ASC') -> 'SafeSOQLBuilder':
        """Set ORDER BY"""
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_\.]*$', field):
            raise ValidationError(f"Invalid field name for ORDER BY: {field}")
        if direction.upper() not in ['ASC', 'DESC']:
            raise ValidationError(f"Invalid ORDER BY direction: {direction}")
        self._order_by = f"{field} {direction.upper()}"
        return self

    def limit(self, limit: int) -> 'SafeSOQLBuilder':
        """Set LIMIT"""
        if not isinstance(limit, int) or limit < 0:
            raise ValidationError(f"Invalid LIMIT value: {limit}")
        self._limit = limit
        return self

    def offset(self, offset: int) -> 'SafeSOQLBuilder':
        """Set OFFSET"""
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError(f"Invalid OFFSET value: {offset}")
        self._offset = offset
        return self

    def build(self) -> str:
        """Build the final SOQL query"""
        if not self._select_fields:
            raise ValidationError("No fields specified in SELECT")
        if not self._from_object:
            raise ValidationError("No object specified in FROM")

        query = f"SELECT {', '.join(self._select_fields)} FROM {self._from_object}"

        if self._where_conditions:
            query += f" WHERE {' AND '.join(self._where_conditions)}"

        if self._order_by:
            query += f" ORDER BY {self._order_by}"

        if self._limit is not None:
            query += f" LIMIT {self._limit}"

        if self._offset is not None:
            query += f" OFFSET {self._offset}"

        return query


def validate_api_name(name: str, metadata_type: str = "API") -> bool:
    """
    Validate Salesforce API name format.

    Added by Sameer

    Rules:
    - Must start with a letter
    - Can contain letters, numbers, underscores
    - Custom objects/fields must end with __c
    - Max 40 characters (80 for some types)
    - No special characters except underscore

    Args:
        name: API name to validate
        metadata_type: Type of metadata (for specific rules)

    Returns:
        True if valid

    Raises:
        ValidationError: If validation fails
    """
    if not name:
        raise ValidationError("API name cannot be empty")

    if len(name) > 80:
        raise ValidationError(f"API name too long (max 80 chars): {name}")

    # Check starts with letter
    if not re.match(r'^[a-zA-Z]', name):
        raise ValidationError(f"API name must start with a letter: {name}")

    # Check valid characters
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*(__c|__mdt|__e|__b|__x|__kav|__ka|__Feed|__Share|__History|__Tag)?$', name):
        raise ValidationError(
            f"API name contains invalid characters (only letters, numbers, underscore allowed): {name}"
        )

    return True


def validate_object_name(name: str) -> bool:
    """
    Validate custom object API name.

    Added by Sameer

    Args:
        name: Object API name

    Returns:
        True if valid

    Raises:
        ValidationError: If validation fails
    """
    validate_api_name(name, "CustomObject")

    # Custom objects must end with __c or __mdt
    if not any(name.endswith(suffix) for suffix in ['__c', '__mdt', '__e', '__b', '__x']):
        # Check if it's a standard object (acceptable)
        standard_objects = ['Account', 'Contact', 'Lead', 'Opportunity', 'Case', 'User', 'Task', 'Event']
        if name not in standard_objects:
            raise ValidationError(
                f"Custom object name must end with __c, __mdt, __e, __b, or __x: {name}"
            )

    return True


def validate_field_name(name: str) -> bool:
    """
    Validate field API name.

    Added by Sameer

    Args:
        name: Field API name

    Returns:
        True if valid

    Raises:
        ValidationError: If validation fails
    """
    validate_api_name(name, "CustomField")

    # Custom fields usually end with __c
    if not name.endswith('__c') and '__' not in name:
        # Could be a standard field, which is acceptable
        pass

    return True


def validate_soql_query(query: str) -> bool:
    """
    Basic SOQL injection prevention and validation.

    Added by Sameer

    Args:
        query: SOQL query string

    Returns:
        True if safe

    Raises:
        ValidationError: If potentially unsafe
    """
    if not query:
        raise ValidationError("SOQL query cannot be empty")

    query_upper = query.upper().strip()

    # Must start with SELECT
    if not query_upper.startswith('SELECT'):
        raise ValidationError("SOQL query must start with SELECT")

    # Block potentially dangerous operations
    dangerous_patterns = [
        '--',  # SQL comments
        '/*',  # Multi-line comments
        ';',   # Multiple statements
        'EXEC',
        'EXECUTE',
        'DROP',
        'DELETE FROM',  # Should use DML API
        'UPDATE ',  # Should use DML API
        'INSERT ',  # Should use DML API
    ]

    for pattern in dangerous_patterns:
        if pattern in query_upper:
            raise ValidationError(f"SOQL query contains potentially dangerous pattern: {pattern}")

    # Check balanced parentheses
    if query.count('(') != query.count(')'):
        raise ValidationError("SOQL query has unbalanced parentheses")

    return True


def validate_email(email: str) -> bool:
    """
    Validate email address format.

    Added by Sameer

    Args:
        email: Email address

    Returns:
        True if valid format

    Raises:
        ValidationError: If invalid
    """
    if not email:
        raise ValidationError("Email cannot be empty")

    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email format: {email}")

    return True


def validate_url(url: str, require_https: bool = False) -> bool:
    """
    Validate URL format.

    Added by Sameer

    Args:
        url: URL to validate
        require_https: Require HTTPS protocol

    Returns:
        True if valid

    Raises:
        ValidationError: If invalid
    """
    if not url:
        raise ValidationError("URL cannot be empty")

    if require_https and not url.startswith('https://'):
        raise ValidationError(f"URL must use HTTPS: {url}")

    if not url.startswith(('http://', 'https://')):
        raise ValidationError(f"URL must start with http:// or https://: {url}")

    return True


def sanitize_metadata_name(name: str) -> str:
    """
    Sanitize metadata name by removing/replacing invalid characters.

    Added by Sameer

    Args:
        name: Raw name input

    Returns:
        Sanitized name safe for Salesforce API
    """
    # Remove leading/trailing whitespace
    name = name.strip()

    # Replace spaces with underscores
    name = name.replace(' ', '_')

    # Remove any characters that aren't alphanumeric or underscore
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)

    # Ensure starts with letter
    if name and not name[0].isalpha():
        name = 'A_' + name

    return name


def validate_label_length(label: str, max_length: int = 40) -> bool:
    """
    Validate label length for Salesforce metadata.

    Added by Sameer

    Args:
        label: Label text
        max_length: Maximum allowed length

    Returns:
        True if valid

    Raises:
        ValidationError: If too long
    """
    if len(label) > max_length:
        raise ValidationError(f"Label too long (max {max_length} chars): {label} ({len(label)} chars)")

    return True


def validate_description_length(description: str, max_length: int = 1000) -> bool:
    """
    Validate description length.

    Added by Sameer

    Args:
        description: Description text
        max_length: Maximum allowed length

    Returns:
        True if valid

    Raises:
        ValidationError: If too long
    """
    if len(description) > max_length:
        raise ValidationError(
            f"Description too long (max {max_length} chars): {len(description)} chars"
        )

    return True
