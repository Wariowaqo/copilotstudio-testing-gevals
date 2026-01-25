"""Copilot Studio Agent Evaluation Tests

This module evaluates Copilot Studio agent responses using multiple quality metrics:
- Correctness: Factual accuracy compared to expected output
- Relevancy: How well the response addresses the user's question  
- Coherence: Logical flow and clarity of the response
- Completeness: Coverage of all key points from expected output

The overall score is a weighted average, with Correctness weighted highest.

SECURITY FEATURES (Phase 1-3):
- Input validation against prompt injection
- Rate limiting for API calls
- Structured logging for observability
"""

from dotenv import load_dotenv
load_dotenv()

import csv
import os
import pytest
import pytest_asyncio
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from testinglib.copilot_client import CopilotStudioClient
from microsoft_agents.activity import ActivityTypes

# =============================================================================
# PHASE 1-3: SECURITY IMPORTS
# =============================================================================
# These modules provide enterprise-grade security features:
# - input_validator: Protects against prompt injection attacks
# - rate_limiter: Prevents API abuse and cost overruns
# - structured_logging: Provides observability and audit trails

from testinglib.input_validator import InputValidator, ValidationResult
from testinglib.rate_limiter import RateLimiter, COPILOT_LIMITER, OPENAI_LIMITER
from testinglib.structured_logging import setup_logging, get_logger, set_correlation_id

# Initialize structured logging (JSON in CI, pretty in local dev)
setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Metric weights for overall score calculation
METRIC_WEIGHTS = {
    "correctness": 0.40,  # Factual accuracy is most important
    "relevancy": 0.25,    # Must answer the question asked
    "completeness": 0.20, # Should cover key points
    "coherence": 0.15,    # Should be well-structured
}

# Pass/fail threshold for overall score
OVERALL_THRESHOLD = 0.50

# Individual metric thresholds
METRIC_THRESHOLDS = {
    "correctness": 0.50,
    "relevancy": 0.50,
    "completeness": 0.40,
    "coherence": 0.40,
}

# =============================================================================
# METRIC DEFINITIONS
# =============================================================================

def create_correctness_metric():
    """Evaluates factual accuracy of the response."""
    return GEval(
        name="Correctness",
        evaluation_steps=[
            "Check whether the facts in 'actual output' contradict any facts in 'expected output'",
            "Heavily penalize factual errors or contradictions",
            "Penalize significant omissions of important details",
            "Vague language or differing opinions are acceptable",
            "Do not penalize AI disclaimers or caveats about accuracy",
        ],
        threshold=METRIC_THRESHOLDS["correctness"],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT]
    )

def create_relevancy_metric():
    """Evaluates how well the response addresses the user's question."""
    return GEval(
        name="Relevancy",
        evaluation_steps=[
            "Determine if the 'actual output' directly addresses the question in 'input'",
            "Penalize responses that go off-topic or provide unrelated information",
            "Penalize responses that only partially answer the question",
            "A good response should stay focused on what was asked",
            "Additional helpful context is acceptable if the core question is answered",
        ],
        threshold=METRIC_THRESHOLDS["relevancy"],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT]
    )

def create_coherence_metric():
    """Evaluates clarity and logical structure of the response."""
    return GEval(
        name="Coherence",
        evaluation_steps=[
            "Evaluate if the 'actual output' is well-organized and easy to understand",
            "Check for logical flow between sentences and ideas",
            "Penalize confusing, contradictory, or poorly structured responses",
            "Penalize grammatical errors that impede understanding",
            "The response should read naturally and professionally",
        ],
        threshold=METRIC_THRESHOLDS["coherence"],
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT]
    )

def create_completeness_metric():
    """Evaluates coverage of key points from the expected output."""
    return GEval(
        name="Completeness",
        evaluation_steps=[
            "Identify the key points in 'expected output'",
            "Check how many of these key points are covered in 'actual output'",
            "Penalize missing important information",
            "Paraphrasing is acceptable if the meaning is preserved",
            "Additional relevant information beyond expected output is acceptable",
        ],
        threshold=METRIC_THRESHOLDS["completeness"],
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT]
    )

# =============================================================================
# TEST DATA LOADING
# =============================================================================

def load_test_cases_from_csv():
    """Load test cases from CSV file."""
    csv_path = os.path.join(os.path.dirname(__file__), "../input/test_cases.csv")
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        return [(row["input_text"], row["expected_output"]) for row in reader]

