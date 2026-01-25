"""
Notification Service for Copilot Studio Test Results

Sends test result notifications to:
- Microsoft Teams (via Incoming Webhook)
- Slack (via Incoming Webhook)
- Email (via SendGrid or SMTP)

Includes rich formatting with test metrics, pass/fail status, and links.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)


@dataclass
class TestSummary:
    """Summary of test execution results."""
    total: int
    passed: int
    failed: int
    pass_rate: float
    avg_score: float
    duration_seconds: float
    environment: str
    agent_name: str
    run_url: Optional[str] = None
    report_url: Optional[str] = None
    
    @property
    def status(self) -> str:
        """Get overall status string."""
        return "passed" if self.failed == 0 else "failed"
    
    @property
    def status_emoji(self) -> str:
        """Get status emoji."""
        if self.failed == 0:
            return "✅"
        elif self.pass_rate >= 0.80:
            return "⚠️"
        else:
            return "❌"
    
    @classmethod
    def from_test_results(
        cls,
        results: List[Dict[str, Any]],
        duration: float,
        environment: str = "unknown",
        agent_name: str = "unknown",
        **kwargs
    ) -> "TestSummary":
        """Create summary from raw test results."""
        total = len(results)
        passed = sum(1 for r in results if r.get("passed", False))
        failed = total - passed
        pass_rate = passed / total if total > 0 else 0
        avg_score = sum(float(r.get("overall_score", 0)) for r in results) / total if total > 0 else 0
        
        return cls(
            total=total,
            passed=passed,
            failed=failed,
            pass_rate=pass_rate,
            avg_score=avg_score,
            duration_seconds=duration,
            environment=environment,
            agent_name=agent_name,
            **kwargs
        )


class NotificationService:
    """
    Service for sending test result notifications.
    
    Usage:
        notifier = NotificationService(
            teams_webhook_url="https://outlook.office.com/webhook/...",
            slack_webhook_url="https://hooks.slack.com/services/..."
        )
        
        summary = TestSummary(...)
        notifier.send_all(summary)
    """
    
    def __init__(
        self,
        teams_webhook_url: Optional[str] = None,
        slack_webhook_url: Optional[str] = None,
        notify_on_success: bool = True,
        notify_on_failure: bool = True,
        failure_threshold: float = 0.80
    ):
        """
        Initialize notification service.
        
        Args:
            teams_webhook_url: Microsoft Teams incoming webhook URL
            slack_webhook_url: Slack incoming webhook URL
            notify_on_success: Whether to notify on successful runs
            notify_on_failure: Whether to notify on failed runs
            failure_threshold: Pass rate threshold below which to always notify
        """
        self.teams_webhook_url = teams_webhook_url or os.environ.get("TEAMS_WEBHOOK_URL")
        self.slack_webhook_url = slack_webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        self.notify_on_success = notify_on_success
        self.notify_on_failure = notify_on_failure
        self.failure_threshold = failure_threshold
    
    def should_notify(self, summary: TestSummary) -> bool:
        """Determine if notification should be sent based on results."""
        if summary.failed > 0:
            return self.notify_on_failure
        elif summary.pass_rate < self.failure_threshold:
            return True  # Always notify if pass rate is below threshold
        else:
            return self.notify_on_success
    
    def send_all(self, summary: TestSummary) -> Dict[str, bool]:
        """
        Send notifications to all configured channels.
        
        Returns:
            Dictionary of channel names and whether notification succeeded
        """
        if not self.should_notify(summary):
            logger.info("Skipping notifications based on configuration")
            return {}
        
        results = {}
        
        if self.teams_webhook_url:
            results["teams"] = self.send_teams(summary)
        
        if self.slack_webhook_url:
            results["slack"] = self.send_slack(summary)
        
        return results
    
    def send_teams(self, summary: TestSummary) -> bool:
        """
        Send notification to Microsoft Teams.
        
        Args:
            summary: Test summary to send
            
        Returns:
            True if notification was sent successfully
        """
        if not self.teams_webhook_url:
            logger.warning("Teams webhook URL not configured")
            return False
        
        # Determine theme color based on status
        if summary.failed == 0:
            theme_color = "00FF00"  # Green
        elif summary.pass_rate >= 0.80:
            theme_color = "FFA500"  # Orange
        else:
            theme_color = "FF0000"  # Red
        
        # Build Teams Adaptive Card message
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": theme_color,
            "summary": f"Copilot Studio Tests: {summary.status_emoji} {summary.status.upper()}",
            "sections": [
                {
                    "activityTitle": f"{summary.status_emoji} Copilot Studio Agent Tests - {summary.status.upper()}",
                    "activitySubtitle": f"Agent: {summary.agent_name} | Environment: {summary.environment}",
                    "activityImage": "https://raw.githubusercontent.com/microsoft/PowerPlatformConnectors/master/custom-connectors/Copilot%20Studio/icon.png",
                    "facts": [
                        {"name": "Total Tests", "value": str(summary.total)},
                        {"name": "Passed", "value": f"✅ {summary.passed}"},
                        {"name": "Failed", "value": f"❌ {summary.failed}"},
                        {"name": "Pass Rate", "value": f"{summary.pass_rate * 100:.1f}%"},
                        {"name": "Avg Score", "value": f"{summary.avg_score:.2f}"},
                        {"name": "Duration", "value": f"{summary.duration_seconds:.1f}s"},
                        {"name": "Timestamp", "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")},
                    ],
                    "markdown": True
                }
            ],
            "potentialAction": []
        }
        
        # Add action buttons if URLs are provided
        if summary.run_url:
            card["potentialAction"].append({
                "@type": "OpenUri",
                "name": "View Run Details",
                "targets": [{"os": "default", "uri": summary.run_url}]
            })
        
        if summary.report_url:
            card["potentialAction"].append({
                "@type": "OpenUri",
                "name": "View Report",
                "targets": [{"os": "default", "uri": summary.report_url}]
            })
        
        return self._send_webhook(self.teams_webhook_url, card)
    
    def send_slack(self, summary: TestSummary) -> bool:
        """
        Send notification to Slack.
        
        Args:
            summary: Test summary to send
            
        Returns:
            True if notification was sent successfully
        """
        if not self.slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False
        
        # Determine color based on status
        if summary.failed == 0:
            color = "good"
        elif summary.pass_rate >= 0.80:
            color = "warning"
        else:
            color = "danger"
        
        # Build Slack message
        message = {
            "attachments": [
                {
                    "color": color,
                    "title": f"{summary.status_emoji} Copilot Studio Agent Tests - {summary.status.upper()}",
                    "title_link": summary.run_url,
                    "text": f"Agent: *{summary.agent_name}* | Environment: *{summary.environment}*",
                    "fields": [
                        {"title": "Total", "value": str(summary.total), "short": True},
                        {"title": "Passed", "value": f"✅ {summary.passed}", "short": True},
                        {"title": "Failed", "value": f"❌ {summary.failed}", "short": True},
                        {"title": "Pass Rate", "value": f"{summary.pass_rate * 100:.1f}%", "short": True},
                        {"title": "Avg Score", "value": f"{summary.avg_score:.2f}", "short": True},
                        {"title": "Duration", "value": f"{summary.duration_seconds:.1f}s", "short": True},
                    ],
                    "footer": "Copilot Studio Testing",
                    "ts": int(datetime.utcnow().timestamp())
                }
            ]
        }
        
        # Add report button if URL provided
        if summary.report_url:
            message["attachments"][0]["actions"] = [
                {
                    "type": "button",
                    "text": "View Report",
                    "url": summary.report_url
                }
            ]
        
        return self._send_webhook(self.slack_webhook_url, message)
    
    def _send_webhook(self, url: str, payload: dict) -> bool:
        """Send payload to webhook URL."""
        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            
            with urlopen(request, timeout=30) as response:
                if response.status == 200:
                    logger.info(f"Notification sent successfully")
                    return True
                else:
                    logger.error(f"Webhook returned status {response.status}")
                    return False
                    
        except URLError as e:
            logger.error(f"Failed to send notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification: {e}")
            return False


def send_test_notification(
    results: List[Dict[str, Any]],
    duration: float,
    environment: str = "unknown",
    agent_name: str = "unknown",
    run_url: Optional[str] = None,
    report_url: Optional[str] = None
) -> Dict[str, bool]:
    """
    Convenience function to send test notifications.
    
    Args:
        results: List of test results
        duration: Test duration in seconds
        environment: Environment name
        agent_name: Agent name
        run_url: URL to the CI/CD run
        report_url: URL to the HTML report
        
    Returns:
        Dictionary of notification results
    """
    summary = TestSummary.from_test_results(
        results=results,
        duration=duration,
        environment=environment,
        agent_name=agent_name,
        run_url=run_url,
        report_url=report_url
    )
    
    notifier = NotificationService()
    return notifier.send_all(summary)
