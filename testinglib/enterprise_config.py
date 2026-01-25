"""
Enterprise Configuration Management for Copilot Studio Testing

This module provides centralized configuration management with support for:
- Multiple environments (dev, staging, production)
- Azure Key Vault integration for secrets
- Environment variable fallbacks
- Configuration validation
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Supported deployment environments."""
    DEVELOPMENT = "dev"
    STAGING = "staging"
    PRODUCTION = "prod"
    
    @classmethod
    def from_string(cls, value: str) -> "Environment":
        """Parse environment from string."""
        mapping = {
            "dev": cls.DEVELOPMENT,
            "development": cls.DEVELOPMENT,
            "staging": cls.STAGING,
            "stage": cls.STAGING,
            "prod": cls.PRODUCTION,
            "production": cls.PRODUCTION,
        }
        return mapping.get(value.lower(), cls.DEVELOPMENT)


@dataclass
class AgentConfig:
    """Configuration for a single Copilot Studio agent."""
    name: str
    environment_id: str
    agent_identifier: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "environment_id": self.environment_id,
            "agent_identifier": self.agent_identifier,
            "description": self.description,
            "tags": self.tags,
        }


@dataclass
class AzureOpenAIConfig:
    """Configuration for Azure OpenAI (DeepEval)."""
    endpoint: str
    api_key: str
    deployment_name: str
    model_name: str = "gpt-4o"
    api_version: str = "2025-01-01-preview"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "api_key": "***",  # Don't expose in logs
            "deployment_name": self.deployment_name,
            "model_name": self.model_name,
            "api_version": self.api_version,
        }


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    teams_webhook_url: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)
    notify_on_failure: bool = True
    notify_on_success: bool = False
    failure_threshold: float = 0.80  # Notify if pass rate drops below this


@dataclass 
class TestConfig:
    """Test execution configuration."""
    test_cases_path: str = "input/test_cases.csv"
    reports_dir: str = "reports"
    overall_threshold: float = 0.50
    metric_weights: Dict[str, float] = field(default_factory=lambda: {
        "correctness": 0.40,
        "relevancy": 0.25,
        "completeness": 0.20,
        "coherence": 0.15,
    })
    parallel_workers: int = 1
    timeout_seconds: int = 300


