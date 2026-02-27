"""Connection pooling for Salesforce MCP Server.

Provides:
- Reusable Salesforce connection management
- Connection health checking
- Automatic reconnection on failure
- Connection pool statistics
- Thread-safe connection access

Created by Sameer
"""
import time
import threading
import logging
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
from contextlib import contextmanager
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """State of a pooled connection"""
    AVAILABLE = "available"
    IN_USE = "in_use"
    STALE = "stale"
    FAILED = "failed"


@dataclass
class ConnectionInfo:
    """Metadata about a pooled connection"""
    connection: Any  # Salesforce connection object
    user_id: str
    instance_url: str
    created_at: float
    last_used: float
    state: ConnectionState = ConnectionState.AVAILABLE
    use_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None

    def is_stale(self, max_age: float = 3600) -> bool:
        """Check if connection is stale (default 1 hour)"""
        return time.time() - self.created_at > max_age

    def is_idle(self, max_idle: float = 300) -> bool:
        """Check if connection has been idle too long (default 5 minutes)"""
        return time.time() - self.last_used > max_idle

    def touch(self):
        """Update last used time"""
        self.last_used = time.time()
        self.use_count += 1

    def mark_error(self, error_msg: str):
        """Record an error"""
        self.error_count += 1
        self.last_error = error_msg
        if self.error_count >= 3:
            self.state = ConnectionState.FAILED


