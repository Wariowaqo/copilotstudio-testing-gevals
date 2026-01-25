# Enterprise Automation Guide - Copilot Studio Testing

This guide provides step-by-step instructions for implementing automated testing of Copilot Studio agents at enterprise scale.

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Phase 1: Service Principal Setup](#phase-1-service-principal-setup)
3. [Phase 2: Configuration Management](#phase-2-configuration-management)
4. [Phase 3: CI/CD Pipeline Setup](#phase-3-cicd-pipeline-setup)
5. [Phase 4: Azure Key Vault Integration](#phase-4-azure-key-vault-integration)
6. [Phase 5: Notifications Setup](#phase-5-notifications-setup)
7. [Phase 6: Result Storage & Analytics](#phase-6-result-storage--analytics)
8. [Phase 7: Multi-Agent Testing](#phase-7-multi-agent-testing)
9. [Operational Runbooks](#operational-runbooks)
10. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Enterprise Test Automation                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │  Test Cases  │    │   CI/CD      │    │   Copilot Studio         │  │
│  │  (CSV/Blob)  │───▶│  Pipeline    │───▶│   Agents                 │  │
│  └──────────────┘    │  (GH/ADO)    │    │   (Dev/Staging/Prod)     │  │
│                      └──────┬───────┘    └──────────────────────────┘  │
│                             │                                           │
│          ┌──────────────────┼──────────────────┐                       │
│          ▼                  ▼                  ▼                        │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐               │
│  │ Azure Key    │   │   DeepEval   │   │   Reports    │               │
│  │ Vault        │   │   (LLM Eval) │   │   (Blob)     │               │
│  │ (Secrets)    │   │              │   │              │               │
│  └──────────────┘   └──────────────┘   └──────┬───────┘               │
│                                               │                        │
│                     ┌─────────────────────────┼─────────────────┐     │
│                     ▼                         ▼                  ▼     │
│             ┌──────────────┐          ┌───────────┐      ┌──────────┐ │
│             │  Power BI    │          │  Teams    │      │ Result   │ │
│             │  Dashboard   │          │  Alerts   │      │ Storage  │ │
│             └──────────────┘          └───────────┘      └──────────┘ │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Service Principal Setup

### Overview
Replace interactive authentication with service principal (client credentials) authentication for headless CI/CD execution.

### Steps

#### 1.1 Create App Registration in Azure AD

1. Go to **Azure Portal** → **Azure Active Directory** → **App registrations**
2. Click **New registration**
3. Configure:
   - **Name**: `CopilotStudio-Testing-SP`
   - **Supported account types**: Single tenant
   - **Redirect URI**: Leave blank (not needed for client credentials)
4. Click **Register**

#### 1.2 Create Client Secret

1. In your app registration, go to **Certificates & secrets**
2. Click **New client secret**
3. Set description: `CI/CD Pipeline Secret`
4. Set expiration: 24 months (or per your security policy)
5. **Copy the secret value immediately** (it won't be shown again)

#### 1.3 Configure API Permissions

1. Go to **API permissions** → **Add a permission**
2. Select **APIs my organization uses**
3. Search for **Power Platform API**
4. Select **Application permissions** (not Delegated)
5. Add `CopilotStudio.Copilots.Invoke`
6. Click **Grant admin consent**

> ⚠️ **Important**: Application permissions require admin consent. Contact your Azure AD administrator if you don't have the required privileges.

#### 1.4 Update Your Code

The new authentication system automatically detects the environment:
- If `APP_CLIENT_SECRET` is set → Uses Service Principal
- Otherwise → Falls back to Interactive authentication

```python
# Authentication is handled automatically
from testinglib.copilot_client import CopilotStudioClient

client = CopilotStudioClient()  # Auto-detects auth method
```

---

## Phase 2: Configuration Management

### Overview
Centralize all configuration using the new `EnterpriseConfig` class.

### Environment Variables

Create environment-specific `.env` files or set in CI/CD:

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_CLIENT_ID` | Yes | Azure AD Application ID |
| `APP_CLIENT_SECRET` | CI only | Client secret (for automation) |
| `TENANT_ID` | Yes | Azure AD Tenant ID |
| `ENVIRONMENT_ID` | Yes | Power Platform Environment ID |
| `AGENT_IDENTIFIER` | Yes | Copilot Studio Agent schema name |
| `ENVIRONMENT` | No | dev/staging/prod (default: dev) |
| `KEY_VAULT_NAME` | No | Azure Key Vault name for secrets |

### Configuration File

Copy `.env.enterprise` to `.env` and configure:

```bash
cp .env.enterprise .env
# Edit .env with your values
```

### Validate Configuration

```python
from testinglib.enterprise_config import EnterpriseConfig

config = EnterpriseConfig.load()
errors = config.validate()
if errors:
    print("Configuration errors:", errors)
else:
    print("Configuration valid!")
    print(config.to_dict())
```

---

## Phase 3: CI/CD Pipeline Setup

### GitHub Actions (Recommended)

#### 3.1 Configure Repository Secrets

Go to **Settings** → **Secrets and variables** → **Actions**:

| Secret Name | Description |
|------------|-------------|
| `APP_CLIENT_ID` | Service principal client ID |
| `APP_CLIENT_SECRET` | Service principal secret |
| `TENANT_ID` | Azure AD tenant ID |
| `ENVIRONMENT_ID` | Power Platform environment ID |
| `AGENT_IDENTIFIER` | Agent schema name |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name |
| `TEAMS_WEBHOOK_URL` | (Optional) Teams webhook URL |

#### 3.2 Create Environments

1. Go to **Settings** → **Environments**
2. Create environments: `dev`, `staging`, `prod`
3. Add environment-specific secrets to each

#### 3.3 Pipeline File

The pipeline is already configured at `.github/workflows/copilot-tests.yml`

**Trigger Options**:
- **Push**: Automatically on push to main/develop
- **Schedule**: Nightly at 2 AM UTC
- **Manual**: Via GitHub Actions UI

### Azure DevOps Alternative

Use `azure-pipelines.yml` for Azure DevOps:

1. Create Variable Groups for each environment
2. Link pipeline to repository
3. Configure service connections

---

## Phase 4: Azure Key Vault Integration

### Overview
Store secrets securely in Azure Key Vault instead of pipeline secrets.

### 4.1 Create Key Vault

```bash
# Create resource group
az group create --name rg-copilot-testing --location eastus

# Create Key Vault
az keyvault create \
  --name kv-copilot-testing \
  --resource-group rg-copilot-testing \
  --location eastus
```

### 4.2 Add Secrets

```bash
# Add each secret
az keyvault secret set --vault-name kv-copilot-testing --name app-client-id --value "your-client-id"
az keyvault secret set --vault-name kv-copilot-testing --name app-client-secret --value "your-secret"
az keyvault secret set --vault-name kv-copilot-testing --name tenant-id --value "your-tenant-id"
# ... add remaining secrets
```

### 4.3 Grant Access to Service Principal

```bash
az keyvault set-policy \
  --name kv-copilot-testing \
  --spn $APP_CLIENT_ID \
  --secret-permissions get list
```

### 4.4 Use Key Vault in Tests

Set `KEY_VAULT_NAME` environment variable:

```bash
export KEY_VAULT_NAME=kv-copilot-testing
```

Secrets are automatically loaded at startup.

---

## Phase 5: Notifications Setup

### Microsoft Teams

#### 5.1 Create Incoming Webhook

1. In Teams, go to the target channel
2. Click **⋯** → **Connectors**
3. Add **Incoming Webhook**
4. Name it: `Copilot Testing Alerts`
5. Copy the webhook URL

#### 5.2 Configure Webhook

Set in environment or Key Vault:

```bash
export TEAMS_WEBHOOK_URL="https://outlook.office.com/webhook/..."
```

#### 5.3 Notification Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTIFY_ON_FAILURE` | true | Send notification on test failures |
| `NOTIFY_ON_SUCCESS` | false | Send notification on success |
| `FAILURE_THRESHOLD` | 0.80 | Alert if pass rate drops below |

### Slack Alternative

Create Slack incoming webhook and set:
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

---

## Phase 6: Result Storage & Analytics

### Local Storage (Development)

Results are stored in `results/` directory by default:
```
results/
├── index.json
└── 2026/
    └── 01/
        └── 25/
            └── abc123-run-id.json
```

### Azure Blob Storage (Production)

#### 6.1 Create Storage Account

```bash
az storage account create \
  --name stcopilottesting \
  --resource-group rg-copilot-testing \
  --location eastus \
  --sku Standard_LRS

# Get connection string
az storage account show-connection-string \
  --name stcopilottesting \
  --resource-group rg-copilot-testing
```

#### 6.2 Configure

```bash
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
```

### Power BI Dashboard

Connect Power BI to Azure Blob Storage for visualizations:

1. **Get Data** → **Azure** → **Azure Blob Storage**
2. Create visuals for:
   - Pass rate trends over time
   - Score distributions by metric
   - Agent comparison charts
   - Failure analysis

---

## Phase 7: Multi-Agent Testing

### Agent Registry

Configure multiple agents in `agents.json`:

```json
{
  "agents": [
    {
      "id": "support-agent-prod",
      "name": "Customer Support Agent",
      "environment_id": "xxx-xxx-xxx",
      "agent_identifier": "cr26e_supportAgent",
      "criticality": "critical",
      "test_schedule": "hourly"
    }
  ]
}
```

### Run Multi-Agent Tests

```python
import asyncio
from testinglib.multi_agent import AgentRegistry, MultiAgentTestOrchestrator

async def main():
    registry = AgentRegistry("agents.json")
    orchestrator = MultiAgentTestOrchestrator(registry)
    
    # Test all critical agents
    results = await orchestrator.test_by_criticality("critical")
    
    # Generate summary report
    orchestrator.generate_summary_report(results)

asyncio.run(main())
```

### Schedule by Criticality

| Criticality | Schedule | Use Case |
|------------|----------|----------|
| Critical | Hourly | Customer-facing production agents |
| High | Every 4 hours | Important internal agents |
| Medium | Daily | Standard agents |
| Low | Weekly | Development/experimental agents |

---

## Operational Runbooks

### Runbook 1: Adding a New Agent

1. Add agent to `agents.json`
2. Create test cases CSV in `input/`
3. Configure environment-specific secrets
4. Run initial test manually
5. Enable scheduled testing

### Runbook 2: Investigating Test Failures

1. Check Teams/Slack notification for summary
2. Download HTML report from pipeline artifacts
3. Review failed test cases:
   - Low correctness → Agent giving wrong answers
   - Low relevancy → Agent going off-topic
   - Low coherence → Response quality issues
4. Check agent configuration in Copilot Studio
5. Review knowledge sources and topics

### Runbook 3: Updating Test Cases

1. Export current test cases
2. Add/modify test cases in CSV
3. Create PR with changes
4. Review test case quality
5. Merge and verify next run

### Runbook 4: Emergency Response

If critical agent tests are failing:

1. Check if agent is published and accessible
2. Verify authentication is working
3. Review recent agent changes
4. Test manually in Copilot Studio
5. Rollback if necessary

---

## Troubleshooting

### Common Issues

#### "Token acquisition failed"

**Cause**: Service principal authentication issue

**Solution**:
1. Verify `APP_CLIENT_SECRET` is correct and not expired
2. Check API permissions have admin consent
3. Verify tenant ID is correct

#### "Agent not found"

**Cause**: Invalid agent identifier or environment

**Solution**:
1. Verify `ENVIRONMENT_ID` matches Power Platform environment
2. Check `AGENT_IDENTIFIER` (schema name from Copilot Studio settings)
3. Ensure agent is published

#### "DeepEval evaluation failed"

**Cause**: Azure OpenAI configuration issue

**Solution**:
1. Verify Azure OpenAI endpoint and key
2. Check deployment name matches
3. Ensure model quota is available

#### "Key Vault access denied"

**Cause**: Insufficient permissions

**Solution**:
1. Verify service principal has secret read permissions
2. Check Key Vault firewall settings
3. Ensure using correct identity in pipeline

---

## Security Best Practices

1. **Rotate secrets regularly** - Set calendar reminders for secret expiration
2. **Use separate service principals** - One per environment (dev/staging/prod)
3. **Limit Key Vault access** - Only grant necessary permissions
4. **Audit access** - Enable Key Vault logging and review
5. **Secure webhooks** - Use HTTPS and validate origins
6. **Protect test data** - Don't include sensitive data in test cases

---

## Support

For issues or questions:
- Review this documentation
- Check the troubleshooting section
- Open a GitHub issue
- Contact the platform team
