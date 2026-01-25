"""
Azure Key Vault Integration for Copilot Studio Testing

This module provides secure secret management using Azure Key Vault.
Supports multiple authentication methods:
- DefaultAzureCredential (recommended for CI/CD)
- Service Principal
- Managed Identity (when running in Azure)
"""

import logging
import os
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SecretMapping:
    """Mapping between Key Vault secret name and environment variable."""
    secret_name: str
    env_var: str
    required: bool = True


# Default secret mappings for Copilot Studio testing
DEFAULT_SECRET_MAPPINGS: List[SecretMapping] = [
    SecretMapping("app-client-id", "APP_CLIENT_ID", required=True),
    SecretMapping("app-client-secret", "APP_CLIENT_SECRET", required=True),
    SecretMapping("tenant-id", "TENANT_ID", required=True),
    SecretMapping("environment-id", "ENVIRONMENT_ID", required=True),
    SecretMapping("agent-identifier", "AGENT_IDENTIFIER", required=True),
    SecretMapping("azure-openai-endpoint", "AZURE_OPENAI_ENDPOINT", required=False),
    SecretMapping("azure-openai-api-key", "AZURE_OPENAI_API_KEY", required=False),
    SecretMapping("azure-openai-deployment", "AZURE_OPENAI_DEPLOYMENT", required=False),
    SecretMapping("teams-webhook-url", "TEAMS_WEBHOOK_URL", required=False),
    SecretMapping("slack-webhook-url", "SLACK_WEBHOOK_URL", required=False),
    SecretMapping("storage-connection-string", "AZURE_STORAGE_CONNECTION_STRING", required=False),
]


