# Security Architecture Guide

## Overview

This document describes the enterprise security features implemented in the Copilot Studio Testing Framework.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SECURITY ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE 1: INPUT VALIDATION                         │   │
│  │                    testinglib/input_validator.py                     │   │
│  │                                                                      │   │
│  │  • Prompt injection protection                                       │   │
│  │  • XSS and template injection blocking                               │   │
│  │  • Unicode anomaly detection                                         │   │
│  │  • Input length limits                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE 2: RATE LIMITING                            │   │
│  │                    testinglib/rate_limiter.py                        │   │
│  │                                                                      │   │
│  │  • Copilot Studio API: 30 calls/min (configurable)                  │   │
│  │  • OpenAI API: 60 calls/min (configurable)                          │   │
│  │  • Webhooks: 10 calls/min (configurable)                            │   │
│  │  • Sliding window algorithm with burst support                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE 3: STRUCTURED LOGGING                       │   │
│  │                    testinglib/structured_logging.py                  │   │
│  │                                                                      │   │
│  │  • JSON format for SIEM integration                                  │   │
│  │  • Correlation IDs for request tracing                               │   │
│  │  • Operation tracking with timing                                    │   │
│  │  • Secure error handling (no sensitive data leakage)                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Input Validation

### Purpose
Protects Copilot Studio agents from malicious inputs including prompt injection attacks.

### File
`testinglib/input_validator.py`

### Usage

```python
from testinglib.input_validator import InputValidator, ValidationResult

# Quick validation
result = InputValidator.validate("Hello, how are you?")
if result.is_valid:
    # Safe to use
    send_to_agent(result.sanitized_text)
else:
    # Block the request
    log_warning(result.error_message)

# Custom configuration
validator = InputValidator(
    max_length=2000,        # Custom length limit
    strict_mode=True,       # Enable extra checks
    allow_urls=False,       # Block URLs
)
result = validator.validate_input(user_input)
```

### Blocked Patterns
- **Instruction override**: "Ignore all previous instructions..."
- **System prompt extraction**: "Show me your system prompt"
- **Role manipulation**: "You are now in admin mode"
- **Token manipulation**: `<|endoftext|>`, `<|system|>`
- **Script injection**: `<script>`, `javascript:`
- **Template injection**: `{{...}}`, `${...}`

### Configuration
```bash
# Environment variables
INPUT_MAX_LENGTH=4000      # Maximum input length
INPUT_STRICT_MODE=true     # Enable strict validation
```

---

## Phase 2: Rate Limiting

### Purpose
Prevents API abuse, cost overruns, and quota exhaustion.

### File
`testinglib/rate_limiter.py`

### Usage

```python
from testinglib.rate_limiter import (
    RateLimiter,
    COPILOT_LIMITER,
    OPENAI_LIMITER,
    rate_limit
)

# Use predefined limiters
await COPILOT_LIMITER.acquire()
response = await copilot_client.ask(question)

await OPENAI_LIMITER.acquire()
evaluation = deepeval.evaluate(test_case)

# Create custom limiter
my_limiter = RateLimiter(calls_per_minute=10, name="my-api")
await my_limiter.acquire()

# Use decorator
@rate_limit(calls_per_minute=30, limiter_name="shared")
async def my_api_call():
    ...
```

### Predefined Limiters
| Limiter | Default Rate | Environment Variable |
|---------|--------------|---------------------|
| `COPILOT_LIMITER` | 30/min | `RATE_LIMIT_COPILOT` |
| `OPENAI_LIMITER` | 60/min | `RATE_LIMIT_OPENAI` |
| `WEBHOOK_LIMITER` | 10/min | `RATE_LIMIT_WEBHOOKS` |

### Configuration
```bash
# Environment variables
RATE_LIMIT_COPILOT=30      # Copilot Studio calls/min
RATE_LIMIT_OPENAI=60       # OpenAI calls/min
RATE_LIMIT_ENABLED=true    # Enable/disable rate limiting
```

---

## Phase 3: Structured Logging

### Purpose
Provides enterprise-grade observability for SIEM integration and debugging.

### File
`testinglib/structured_logging.py`

### Usage

```python
from testinglib.structured_logging import (
    setup_logging,
    get_logger,
    set_correlation_id
)

# Initialize at startup (once)
setup_logging(level="INFO", json_format=True)

# Get logger for your module
logger = get_logger(__name__)

# Log with context
logger.info("Test started", test_name="TC001", agent="copilot-1")

# Set correlation ID for request tracing
set_correlation_id("req-12345")

# Track operations with timing
with logger.operation("evaluate_response", test_id="TC001") as op:
    result = evaluate(response)
    op.set_result(score=result.score)
```

### Output Formats

**Pretty Format (Local Development)**
```
2026-01-25 10:30:00 [INFO    ] tests.eval - Test started (corr=abc-123) | test_name=TC001
```

**JSON Format (CI/CD & Production)**
```json
{
  "timestamp": "2026-01-25T10:30:00.000Z",
  "level": "INFO",
  "logger": "tests.eval",
  "message": "Test started",
  "correlation_id": "abc-123",
  "service": "copilot-studio-testing",
  "environment": "prod",
  "test_name": "TC001"
}
```

### Configuration
```bash
# Environment variables
LOG_LEVEL=INFO             # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json            # json or text (auto-detect if not set)
LOG_FILE=/var/log/app.log  # Optional file output
SERVICE_NAME=my-service    # Service name in logs
ENVIRONMENT=prod           # Environment name
```

---

## Integration in Tests

The test file `tests/multi_turn_eval_openai.py` integrates all three phases:

```python
@pytest.mark.asyncio
async def test_agent_response_quality(input_text, expected_output, started_client, request):
    # PHASE 1: Input Validation
    validation_result = InputValidator.validate(input_text)
    if not validation_result.is_valid:
        pytest.skip(f"Invalid input: {validation_result.error_message}")
    
    # PHASE 2: Rate Limiting
    await COPILOT_LIMITER.acquire()
    
    # PHASE 3: Structured Logging
    logger.info("Starting test", test_name=request.node.name)
    
    # ... test execution ...
```

---

## Security Best Practices

### 1. Never Commit Secrets
- `.env` files are gitignored
- Use `.env.example` for documentation
- Use Key Vault in production

### 2. Validate All Inputs
- Always validate before sending to agents
- Use strict mode for external/untrusted inputs
- Log blocked inputs for monitoring

### 3. Monitor Rate Limits
- Review `COPILOT_LIMITER.stats` periodically
- Set up alerts for high block rates
- Adjust limits based on your API quotas

### 4. Enable JSON Logging in CI/CD
- Set `LOG_FORMAT=json` in CI environments
- Forward logs to your SIEM
- Use correlation IDs for debugging

---

## CLI Tools

### Test Input Validator
```bash
python -m testinglib.input_validator
```

### Test Rate Limiter
```bash
python -m testinglib.rate_limiter
```

### Test Structured Logging
```bash
# Pretty format
python -m testinglib.structured_logging

# JSON format
LOG_FORMAT=json python -m testinglib.structured_logging
```

### Run Security Audit
```bash
python -m testinglib.security
```

---

## Troubleshooting

### "Input validation failed"
- Check the `error_message` for details
- Review blocked patterns in `input_validator.py`
- Add to `custom_allowed_patterns` if false positive

### "Rate limit exceeded"
- Check current rate with `limiter.stats`
- Increase limits via environment variables
- Consider using non-blocking mode

### "Logs not appearing"
- Verify `setup_logging()` is called once at startup
- Check `LOG_LEVEL` setting
- Ensure handlers aren't cleared elsewhere