class EnterpriseConfig:
    """
    Centralized enterprise configuration manager.
    
    Loads configuration from environment variables with support for:
    - Azure Key Vault (when KEY_VAULT_NAME is set)
    - Local .env files (for development)
    - Direct environment variables
    
    Usage:
        config = EnterpriseConfig.load()
        print(config.current_environment)
        print(config.agent.environment_id)
    """
    
    def __init__(
        self,
        environment: Environment,
        client_id: str,
        tenant_id: str,
        client_secret: Optional[str],
        agent: AgentConfig,
        azure_openai: Optional[AzureOpenAIConfig],
        notifications: NotificationConfig,
        test_config: TestConfig,
        key_vault_name: Optional[str] = None,
    ):
        self.environment = environment
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.client_secret = client_secret
        self.agent = agent
        self.azure_openai = azure_openai
        self.notifications = notifications
        self.test_config = test_config
        self.key_vault_name = key_vault_name
    
    @property
    def current_environment(self) -> str:
        """Get the current environment name."""
        return self.environment.value
    
    @property
    def is_ci(self) -> bool:
        """Check if running in CI environment."""
        ci_vars = ["CI", "GITHUB_ACTIONS", "AZURE_PIPELINES", "TF_BUILD"]
        return any(os.environ.get(var) for var in ci_vars)
    
    @classmethod
    def load(cls, env_file: Optional[str] = None) -> "EnterpriseConfig":
        """
        Load configuration from environment.
        
        Args:
            env_file: Optional path to .env file
            
        Returns:
            EnterpriseConfig instance
        """
        # Load .env file if specified or exists
        if env_file or os.path.exists(".env"):
            from dotenv import load_dotenv
            load_dotenv(env_file or ".env")
        
        # Check for Key Vault and load secrets if available
        key_vault_name = os.environ.get("KEY_VAULT_NAME")
        if key_vault_name:
            cls._load_from_keyvault(key_vault_name)
        
        # Parse environment
        env_str = os.environ.get("ENVIRONMENT", "dev")
        environment = Environment.from_string(env_str)
        
        # Required credentials
        client_id = os.environ.get("APP_CLIENT_ID")
        tenant_id = os.environ.get("TENANT_ID")
        client_secret = os.environ.get("APP_CLIENT_SECRET")
        
        if not client_id:
            raise ValueError("APP_CLIENT_ID is required")
        if not tenant_id:
            raise ValueError("TENANT_ID is required")
        
        # Agent configuration
        agent = AgentConfig(
            name=os.environ.get("AGENT_NAME", "Default Agent"),
            environment_id=os.environ.get("ENVIRONMENT_ID", ""),
            agent_identifier=os.environ.get("AGENT_IDENTIFIER", ""),
            description=os.environ.get("AGENT_DESCRIPTION", ""),
        )
        
        if not agent.environment_id:
            raise ValueError("ENVIRONMENT_ID is required")
        if not agent.agent_identifier:
            raise ValueError("AGENT_IDENTIFIER is required")
        
        # Azure OpenAI configuration (optional)
        azure_openai = None
        aoai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        aoai_key = os.environ.get("AZURE_OPENAI_API_KEY")
        aoai_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        
        if aoai_endpoint and aoai_key and aoai_deployment:
            azure_openai = AzureOpenAIConfig(
                endpoint=aoai_endpoint,
                api_key=aoai_key,
                deployment_name=aoai_deployment,
                model_name=os.environ.get("AZURE_OPENAI_MODEL", "gpt-4o"),
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
            )
        
        # Notification configuration
        notifications = NotificationConfig(
            teams_webhook_url=os.environ.get("TEAMS_WEBHOOK_URL"),
            slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL"),
            notify_on_failure=os.environ.get("NOTIFY_ON_FAILURE", "true").lower() == "true",
            notify_on_success=os.environ.get("NOTIFY_ON_SUCCESS", "false").lower() == "true",
            failure_threshold=float(os.environ.get("FAILURE_THRESHOLD", "0.80")),
        )
        
        # Test configuration
        test_config = TestConfig(
            test_cases_path=os.environ.get("TEST_CASES_PATH", "input/test_cases.csv"),
            reports_dir=os.environ.get("REPORTS_DIR", "reports"),
            overall_threshold=float(os.environ.get("OVERALL_THRESHOLD", "0.50")),
            timeout_seconds=int(os.environ.get("TEST_TIMEOUT", "300")),
        )
        
        config = cls(
            environment=environment,
            client_id=client_id,
            tenant_id=tenant_id,
            client_secret=client_secret,
            agent=agent,
            azure_openai=azure_openai,
            notifications=notifications,
            test_config=test_config,
            key_vault_name=key_vault_name,
        )
        
        logger.info(f"Loaded configuration for environment: {environment.value}")
        return config
    
    @staticmethod
    def _load_from_keyvault(vault_name: str):
        """Load secrets from Azure Key Vault into environment variables."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            
            vault_url = f"https://{vault_name}.vault.azure.net"
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=vault_url, credential=credential)
            
            # Map of Key Vault secret names to environment variables
            secret_mappings = {
                "app-client-id": "APP_CLIENT_ID",
                "app-client-secret": "APP_CLIENT_SECRET", 
                "tenant-id": "TENANT_ID",
                "environment-id": "ENVIRONMENT_ID",
                "agent-identifier": "AGENT_IDENTIFIER",
                "azure-openai-endpoint": "AZURE_OPENAI_ENDPOINT",
                "azure-openai-api-key": "AZURE_OPENAI_API_KEY",
                "azure-openai-deployment": "AZURE_OPENAI_DEPLOYMENT",
                "teams-webhook-url": "TEAMS_WEBHOOK_URL",
            }
            
            for secret_name, env_var in secret_mappings.items():
                try:
                    secret = client.get_secret(secret_name)
                    if secret.value:
                        os.environ[env_var] = secret.value
                        logger.debug(f"Loaded {env_var} from Key Vault")
                except Exception:
                    # Secret doesn't exist, skip
                    pass
                    
            logger.info(f"Loaded secrets from Key Vault: {vault_name}")
            
        except ImportError:
            logger.warning(
                "Azure SDK not installed. Install with: pip install azure-identity azure-keyvault-secrets"
            )
        except Exception as e:
            logger.error(f"Failed to load secrets from Key Vault: {e}")
    
    def validate(self) -> List[str]:
        """
        Validate the configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not self.client_id:
            errors.append("APP_CLIENT_ID is missing")
        if not self.tenant_id:
            errors.append("TENANT_ID is missing")
        if not self.agent.environment_id:
            errors.append("ENVIRONMENT_ID is missing")
        if not self.agent.agent_identifier:
            errors.append("AGENT_IDENTIFIER is missing")
        
        # Check for client secret in CI
        if self.is_ci and not self.client_secret:
            errors.append("APP_CLIENT_SECRET is required in CI environment")
        
        # Validate metric weights sum to 1.0
        weights_sum = sum(self.test_config.metric_weights.values())
        if abs(weights_sum - 1.0) > 0.01:
            errors.append(f"Metric weights must sum to 1.0 (got {weights_sum})")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (safe for logging)."""
        return {
            "environment": self.environment.value,
            "is_ci": self.is_ci,
            "client_id": self.client_id[:8] + "..." if self.client_id else None,
            "tenant_id": self.tenant_id[:8] + "..." if self.tenant_id else None,
            "has_client_secret": bool(self.client_secret),
            "agent": self.agent.to_dict(),
            "azure_openai": self.azure_openai.to_dict() if self.azure_openai else None,
            "notifications": {
                "teams_configured": bool(self.notifications.teams_webhook_url),
                "slack_configured": bool(self.notifications.slack_webhook_url),
                "notify_on_failure": self.notifications.notify_on_failure,
            },
            "test_config": {
                "test_cases_path": self.test_config.test_cases_path,
                "overall_threshold": self.test_config.overall_threshold,
            },
        }
