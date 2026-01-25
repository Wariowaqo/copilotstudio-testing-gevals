"""
Multi-Agent Registry and Orchestration

Provides enterprise-grade management for testing multiple Copilot Studio agents:
- Agent registry with metadata
- Parallel test execution
- Environment-specific agent configurations
- Centralized test case management per agent
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import json
import csv

logger = logging.getLogger(__name__)


@dataclass
class AgentDefinition:
    """Definition of a Copilot Studio agent to test."""
    
    # Required fields
    id: str
    name: str
    environment_id: str
    agent_identifier: str
    
    # Optional metadata
    description: str = ""
    owner: str = ""
    team: str = ""
    criticality: str = "medium"  # low, medium, high, critical
    tags: List[str] = field(default_factory=list)
    
    # Test configuration
    test_cases_path: Optional[str] = None
    threshold: float = 0.50
    
    # Environment overrides (if different from global)
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    
    # Scheduling
    test_schedule: str = "daily"  # manual, hourly, daily, weekly
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentDefinition":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class AgentRegistry:
    """
    Registry for managing multiple Copilot Studio agents.
    
    Supports loading agents from:
    - JSON configuration file
    - YAML configuration file
    - Environment variables
    - Programmatic registration
    
    Usage:
        registry = AgentRegistry("agents.json")
        
        # Get all agents
        agents = registry.get_all()
        
        # Get agents by environment
        prod_agents = registry.get_by_environment("prod")
        
        # Get agents by tag
        customer_support_agents = registry.get_by_tag("customer-support")
        
        # Get specific agent
        agent = registry.get("my-agent-id")
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize agent registry.
        
        Args:
            config_path: Path to agents configuration file (JSON or YAML)
        """
        self._agents: Dict[str, AgentDefinition] = {}
        self._config_path = config_path
        
        if config_path:
            self.load_from_file(config_path)
        else:
            # Try default paths
            for default_path in ["agents.json", "agents.yaml", "config/agents.json"]:
                if os.path.exists(default_path):
                    self.load_from_file(default_path)
                    break
    
    def load_from_file(self, path: str):
        """Load agents from configuration file."""
        path = Path(path)
        
        if not path.exists():
            logger.warning(f"Agent configuration file not found: {path}")
            return
        
        with open(path, "r") as f:
            if path.suffix in [".yaml", ".yml"]:
                try:
                    import yaml
                    data = yaml.safe_load(f)
                except ImportError:
                    logger.error("PyYAML not installed. Install with: pip install pyyaml")
                    return
            else:
                data = json.load(f)
        
        agents_data = data.get("agents", [])
        for agent_data in agents_data:
            agent = AgentDefinition.from_dict(agent_data)
            self.register(agent)
        
        logger.info(f"Loaded {len(agents_data)} agents from {path}")
    
    def register(self, agent: AgentDefinition):
        """Register an agent in the registry."""
        self._agents[agent.id] = agent
        logger.debug(f"Registered agent: {agent.id} ({agent.name})")
    
    def unregister(self, agent_id: str):
        """Remove an agent from the registry."""
        if agent_id in self._agents:
            del self._agents[agent_id]
    
    def get(self, agent_id: str) -> Optional[AgentDefinition]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def get_all(self, enabled_only: bool = True) -> List[AgentDefinition]:
        """Get all registered agents."""
        agents = list(self._agents.values())
        if enabled_only:
            agents = [a for a in agents if a.enabled]
        return agents
    
    def get_by_tag(self, tag: str) -> List[AgentDefinition]:
        """Get agents by tag."""
        return [a for a in self._agents.values() if tag in a.tags and a.enabled]
    
    def get_by_criticality(self, criticality: str) -> List[AgentDefinition]:
        """Get agents by criticality level."""
        return [a for a in self._agents.values() if a.criticality == criticality and a.enabled]
    
    def get_by_team(self, team: str) -> List[AgentDefinition]:
        """Get agents by team."""
        return [a for a in self._agents.values() if a.team == team and a.enabled]
    
    def get_by_schedule(self, schedule: str) -> List[AgentDefinition]:
        """Get agents by test schedule."""
        return [a for a in self._agents.values() if a.test_schedule == schedule and a.enabled]
    
    def save_to_file(self, path: Optional[str] = None):
        """Save registry to configuration file."""
        path = path or self._config_path
        if not path:
            raise ValueError("No configuration path specified")
        
        data = {
            "agents": [a.to_dict() for a in self._agents.values()]
        }
        
        path = Path(path)
        with open(path, "w") as f:
            if path.suffix in [".yaml", ".yml"]:
                import yaml
                yaml.dump(data, f, default_flow_style=False)
            else:
                json.dump(data, f, indent=2)
        
        logger.info(f"Saved {len(self._agents)} agents to {path}")


@dataclass
class AgentTestResult:
    """Result of testing a single agent."""
    agent_id: str
    agent_name: str
    success: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    pass_rate: float
    avg_score: float
    duration_seconds: float
    error_message: Optional[str] = None
    report_path: Optional[str] = None


class MultiAgentTestOrchestrator:
    """
    Orchestrates testing of multiple Copilot Studio agents.
    
    Supports:
    - Sequential execution (default)
    - Parallel execution
    - Selective execution (by tag, criticality, etc.)
    - Result aggregation
    
    Usage:
        registry = AgentRegistry("agents.json")
        orchestrator = MultiAgentTestOrchestrator(registry)
        
        # Test all agents
        results = await orchestrator.test_all()
        
        # Test specific agents
        results = await orchestrator.test_by_tag("customer-support")
        
        # Test critical agents only
        results = await orchestrator.test_by_criticality("critical")
    """
    
    def __init__(
        self,
        registry: AgentRegistry,
        parallel: bool = False,
        max_workers: int = 3
    ):
        """
        Initialize orchestrator.
        
        Args:
            registry: Agent registry
            parallel: Whether to run tests in parallel
            max_workers: Maximum parallel workers (if parallel=True)
        """
        self.registry = registry
        self.parallel = parallel
        self.max_workers = max_workers
        self._test_function: Optional[Callable] = None
    
    def set_test_function(self, func: Callable):
        """
        Set the test function to run for each agent.
        
        The function should accept an AgentDefinition and return AgentTestResult.
        """
        self._test_function = func
    
    async def test_agent(self, agent: AgentDefinition) -> AgentTestResult:
        """
        Test a single agent.
        
        Override this method or use set_test_function() to customize.
        """
        if self._test_function:
            return await self._test_function(agent)
        
        # Default implementation - runs pytest for the agent
        return await self._run_pytest_for_agent(agent)
    
    async def _run_pytest_for_agent(self, agent: AgentDefinition) -> AgentTestResult:
        """Run pytest for a specific agent."""
        import subprocess
        import time
        
        start_time = time.time()
        
        # Set environment variables for this agent
        env = os.environ.copy()
        env["ENVIRONMENT_ID"] = agent.environment_id
        env["AGENT_IDENTIFIER"] = agent.agent_identifier
        env["AGENT_NAME"] = agent.name
        
        if agent.tenant_id:
            env["TENANT_ID"] = agent.tenant_id
        if agent.client_id:
            env["APP_CLIENT_ID"] = agent.client_id
        if agent.test_cases_path:
            env["TEST_CASES_PATH"] = agent.test_cases_path
        
        # Create agent-specific report path
        report_dir = Path("reports") / agent.id
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "evaluation_report.html"
        env["REPORTS_DIR"] = str(report_dir)
        
        try:
            # Run pytest
            result = subprocess.run(
                ["pytest", "tests/", "-v", "--tb=short", "-q"],
                env=env,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            duration = time.time() - start_time
            
            # Parse pytest output to get pass/fail counts
            output = result.stdout + result.stderr
            passed, failed = self._parse_pytest_output(output)
            total = passed + failed
            
            return AgentTestResult(
                agent_id=agent.id,
                agent_name=agent.name,
                success=result.returncode == 0,
                total_tests=total,
                passed_tests=passed,
                failed_tests=failed,
                pass_rate=passed / total if total > 0 else 0,
                avg_score=0,  # Would need to parse from report
                duration_seconds=duration,
                report_path=str(report_path) if report_path.exists() else None
            )
            
        except subprocess.TimeoutExpired:
            return AgentTestResult(
                agent_id=agent.id,
                agent_name=agent.name,
                success=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                pass_rate=0,
                avg_score=0,
                duration_seconds=600,
                error_message="Test execution timed out"
            )
        except Exception as e:
            return AgentTestResult(
                agent_id=agent.id,
                agent_name=agent.name,
                success=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                pass_rate=0,
                avg_score=0,
                duration_seconds=time.time() - start_time,
                error_message=str(e)
            )
    
    def _parse_pytest_output(self, output: str) -> tuple:
        """Parse pytest output to extract pass/fail counts."""
        import re
        
        # Look for pattern like "10 passed, 2 failed"
        match = re.search(r"(\d+) passed", output)
        passed = int(match.group(1)) if match else 0
        
        match = re.search(r"(\d+) failed", output)
        failed = int(match.group(1)) if match else 0
        
        return passed, failed
    
    async def test_all(self) -> List[AgentTestResult]:
        """Test all registered agents."""
        agents = self.registry.get_all()
        return await self._run_tests(agents)
    
    async def test_by_tag(self, tag: str) -> List[AgentTestResult]:
        """Test agents with specific tag."""
        agents = self.registry.get_by_tag(tag)
        return await self._run_tests(agents)
    
    async def test_by_criticality(self, criticality: str) -> List[AgentTestResult]:
        """Test agents with specific criticality."""
        agents = self.registry.get_by_criticality(criticality)
        return await self._run_tests(agents)
    
    async def test_by_schedule(self, schedule: str) -> List[AgentTestResult]:
        """Test agents with specific schedule."""
        agents = self.registry.get_by_schedule(schedule)
        return await self._run_tests(agents)
    
    async def test_agents(self, agent_ids: List[str]) -> List[AgentTestResult]:
        """Test specific agents by ID."""
        agents = [self.registry.get(id) for id in agent_ids]
        agents = [a for a in agents if a is not None]
        return await self._run_tests(agents)
    
    async def _run_tests(self, agents: List[AgentDefinition]) -> List[AgentTestResult]:
        """Run tests for a list of agents."""
        if not agents:
            logger.warning("No agents to test")
            return []
        
        logger.info(f"Testing {len(agents)} agents (parallel={self.parallel})")
        
        if self.parallel:
            return await self._run_parallel(agents)
        else:
            return await self._run_sequential(agents)
    
    async def _run_sequential(self, agents: List[AgentDefinition]) -> List[AgentTestResult]:
        """Run tests sequentially."""
        results = []
        for agent in agents:
            logger.info(f"Testing agent: {agent.name} ({agent.id})")
            result = await self.test_agent(agent)
            results.append(result)
            logger.info(
                f"Agent {agent.name}: {'✅ PASSED' if result.success else '❌ FAILED'} "
                f"({result.passed_tests}/{result.total_tests} tests)"
            )
        return results
    
    async def _run_parallel(self, agents: List[AgentDefinition]) -> List[AgentTestResult]:
        """Run tests in parallel with limited concurrency."""
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def test_with_semaphore(agent: AgentDefinition) -> AgentTestResult:
            async with semaphore:
                logger.info(f"Testing agent: {agent.name} ({agent.id})")
                return await self.test_agent(agent)
        
        tasks = [test_with_semaphore(agent) for agent in agents]
        results = await asyncio.gather(*tasks)
        
        for result in results:
            logger.info(
                f"Agent {result.agent_name}: {'✅ PASSED' if result.success else '❌ FAILED'} "
                f"({result.passed_tests}/{result.total_tests} tests)"
            )
        
        return list(results)
    
    def generate_summary_report(
        self,
        results: List[AgentTestResult],
        output_path: str = "reports/multi_agent_summary.html"
    ) -> str:
        """Generate summary report for all tested agents."""
        total_agents = len(results)
        passed_agents = sum(1 for r in results if r.success)
        total_tests = sum(r.total_tests for r in results)
        passed_tests = sum(r.passed_tests for r in results)
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Multi-Agent Test Summary</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 40px; background: #0d1117; color: #e6edf3; }}
        h1 {{ color: #c9a227; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .metric {{ background: #161b22; padding: 20px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 36px; font-weight: bold; }}
        .metric-label {{ color: #8b949e; margin-top: 8px; }}
        .success {{ color: #3fb950; }}
        .failure {{ color: #f85149; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ background: #161b22; color: #c9a227; }}
        tr:hover {{ background: #1c2128; }}
        .status-pass {{ color: #3fb950; }}
        .status-fail {{ color: #f85149; }}
    </style>
</head>
<body>
    <h1>🤖 Multi-Agent Test Summary</h1>
    <p>Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
    
    <div class="summary">
        <div class="metric">
            <div class="metric-value">{total_agents}</div>
            <div class="metric-label">Total Agents</div>
        </div>
        <div class="metric">
            <div class="metric-value success">{passed_agents}</div>
            <div class="metric-label">Passed</div>
        </div>
        <div class="metric">
            <div class="metric-value failure">{total_agents - passed_agents}</div>
            <div class="metric-label">Failed</div>
        </div>
        <div class="metric">
            <div class="metric-value">{passed_tests}/{total_tests}</div>
            <div class="metric-label">Tests Passed</div>
        </div>
    </div>
    
    <table>
        <tr>
            <th>Status</th>
            <th>Agent</th>
            <th>Tests</th>
            <th>Pass Rate</th>
            <th>Duration</th>
            <th>Report</th>
        </tr>
"""
        
        for r in results:
            status_class = "status-pass" if r.success else "status-fail"
            status_icon = "✅" if r.success else "❌"
            report_link = f'<a href="{r.report_path}">View</a>' if r.report_path else "-"
            
            html += f"""
        <tr>
            <td class="{status_class}">{status_icon}</td>
            <td>{r.agent_name}</td>
            <td>{r.passed_tests}/{r.total_tests}</td>
            <td>{r.pass_rate*100:.1f}%</td>
            <td>{r.duration_seconds:.1f}s</td>
            <td>{report_link}</td>
        </tr>
"""
        
        html += """
    </table>
</body>
</html>
"""
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(html)
        
        logger.info(f"Generated summary report: {output_path}")
        return output_path
