import webbrowser
import threading
import time
import json
import requests
import secrets
import psutil  # Added for port management
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from typing import Dict, Any
import socket
from simple_salesforce import Salesforce

from app.mcp.server import register_tool
from app.config import get_config
from app.utils.retry import retry
from app.utils.validators import validate_url

logger = logging.getLogger(__name__)

# Global storage (memory only - cleared when process ends)
_oauth_tokens = {}
_oauth_callback_data = {}

class SalesforceCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        if parsed_url.path in ['/', '/OauthRedirect']:
            if 'code' in query_params:
                auth_code = query_params['code'][0]
                state = query_params.get('state', [None])[0]

                _oauth_callback_data[state] = {
                    'code': auth_code,
                    'timestamp': time.time()
                }

                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                html_response = b'''<html>
                <head><title>Salesforce Authentication</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h2 style="color: #2e844a;">Authentication Received</h2>
                    <p>Processing your login... You can close this window.</p>
                    <p style="color: #666; font-size: 14px;">Check Claude Desktop for the login status.</p>
                </body>
                </html>'''
                self.wfile.write(html_response)

            elif 'error' in query_params:
                error = query_params['error'][0]
                error_description = query_params.get('error_description', ['Unknown error'])[0]
                _oauth_callback_data['error'] = {
                    'error': error,
                    'description': error_description
                }
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                html_response = f'''<html>
                <head><title>Salesforce Authentication Failed</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h2 style="color: #c23934;">Authentication Failed</h2>
                    <p><strong>Error:</strong> {error}</p>
                    <p><strong>Description:</strong> {error_description}</p>
                    <hr style="width: 50%; margin: 30px auto;">
                    <h3>Common Solutions:</h3>
                    <ul style="text-align: left; max-width: 500px; margin: 20px auto;">
                        <li>Try using username/password login instead</li>
                        <li>Check if your org allows OAuth authentication</li>
                        <li>Verify you have the correct permissions</li>
                        <li>Contact your Salesforce administrator</li>
                    </ul>
                    <p style="color: #666; font-size: 14px; margin-top: 30px;">
                        You can close this window and check Claude Desktop.
                    </p>
                </body>
                </html>'''.encode('utf-8')
                self.wfile.write(html_response)

    def log_message(self, format, *args):
        pass

class ReusableDualStackHTTPServer(HTTPServer):
    allow_reuse_address = True
    address_family = socket.AF_INET6  # bind IPv6, then allow v4-mapped
    def server_bind(self):
        try:
            # Accept both IPv6 and IPv4 on the same socket (if OS supports it)
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except Exception:
            pass
        super().server_bind()
        
def _free_port(port: int) -> None:
    """Free up the specified port by terminating any processes using it"""
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr and conn.laddr.port == port and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    proc.terminate()
                    proc.wait(timeout=3)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    pass  # Ignore errors - process may have already closed
        # Small delay to ensure port is fully released
        time.sleep(0.5)
    except Exception:
        pass  # Ignore any errors in port cleanup


def _start_callback_server(port: int = 1717):
    """Start callback server after ensuring port is free (Windows-safe, dual-stack)."""
    # Skip OAuth callback server in hosted/production environments
    import os
    if os.getenv('RENDER') or os.getenv('SFMCP_OAUTH_DISABLED') == 'true':
        logger.warning("OAuth callback server disabled for hosted deployment")
        return None

    _free_port(port)

    # Try dual-stack first (bind to '::' so both ::1 and 127.0.0.1 work)
    server = None
    last_err = None
    for attempt in range(3):
        try:
            server = ReusableDualStackHTTPServer(('::', port), SalesforceCallbackHandler)
            break
        except OSError as e:
            last_err = e
            # Fallback: re-attempt after brief pause (handles slow TIME_WAIT release)
            time.sleep(0.3)

    # If dual-stack binding failed (older OSes), fall back to plain IPv4 on localhost
    if server is None:
        for attempt in range(3):
            try:
                server = HTTPServer(('localhost', port), SalesforceCallbackHandler)
                break
            except OSError as e:
                last_err = e
                time.sleep(0.3)

    if server is None:
        raise OSError(f"Port {port} could not be bound after retries: {last_err}")

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server

def _create_json_response(success, **kwargs):
    """Create guaranteed valid JSON response"""
    result = {"success": success}
    
    # Only add safe, JSON-serializable values
    for key, value in kwargs.items():
        if value is None:
            result[key] = None
        elif isinstance(value, (str, int, float, bool)):
            result[key] = value
        elif isinstance(value, (list, dict)):
            result[key] = value
        else:
            result[key] = str(value)
    
    # Return clean JSON string
    return json.dumps(result, indent=2)

@register_tool
def salesforce_production_login() -> str:
    """Login to Salesforce production org."""
    return _do_login("production", "https://login.salesforce.com")

@register_tool
def salesforce_sandbox_login() -> str:
    """Login to Salesforce sandbox org."""
    return _do_login("sandbox", "https://test.salesforce.com")

