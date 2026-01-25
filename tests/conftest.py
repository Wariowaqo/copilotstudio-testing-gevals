"""
Pytest Configuration for Copilot Studio Agent Evaluation

This module:
- Collects test results during test execution
- Generates a beautiful custom HTML report after tests complete
"""

import pytest
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from testinglib.report_generator import generate_html_report

# Fix for Python 3.14 compatibility with aiohttp
if sys.version_info >= (3, 14):
    import nest_asyncio
    nest_asyncio.apply()

@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.get_event_loop_policy()


# =============================================================================
# TEST RESULTS COLLECTION
# =============================================================================

# Global list to collect test results
_test_results = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Collect test results after each test completes."""
    outcome = yield
    report = outcome.get_result()
    
    if report.when == "call":
        # Extract test data from the node
        test_data = {
            "input_text": getattr(item, "input_text", ""),
            "expected": getattr(item, "expected", ""),
            "actual": getattr(item, "actual", ""),
            "conversation_id": getattr(item, "conversation_id", ""),
            "correctness_score": getattr(item, "correctness_score", "0.00"),
            "relevancy_score": getattr(item, "relevancy_score", "0.00"),
            "coherence_score": getattr(item, "coherence_score", "0.00"),
            "completeness_score": getattr(item, "completeness_score", "0.00"),
            "correctness_reason": getattr(item, "correctness_reason", ""),
            "relevancy_reason": getattr(item, "relevancy_reason", ""),
            "coherence_reason": getattr(item, "coherence_reason", ""),
            "completeness_reason": getattr(item, "completeness_reason", ""),
            "overall_score": getattr(item, "overall_score", "0.00"),
            "passed": report.passed,
        }
        _test_results.append(test_data)


def pytest_sessionfinish(session, exitstatus):
    """Generate custom HTML report after all tests complete."""
    print(f"\nRunning teardown with pytest sessionfinish...")
    
    if _test_results:
        try:
            # Determine output path - same location as pytest-html report or default
            report_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
            
            # Ensure reports directory exists
            os.makedirs(report_dir, exist_ok=True)
            
            output_path = os.path.join(report_dir, "evaluation_report.html")
            
            print(f"\n📊 Generating report with {len(_test_results)} test results...")
            generate_html_report(_test_results, output_path)
            print(f"✨ Custom report generated: {output_path}")
        except Exception as e:
            print(f"\n⚠️ Error generating report: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\n⚠️ No test results collected for report generation")
