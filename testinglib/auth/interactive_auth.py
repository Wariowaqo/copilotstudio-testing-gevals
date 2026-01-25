"""
Interactive Authentication for Copilot Studio

This module provides interactive authentication using MSAL public client.
Used for local development and manual testing scenarios.

Required Environment Variables:
    - APP_CLIENT_ID: Azure AD Application (client) ID
    - TENANT_ID: Azure AD Tenant ID
"""

import logging
import os
from typing import Optional
from msal import PublicClientApplication

from testinglib.msal_cache_plugin import get_msal_token_cache

logger = logging.getLogger(__name__)


class InteractiveAuth:
    """
    Interactive authentication for local development scenarios.
    
    Uses device code flow or interactive browser login.
    Caches tokens for reuse across sessions.
    """
    
    # Power Platform API scope
    DEFAULT_SCOPE = "https://api.powerplatform.com/.default"
    
    def __init__(
        self,
        client_id: str,
        tenant_id: str,
        cache_path: Optional[str] = None,
        scope: Optional[str] = None
    ):
        """
        Initialize interactive authentication.
        
        Args:
            client_id: Azure AD Application (client) ID
            tenant_id: Azure AD Tenant ID
            cache_path: Optional path for token cache file
            scope: Optional custom scope (defaults to Power Platform API)
        """
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.scope = scope or self.DEFAULT_SCOPE
        
        # Set up cache path
        default_cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "bin"
        )
        os.makedirs(default_cache_dir, exist_ok=True)
        self.cache_path = cache_path or os.path.join(default_cache_dir, "token_cache.bin")
        
        self._app: Optional[PublicClientApplication] = None
    
    @property
    def authority(self) -> str:
        """Get the Azure AD authority URL."""
        return f"https://login.microsoftonline.com/{self.tenant_id}"
    
    def _get_app(self) -> PublicClientApplication:
        """Get or create the MSAL Public Client Application."""
        if self._app is None:
            cache = get_msal_token_cache(self.cache_path)
            self._app = PublicClientApplication(
                client_id=self.client_id,
                authority=self.authority,
                token_cache=cache
            )
        return self._app
    
    def acquire_token(self) -> str:
        """
        Acquire an access token, using cached token if available.
        
        Falls back to interactive login if no cached token exists.
        
        Returns:
            Access token string
            
        Raises:
            Exception: If token acquisition fails
        """
        app = self._get_app()
        scopes = [self.scope]
        accounts = app.get_accounts()
        
        result = None
        
        # Try cached token first
        if accounts:
            logger.info(f"Found cached account: {accounts[0].get('username', 'unknown')}")
            result = app.acquire_token_silent(scopes=scopes, account=accounts[0])
        
        # Fall back to interactive login
        if not result:
            logger.info("No cached token, starting interactive login...")
            result = app.acquire_token_interactive(scopes=scopes)
        
        if "access_token" in result:
            logger.info("Successfully acquired access token")
            return result["access_token"]
        else:
            error = result.get("error", "unknown_error")
            error_desc = result.get("error_description", "No description available")
            logger.error(f"Token acquisition failed: {error} - {error_desc}")
            raise Exception(f"Interactive token acquisition failed: {error_desc}")
