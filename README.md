# PytestAgentsSDK

This project provides a sample test harness for evaluating Copilot Studio agents using [**Pytest**](https://docs.pytest.org/en/stable/) and [**DeepEval**](https://github.com/confident-ai/deepeval). It uses the [Microsoft 365 Agents SDK](https://github.com/microsoft/agents) to communicate with Copilot Studio and focuses on **semantic evaluation** of agent responses using DeepEval’s `GEval` metric.

## Features

- Multi-turn conversation testing against a Copilot Studio agent
- Semantic response evaluation using DeepEval’s `GEval` metric
- Loads test cases from a CSV file
- Custom HTML reporting with detailed metadata (user input, actual and expected output, score, reason)
- Authentication via MSAL, supporting [“Authenticate with Microsoft”](https://learn.microsoft.com/en-us/microsoft-copilot-studio/configuration-end-user-authentication#authenticate-with-microsoft) in Copilot Studio
- Easily extensible for use with additional metrics and long-term result tracking using DeepEval and Pytest plugins

---

## Setup

### **1. Clone the repository**

```bash
git clone https://github.com/microsoft/CopilotStudioSamples.git
cd CopilotStudioSamples/FunctionalTesting/PytestAgentsSDK
```

### **2. Create and activate a virtual environment**

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
```

### **3. Install required dependencies**

```bash
pip install -r requirements.txt
```

### **4. Create an app registration**

You will need to register an application in Azure for the SDK to authenticate with Copilot Studio:

- Create a **single-tenant** app registration in Azure
- Under **Authentication → Platform configurations**, click **Add a platform**, and select **Mobile and desktop applications**
- Add these redirect URIs:
  - `msal40347a26-35bb-48f3-bdc4-7f4f209aecb1://auth`  (MSAL only)
  - `http://localhost`
- Under **API permissions**, click **Add a permission**
  - Choose **APIs my organization uses**, then search for **Power Platform API**
  - Choose **Delegated permissions**, then add `CopilotStudio.Copilots.Invoke`

> Note: If the Power Platform API doesn't appear, visibility can be stale — run the refresh script in the [Microsoft docs](https://learn.microsoft.com/en-us/power-platform/admin/programmability-authentication-v2?tabs=powershell#step-2-configure-api-permissions).

### **5. Authentication and Agent details**

Create a `.env` file (you can copy from `.env.template`) and populate it with your MSAL and Copilot Studio agent configuration:

```env
APP_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ENVIRONMENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AGENT_IDENTIFIER=cr26e_dMyAgent  # This is the schema name, found under Settings > Advanced > Metadata
```

### **6. Configure Azure OpenAI or OpenAI details**

You can use either OpenAI or Azure OpenAI with DeepEval.

#### To configure Azure OpenAI using the DeepEval CLI:

```bash
deepeval set-azure-openai \
    --openai-endpoint=<endpoint> \                     # e.g. https://example-resource.openai.azure.com/
    --openai-api-key=<api_key> \
    --openai-model-name=<model_name> \                 # e.g. gpt-4o
    --deployment-name=<deployment_name> \              # e.g. Test Deployment
    --openai-api-version=<openai_api_version>          # e.g. 2025-01-01-preview
```

> These values will be stored in a local `.deepeval` configuration file.

Alternatively, if you're using OpenAI (not Azure), set the following environment variable:

```bash
export OPENAI_API_KEY=<your-openai-key>
```

### **7. Publish and set agent authentication**

Before running tests, ensure that your Copilot Studio agent is:

- **Published** in the Copilot Studio portal
- Configured to use **[Authenticate with Microsoft](https://learn.microsoft.com/en-us/microsoft-copilot-studio/configuration-end-user-authentication#authenticate-with-microsoft)** under **Settings > Security > Authentication**

### **8. Prepare Test Cases (CSV Input)**

Before running the tests, populate the CSV file at `input/test_cases.csv` with your test cases.

The CSV file must contain two columns:

- `input_text`: The message sent to the Copilot Studio agent
- `expected_output`: The ideal response you'd expect from the agent

#### Example:

```csv
input_text,expected_output
What is the capital of France?,The capital of France is Paris, which is known for its historical landmarks like the Eiffel Tower and the Louvre Museum.
Who wrote 'Hamlet'?,William Shakespeare wrote the play 'Hamlet', which is considered one of the greatest works of English literature.
What is the chemical symbol for water?,H3O is the correct chemical symbol for water.
```

---

## Running the Tests

From the project directory, run:

```bash
pytest tests/multi_turn_eval_openai.py -v
```

This will:

- Start a conversation with your Copilot Studio agent
- Send test questions and capture responses
- Evaluate responses across **4 metrics**: Correctness, Relevancy, Coherence, and Completeness
- Calculate a weighted overall score
- Automatically generate a custom HTML report at `reports/evaluation_report.html`

---

## Output

The custom HTML report (`reports/evaluation_report.html`) features a modern dark-themed dashboard designed for testing teams:

### Dashboard Features

| Feature | Description |
|---------|-------------|
| **📊 Stats Bar** | Quick overview showing Total Tests, Passed, Failed, and Average Score |
| **🔍 Search** | Filter tests by typing any keyword from questions or content |
| **🏷️ Filter Chips** | One-click filters for All, Passed, Failed, High Score, or Low Score |
| **📋 Compact Table** | Scannable table view with Status, Conversation ID, Question, Score, and Metrics |
| **📐 Mini Metrics** | Color-coded score pills (C/R/Co/Cm) in each row for quick assessment |
| **⏩ Details Modal** | Click "Details →" to open a slide-in panel with full information |
| **⌨️ Keyboard Nav** | Use ← → arrow keys to navigate between tests in the modal |

### Metrics Breakdown

Each test is evaluated across 4 weighted metrics:

| Metric | Weight | Description |
|--------|--------|-------------|
| **Correctness** | 40% | Factual accuracy - penalizes contradictions and errors |
| **Relevancy** | 25% | How directly the response addresses the user's question |
| **Completeness** | 20% | Coverage of key points from the expected answer |
| **Coherence** | 15% | Clarity, logical structure, and professional tone |

The **Overall Score** is a weighted average. Tests pass if the overall score meets the threshold (default: 0.50).

---

## Project Structure

```
├── pytest.ini                 # Pytest configuration
├── requirements.txt           # Python dependencies
├── README.md                  # This documentation
├── .env                       # Environment variables (you create this)
├── .gitignore                 # Git ignore rules
├── input/
│   └── test_cases.csv         # Test input/expected output pairs
├── reports/
│   └── evaluation_report.html # Generated custom HTML dashboard
├── testinglib/
│   ├── config.py              # Copilot Studio connection settings
│   ├── copilot_client.py      # Client wrapper for Copilot Studio API
│   ├── msal_cache_plugin.py   # Token caching for MSAL authentication
│   └── report_generator.py    # Custom HTML report generator
└── tests/
    ├── conftest.py            # Pytest hooks and report generation trigger
    └── multi_turn_eval_openai.py  # Main test file with 4-metric evaluation
```

---

## File Descriptions

### Configuration Files

| File | Description |
|------|-------------|
| **`pytest.ini`** | Pytest configuration file. Sets the Python path, test directory (`tests/`), enables async mode for pytest-asyncio, and configures the event loop scope for async fixtures. |
| **`requirements.txt`** | Lists all Python dependencies including the Microsoft Agents SDK, pytest, DeepEval, MSAL authentication libraries, and pytest-html for report generation. |
| **`.env`** | Environment variables file (you create this from `.env.template`). Contains your Azure app registration credentials and Copilot Studio agent configuration. |

### Input/Output

| File | Description |
|------|-------------|
| **`input/test_cases.csv`** | CSV file containing test cases with two columns: `input_text` (the question to send to the agent) and `expected_output` (the ideal response for semantic comparison). Each row becomes a separate test case. |
| **`reports/evaluation_report.html`** | Custom HTML dashboard report. Open in a browser to view the interactive table with search, filters, and expandable details for each test. |

### Test Library (`testinglib/`)

| File | Description |
|------|-------------|
| **`config.py`** | Defines `McsConnectionSettings`, a class that extends the SDK's `ConnectionSettings`. It reads configuration from environment variables (`APP_CLIENT_ID`, `TENANT_ID`, `ENVIRONMENT_ID`, `AGENT_IDENTIFIER`) and validates required values. |
| **`copilot_client.py`** | Contains `CopilotStudioClient`, the main wrapper class that handles authentication and communication with Copilot Studio. It acquires tokens via MSAL (with caching) and initializes the `CopilotClient` from the Microsoft Agents SDK. |
| **`msal_cache_plugin.py`** | Provides `get_msal_token_cache()`, a helper function that creates a persistent token cache. It attempts encrypted storage first, falling back to plaintext on systems where encryption is unavailable. This avoids repeated interactive logins. |
| **`report_generator.py`** | Custom HTML report generator that creates the interactive dashboard. Generates a standalone HTML file with dark theme, table view, search/filter controls, and modal details panel. Called automatically by `conftest.py` after tests complete. |

### Tests (`tests/`)

| File | Description |
|------|-------------|
| **`conftest.py`** | Pytest configuration and hooks. Collects test results during execution and triggers the custom HTML report generation after all tests complete. Includes compatibility fixes for async event loops. |
| **`multi_turn_eval_openai.py`** | The main test file with 4-metric evaluation. Loads test cases from CSV, communicates with Copilot Studio, and evaluates responses using DeepEval's `GEval` across Correctness (40%), Relevancy (25%), Completeness (20%), and Coherence (15%). Calculates weighted overall score and attaches all data for reporting. |

---

## How It Works

1. **Test cases are loaded** from `input/test_cases.csv`
2. **A conversation is started** with your Copilot Studio agent using the Microsoft Agents SDK
3. **Each test case question** is sent to the agent via `ask_question()`
4. **The agent's response** is captured and evaluated across 4 metrics:
   - **Correctness** (40%): Factual accuracy vs expected output
   - **Relevancy** (25%): How directly it addresses the question
   - **Completeness** (20%): Coverage of key points
   - **Coherence** (15%): Clarity and logical structure
5. **A weighted overall score** is calculated from the 4 metrics
6. **Results are collected** by `conftest.py` during test execution
7. **Custom HTML report** is auto-generated at `reports/evaluation_report.html`

---

## Customization

### Adjusting Metric Weights

In `tests/multi_turn_eval_openai.py`, modify the `METRIC_WEIGHTS` dictionary:

```python
METRIC_WEIGHTS = {
    "correctness": 0.40,  # Factual accuracy (most important)
    "relevancy": 0.25,    # Addresses the question
    "completeness": 0.20, # Covers key points
    "coherence": 0.15,    # Well-structured
}
```

### Adjusting the Pass/Fail Threshold

Modify the `OVERALL_THRESHOLD` to change when tests pass:

```python
OVERALL_THRESHOLD = 0.50  # Adjust this value (0.0 to 1.0)
```

### Modifying Individual Metric Thresholds

Each metric also has its own threshold for detailed analysis:

```python
METRIC_THRESHOLDS = {
    "correctness": 0.50,
    "relevancy": 0.50,
    "completeness": 0.40,
    "coherence": 0.40,
}
```

### Customizing Evaluation Criteria

Each metric has its own `evaluation_steps`. For example, to modify the Correctness evaluation:

```python
def create_correctness_metric():
    return GEval(
        name="Correctness",
        evaluation_steps=[
            "Check whether the facts in 'actual output' contradict any facts in 'expected output'",
            "Heavily penalize factual errors or contradictions",
            "Penalize significant omissions of important details",
            # Add or modify steps here
        ],
        ...
    )
```

### Adding New Test Cases

Simply add new rows to `input/test_cases.csv`:

```csv
input_text,expected_output
Your question here,The expected answer here
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Token acquisition failed** | Delete `bin/token_cache.bin` and run again to re-authenticate interactively |
| **Agent not responding** | Ensure your agent is published in Copilot Studio and authentication is set to "Authenticate with Microsoft" |
| **Tests timing out** | Check your network connection and agent availability; consider increasing timeouts |
| **Python 3.13+ async errors** | Use Python 3.12 for best compatibility with aiohttp and pytest-asyncio |