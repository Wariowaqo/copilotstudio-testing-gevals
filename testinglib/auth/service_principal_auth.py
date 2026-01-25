"""
Service Principal Authentication for Copilot Studio

This module provides non-interactive authentication using Azure AD service principals.
Ideal for CI/CD pipelines and automated testing scenarios.

Required Environment Variables:
    - APP_CLIENT_ID: Azure AD Application (client) ID
    - APP_CLIENT_SECRET: Client secret for the application
    - TENANT_ID: Azure AD Tenant ID
"""

import logging
from typing import Optional
from msal import ConfidentialClientApplication

logger = logging.getLogger(__name__)


class ServicePrincipalAuth:
    """
    Service Principal authentication for automated/headless scenarios.
    
    Uses client credentials flow (OAuth 2.0 client credentials grant) which
    doesn't require user interaction - perfect for CI/CD pipelines.
    """
    
    # Power Platform API scope
    DEFAULT_SCOPE = "https://api.powerplatform.com/.default"
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        scope: Optional[str] = None
    ):
        """
        Initialize service principal authentication.
        
        Args:
            client_id: Azure AD Application (client) ID
            client_secret: Client secret for the application
            tenant_id: Azure AD Tenant ID
            scope: Optional custom scope (defaults to Power Platform API)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.scope = scope or self.DEFAULT_SCOPE
        
        self._app: Optional[ConfidentialClientApplication] = None
        self._token_cache: dict = {}
    
    @property
    def authority(self) -> str:
        """Get the Azure AD authority URL."""
        return f"https://login.microsoftonline.com/{self.tenant_id}"
    
    def _get_app(self) -> ConfidentialClientApplication:
        """Get or create the MSAL Confidential Client Application."""
        if self._app is None:
            self._app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=self.authority
            )
        return self._app
    
    def acquire_token(self) -> str:
        """
        Acquire an access token using client credentials flow.
        
        Returns:
            Access token string
            
        Raises:
            Exception: If token acquisition fails
        """
        app = self._get_app()
        scopes = [self.scope]
        
        # Try to get token from cache first
        result = app.acquire_token_silent(scopes=scopes, account=None)
        
        if not result:
            logger.info("No cached token found, acquiring new token via client credentials")
            result = app.acquire_token_for_client(scopes=scopes)
        
        if "access_token" in result:
            # Log success without exposing token
            token = result["access_token"]
            logger.info(f"Successfully acquired access token (length: {len(token)})")
            return token
        else:
            error = result.get("error", "unknown_error")
            error_desc = result.get("error_description", "No description available")
            # Don't log full error_desc as it may contain hints about credentials
            logger.error(f"Token acquisition failed: {error}")
            raise AuthenticationError(f"Service principal token acquisition failed: {error}")
    
    def acquire_token_with_retry(self, max_retries: int = 3, retry_delay: float = 1.0) -> str:
        """
        Acquire token with exponential backoff retry.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (seconds)
            
        Returns:
            Access token string
            
        Raises:
            AuthenticationError: If all retry attempts fail
        """
        import time
        
        last_error = None
        for attempt in range(max_retries):
            try:
                return self.acquire_token()
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Token acquisition attempt {attempt + 1} failed, retrying in {delay}s")
                    time.sleep(delay)
        
        raise AuthenticationError(f"All {max_retries} token acquisition attempts failed: {last_error}")
    
    def validate_credentials(self) -> bool:
        """
        Validate that the service principal credentials are working.
        
        Returns:
            True if credentials are valid and token can be acquired
        """
        try:
            self.acquire_token()
            return True
        except Exception:
            # Don't log the exception details - could contain sensitive info
            logger.error("Credential validation failed")
            return False


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass
