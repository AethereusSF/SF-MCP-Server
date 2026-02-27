"""Utility modules for Salesforce MCP Server

Created by Sameer
"""
from app.utils.cache import (
    get_cache,
    cached,
    cache_object_metadata,
    get_cached_object_metadata,
    cache_field_definitions,
    get_cached_field_definitions,
    cache_validation_rules,
    get_cached_validation_rules,
    invalidate_object_cache,
)

from app.utils.validators import (
    ValidationError,
    escape_soql_string,
    escape_soql_like,
    build_safe_soql_in_clause,
    build_safe_where_clause,
    SafeSOQLBuilder,
    validate_api_name,
    validate_soql_query,
    sanitize_metadata_name,
)

from app.utils.errors import (
    ErrorCategory,
    SalesforceError,
    enhance_error_message,
    create_error_response,
    handle_authentication_error,
    handle_query_error,
    handle_deployment_error,
    handle_bulk_operation_error,
    log_and_return_error,
)

from app.utils.pagination import (
    PaginationInfo,
    PaginatedResponse,
    paginate_list,
    paginate_from_cursor,
    create_paginated_response,
    encode_cursor,
    decode_cursor,
    add_pagination_to_soql,
    paginated_query_response,
    paginated_metadata_response,
)

from app.utils.connection_pool import (
    ConnectionPool,
    ConnectionState,
    get_connection_pool,
    get_pooled_connection,
    release_pooled_connection,
    update_pooled_connection,
    remove_pooled_connection,
    get_pool_stats,
    cleanup_pool,
)

__all__ = [
    # Cache
    'get_cache',
    'cached',
    'cache_object_metadata',
    'get_cached_object_metadata',
    'cache_field_definitions',
    'get_cached_field_definitions',
    'cache_validation_rules',
    'get_cached_validation_rules',
    'invalidate_object_cache',
    # Validators
    'ValidationError',
    'escape_soql_string',
    'escape_soql_like',
    'build_safe_soql_in_clause',
    'build_safe_where_clause',
    'SafeSOQLBuilder',
    'validate_api_name',
    'validate_soql_query',
    'sanitize_metadata_name',
    # Error Handling
    'ErrorCategory',
    'SalesforceError',
    'enhance_error_message',
    'create_error_response',
    'handle_authentication_error',
    'handle_query_error',
    'handle_deployment_error',
    'handle_bulk_operation_error',
    'log_and_return_error',
    # Pagination
    'PaginationInfo',
    'PaginatedResponse',
    'paginate_list',
    'paginate_from_cursor',
    'create_paginated_response',
    'encode_cursor',
    'decode_cursor',
    'add_pagination_to_soql',
    'paginated_query_response',
    'paginated_metadata_response',
    # Connection Pool
    'ConnectionPool',
    'ConnectionState',
    'get_connection_pool',
    'get_pooled_connection',
    'release_pooled_connection',
    'update_pooled_connection',
    'remove_pooled_connection',
    'get_pool_stats',
    'cleanup_pool',
]
