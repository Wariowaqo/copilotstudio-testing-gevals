"""
Copilot Studio Client with Enterprise Authentication

This module provides a client for interacting with Copilot Studio agents.
It supports both interactive (local dev) and service principal (CI/CD) authentication.
"""

import asyncio
import logging
from os import environ, path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from microsoft_agents.copilotstudio.client import CopilotClient

from testinglib.config import McsConnectionSettings
from testinglib.auth import AuthFactory, AuthMode

logger = logging.getLogger(__name__)


class CopilotStudioClient:
    """
    Client for interacting with Copilot Studio agents.
    
    Automatically selects the appropriate authentication method:
    - Service Principal: When APP_CLIENT_SECRET is set (CI/CD)
    - Interactive: When running locally without client secret
    
    Usage:
        client = CopilotStudioClient()
        async for activity in client.client.ask_question("Hello"):
            print(activity.text)
    """
    
    def __init__(
        self,
        auth_mode: AuthMode = AuthMode.AUTO,
        connection_settings: Optional[McsConnectionSettings] = None
    ):
        """
        Initialize the Copilot Studio client.
        
        Args:
            auth_mode: Authentication mode (AUTO, SERVICE_PRINCIPAL, or INTERACTIVE)
            connection_settings: Optional custom connection settings
        """
        self.connection_settings = connection_settings or McsConnectionSettings()
        self.auth_mode = auth_mode
        self.conversation_id: Optional[str] = None
        
        # Acquire token using the auth factory
        self.token = self._acquire_token()
        
        # Initialize the Copilot client
        self.client = CopilotClient(self.connection_settings, self.token)
        
        logger.info(f"Initialized CopilotStudioClient with auth mode: {AuthFactory.get_current_mode()}")

    def _acquire_token(self) -> str:
        """
        Acquire authentication token using the appropriate method.
        
        Returns:
            Access token string
        """
        auth = AuthFactory.create(
            mode=self.auth_mode,
            client_id=self.connection_settings.app_client_id,
            tenant_id=self.connection_settings.tenant_id
        )
        return auth.acquire_token()