class ConnectionPool:
    """
    Thread-safe connection pool for Salesforce connections.

    Features:
    - Multiple org support (each org gets its own pooled connection)
    - Automatic reconnection
    - Connection health checking
    - Usage statistics
    """

    # Default configuration
    MAX_CONNECTIONS = 10
    MAX_AGE = 3600  # 1 hour
    MAX_IDLE = 300  # 5 minutes
    HEALTH_CHECK_INTERVAL = 60  # 1 minute

    def __init__(
        self,
        max_connections: int = MAX_CONNECTIONS,
        max_age: float = MAX_AGE,
        max_idle: float = MAX_IDLE
    ):
        self._connections: OrderedDict[str, ConnectionInfo] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "reconnections": 0,
            "errors": 0
        }
        self.max_connections = max_connections
        self.max_age = max_age
        self.max_idle = max_idle

    def get_connection(
        self,
        user_id: str,
        connection_factory: Optional[Callable[[], Any]] = None
    ) -> Optional[Any]:
        """
        Get a connection from the pool.

        Args:
            user_id: Unique identifier for the org/user
            connection_factory: Optional factory to create new connection

        Returns:
            Salesforce connection object or None
        """
        with self._lock:
            self._stats["total_requests"] += 1

            # Check if we have an existing connection
            if user_id in self._connections:
                conn_info = self._connections[user_id]

                # Check if connection is usable
                if self._is_connection_usable(conn_info):
                    conn_info.touch()
                    conn_info.state = ConnectionState.IN_USE
                    self._stats["cache_hits"] += 1
                    logger.debug(f"Pool hit for {user_id}")
                    return conn_info.connection

                # Connection not usable, remove it
                logger.info(f"Removing stale/failed connection for {user_id}")
                del self._connections[user_id]

            self._stats["cache_misses"] += 1

            # Create new connection if factory provided
            if connection_factory:
                try:
                    connection = connection_factory()
                    if connection:
                        self._add_connection(user_id, connection)
                        return connection
                except Exception as e:
                    logger.error(f"Failed to create connection: {e}")
                    self._stats["errors"] += 1

            return None

    def _is_connection_usable(self, conn_info: ConnectionInfo) -> bool:
        """Check if a connection is usable"""
        if conn_info.state == ConnectionState.FAILED:
            return False
        if conn_info.is_stale(self.max_age):
            conn_info.state = ConnectionState.STALE
            return False
        return True

    def _add_connection(
        self,
        user_id: str,
        connection: Any,
        instance_url: str = ""
    ) -> ConnectionInfo:
        """Add a new connection to the pool"""
        with self._lock:
            # Evict oldest if at capacity
            while len(self._connections) >= self.max_connections:
                oldest_key = next(iter(self._connections))
                logger.info(f"Evicting connection for {oldest_key}")
                del self._connections[oldest_key]

            now = time.time()
            conn_info = ConnectionInfo(
                connection=connection,
                user_id=user_id,
                instance_url=instance_url,
                created_at=now,
                last_used=now,
                state=ConnectionState.IN_USE
            )
            self._connections[user_id] = conn_info
            logger.info(f"Added new connection for {user_id}")
            return conn_info

    def release_connection(self, user_id: str, success: bool = True, error: Optional[str] = None):
        """
        Release a connection back to the pool.

        Args:
            user_id: Connection identifier
            success: Whether the operation was successful
            error: Optional error message
        """
        with self._lock:
            if user_id in self._connections:
                conn_info = self._connections[user_id]
                if success:
                    conn_info.state = ConnectionState.AVAILABLE
                else:
                    conn_info.mark_error(error or "Unknown error")
                    if conn_info.state == ConnectionState.FAILED:
                        logger.warning(f"Connection marked failed for {user_id}")

    def remove_connection(self, user_id: str) -> bool:
        """
        Remove a connection from the pool.

        Args:
            user_id: Connection identifier

        Returns:
            True if connection was removed
        """
        with self._lock:
            if user_id in self._connections:
                del self._connections[user_id]
                logger.info(f"Removed connection for {user_id}")
                return True
            return False

    def update_connection(
        self,
        user_id: str,
        connection: Any,
        instance_url: str = ""
    ):
        """
        Update an existing connection or add a new one.

        Args:
            user_id: Connection identifier
            connection: New Salesforce connection
            instance_url: Instance URL
        """
        with self._lock:
            if user_id in self._connections:
                # Update existing
                conn_info = self._connections[user_id]
                conn_info.connection = connection
                conn_info.instance_url = instance_url
                conn_info.state = ConnectionState.AVAILABLE
                conn_info.error_count = 0
                conn_info.last_error = None
                conn_info.touch()
                self._stats["reconnections"] += 1
                logger.info(f"Updated connection for {user_id}")
            else:
                # Add new
                self._add_connection(user_id, connection, instance_url)

    @contextmanager
    def connection(
        self,
        user_id: str,
        connection_factory: Optional[Callable[[], Any]] = None
    ):
        """
        Context manager for using a pooled connection.

        Args:
            user_id: Connection identifier
            connection_factory: Optional factory to create new connection

        Yields:
            Salesforce connection object

        Example:
            with pool.connection("user123") as sf:
                result = sf.query("SELECT Id FROM Account")
        """
        conn = self.get_connection(user_id, connection_factory)
        try:
            yield conn
            self.release_connection(user_id, success=True)
        except Exception as e:
            self.release_connection(user_id, success=False, error=str(e))
            raise

    def cleanup_idle_connections(self) -> int:
        """
        Remove idle connections from the pool.

        Returns:
            Number of connections removed
        """
        with self._lock:
            removed = 0
            idle_users = [
                user_id for user_id, conn_info in self._connections.items()
                if conn_info.is_idle(self.max_idle) and conn_info.state == ConnectionState.AVAILABLE
            ]
            for user_id in idle_users:
                del self._connections[user_id]
                removed += 1
            if removed > 0:
                logger.info(f"Cleaned up {removed} idle connections")
            return removed

    def cleanup_failed_connections(self) -> int:
        """
        Remove failed connections from the pool.

        Returns:
            Number of connections removed
        """
        with self._lock:
            removed = 0
            failed_users = [
                user_id for user_id, conn_info in self._connections.items()
                if conn_info.state == ConnectionState.FAILED
            ]
            for user_id in failed_users:
                del self._connections[user_id]
                removed += 1
            if removed > 0:
                logger.info(f"Cleaned up {removed} failed connections")
            return removed

    def clear(self) -> int:
        """
        Clear all connections from the pool.

        Returns:
            Number of connections cleared
        """
        with self._lock:
            count = len(self._connections)
            self._connections.clear()
            self._stats = {
                "total_requests": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "reconnections": 0,
                "errors": 0
            }
            logger.info(f"Cleared {count} connections from pool")
            return count

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        with self._lock:
            active = sum(
                1 for c in self._connections.values()
                if c.state in [ConnectionState.AVAILABLE, ConnectionState.IN_USE]
            )
            hit_rate = (
                self._stats["cache_hits"] / self._stats["total_requests"] * 100
                if self._stats["total_requests"] > 0 else 0
            )
            return {
                "total_connections": len(self._connections),
                "active_connections": active,
                "total_requests": self._stats["total_requests"],
                "cache_hits": self._stats["cache_hits"],
                "cache_misses": self._stats["cache_misses"],
                "hit_rate_percent": round(hit_rate, 2),
                "reconnections": self._stats["reconnections"],
                "errors": self._stats["errors"],
                "connections": [
                    {
                        "user_id": user_id,
                        "state": conn_info.state.value,
                        "use_count": conn_info.use_count,
                        "age_seconds": round(time.time() - conn_info.created_at, 1),
                        "idle_seconds": round(time.time() - conn_info.last_used, 1)
                    }
                    for user_id, conn_info in self._connections.items()
                ]
            }

    def health_check(self, check_func: Optional[Callable[[Any], bool]] = None) -> Dict[str, Any]:
        """
        Perform health check on all connections.

        Args:
            check_func: Optional function to test connection health

        Returns:
            Health check results
        """
        results = {
            "healthy": 0,
            "unhealthy": 0,
            "details": []
        }

        with self._lock:
            for user_id, conn_info in list(self._connections.items()):
                is_healthy = True
                status = "healthy"

                # Check state
                if conn_info.state == ConnectionState.FAILED:
                    is_healthy = False
                    status = "failed"
                elif conn_info.is_stale(self.max_age):
                    is_healthy = False
                    status = "stale"
                elif check_func:
                    try:
                        if not check_func(conn_info.connection):
                            is_healthy = False
                            status = "check_failed"
                    except Exception as e:
                        is_healthy = False
                        status = f"error: {str(e)}"

                if is_healthy:
                    results["healthy"] += 1
                else:
                    results["unhealthy"] += 1

                results["details"].append({
                    "user_id": user_id,
                    "status": status,
                    "error_count": conn_info.error_count,
                    "last_error": conn_info.last_error
                })

        return results