test_cases = load_test_cases_from_csv()

# =============================================================================
# FIXTURES
# =============================================================================

@pytest_asyncio.fixture(loop_scope="function")
async def started_client():
    """Initialize and start a conversation with the Copilot Studio agent."""
    client = CopilotStudioClient()
    async for activity in client.client.start_conversation():
        if client.client._current_conversation_id:
            break
    client.conversation_id = client.client._current_conversation_id
    print(f"[DEBUG] Started conversation with ID: {client.conversation_id}")
    return client

# =============================================================================
# TEST FUNCTION
# =============================================================================

@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("input_text, expected_output", test_cases)
async def test_agent_response_quality(input_text, expected_output, started_client, request):
    """
    Evaluate agent response quality across multiple metrics.
    
    Metrics evaluated:
    - Correctness (40%): Factual accuracy
    - Relevancy (25%): Addresses the question
    - Completeness (20%): Covers key points
    - Coherence (15%): Clear and well-structured
    
    Security Features:
    - Input validation (prompt injection protection)
    - Rate limiting (API abuse protection)
    - Structured logging (audit trail)
    """
    # -------------------------------------------------------------------------
    # PHASE 1: INPUT VALIDATION
    # -------------------------------------------------------------------------
    # Validate input against prompt injection and other attacks
    # This protects your Copilot Studio agent from malicious inputs
    
    validation_result = InputValidator.validate(input_text)
    if not validation_result.is_valid:
        logger.warning(
            "Input validation failed",
            input_preview=input_text[:50],
            error=validation_result.error_message,
            severity=validation_result.severity.value
        )
        pytest.skip(f"Input validation failed: {validation_result.error_message}")
    
    # Use sanitized input for the test
    sanitized_input = validation_result.sanitized_text
    
    # -------------------------------------------------------------------------
    # PHASE 2: RATE LIMITING
    # -------------------------------------------------------------------------
    # Acquire rate limit before calling the API
    # This prevents cost overruns and API quota exhaustion
    
    await COPILOT_LIMITER.acquire()
    
    # -------------------------------------------------------------------------
    # PHASE 3: STRUCTURED LOGGING
    # -------------------------------------------------------------------------
    # Set correlation ID for this test (enables tracing across logs)
    test_correlation_id = f"test-{request.node.name[:20]}-{os.urandom(4).hex()}"
    set_correlation_id(test_correlation_id)
    
    logger.info(
        "Starting test evaluation",
        test_name=request.node.name,
        input_preview=sanitized_input[:50] + "..." if len(sanitized_input) > 50 else sanitized_input
    )
    
    # Get response from agent
    actual_output = ""
    async for activity in started_client.client.ask_question(sanitized_input):
        if activity and activity.type == ActivityTypes.message:
            actual_output += activity.text or ""
    actual_output = actual_output.strip()
    
    logger.debug(
        "Received agent response",
        response_length=len(actual_output),
        response_preview=actual_output[:100] + "..." if len(actual_output) > 100 else actual_output
    )

    # Create test case (using original input_text for expected_output comparison)
    test_case = LLMTestCase(
        input=sanitized_input,
        actual_output=actual_output,
        expected_output=expected_output
    )

    # -------------------------------------------------------------------------
    # EVALUATION: Rate limit the LLM evaluation calls
    # -------------------------------------------------------------------------
    # DeepEval uses OpenAI for evaluation - apply rate limiting
    
    # Initialize metrics
    correctness = create_correctness_metric()
    relevancy = create_relevancy_metric()
    coherence = create_coherence_metric()
    completeness = create_completeness_metric()

    # Evaluate all metrics (rate-limited)
    # Each metric call uses OpenAI, so we rate limit them
    await OPENAI_LIMITER.acquire()
    correctness.measure(test_case)
    
    await OPENAI_LIMITER.acquire()
    relevancy.measure(test_case)
    
    await OPENAI_LIMITER.acquire()
    coherence.measure(test_case)
    
    await OPENAI_LIMITER.acquire()
    completeness.measure(test_case)

    # Calculate weighted overall score
    overall_score = (
        correctness.score * METRIC_WEIGHTS["correctness"] +
        relevancy.score * METRIC_WEIGHTS["relevancy"] +
        coherence.score * METRIC_WEIGHTS["coherence"] +
        completeness.score * METRIC_WEIGHTS["completeness"]
    )

    # Build detailed results for report
    metrics_breakdown = {
        "correctness": {"score": correctness.score, "reason": correctness.reason, "weight": METRIC_WEIGHTS["correctness"]},
        "relevancy": {"score": relevancy.score, "reason": relevancy.reason, "weight": METRIC_WEIGHTS["relevancy"]},
        "coherence": {"score": coherence.score, "reason": coherence.reason, "weight": METRIC_WEIGHTS["coherence"]},
        "completeness": {"score": completeness.score, "reason": completeness.reason, "weight": METRIC_WEIGHTS["completeness"]},
    }

    # Attach all data to pytest node for HTML report
    request.node.input_text = input_text
    request.node.expected = expected_output
    request.node.actual = actual_output
    request.node.conversation_id = started_client.conversation_id
    
    # Individual metric scores
    request.node.correctness_score = f"{correctness.score:.2f}"
    request.node.relevancy_score = f"{relevancy.score:.2f}"
    request.node.coherence_score = f"{coherence.score:.2f}"
    request.node.completeness_score = f"{completeness.score:.2f}"
    
    # Individual metric reasons
    request.node.correctness_reason = correctness.reason or ""
    request.node.relevancy_reason = relevancy.reason or ""
    request.node.coherence_reason = coherence.reason or ""
    request.node.completeness_reason = completeness.reason or ""
    
    # Overall score
    request.node.overall_score = f"{overall_score:.2f}"
    request.node.threshold = f"{OVERALL_THRESHOLD:.2f}"

    # Determine which metrics failed
    failed_metrics = []
    if correctness.score < METRIC_THRESHOLDS["correctness"]:
        failed_metrics.append(f"Correctness ({correctness.score:.2f} < {METRIC_THRESHOLDS['correctness']})")
    if relevancy.score < METRIC_THRESHOLDS["relevancy"]:
        failed_metrics.append(f"Relevancy ({relevancy.score:.2f} < {METRIC_THRESHOLDS['relevancy']})")
    if coherence.score < METRIC_THRESHOLDS["coherence"]:
        failed_metrics.append(f"Coherence ({coherence.score:.2f} < {METRIC_THRESHOLDS['coherence']})")
    if completeness.score < METRIC_THRESHOLDS["completeness"]:
        failed_metrics.append(f"Completeness ({completeness.score:.2f} < {METRIC_THRESHOLDS['completeness']})")

    # Assertion with detailed failure message
    failure_msg = (
        f"\n{'='*60}\n"
        f"EVALUATION FAILED\n"
        f"{'='*60}\n"
        f"Overall Score: {overall_score:.2f} (threshold: {OVERALL_THRESHOLD})\n"
        f"\nMetric Breakdown:\n"
        f"  • Correctness:  {correctness.score:.2f} (weight: {METRIC_WEIGHTS['correctness']*100:.0f}%)\n"
        f"  • Relevancy:    {relevancy.score:.2f} (weight: {METRIC_WEIGHTS['relevancy']*100:.0f}%)\n"
        f"  • Coherence:    {coherence.score:.2f} (weight: {METRIC_WEIGHTS['coherence']*100:.0f}%)\n"
        f"  • Completeness: {completeness.score:.2f} (weight: {METRIC_WEIGHTS['completeness']*100:.0f}%)\n"
    )
    
    if failed_metrics:
        failure_msg += f"\nFailed Metrics: {', '.join(failed_metrics)}\n"
    
    failure_msg += f"\nCorrectness Reason: {correctness.reason}\n"
    failure_msg += f"{'='*60}"

    # -------------------------------------------------------------------------
    # PHASE 3: LOG TEST COMPLETION
    # -------------------------------------------------------------------------
    passed = overall_score >= OVERALL_THRESHOLD
    logger.info(
        "Test evaluation completed",
        test_name=request.node.name,
        passed=passed,
        overall_score=round(overall_score, 2),
        threshold=OVERALL_THRESHOLD,
        correctness_score=round(correctness.score, 2),
        relevancy_score=round(relevancy.score, 2),
        coherence_score=round(coherence.score, 2),
        completeness_score=round(completeness.score, 2),
        failed_metrics=failed_metrics if failed_metrics else None
    )

    assert overall_score >= OVERALL_THRESHOLD, failure_msg
