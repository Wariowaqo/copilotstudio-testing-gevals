"""
Security Utilities for Copilot Studio Testing

This module provides security checks and validations:
- Credential validation without logging sensitive data
- Secret detection in files
- Security best practices enforcement
"""

import os
import re
import logging
from typing import List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SecurityValidator:
    """
    Validates security configurations and detects potential issues.
    
    Usage:
        validator = SecurityValidator()
        issues = validator.check_all()
        if issues:
            for issue in issues:
                print(f"[{issue[0]}] {issue[1]}")
    """
    
    # Patterns that indicate secrets (should never be in code/logs)
    SECRET_PATTERNS = [
        (r'sk-[a-zA-Z0-9]{20,}', 'OpenAI API Key'),
        (r'sk-proj-[a-zA-Z0-9\-_]{50,}', 'OpenAI Project API Key'),
        # Only match GUIDs that look like actual credentials (with context)
        (r'(client[_-]?id|secret|password|key)\s*[=:]\s*["\']?[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', 'Hardcoded GUID Credential'),
        (r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', 'Private Key'),
        # Only match actual connection strings, not patterns/docs
        (r'DefaultEndpointsProtocol=https;AccountName=[a-z0-9]+;', 'Azure Storage Connection String'),
    ]
    
    # Files that should never contain secrets
    CODE_EXTENSIONS = ['.py', '.js', '.ts', '.yml', '.yaml', '.json', '.md']
    
    # Files that are expected to contain secrets (should be gitignored)
    SECRET_FILES = ['.env', '.env.local', '.env.enterprise', 'token_cache.json']
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd())
    
    def check_all(self) -> List[Tuple[str, str]]:
        """
        Run all security checks.
        
        Returns:
            List of (severity, message) tuples
        """
        issues = []
        issues.extend(self.check_env_file_security())
        issues.extend(self.check_gitignore())
        issues.extend(self.check_code_for_secrets())
        issues.extend(self.check_logging_config())
        return issues
    
    def check_env_file_security(self) -> List[Tuple[str, str]]:
        """Check that .env files are properly secured."""
        issues = []
        
        for secret_file in self.SECRET_FILES:
            file_path = self.workspace_root / secret_file
            if file_path.exists():
                # Check if it's in gitignore
                if not self._is_gitignored(secret_file):
                    issues.append((
                        "CRITICAL",
                        f"Secret file '{secret_file}' exists but may not be in .gitignore"
                    ))
        
        return issues
    
    def check_gitignore(self) -> List[Tuple[str, str]]:
        """Check that .gitignore exists and covers secrets."""
        issues = []
        gitignore_path = self.workspace_root / ".gitignore"
        
        if not gitignore_path.exists():
            issues.append(("CRITICAL", ".gitignore file is missing"))
            return issues
        
        with open(gitignore_path, 'r') as f:
            content = f.read()
        
        required_patterns = ['.env', '*.bin', '__pycache__']
        for pattern in required_patterns:
            if pattern not in content:
                issues.append(("WARNING", f".gitignore should include '{pattern}'"))
        
        return issues
    
    def check_code_for_secrets(self) -> List[Tuple[str, str]]:
        """Scan code files for potential hardcoded secrets."""
        issues = []
        
        for ext in self.CODE_EXTENSIONS:
            for file_path in self.workspace_root.rglob(f"*{ext}"):
                # Skip virtual environments and node_modules
                if any(skip in str(file_path) for skip in ['venv', 'node_modules', '.git', '__pycache__']):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    for pattern, secret_type in self.SECRET_PATTERNS:
                        if re.search(pattern, content):
                            # Skip .env.example which has placeholders
                            if '.example' in str(file_path):
                                continue
                            # GUIDs in workflow files are often not secrets
                            if secret_type == 'GUID (potential secret)' and ext in ['.yml', '.yaml']:
                                continue
                            
                            rel_path = file_path.relative_to(self.workspace_root)
                            issues.append((
                                "CRITICAL",
                                f"Potential {secret_type} found in {rel_path}"
                            ))
                except Exception:
                    pass
        
        return issues
    
    def check_logging_config(self) -> List[Tuple[str, str]]:
        """Check that logging doesn't expose secrets."""
        issues = []
        
        # Check Python files for potential secret logging
        for file_path in self.workspace_root.rglob("*.py"):
            if any(skip in str(file_path) for skip in ['venv', '__pycache__']):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for logging of secret-related variables
                dangerous_patterns = [
                    r'logger\.(info|debug|warning|error).*secret',
                    r'logger\.(info|debug|warning|error).*password',
                    r'logger\.(info|debug|warning|error).*api_key',
                    r'print\(.*secret',
                    r'print\(.*password',
                    r'print\(.*api_key',
                ]
                
                for pattern in dangerous_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        rel_path = file_path.relative_to(self.workspace_root)
                        issues.append((
                            "WARNING",
                            f"Potential secret logging in {rel_path}"
                        ))
                        break
                        
            except Exception:
                pass
        
        return issues
    
    def _is_gitignored(self, filename: str) -> bool:
        """Check if a file pattern is in .gitignore."""
        gitignore_path = self.workspace_root / ".gitignore"
        if not gitignore_path.exists():
            return False
        
        with open(gitignore_path, 'r') as f:
            content = f.read()
        
        # Simple check - not a full gitignore parser
        return filename in content or f"*{Path(filename).suffix}" in content


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """
    Mask a secret value for safe logging.
    
    Args:
        value: The secret value
        visible_chars: Number of characters to show at the end
        
    Returns:
        Masked string like "***abc123"
    """
    if not value or len(value) <= visible_chars:
        return "***"
    return f"***{value[-visible_chars:]}"


def validate_credentials_present() -> Tuple[bool, List[str]]:
    """
    Validate that required credentials are present without logging their values.
    
    Returns:
        Tuple of (all_present, missing_vars)
    """
    required_vars = [
        "APP_CLIENT_ID",
        "TENANT_ID",
        "ENVIRONMENT_ID",
        "AGENT_IDENTIFIER",
    ]
    
    # At least one LLM key required
    llm_vars = ["OPENAI_API_KEY", "AZURE_OPENAI_API_KEY"]
    
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
    
    # Check for LLM
    if not any(os.environ.get(var) for var in llm_vars):
        missing.append("OPENAI_API_KEY or AZURE_OPENAI_API_KEY")
    
    return len(missing) == 0, missing


def run_security_audit() -> int:
    """
    Run security audit and return exit code.
    
    Returns:
        0 if no critical issues, 1 otherwise
    """
    print("🔒 Running Security Audit...")
    print("=" * 60)
    
    validator = SecurityValidator()
    issues = validator.check_all()
    
    critical_count = 0
    warning_count = 0
    
    for severity, message in issues:
        if severity == "CRITICAL":
            print(f"❌ [{severity}] {message}")
            critical_count += 1
        else:
            print(f"⚠️  [{severity}] {message}")
            warning_count += 1
    
    print("=" * 60)
    
    if critical_count > 0:
        print(f"❌ Found {critical_count} critical issue(s) and {warning_count} warning(s)")
        return 1
    elif warning_count > 0:
        print(f"⚠️  Found {warning_count} warning(s), no critical issues")
        return 0
    else:
        print("✅ No security issues found")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(run_security_audit())
