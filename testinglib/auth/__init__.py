# Authentication module for Copilot Studio testing
# Supports both interactive and service principal authentication

from .auth_factory import AuthFactory, AuthMode
from .service_principal_auth import ServicePrincipalAuth, AuthenticationError
from .interactive_auth import InteractiveAuth

__all__ = [
    "AuthFactory",
    "AuthMode",
    "ServicePrincipalAuth",
    "InteractiveAuth",
    "AuthenticationError",
]
