#!/usr/bin/env python3
"""
Copilot Studio Testing CLI

Command-line interface for managing enterprise Copilot Studio testing.

Usage:
    python cli.py validate              # Validate configuration
    python cli.py test                  # Run tests for default agent
    python cli.py test --agent-id X     # Run tests for specific agent
    python cli.py test --all            # Run tests for all agents
    python cli.py test --critical       # Run tests for critical agents
    python cli.py list-agents           # List registered agents
    python cli.py keyvault validate     # Validate Key Vault secrets
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def cmd_validate(args):
    """Validate configuration."""
    from testinglib.enterprise_config import EnterpriseConfig
    
    print("🔍 Validating configuration...\n")
    
    try:
        config = EnterpriseConfig.load()
        errors = config.validate()
        
        if errors:
            print("❌ Configuration errors found:\n")
            for error in errors:
                print(f"   • {error}")
            return 1
        
        print("✅ Configuration is valid!\n")
        print("Configuration Summary:")
        print(f"   Environment: {config.environment.value}")
        print(f"   Agent: {config.agent.name}")
        print(f"   Agent ID: {config.agent.agent_identifier}")
        print(f"   Environment ID: {config.agent.environment_id[:8]}...")
        print(f"   Auth Mode: {'Service Principal' if config.client_secret else 'Interactive'}")
        print(f"   Azure OpenAI: {'Configured' if config.azure_openai else 'Not configured'}")
        print(f"   Teams Notifications: {'Configured' if config.notifications.teams_webhook_url else 'Not configured'}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return 1


def cmd_test(args):
    """Run tests."""
    import subprocess
    
    print(f"🧪 Running Copilot Studio Tests\n")
    print(f"   Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Build pytest command
    cmd = ["pytest", "tests/", "-v"]
    
    if args.quick:
        cmd.extend(["-x", "--tb=short"])  # Stop on first failure
    
    if args.html_report:
        os.makedirs("reports", exist_ok=True)
        # Reports are generated automatically by conftest.py
    
    # Set environment variables for specific agent if provided
    env = os.environ.copy()
    
    if args.agent_id:
        # Load agent from registry
        from testinglib.multi_agent import AgentRegistry
        registry = AgentRegistry()
        agent = registry.get(args.agent_id)
        
        if not agent:
            print(f"❌ Agent not found: {args.agent_id}")
            return 1
        
        print(f"   Agent: {agent.name}")
        env["ENVIRONMENT_ID"] = agent.environment_id
        env["AGENT_IDENTIFIER"] = agent.agent_identifier
        env["AGENT_NAME"] = agent.name
        
        if agent.test_cases_path:
            env["TEST_CASES_PATH"] = agent.test_cases_path
    
    print()
    
    # Run pytest
    result = subprocess.run(cmd, env=env)
    return result.returncode


def cmd_test_all(args):
    """Run tests for all agents."""
    asyncio.run(_test_multiple(args, filter_type="all"))


def cmd_test_critical(args):
    """Run tests for critical agents."""
    asyncio.run(_test_multiple(args, filter_type="critical"))


async def _test_multiple(args, filter_type: str):
    """Run tests for multiple agents."""
    from testinglib.multi_agent import AgentRegistry, MultiAgentTestOrchestrator
    
    print(f"🤖 Running Multi-Agent Tests ({filter_type})\n")
    
    registry = AgentRegistry()
    orchestrator = MultiAgentTestOrchestrator(
        registry,
        parallel=args.parallel if hasattr(args, 'parallel') else False
    )
    
    if filter_type == "critical":
        results = await orchestrator.test_by_criticality("critical")
    else:
        results = await orchestrator.test_all()
    
    # Generate summary
    orchestrator.generate_summary_report(results)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for r in results if r.success)
    
    for r in results:
        status = "✅" if r.success else "❌"
        print(f"{status} {r.agent_name}: {r.passed_tests}/{r.total_tests} tests passed")
    
    print("=" * 60)
    print(f"Total: {passed}/{total} agents passed")
    
    return 0 if passed == total else 1


def cmd_list_agents(args):
    """List registered agents."""
    from testinglib.multi_agent import AgentRegistry
    
    print("📋 Registered Agents\n")
    
    registry = AgentRegistry()
    agents = registry.get_all(enabled_only=not args.all)
    
    if not agents:
        print("No agents registered. Add agents to agents.json")
        return 0
    
    for agent in agents:
        status = "✓" if agent.enabled else "✗"
        print(f"[{status}] {agent.id}")
        print(f"    Name: {agent.name}")
        print(f"    Criticality: {agent.criticality}")
        print(f"    Schedule: {agent.test_schedule}")
        print(f"    Environment: {agent.environment_id[:8]}...")
        print()
    
    return 0


def cmd_keyvault_validate(args):
    """Validate Key Vault secrets."""
    vault_name = args.vault_name or os.environ.get("KEY_VAULT_NAME")
    
    if not vault_name:
        print("❌ Key Vault name not specified")
        print("   Use --vault-name or set KEY_VAULT_NAME environment variable")
        return 1
    
    from testinglib.keyvault import KeyVaultSecretManager
    
    print(f"🔐 Validating Key Vault: {vault_name}\n")
    
    kv = KeyVaultSecretManager(vault_name)
    
    if not kv.is_available:
        print("❌ Azure SDK not available or Key Vault not accessible")
        return 1
    
    results = kv.validate_secrets()
    
    all_ok = True
    for secret_name, exists in results.items():
        mapping = next((m for m in kv.secret_mappings if m.secret_name == secret_name), None)
        required = mapping.required if mapping else False
        
        if exists:
            status = "✅"
        elif required:
            status = "❌"
            all_ok = False
        else:
            status = "⚠️"
        
        req_label = "(required)" if required else "(optional)"
        print(f"   {status} {secret_name} {req_label}")
    
    print()
    if all_ok:
        print("✅ All required secrets are present")
    else:
        print("❌ Some required secrets are missing")
    
    return 0 if all_ok else 1


def cmd_notify_test(args):
    """Send test notification."""
    from testinglib.notifications import NotificationService, TestSummary
    
    print("📤 Sending test notification...\n")
    
    # Create dummy test summary
    summary = TestSummary(
        total=10,
        passed=8,
        failed=2,
        pass_rate=0.8,
        avg_score=0.75,
        duration_seconds=120,
        environment="test",
        agent_name="Test Agent",
        run_url="https://github.com"
    )
    
    notifier = NotificationService()
    results = notifier.send_all(summary)
    
    for channel, success in results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {channel}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Copilot Studio Testing CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python cli.py validate                    Validate configuration
    python cli.py test                        Run tests with default config
    python cli.py test --agent-id my-agent    Test specific agent
    python cli.py test --all                  Test all registered agents
    python cli.py test --critical             Test critical agents only
    python cli.py list-agents                 List all registered agents
    python cli.py keyvault validate           Validate Key Vault secrets
    python cli.py notify test                 Send test notification
        """
    )
    
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")
    validate_parser.set_defaults(func=cmd_validate)
    
    # test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("--agent-id", help="Specific agent ID to test")
    test_parser.add_argument("--all", action="store_true", help="Test all agents")
    test_parser.add_argument("--critical", action="store_true", help="Test critical agents")
    test_parser.add_argument("--parallel", action="store_true", help="Run in parallel")
    test_parser.add_argument("--quick", action="store_true", help="Quick mode (stop on first failure)")
    test_parser.add_argument("--html-report", action="store_true", default=True, help="Generate HTML report")
    test_parser.set_defaults(func=cmd_test)
    
    # list-agents command
    list_parser = subparsers.add_parser("list-agents", help="List registered agents")
    list_parser.add_argument("--all", action="store_true", help="Include disabled agents")
    list_parser.set_defaults(func=cmd_list_agents)
    
    # keyvault command
    kv_parser = subparsers.add_parser("keyvault", help="Key Vault operations")
    kv_subparsers = kv_parser.add_subparsers(dest="kv_command")
    
    kv_validate = kv_subparsers.add_parser("validate", help="Validate Key Vault secrets")
    kv_validate.add_argument("--vault-name", help="Key Vault name")
    kv_validate.set_defaults(func=cmd_keyvault_validate)
    
    # notify command
    notify_parser = subparsers.add_parser("notify", help="Notification operations")
    notify_subparsers = notify_parser.add_subparsers(dest="notify_command")
    
    notify_test = notify_subparsers.add_parser("test", help="Send test notification")
    notify_test.set_defaults(func=cmd_notify_test)
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Handle special cases
    if args.command == "test":
        if args.all:
            return asyncio.run(_test_multiple(args, "all"))
        elif args.critical:
            return asyncio.run(_test_multiple(args, "critical"))
    
    if hasattr(args, 'func'):
        return args.func(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