# =============================================================================
# GLOBAL POOL INSTANCE
# =============================================================================

_global_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool() -> ConnectionPool:
    """Get the global connection pool instance (lazy initialization)"""
    global _global_pool
    if _global_pool is None:
        with _pool_lock:
            if _global_pool is None:
                _global_pool = ConnectionPool()
    return _global_pool


def reset_connection_pool():
    """Reset the global connection pool (for testing)"""
    global _global_pool
    with _pool_lock:
        if _global_pool:
            _global_pool.clear()
        _global_pool = None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_pooled_connection(
    user_id: str,
    connection_factory: Optional[Callable[[], Any]] = None
) -> Optional[Any]:
    """Get a connection from the global pool"""
    return get_connection_pool().get_connection(user_id, connection_factory)


def release_pooled_connection(user_id: str, success: bool = True, error: Optional[str] = None):
    """Release a connection back to the global pool"""
    get_connection_pool().release_connection(user_id, success, error)


def update_pooled_connection(user_id: str, connection: Any, instance_url: str = ""):
    """Update a connection in the global pool"""
    get_connection_pool().update_connection(user_id, connection, instance_url)


def remove_pooled_connection(user_id: str) -> bool:
    """Remove a connection from the global pool"""
    return get_connection_pool().remove_connection(user_id)


def get_pool_stats() -> Dict[str, Any]:
    """Get global pool statistics"""
    return get_connection_pool().get_stats()


def cleanup_pool():
    """Cleanup idle and failed connections"""
    pool = get_connection_pool()
    pool.cleanup_idle_connections()
    pool.cleanup_failed_connections()
