"""Salesforce connection management with OAuth support"""
from simple_salesforce import Salesforce
import threading
import time
import logging

from app.config import get_config

logger = logging.getLogger(__name__)

# Import OAuth functions
try:
    from app.mcp.tools.oauth_auth import get_stored_tokens, refresh_salesforce_token
    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False
    logger.warning("⚠️ OAuth module not available")

# Thread-local storage
local = threading.local()

def _resolve_token(user_id, stored_tokens):
    """Pick the token dict to use, applying multi-org active-org logic."""
    if user_id and user_id in stored_tokens:
        return user_id, stored_tokens[user_id]
    try:
        from app.mcp.tools.multi_org import _active_org
        if _active_org.get("user_id") and _active_org["user_id"] in stored_tokens:
            uid = _active_org["user_id"]
            return uid, stored_tokens[uid]
    except ImportError:
        pass
    uid, tok = next(iter(stored_tokens.items()))
    return uid, tok


def get_salesforce_connection(user_id: str = None):
    """
    Get Salesforce connection using OAuth tokens (no config required).

    Multi-org support: If user_id is provided, connects to that specific org.
    Otherwise, uses the active org from multi_org module or first available.

    Args:
        user_id: Specific user ID (optional, uses active org or first available)

    Returns:
        Salesforce connection instance
    """
    if not OAUTH_AVAILABLE:
        raise Exception("OAuth not available. Please ensure oauth_auth module is imported.")

    stored_tokens = get_stored_tokens()
    if not stored_tokens:
        raise Exception(
            "❌ No active Salesforce sessions found.\n"
            "Please run one of these commands first:\n"
            "- salesforce_production_login() - for production orgs\n"
            "- salesforce_sandbox_login() - for sandbox orgs\n"
            "- salesforce_custom_login('https://yourorg.my.salesforce.com') - for custom domains"
        )

    # Resolve which user/token to use before touching the cache
    selected_user, token_data = _resolve_token(user_id, stored_tokens)

    # Per-org connection cache keyed by selected_user
    if not hasattr(local, 'sf_connections'):
        local.sf_connections = {}

    config = get_config()

    # Evict stale cached connection for this org
    if selected_user in local.sf_connections:
        token_age = time.time() - token_data['login_timestamp']
        if token_age > config.token_refresh_threshold_seconds:
            logger.info("Cached connection for %s is stale — refreshing", selected_user)
            del local.sf_connections[selected_user]

    if selected_user not in local.sf_connections:
        logger.info("🔗 Creating Salesforce connection for %s...", selected_user)

        # Refresh token if needed
        token_age = time.time() - token_data['login_timestamp']
        if token_age > config.token_refresh_threshold_seconds:
            logger.info("🔄 Refreshing token for %s...", selected_user)
            if not refresh_salesforce_token(selected_user):
                raise Exception(f"Failed to refresh token for {selected_user}. Please login again.")
            token_data = get_stored_tokens()[selected_user]

        local.sf_connections[selected_user] = Salesforce(
            instance_url=token_data['instance_url'],
            session_id=token_data['access_token']
        )
        logger.info("✅ Connected to %s as user %s", token_data['instance_url'], selected_user)

    return local.sf_connections[selected_user]

def clear_connection_cache(user_id: str = None):
    """Clear connection cache to force new connection. Pass user_id to clear one org only."""
    if not hasattr(local, 'sf_connections'):
        return
    if user_id:
        local.sf_connections.pop(user_id, None)
    else:
        local.sf_connections.clear()