@register_tool
def salesforce_custom_login(domain_url: str) -> str:
    """Login to custom Salesforce domain."""
    try:
        validate_url(domain_url, require_https=True)
    except Exception as e:
        return _create_json_response(False, error=f"Invalid domain URL: {str(e)}")

    clean_domain = domain_url.rstrip('/')
    return _do_login("custom", clean_domain)


def _do_login(org_type: str, auth_url: str) -> str:
    """Perform OAuth login with automatic port cleanup and guaranteed JSON response"""
    try:
        # Setup
        config = get_config()
        state = secrets.token_urlsafe(16)  # Shorter, safer token
        callback_port = config.oauth_callback_port
        redirect_uri = f"http://localhost:{callback_port}/OauthRedirect"
        
        # Start server (this will automatically free the port first)
        server = _start_callback_server(callback_port)

        # Check if OAuth is disabled (hosted environment)
        if server is None:
            return _create_json_response(
                False,
                error="OAuth login is not available in hosted deployment",
                message="Please use salesforce_login_username_password instead",
                hint="OAuth requires local browser access which is not available on hosted servers"
            )

        # Build URL
        params = {
            'response_type': 'code',
            'client_id': 'PlatformCLI',
            'redirect_uri': redirect_uri,
            'state': state,
            'scope': 'api web refresh_token'
        }
        
        login_url = auth_url + "/services/oauth2/authorize?" + urlencode(params)
        
        # Open browser
        webbrowser.open(login_url)
        
        # Wait for callback (simplified)
        timeout = config.oauth_timeout_seconds
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            if state in _oauth_callback_data:
                # Success case
                callback_data = _oauth_callback_data.pop(state)
                try:
                    server.shutdown()
                except:
                    pass  # Ignore server shutdown errors
                
                # Get token
                token_url = f"{auth_url}/services/oauth2/token"
                token_data = {
                    'grant_type': 'authorization_code',
                    'client_id': 'PlatformCLI',
                    'redirect_uri': redirect_uri,
                    'code': callback_data['code']
                }

                try:
                    response = requests.post(token_url, data=token_data, timeout=30)
                    response.raise_for_status()
                    token_response = response.json()

                    # Store token
                    user_id = token_response.get('id', '').split('/')[-1] or 'user'
                    _oauth_tokens[user_id] = {
                        'access_token': token_response['access_token'],
                        'refresh_token': token_response.get('refresh_token'),
                        'instance_url': token_response['instance_url'],
                        'user_id': user_id,
                        'login_timestamp': time.time(),
                        'org_type': org_type
                    }

                    return _create_json_response(
                        True,
                        message="Login successful",
                        user_id=user_id,
                        instance_url=token_response['instance_url'],
                        org_type=org_type
                    )
                except requests.exceptions.HTTPError as http_err:
                    error_detail = "Token exchange failed"
                    try:
                        error_json = response.json()
                        error_detail = f"{error_json.get('error', 'unknown')}: {error_json.get('error_description', 'No description')}"
                    except:
                        error_detail = f"HTTP {response.status_code}: {str(http_err)}"

                    return _create_json_response(
                        False,
                        error="OAuth token exchange failed",
                        details=error_detail,
                        suggestion="Try using username/password login instead with salesforce_login_username_password"
                    )
                except Exception as token_err:
                    return _create_json_response(
                        False,
                        error="Token processing failed",
                        details=str(token_err),
                        suggestion="Try using username/password login instead with salesforce_login_username_password"
                    )
            
            elif 'error' in _oauth_callback_data:
                # Error case
                error_data = _oauth_callback_data.pop('error')
                try:
                    server.shutdown()
                except:
                    pass
                return _create_json_response(
                    False,
                    error="OAuth authorization failed",
                    details=f"{error_data.get('error', 'Unknown error')}: {error_data.get('description', '')}",
                    suggestion="Try using username/password login instead with salesforce_login_username_password"
                )
            
            time.sleep(1)
        
        # Timeout case
        try:
            server.shutdown()
        except:
            pass
        return _create_json_response(False, error="Login timeout")
        
    except Exception as e:
        return _create_json_response(False, error=f"Login error: {str(e)}")

@register_tool
def salesforce_logout() -> str:
    """Clear stored tokens."""
    try:
        count = len(_oauth_tokens)
        _oauth_tokens.clear()
        _oauth_callback_data.clear()
        return _create_json_response(True, message=f"Logged out {count} sessions")
    except Exception as e:
        return _create_json_response(False, error=str(e))

@register_tool
def salesforce_auth_status() -> str:
    """Check authentication status."""
    try:
        if not _oauth_tokens:
            return _create_json_response(
                True, 
                authenticated=False, 
                message="No active sessions"
            )
        
        sessions = []
        for user_id, token_info in _oauth_tokens.items():
            age_minutes = round((time.time() - token_info['login_timestamp']) / 60, 1)
            sessions.append({
                "user_id": user_id,
                "instance_url": token_info['instance_url'],
                "org_type": token_info.get('org_type', 'unknown'),
                "age_minutes": age_minutes
            })
        
        return _create_json_response(
            True,
            authenticated=True,
            sessions=sessions,
            total_sessions=len(sessions)
        )
    except Exception as e:
        return _create_json_response(False, error=str(e))

