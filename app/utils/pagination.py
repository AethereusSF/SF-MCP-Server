"""Response pagination utilities for Salesforce MCP Server.

Provides:
- Standardized pagination for large result sets
- Cursor-based and offset-based pagination support
- Automatic chunking for large responses
- Pagination metadata in responses

Created by Sameer
"""
import json
import base64
import logging
from typing import Any, Dict, List, Optional, TypeVar, Generic, Callable
from dataclasses import dataclass, asdict
from math import ceil

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class PaginationInfo:
    """Pagination metadata for responses"""
    total_records: int
    page_size: int
    current_page: int
    total_pages: int
    has_next: bool
    has_previous: bool
    next_cursor: Optional[str] = None
    previous_cursor: Optional[str] = None
    start_index: int = 0
    end_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            "total_records": self.total_records,
            "page_size": self.page_size,
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_previous": self.has_previous,
            "next_cursor": self.next_cursor,
            "previous_cursor": self.previous_cursor,
            "start_index": self.start_index,
            "end_index": self.end_index
        }


@dataclass
class PaginatedResponse(Generic[T]):
    """Paginated response wrapper"""
    success: bool
    data: List[T]
    pagination: PaginationInfo
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        result = {
            "success": self.success,
            "data": self.data,
            "pagination": self.pagination.to_dict()
        }
        if self.message:
            result["message"] = self.message
        return result

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, default=str)


# =============================================================================
# CURSOR UTILITIES
# =============================================================================

def encode_cursor(offset: int, page_size: int, extra_data: Optional[Dict] = None) -> str:
    """
    Encode pagination cursor.

    Args:
        offset: Current offset
        page_size: Page size
        extra_data: Optional additional data to encode

    Returns:
        Base64 encoded cursor string
    """
    cursor_data = {
        "o": offset,
        "p": page_size
    }
    if extra_data:
        cursor_data["e"] = extra_data

    cursor_json = json.dumps(cursor_data)
    return base64.urlsafe_b64encode(cursor_json.encode()).decode()


def decode_cursor(cursor: str) -> Dict[str, Any]:
    """
    Decode pagination cursor.

    Args:
        cursor: Base64 encoded cursor string

    Returns:
        Dictionary with offset, page_size, and extra_data
    """
    try:
        cursor_json = base64.urlsafe_b64decode(cursor.encode()).decode()
        cursor_data = json.loads(cursor_json)
        return {
            "offset": cursor_data.get("o", 0),
            "page_size": cursor_data.get("p", 100),
            "extra_data": cursor_data.get("e")
        }
    except Exception as e:
        logger.warning(f"Failed to decode cursor: {e}")
        return {"offset": 0, "page_size": 100, "extra_data": None}


# =============================================================================
# PAGINATION FUNCTIONS
# =============================================================================

def paginate_list(
    items: List[T],
    page: int = 1,
    page_size: int = 100,
    include_cursors: bool = True
) -> PaginatedResponse[T]:
    """
    Paginate a list of items.

    Args:
        items: List of items to paginate
        page: Page number (1-indexed)
        page_size: Number of items per page
        include_cursors: Whether to include cursor strings

    Returns:
        PaginatedResponse with paginated data
    """
    total_records = len(items)
    total_pages = ceil(total_records / page_size) if page_size > 0 else 1

    # Ensure valid page number
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1

    # Calculate indices
    start_index = (page - 1) * page_size
    end_index = min(start_index + page_size, total_records)

    # Get page data
    page_data = items[start_index:end_index]

    # Calculate pagination info
    has_next = page < total_pages
    has_previous = page > 1

    # Generate cursors
    next_cursor = None
    previous_cursor = None
    if include_cursors:
        if has_next:
            next_cursor = encode_cursor(end_index, page_size)
        if has_previous:
            prev_offset = max(0, start_index - page_size)
            previous_cursor = encode_cursor(prev_offset, page_size)

    pagination = PaginationInfo(
        total_records=total_records,
        page_size=page_size,
        current_page=page,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
        next_cursor=next_cursor,
        previous_cursor=previous_cursor,
        start_index=start_index,
        end_index=end_index
    )

    return PaginatedResponse(
        success=True,
        data=page_data,
        pagination=pagination
    )