class KeyVaultSecretManager:
    """
    Manages secrets from Azure Key Vault.
    
    Usage:
        # Initialize with vault name
        kv = KeyVaultSecretManager("my-keyvault")
        
        # Load all secrets to environment
        kv.load_secrets_to_env()
        
        # Or get individual secret
        secret = kv.get_secret("app-client-id")
    """
    
    def __init__(
        self,
        vault_name: str,
        credential=None,
        secret_mappings: Optional[List[SecretMapping]] = None
    ):
        """
        Initialize Key Vault secret manager.
        
        Args:
            vault_name: Name of the Azure Key Vault
            credential: Azure credential (uses DefaultAzureCredential if not provided)
            secret_mappings: Custom secret name to env var mappings
        """
        self.vault_name = vault_name
        self.vault_url = f"https://{vault_name}.vault.azure.net"
        self.secret_mappings = secret_mappings or DEFAULT_SECRET_MAPPINGS
        
        # Initialize Azure SDK (lazy import for environments without Azure SDK)
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            
            self.credential = credential or DefaultAzureCredential()
            self.client = SecretClient(
                vault_url=self.vault_url,
                credential=self.credential
            )
            self._available = True
            logger.info(f"Connected to Key Vault: {vault_name}")
            
        except ImportError:
            logger.warning(
                "Azure SDK not installed. Install with: "
                "pip install azure-identity azure-keyvault-secrets"
            )
            self._available = False
            self.client = None
    
    @property
    def is_available(self) -> bool:
        """Check if Key Vault client is available."""
        return self._available
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Get a secret value from Key Vault.
        
        Args:
            secret_name: Name of the secret in Key Vault
            
        Returns:
            Secret value or None if not found
        """
        if not self._available:
            logger.warning("Key Vault not available, cannot retrieve secret")
            return None
        
        try:
            secret = self.client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            logger.debug(f"Secret '{secret_name}' not found in Key Vault: {e}")
            return None
    
    def load_secrets_to_env(
        self,
        overwrite: bool = False,
        raise_on_missing: bool = False
    ) -> Dict[str, bool]:
        """
        Load all mapped secrets from Key Vault to environment variables.
        
        Args:
            overwrite: Whether to overwrite existing environment variables
            raise_on_missing: Whether to raise error if required secret is missing
            
        Returns:
            Dictionary of secret names and whether they were loaded successfully
        """
        if not self._available:
            logger.warning("Key Vault not available, skipping secret loading")
            return {}
        
        results = {}
        missing_required = []
        
        for mapping in self.secret_mappings:
            # Skip if env var already set and not overwriting
            if not overwrite and os.environ.get(mapping.env_var):
                logger.debug(f"Skipping {mapping.env_var} - already set")
                results[mapping.secret_name] = True
                continue
            
            # Get secret from Key Vault
            value = self.get_secret(mapping.secret_name)
            
            if value:
                os.environ[mapping.env_var] = value
                results[mapping.secret_name] = True
                logger.info(f"Loaded {mapping.env_var} from Key Vault")
            else:
                results[mapping.secret_name] = False
                if mapping.required:
                    missing_required.append(mapping.secret_name)
                    logger.warning(f"Required secret missing: {mapping.secret_name}")
        
        if raise_on_missing and missing_required:
            raise ValueError(
                f"Required secrets missing from Key Vault: {', '.join(missing_required)}"
            )
        
        return results
    
    def list_secrets(self) -> List[str]:
        """
        List all secret names in the Key Vault.
        
        Returns:
            List of secret names
        """
        if not self._available:
            return []
        
        try:
            return [s.name for s in self.client.list_properties_of_secrets()]
        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []
    
    def validate_secrets(self) -> Dict[str, bool]:
        """
        Validate that all required secrets exist in Key Vault.
        
        Returns:
            Dictionary of secret names and whether they exist
        """
        if not self._available:
            return {m.secret_name: False for m in self.secret_mappings}
        
        existing_secrets = set(self.list_secrets())
        return {
            mapping.secret_name: mapping.secret_name in existing_secrets
            for mapping in self.secret_mappings
        }


def load_secrets_from_keyvault(
    vault_name: Optional[str] = None,
    overwrite: bool = False
) -> bool:
    """
    Convenience function to load secrets from Key Vault.
    
    Args:
        vault_name: Key Vault name (or from KEY_VAULT_NAME env var)
        overwrite: Whether to overwrite existing env vars
        
    Returns:
        True if secrets were loaded successfully
    """
    vault_name = vault_name or os.environ.get("KEY_VAULT_NAME")
    
    if not vault_name:
        logger.debug("No Key Vault configured (KEY_VAULT_NAME not set)")
        return False
    
    try:
        kv = KeyVaultSecretManager(vault_name)
        if kv.is_available:
            kv.load_secrets_to_env(overwrite=overwrite)
            return True
    except Exception as e:
        logger.error(f"Failed to load secrets from Key Vault: {e}")
    
    return False


# =============================================================================
# CLI for testing Key Vault connection
# =============================================================================
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 2:
        print("Usage: python keyvault.py <vault-name> [--validate]")
        sys.exit(1)
    
    vault_name = sys.argv[1]
    validate_only = "--validate" in sys.argv
    
    kv = KeyVaultSecretManager(vault_name)
    
    if not kv.is_available:
        print("❌ Azure SDK not available")
        sys.exit(1)
    
    if validate_only:
        print(f"\n🔍 Validating secrets in Key Vault: {vault_name}")
        results = kv.validate_secrets()
        
        for secret_name, exists in results.items():
            mapping = next((m for m in kv.secret_mappings if m.secret_name == secret_name), None)
            required = "required" if mapping and mapping.required else "optional"
            status = "✅" if exists else "❌"
            print(f"  {status} {secret_name} ({required})")
    else:
        print(f"\n📥 Loading secrets from Key Vault: {vault_name}")
        results = kv.load_secrets_to_env()
        
        loaded = sum(1 for v in results.values() if v)
        total = len(results)
        print(f"\n✅ Loaded {loaded}/{total} secrets to environment")