# Export functions
def get_stored_tokens():
    return _oauth_tokens.copy()

@retry(max_attempts=3, backoff=2.0, exceptions=(requests.RequestException,))
def refresh_salesforce_token(user_id: str) -> bool:
    if user_id not in _oauth_tokens:
        return False

    token_info = _oauth_tokens[user_id]
    refresh_token = token_info.get('refresh_token')
    if not refresh_token:
        return False

    try:
        refresh_url = f"{token_info['instance_url']}/services/oauth2/token"
        data = {
            'grant_type': 'refresh_token',
            'client_id': 'PlatformCLI',
            'refresh_token': refresh_token
        }

        response = requests.post(refresh_url, data=data, timeout=30)
        response.raise_for_status()
        new_token = response.json()

        token_info.update({
            'access_token': new_token['access_token'],
            'login_timestamp': time.time()
        })

        return True
    except:
        return False

@register_tool
def salesforce_get_domain_from_url(org_url: str) -> str:
    """
    Extract the domain parameter from a Salesforce org URL for use with login.

    This helper tool makes it easy to get the correct domain parameter for authentication.

    Args:
        org_url: Full Salesforce org URL (e.g., https://curious-narwhal-rzlj6k-dev-ed.trailblaze.my.salesforce.com)

    Returns:
        JSON with extracted domain value

    Example:
        salesforce_get_domain_from_url("https://curious-narwhal-rzlj6k-dev-ed.trailblaze.my.salesforce.com")
        Returns: "curious-narwhal-rzlj6k-dev-ed.trailblaze.my"
    """
    try:
        import re
        from urllib.parse import urlparse

        # Parse URL
        parsed = urlparse(org_url)
        hostname = parsed.hostname or parsed.path

        # Remove .salesforce.com
        if hostname.endswith('.salesforce.com'):
            domain = hostname.replace('.salesforce.com', '')
        else:
            domain = hostname

        # Determine org type
        if domain == 'login':
            org_type = 'production'
            login_url = 'https://login.salesforce.com'
        elif domain == 'test':
            org_type = 'sandbox'
            login_url = 'https://test.salesforce.com'
        elif 'sandbox' in domain.lower():
            org_type = 'sandbox'
            login_url = f'https://{domain}.salesforce.com'
        else:
            org_type = 'custom/developer'
            login_url = f'https://{domain}.salesforce.com'

        return _create_json_response(
            True,
            domain=domain,
            org_type=org_type,
            login_url=login_url,
            original_url=org_url,
            next_step=f"Use salesforce_login_username_password with domain: '{domain}'"
        )

    except Exception as e:
        return _create_json_response(
            False,
            error=f"Failed to extract domain: {str(e)}",
            original_url=org_url
        )


@register_tool
def salesforce_login_username_password(username: str, password: str, security_token: str = "", domain: str = "login") -> str:
    """
    Login to Salesforce using username and password.

    Args:
        username: Salesforce username (email)
        password: Salesforce password
        security_token: Security token (optional if IP is trusted, otherwise required)
        domain: Salesforce domain (test, login, or custom domain like mydomain.my.salesforce.com)

    Returns:
        JSON response with login status

    Example:
        salesforce_login_username_password(
            username="user@example.com",
            password="mypassword",
            security_token="AbC123XyZ",
            domain="test"  # or "login" for production, or "mydomain.my" for custom
        )

    Note: Security token can be found in Salesforce under:
    Setup → Personal Setup → My Personal Information → Reset My Security Token
    """
    try:
        # Connect to Salesforce
        # Note: simple_salesforce expects security_token as separate parameter
        sf = Salesforce(
            username=username,
            password=password,
            security_token=security_token,
            domain=domain
        )

        # Get the actual User ID by querying UserInfo
        user_query = sf.query("SELECT Id FROM User WHERE Username = '{}'".format(username))
        if user_query['totalSize'] == 0:
            raise Exception(f"Could not find user with username: {username}")

        user_id = user_query['records'][0]['Id']
        instance_url = f"https://{sf.sf_instance}"

        # Determine org type from domain
        org_type = 'sandbox' if domain == 'test' else 'production' if domain == 'login' else 'custom'

        # Store token info
        _oauth_tokens[user_id] = {
            'access_token': sf.session_id,
            'refresh_token': None,
            'instance_url': instance_url,
            'user_id': user_id,
            'login_timestamp': time.time(),
            'org_type': org_type,
            'domain': domain,
            'sf_client': sf  # Store the Salesforce client for later use
        }

        return _create_json_response(
            True,
            message="Login successful with username/password",
            user_id=user_id,
            instance_url=instance_url,
            org_type=org_type,
            domain=domain
        )

    except Exception as e:
        error_msg = str(e)
        return _create_json_response(
            False,
            error=f"Login failed: {error_msg}"
        )
