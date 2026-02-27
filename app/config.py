"""
Configuration management for Salesforce MCP Server
Supports environment variables and .env files

Created by Sameer
"""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class SalesforceConfig(BaseSettings):
    """Salesforce MCP Server configuration

    Added by Sameer
    """

    # Server Configuration
    mcp_server_name: str = Field(default="salesforce-mcp-server", description="MCP server name")
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")

    # OAuth Configuration
    oauth_callback_port: int = Field(default=1717, description="OAuth callback server port")
    oauth_timeout_seconds: int = Field(default=300, description="OAuth login timeout in seconds")

    # API Configuration
    salesforce_api_version: str = Field(default="62.0", description="Salesforce API version")
    max_retries: int = Field(default=3, description="Maximum retry attempts for API calls")
    retry_backoff_seconds: float = Field(default=2.0, description="Retry backoff multiplier")
    request_timeout_seconds: int = Field(default=120, description="Default request timeout")

    # Deployment Configuration
    deploy_timeout_seconds: int = Field(default=300, description="Metadata deploy timeout")
    deploy_poll_interval_seconds: int = Field(default=5, description="Deploy status poll interval")

    # Token Management
    token_refresh_threshold_seconds: int = Field(default=5400, description="Refresh token after 90 minutes")
    token_storage_encrypted: bool = Field(default=False, description="Encrypt stored tokens")
    token_encryption_key: Optional[str] = Field(default=None, description="Encryption key for tokens")

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=False, description="Enable rate limiting")
    rate_limit_requests_per_minute: int = Field(default=100, description="Max requests per minute")

    # Development
    debug_mode: bool = Field(default=False, description="Enable debug mode")

    # HTTP/SSE Server Configuration
    http_host: str = Field(default="0.0.0.0", description="HTTP server host (0.0.0.0 for network access)")
    http_port: int = Field(default=8000, description="HTTP server port")
    api_key: str = Field(default="your-secret-api-key-change-this", description="API key for authentication")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "SFMCP_"


# Global configuration instance
_config: Optional[SalesforceConfig] = None


def get_config() -> SalesforceConfig:
    """Get global configuration instance (singleton pattern)

    Added by Sameer
    """
    global _config
    if _config is None:
        _config = SalesforceConfig()
    return _config


def reload_config() -> SalesforceConfig:
    """Reload configuration from environment/file

    Added by Sameer
    """
    global _config
    _config = SalesforceConfig()
    return _config
