"""
Global caching layer for Salesforce MCP Server.

Provides thread-safe caching for:
- Object metadata
- Field definitions
- Validation rules
- Apex class bodies
- Query results

Created by Sameer
"""
import time
import threading
import logging
from typing import Any, Optional, Dict, Callable, TypeVar, Generic
from functools import wraps
from dataclasses import dataclass, field
from collections import OrderedDict

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry:
    """Single cache entry with value and metadata"""
    value: Any
    created_at: float
    ttl: float
    hits: int = 0

    def is_expired(self) -> bool:
        """Check if entry has expired"""
        return time.time() - self.created_at > self.ttl

    def touch(self):
        """Increment hit counter"""
        self.hits += 1


class GlobalCache:
    """
    Thread-safe global cache with TTL support.

    Features:
    - Configurable TTL per cache category
    - LRU eviction when max size reached
    - Thread-safe operations
    - Hit/miss statistics
    - Automatic cleanup of expired entries
    """

    # Default TTL values (in seconds)
    DEFAULT_TTL = {
        'object_metadata': 600,    # 10 minutes
        'field_definitions': 600,  # 10 minutes
        'validation_rules': 300,   # 5 minutes
        'apex_classes': 300,       # 5 minutes
        'query_results': 60,       # 1 minute
        'org_info': 3600,          # 1 hour
        'default': 300             # 5 minutes
    }

    MAX_SIZE = 1000  # Maximum entries per category

    def __init__(self):
        self._cache: Dict[str, Dict[str, CacheEntry]] = {}
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }

    def _get_category_cache(self, category: str) -> Dict[str, CacheEntry]:
        """Get or create cache dict for a category"""
        if category not in self._cache:
            self._cache[category] = OrderedDict()
        return self._cache[category]

    def get(self, category: str, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            category: Cache category (e.g., 'object_metadata')
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            cache = self._get_category_cache(category)
            entry = cache.get(key)

            if entry is None:
                self._stats['misses'] += 1
                return None

            if entry.is_expired():
                del cache[key]
                self._stats['misses'] += 1
                logger.debug(f"Cache expired: {category}/{key}")
                return None

            # Move to end for LRU
            cache.move_to_end(key)
            entry.touch()
            self._stats['hits'] += 1
            logger.debug(f"Cache hit: {category}/{key}")
            return entry.value

    def set(self, category: str, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        Set value in cache.

        Args:
            category: Cache category
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses category default if not specified)
        """
        with self._lock:
            cache = self._get_category_cache(category)

            # Determine TTL
            if ttl is None:
                ttl = self.DEFAULT_TTL.get(category, self.DEFAULT_TTL['default'])

            # Evict oldest if at capacity
            while len(cache) >= self.MAX_SIZE:
                oldest_key = next(iter(cache))
                del cache[oldest_key]
                self._stats['evictions'] += 1
                logger.debug(f"Cache eviction: {category}/{oldest_key}")

            # Store entry
            cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl
            )
            logger.debug(f"Cache set: {category}/{key} (TTL: {ttl}s)")

    def delete(self, category: str, key: str) -> bool:
        """
        Delete specific entry from cache.

        Args:
            category: Cache category
            key: Cache key

        Returns:
            True if entry was deleted, False if not found
        """
        with self._lock:
            cache = self._get_category_cache(category)
            if key in cache:
                del cache[key]
                logger.debug(f"Cache delete: {category}/{key}")
                return True
            return False

    def clear_category(self, category: str) -> int:
        """
        Clear all entries in a category.

        Args:
            category: Cache category to clear

        Returns:
            Number of entries cleared
        """
        with self._lock:
            if category in self._cache:
                count = len(self._cache[category])
                self._cache[category] = OrderedDict()
                logger.info(f"Cache cleared: {category} ({count} entries)")
                return count
            return 0

    def clear_all(self) -> int:
        """
        Clear entire cache.

        Returns:
            Total number of entries cleared
        """
        with self._lock:
            total = sum(len(c) for c in self._cache.values())
            self._cache = {}
            self._stats = {'hits': 0, 'misses': 0, 'evictions': 0}
            logger.info(f"Cache cleared: all ({total} entries)")
            return total

    def invalidate_pattern(self, category: str, pattern: str) -> int:
        """
        Invalidate all entries matching a pattern.

        Args:
            category: Cache category
            pattern: Pattern to match (supports * wildcard)

        Returns:
            Number of entries invalidated
        """
        import fnmatch
        with self._lock:
            cache = self._get_category_cache(category)
            keys_to_delete = [k for k in cache.keys() if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_delete:
                del cache[key]
            logger.info(f"Cache invalidated: {category}/{pattern} ({len(keys_to_delete)} entries)")
            return len(keys_to_delete)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_entries = sum(len(c) for c in self._cache.values())
            hit_rate = (
                self._stats['hits'] / (self._stats['hits'] + self._stats['misses']) * 100
                if (self._stats['hits'] + self._stats['misses']) > 0 else 0
            )
            return {
                'total_entries': total_entries,
                'categories': {k: len(v) for k, v in self._cache.items()},
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'evictions': self._stats['evictions'],
                'hit_rate_percent': round(hit_rate, 2)
            }

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            removed = 0
            for category, cache in self._cache.items():
                expired_keys = [k for k, v in cache.items() if v.is_expired()]
                for key in expired_keys:
                    del cache[key]
                    removed += 1
            if removed > 0:
                logger.info(f"Cache cleanup: removed {removed} expired entries")
            return removed


# Global singleton instance
_global_cache = GlobalCache()


def get_cache() -> GlobalCache:
    """Get the global cache instance"""
    return _global_cache


def cached(category: str, key_func: Optional[Callable[..., str]] = None, ttl: Optional[float] = None):
    """
    Decorator for caching function results.

    Args:
        category: Cache category
        key_func: Function to generate cache key from arguments (default: str(args))
        ttl: Time-to-live in seconds

    Example:
        @cached('object_metadata', key_func=lambda obj: obj)
        def get_object_metadata(object_name: str) -> dict:
            # Expensive API call
            return sf.describe(object_name)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"

            # Check cache
            cache = get_cache()
            cached_value = cache.get(category, key)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(category, key, result, ttl)
            return result

        # Add cache control methods to wrapper
        wrapper.cache_clear = lambda: get_cache().invalidate_pattern(category, f"{func.__name__}:*")
        wrapper.cache_info = lambda: get_cache().get_stats()

        return wrapper
    return decorator


# Convenience functions for common cache operations
def cache_object_metadata(object_name: str, metadata: dict) -> None:
    """Cache object metadata"""
    get_cache().set('object_metadata', object_name, metadata)


def get_cached_object_metadata(object_name: str) -> Optional[dict]:
    """Get cached object metadata"""
    return get_cache().get('object_metadata', object_name)


def cache_field_definitions(object_name: str, fields: list) -> None:
    """Cache field definitions for an object"""
    get_cache().set('field_definitions', object_name, fields)


def get_cached_field_definitions(object_name: str) -> Optional[list]:
    """Get cached field definitions"""
    return get_cache().get('field_definitions', object_name)


def cache_validation_rules(object_name: str, rules: list) -> None:
    """Cache validation rules for an object"""
    get_cache().set('validation_rules', object_name, rules)


def get_cached_validation_rules(object_name: str) -> Optional[list]:
    """Get cached validation rules"""
    return get_cache().get('validation_rules', object_name)


def invalidate_object_cache(object_name: str) -> None:
    """Invalidate all cache entries for an object (after deployment)"""
    cache = get_cache()
    cache.delete('object_metadata', object_name)
    cache.delete('field_definitions', object_name)
    cache.delete('validation_rules', object_name)
    cache.invalidate_pattern('query_results', f"*{object_name}*")
    logger.info(f"Invalidated cache for object: {object_name}")