def paginate_from_cursor(
    items: List[T],
    cursor: Optional[str] = None,
    page_size: int = 100
) -> PaginatedResponse[T]:
    """
    Paginate using cursor-based pagination.

    Args:
        items: List of items to paginate
        cursor: Optional cursor from previous response
        page_size: Number of items per page (used if no cursor)

    Returns:
        PaginatedResponse with paginated data
    """
    if cursor:
        cursor_data = decode_cursor(cursor)
        offset = cursor_data["offset"]
        page_size = cursor_data["page_size"]
    else:
        offset = 0

    total_records = len(items)
    end_index = min(offset + page_size, total_records)
    page_data = items[offset:end_index]

    # Calculate page number
    current_page = (offset // page_size) + 1 if page_size > 0 else 1
    total_pages = ceil(total_records / page_size) if page_size > 0 else 1

    has_next = end_index < total_records
    has_previous = offset > 0

    # Generate cursors
    next_cursor = encode_cursor(end_index, page_size) if has_next else None
    prev_offset = max(0, offset - page_size)
    previous_cursor = encode_cursor(prev_offset, page_size) if has_previous else None

    pagination = PaginationInfo(
        total_records=total_records,
        page_size=page_size,
        current_page=current_page,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
        next_cursor=next_cursor,
        previous_cursor=previous_cursor,
        start_index=offset,
        end_index=end_index
    )

    return PaginatedResponse(
        success=True,
        data=page_data,
        pagination=pagination
    )


def create_paginated_response(
    items: List[Any],
    page: int = 1,
    page_size: int = 100,
    cursor: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a JSON paginated response string.

    Args:
        items: List of items to paginate
        page: Page number (ignored if cursor provided)
        page_size: Number of items per page
        cursor: Optional cursor for cursor-based pagination
        extra_fields: Additional fields to include in response

    Returns:
        JSON string with paginated response
    """
    if cursor:
        response = paginate_from_cursor(items, cursor, page_size)
    else:
        response = paginate_list(items, page, page_size)

    result = response.to_dict()

    if extra_fields:
        result.update(extra_fields)

    return json.dumps(result, indent=2, default=str)


# =============================================================================
# SOQL PAGINATION HELPERS
# =============================================================================

def add_pagination_to_soql(
    query: str,
    limit: int = 100,
    offset: int = 0
) -> str:
    """
    Add LIMIT and OFFSET to a SOQL query if not present.

    Args:
        query: SOQL query string
        limit: Maximum records to return
        offset: Starting offset

    Returns:
        SOQL query with pagination clauses
    """
    query = query.strip()
    query_upper = query.upper()

    # Check if LIMIT already exists
    if " LIMIT " not in query_upper:
        query = f"{query} LIMIT {limit}"

    # Check if OFFSET already exists (only add if offset > 0)
    if offset > 0 and " OFFSET " not in query_upper:
        query = f"{query} OFFSET {offset}"

    return query


def extract_pagination_from_soql(query: str) -> Dict[str, int]:
    """
    Extract LIMIT and OFFSET values from a SOQL query.

    Args:
        query: SOQL query string

    Returns:
        Dictionary with limit and offset values
    """
    import re

    result = {"limit": None, "offset": 0}

    # Extract LIMIT
    limit_match = re.search(r'\bLIMIT\s+(\d+)', query, re.IGNORECASE)
    if limit_match:
        result["limit"] = int(limit_match.group(1))

    # Extract OFFSET
    offset_match = re.search(r'\bOFFSET\s+(\d+)', query, re.IGNORECASE)
    if offset_match:
        result["offset"] = int(offset_match.group(1))

    return result


def build_next_page_query(
    base_query: str,
    current_offset: int,
    page_size: int,
    total_available: Optional[int] = None
) -> Optional[str]:
    """
    Build the query for the next page of results.

    Args:
        base_query: Original SOQL query (without LIMIT/OFFSET)
        current_offset: Current offset
        page_size: Page size
        total_available: Total records available (optional)

    Returns:
        Next page query or None if no more pages
    """
    import re

    # Remove existing LIMIT and OFFSET
    clean_query = re.sub(r'\s+LIMIT\s+\d+', '', base_query, flags=re.IGNORECASE)
    clean_query = re.sub(r'\s+OFFSET\s+\d+', '', clean_query, flags=re.IGNORECASE)

    next_offset = current_offset + page_size

    # Check if we've reached the end
    if total_available is not None and next_offset >= total_available:
        return None

    return add_pagination_to_soql(clean_query, page_size, next_offset)


# =============================================================================
# RESPONSE SIZE UTILITIES
# =============================================================================

DEFAULT_MAX_RESPONSE_SIZE = 500000  # 500KB default max response size


def chunk_large_response(
    data: List[Any],
    max_size: int = DEFAULT_MAX_RESPONSE_SIZE,
    page_size: int = 100
) -> List[PaginatedResponse]:
    """
    Split a large response into chunks that fit within size limits.

    Args:
        data: List of items to chunk
        max_size: Maximum response size in bytes
        page_size: Initial page size to try

    Returns:
        List of PaginatedResponse objects
    """
    chunks = []
    current_page = 1

    while (current_page - 1) * page_size < len(data):
        response = paginate_list(data, current_page, page_size)

        # Check if response fits within size limit
        response_json = response.to_json()
        if len(response_json.encode('utf-8')) > max_size and page_size > 10:
            # Response too large, reduce page size and retry
            page_size = page_size // 2
            response = paginate_list(data, current_page, page_size)

        chunks.append(response)
        current_page += 1

        # Safety limit
        if current_page > 1000:
            logger.warning("Chunking hit safety limit of 1000 pages")
            break

    return chunks


def estimate_response_size(items: List[Any]) -> int:
    """
    Estimate the JSON response size for a list of items.

    Args:
        items: List of items

    Returns:
        Estimated size in bytes
    """
    try:
        return len(json.dumps(items, default=str).encode('utf-8'))
    except Exception:
        # Rough estimate: 100 bytes per item
        return len(items) * 100


def get_optimal_page_size(
    total_items: int,
    max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE,
    sample_items: Optional[List[Any]] = None
) -> int:
    """
    Calculate optimal page size based on item size and max response size.

    Args:
        total_items: Total number of items
        max_response_size: Maximum response size in bytes
        sample_items: Optional sample of items to estimate size

    Returns:
        Optimal page size
    """
    if sample_items and len(sample_items) > 0:
        # Calculate average item size
        sample_size = estimate_response_size(sample_items)
        avg_item_size = sample_size / len(sample_items)

        # Account for pagination metadata overhead (~500 bytes)
        available_size = max_response_size - 500
        optimal_size = int(available_size / avg_item_size)

        # Clamp to reasonable bounds
        return max(10, min(optimal_size, 2000))

    # Default page size
    return 100


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def paginated_query_response(
    records: List[Dict],
    total_size: int,
    query: str,
    page: int = 1,
    page_size: int = 100
) -> str:
    """
    Create a paginated response for SOQL query results.

    Args:
        records: Query result records
        total_size: Total matching records
        query: Original SOQL query
        page: Current page number
        page_size: Page size

    Returns:
        JSON response string
    """
    total_pages = ceil(total_size / page_size) if page_size > 0 else 1

    response = {
        "success": True,
        "total_size": total_size,
        "records": records,
        "query": query,
        "pagination": {
            "current_page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_more": page < total_pages,
            "records_returned": len(records)
        }
    }

    if page < total_pages:
        response["pagination"]["next_page_hint"] = (
            f"Add 'OFFSET {page * page_size}' to query for next page"
        )

    return json.dumps(response, indent=2, default=str)


def paginated_metadata_response(
    items: List[Dict],
    metadata_type: str,
    page: int = 1,
    page_size: int = 100
) -> str:
    """
    Create a paginated response for metadata listing.

    Args:
        items: Metadata items
        metadata_type: Type of metadata
        page: Current page number
        page_size: Page size

    Returns:
        JSON response string
    """
    response = paginate_list(items, page, page_size)
    result = response.to_dict()
    result["metadata_type"] = metadata_type

    return json.dumps(result, indent=2, default=str)
