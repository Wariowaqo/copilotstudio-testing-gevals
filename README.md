# Copilot Studio Automated Testing with G-Evals

Automated quality evaluation for [Microsoft Copilot Studio](https://www.microsoft.com/en-us/microsoft-copilot/microsoft-copilot-studio) agents using **LLM-as-a-Judge**. This framework sends test questions to your agent, captures real responses, and evaluates them semantically using [DeepEval's G-Eval](https://docs.confident-ai.com/docs/metrics-llm-evals) metrics — powered by OpenAI.

Instead of brittle string matching, G-Eval uses an LLM to judge the quality of each response against your expected output. This means your tests can handle paraphrasing, different wording, and natural language variation — just like a human reviewer would.

## What is G-Eval?

[G-Eval](https://arxiv.org/abs/2303.16634) is an evaluation framework introduced in the paper *"G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment"*. It uses large language models as evaluators by providing them with structured evaluation criteria (called "evaluation steps") and asking them to score responses on a scale of 0 to 1.

**Why G-Eval over traditional metrics?**

| Approach | Limitation |
|----------|------------|
| Exact string match | Fails on paraphrasing or synonyms |
| BLEU / ROUGE | Surface-level n-gram overlap, misses semantic meaning |
| Embedding similarity | Catches meaning but can't evaluate factual accuracy |
| **G-Eval (LLM-as-a-Judge)** | **Understands context, evaluates factual accuracy, and aligns with human judgment** |

DeepEval implements G-Eval as the [`GEval` metric](https://docs.confident-ai.com/docs/metrics-llm-evals), which this project uses to evaluate four dimensions of response quality.

**Further reading:**

- [G-Eval Paper (arXiv)](https://arxiv.org/abs/2303.16634)
- [DeepEval G-Eval Documentation](https://docs.confident-ai.com/docs/metrics-llm-evals)
- [DeepEval GitHub Repository](https://github.com/confident-ai/deepeval)
- [Understanding LLM-as-a-Judge](https://www.confident-ai.com/blog/llm-as-a-judge)

---

## How It Works

```
test_cases.csv ──> Pytest ──> Microsoft Agents SDK ──> Copilot Studio Agent
                                                              |
                                                        Agent Response
                                                              |
                                                              v
                                                    DeepEval G-Eval Metrics
                                                    (powered by OpenAI)
                                                              |
                                          +-------------------+-------------------+
                                          |                   |                   |
                                    Correctness (40%)   Relevancy (25%)   Completeness (20%)
                                                              |
                                                        Coherence (15%)
                                                              |
                                                              v
                                                   Weighted Overall Score
                                                   Pass/Fail (threshold: 0.50)
                                                              |
                                                              v
                                                    HTML Dashboard Report
```

1. Test cases are loaded from `input/test_cases.csv`
2. Each question is sent to your Copilot Studio agent via the [Microsoft Agents SDK](https://github.com/microsoft/Agents-for-python)
3. The agent's actual response is evaluated across 4 G-Eval metrics
4. A weighted overall score determines pass/fail
5. An interactive HTML report is generated at `reports/evaluation_report.html`

---

## Evaluation Metrics

Each response is scored from 0 to 1 across four metrics, using custom evaluation steps that guide the LLM judge:

| Metric | Weight | What it evaluates | Key evaluation criteria |
|--------|--------|-------------------|------------------------|
| **Correctness** | 40% | Factual accuracy against expected output | Penalizes contradictions and factual errors; tolerates AI disclaimers |
| **Relevancy** | 25% | Whether the response addresses the actual question | Penalizes off-topic or partial answers |
| **Completeness** | 20% | Coverage of key points from expected output | Accepts paraphrasing; penalizes missing information |
| **Coherence** | 15% | Clarity, logical flow, and professional tone | Penalizes confusing structure and grammar issues |

The **overall score** is a weighted average. A test passes if the overall score meets the threshold (default: `0.50`).

All weights, thresholds, and evaluation criteria are fully configurable in `tests/multi_turn_eval_openai.py`.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Wariowaqo/cs-testing-gevals.git
cd cs-testing-gevals
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create an Azure App Registration

Register an application in Azure for the SDK to authenticate with Copilot Studio:

- Create a **single-tenant** app registration in [Azure Portal](https://portal.azure.com)
- Under **Authentication > Platform configurations**, click **Add a platform** > **Mobile and desktop applications**
- Add these redirect URIs:
  - `msal40347a26-35bb-48f3-bdc4-7f4f209aecb1://auth`
  - `http://localhost`
- Under **API permissions**, click **Add a permission**:
  - Choose **APIs my organization uses** > search **Power Platform API**
  - Select **Delegated permissions** > add `CopilotStudio.Copilots.Invoke`

> If Power Platform API doesn't appear, see [Microsoft's refresh instructions](https://learn.microsoft.com/en-us/power-platform/admin/programmability-authentication-v2?tabs=powershell#step-2-configure-api-permissions).

### 5. Configure environment variables

Create a `.env` file in the project root:

```env
APP_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ENVIRONMENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AGENT_IDENTIFIER=your_agent_schema_name

# OpenAI API Key (for G-Eval evaluation)
OPENAI_API_KEY=sk-your-key-here
```

**Where to find these values:**

| Variable | Where to find it |
|----------|-----------------|
| `APP_CLIENT_ID` | Azure Portal > App registrations > Your app > Application (client) ID |
| `TENANT_ID` | Azure Portal > Microsoft Entra ID > Overview > Tenant ID |
| `ENVIRONMENT_ID` | Copilot Studio URL or Settings > Session details |
| `AGENT_IDENTIFIER` | Copilot Studio > Your agent > Settings > Advanced > Metadata (schema name) |
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |

**Azure OpenAI alternative:** If you prefer Azure OpenAI instead of OpenAI, configure it via the DeepEval CLI:

```bash
deepeval set-azure-openai \
    --openai-endpoint=https://your-resource.openai.azure.com/ \
    --openai-api-key=your-key \
    --openai-model-name=gpt-4o \
    --deployment-name=your-deployment \
    --openai-api-version=2025-01-01-preview
```

### 6. Publish your agent

Ensure your Copilot Studio agent is:

- **Published** in the Copilot Studio portal
- Using **[Authenticate with Microsoft](https://learn.microsoft.com/en-us/microsoft-copilot-studio/configuration-end-user-authentication#authenticate-with-microsoft)** under Settings > Security > Authentication

### 7. Add test cases

Populate `input/test_cases.csv` with your test scenarios:

```csv
input_text,expected_output
What is Power Platform?,Power Platform is a suite of low-code tools including Power Apps Power Automate Power BI and Copilot Studio.
```

---

## Running Tests

```bash
pytest tests/multi_turn_eval_openai.py -v
```

On first run, a browser window opens for MSAL interactive login. Subsequent runs use the cached token.

**Useful options:**

```bash
pytest tests/multi_turn_eval_openai.py -v --tb=short    # Concise error tracebacks
pytest tests/multi_turn_eval_openai.py -x               # Stop on first failure
pytest tests/multi_turn_eval_openai.py -v -k "capital"   # Run tests matching keyword
```

---

## HTML Report

After tests complete, an interactive HTML dashboard is generated at `reports/evaluation_report.html`. Open it in any browser.

**Dashboard features:**

| Feature | Description |
|---------|-------------|
| Stats bar | Total tests, passed, failed, average score at a glance |
| Search | Filter tests by keyword |
| Filter chips | One-click filters: All, Passed, Failed, High Score, Low Score |
| Compact table | Status, conversation ID, question, overall score, mini metric pills |
| Details panel | Click any row to see full question, expected output, actual output, scores, and LLM reasoning |
| Keyboard nav | Arrow keys to navigate between tests in the detail view |

---

## Project Structure

```
├── .env                       # Your credentials (git-ignored)
├── .gitignore                 # Git ignore rules
├── pytest.ini                 # Pytest configuration
├── requirements.txt           # Python dependencies
├── README.md
├── input/
│   └── test_cases.csv         # Test input / expected output pairs
├── reports/
│   └── evaluation_report.html # Generated HTML dashboard
├── testinglib/
│   ├── config.py              # Copilot Studio connection settings
│   ├── copilot_client.py      # MSAL auth + Copilot Studio client wrapper
│   ├── msal_cache_plugin.py   # Persistent token cache
│   └── report_generator.py    # HTML report generator
└── tests/
    ├── conftest.py            # Pytest hooks for result collection + report trigger
    └── multi_turn_eval_openai.py  # Main test file with 4 G-Eval metrics
```

---

## Customization

### Metric Weights

Adjust how much each metric contributes to the overall score in `tests/multi_turn_eval_openai.py`:

```python
METRIC_WEIGHTS = {
    "correctness": 0.40,
    "relevancy": 0.25,
    "completeness": 0.20,
    "coherence": 0.15,
}
```

### Pass/Fail Threshold

```python
OVERALL_THRESHOLD = 0.50  # 0.0 to 1.0
```

### Evaluation Criteria

Each metric uses custom `evaluation_steps` that guide the LLM judge. Modify them to match your domain:

```python
def create_correctness_metric():
    return GEval(
        name="Correctness",
        evaluation_steps=[
            "Check whether facts in 'actual output' contradict 'expected output'",
            "Heavily penalize factual errors",
            # Add domain-specific criteria here
        ],
        threshold=0.50,
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT
        ]
    )
```

See the [DeepEval G-Eval docs](https://docs.confident-ai.com/docs/metrics-llm-evals) for guidance on writing effective evaluation steps.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Token acquisition failed | Delete `bin/cache.bin` and re-run to trigger interactive login |
| Agent not responding | Verify agent is published and auth is set to "Authenticate with Microsoft" |
| `ModuleNotFoundError` | Ensure virtual environment is activated and `pip install -r requirements.txt` completed |
| Python 3.13+ async errors | Use Python 3.12 for best compatibility with aiohttp |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Test framework | [Pytest](https://docs.pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) |
| Agent communication | [Microsoft Agents SDK](https://github.com/microsoft/Agents-for-python) (DirectLine) |
| Authentication | [MSAL](https://learn.microsoft.com/en-us/entra/msal/python/) with persistent token cache |
| LLM evaluation | [DeepEval](https://docs.confident-ai.com/) G-Eval metrics |
| LLM judge | [OpenAI GPT-4o](https://platform.openai.com/) (configurable to Azure OpenAI) |

---

## Resources

- [DeepEval G-Eval Metric Documentation](https://docs.confident-ai.com/docs/metrics-llm-evals)
- [G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment (Paper)](https://arxiv.org/abs/2303.16634)
- [DeepEval GitHub](https://github.com/confident-ai/deepeval)
- [Microsoft Agents SDK for Python](https://github.com/microsoft/Agents-for-python)
- [Copilot Studio Authentication Setup](https://learn.microsoft.com/en-us/microsoft-copilot-studio/configuration-end-user-authentication)
- [Azure App Registration Guide](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app)
- [MSAL Python Documentation](https://learn.microsoft.com/en-us/entra/msal/python/)
