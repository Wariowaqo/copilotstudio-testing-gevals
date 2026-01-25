"""
Authentication Factory for Copilot Studio Testing

Automatically selects the appropriate authentication method based on
available credentials and environment configuration.

Priority:
    1. Service Principal (if APP_CLIENT_SECRET is set) - for CI/CD
    2. Interactive (fallback) - for local development
"""

import logging
import os
from enum import Enum
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class AuthMode(Enum):
    """Available authentication modes."""
    AUTO = "auto"              # Automatically detect based on environment
    SERVICE_PRINCIPAL = "sp"   # Force service principal authentication
    INTERACTIVE = "interactive" # Force interactive authentication


class TokenProvider(Protocol):
    """Protocol for token providers."""
    def acquire_token(self) -> str:
        """Acquire an access token."""
        ...


class AuthFactory:
    """
    Factory for creating authentication providers.
    
    Automatically selects the best authentication method based on
    available credentials, or allows explicit selection.
    
    Usage:
        # Auto-detect (recommended)
        auth = AuthFactory.create()
        token = auth.acquire_token()
        
        # Force service principal
        auth = AuthFactory.create(mode=AuthMode.SERVICE_PRINCIPAL)
        
        # Force interactive
        auth = AuthFactory.create(mode=AuthMode.INTERACTIVE)
    """
    
    @staticmethod
    def create(
        mode: AuthMode = AuthMode.AUTO,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
        cache_path: Optional[str] = None
    ) -> TokenProvider:
        """
        Create an authentication provider.
        
        Args:
            mode: Authentication mode (AUTO, SERVICE_PRINCIPAL, or INTERACTIVE)
            client_id: Azure AD Application ID (or from APP_CLIENT_ID env var)
            client_secret: Client secret (or from APP_CLIENT_SECRET env var)
            tenant_id: Azure AD Tenant ID (or from TENANT_ID env var)
            cache_path: Optional token cache path for interactive auth
            
        Returns:
            TokenProvider instance
            
        Raises:
            ValueError: If required credentials are missing
        """
        # Get credentials from parameters or environment
        client_id = client_id or os.environ.get("APP_CLIENT_ID")
        client_secret = client_secret or os.environ.get("APP_CLIENT_SECRET")
        tenant_id = tenant_id or os.environ.get("TENANT_ID")
        
        # Validate required credentials
        if not client_id:
            raise ValueError("APP_CLIENT_ID is required")
        if not tenant_id:
            raise ValueError("TENANT_ID is required")
        
        # Determine authentication mode
        if mode == AuthMode.AUTO:
            mode = AuthFactory._detect_mode(client_secret)
        
        # Create appropriate provider
        if mode == AuthMode.SERVICE_PRINCIPAL:
            return AuthFactory._create_service_principal(
                client_id, client_secret, tenant_id
            )
        else:
            return AuthFactory._create_interactive(
                client_id, tenant_id, cache_path
            )
    
    @staticmethod
    def _detect_mode(client_secret: Optional[str]) -> AuthMode:
        """Auto-detect the best authentication mode."""
        # Check for CI/CD environment indicators
        ci_indicators = [
            "CI",
            "GITHUB_ACTIONS",
            "AZURE_PIPELINES",
            "TF_BUILD",
            "JENKINS_URL",
            "GITLAB_CI"
        ]
        
        is_ci = any(os.environ.get(var) for var in ci_indicators)
        has_secret = bool(client_secret)
        
        if has_secret:
            logger.info("Client secret detected, using service principal authentication")
            return AuthMode.SERVICE_PRINCIPAL
        elif is_ci:
            logger.warning("CI environment detected but no client secret found!")
            raise ValueError(
                "Running in CI environment but APP_CLIENT_SECRET is not set. "
                "Service principal authentication requires a client secret."
            )
        else:
            logger.info("Using interactive authentication (local development)")
            return AuthMode.INTERACTIVE
    
    @staticmethod
    def _create_service_principal(
        client_id: str,
        client_secret: Optional[str],
        tenant_id: str
    ):
        """Create a service principal auth provider."""
        if not client_secret:
            raise ValueError(
                "APP_CLIENT_SECRET is required for service principal authentication"
            )
        
        from .service_principal_auth import ServicePrincipalAuth
        return ServicePrincipalAuth(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id
        )
    
    @staticmethod
    def _create_interactive(
        client_id: str,
        tenant_id: str,
        cache_path: Optional[str]
    ):
        """Create an interactive auth provider."""
        from .interactive_auth import InteractiveAuth
        return InteractiveAuth(
            client_id=client_id,
            tenant_id=tenant_id,
            cache_path=cache_path
        )
    
    @staticmethod
    def get_current_mode() -> str:
        """
        Get a description of the current authentication mode.
        
        Returns:
            Human-readable description of the auth mode
        """
        client_secret = os.environ.get("APP_CLIENT_SECRET")
        
        if client_secret:
            return "Service Principal (automated/CI)"
        else:
            return "Interactive (local development)"
