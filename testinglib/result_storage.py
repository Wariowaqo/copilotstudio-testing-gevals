"""
Result Storage Service for Copilot Studio Testing

Provides persistent storage of test results for historical tracking and analytics.
Supports multiple storage backends:
- Azure Blob Storage (recommended for cloud deployments)
- Local JSON files (for development)
- Azure SQL Database (optional, for structured queries)
"""

import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class TestRunResult:
    """Complete record of a test run."""
    run_id: str
    timestamp: str
    environment: str
    agent_name: str
    agent_identifier: str
    
    # Summary metrics
    total_tests: int
    passed_tests: int
    failed_tests: int
    pass_rate: float
    avg_overall_score: float
    avg_correctness_score: float
    avg_relevancy_score: float
    avg_coherence_score: float
    avg_completeness_score: float
    
    # Execution details
    duration_seconds: float
    pipeline_url: Optional[str] = None
    report_url: Optional[str] = None
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    triggered_by: Optional[str] = None
    
    # Individual test results
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_test_results(
        cls,
        results: List[Dict[str, Any]],
        duration: float,
        environment: str,
        agent_name: str,
        agent_identifier: str,
        **kwargs
    ) -> "TestRunResult":
        """Create TestRunResult from raw test results."""
        total = len(results)
        passed = sum(1 for r in results if r.get("passed", False))
        
        def avg_score(key: str) -> float:
            scores = [float(r.get(key, 0)) for r in results]
            return sum(scores) / len(scores) if scores else 0
        
        return cls(
            run_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat(),
            environment=environment,
            agent_name=agent_name,
            agent_identifier=agent_identifier,
            total_tests=total,
            passed_tests=passed,
            failed_tests=total - passed,
            pass_rate=passed / total if total > 0 else 0,
            avg_overall_score=avg_score("overall_score"),
            avg_correctness_score=avg_score("correctness_score"),
            avg_relevancy_score=avg_score("relevancy_score"),
            avg_coherence_score=avg_score("coherence_score"),
            avg_completeness_score=avg_score("completeness_score"),
            duration_seconds=duration,
            test_results=results,
            **kwargs
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


class ResultStorageBackend(ABC):
    """Abstract base class for result storage backends."""
    
    @abstractmethod
    def save(self, result: TestRunResult) -> str:
        """Save a test run result. Returns the storage path/identifier."""
        pass
    
    @abstractmethod
    def load(self, run_id: str) -> Optional[TestRunResult]:
        """Load a test run result by ID."""
        pass
    
    @abstractmethod
    def list_runs(
        self,
        environment: Optional[str] = None,
        agent_identifier: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List recent test runs with basic info."""
        pass


class LocalFileStorage(ResultStorageBackend):
    """
    Local file storage for development and simple deployments.
    
    Stores results as JSON files organized by date.
    """
    
    def __init__(self, base_path: str = "results"):
        """Initialize local file storage."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_path / "index.json"
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure index file exists."""
        if not self.index_file.exists():
            self._save_index([])
    
    def _load_index(self) -> List[Dict[str, Any]]:
        """Load the runs index."""
        try:
            with open(self.index_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_index(self, index: List[Dict[str, Any]]):
        """Save the runs index."""
        with open(self.index_file, "w") as f:
            json.dump(index, f, indent=2)
    
    def _get_file_path(self, result: TestRunResult) -> Path:
        """Get file path for a result."""
        date = datetime.fromisoformat(result.timestamp).strftime("%Y/%m/%d")
        directory = self.base_path / date
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{result.run_id}.json"
    
    def save(self, result: TestRunResult) -> str:
        """Save result to local file."""
        file_path = self._get_file_path(result)
        
        with open(file_path, "w") as f:
            f.write(result.to_json())
        
        # Update index
        index = self._load_index()
        index.insert(0, {
            "run_id": result.run_id,
            "timestamp": result.timestamp,
            "environment": result.environment,
            "agent_name": result.agent_name,
            "agent_identifier": result.agent_identifier,
            "total_tests": result.total_tests,
            "passed_tests": result.passed_tests,
            "pass_rate": result.pass_rate,
            "file_path": str(file_path.relative_to(self.base_path))
        })
        
        # Keep only last 1000 entries in index
        index = index[:1000]
        self._save_index(index)
        
        logger.info(f"Saved test run to {file_path}")
        return str(file_path)
    
    def load(self, run_id: str) -> Optional[TestRunResult]:
        """Load result from local file."""
        index = self._load_index()
        entry = next((e for e in index if e["run_id"] == run_id), None)
        
        if not entry:
            return None
        
        file_path = self.base_path / entry["file_path"]
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return TestRunResult(**data)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load run {run_id}: {e}")
            return None
    
    def list_runs(
        self,
        environment: Optional[str] = None,
        agent_identifier: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List recent runs from index."""
        index = self._load_index()
        
        # Filter
        if environment:
            index = [e for e in index if e.get("environment") == environment]
        if agent_identifier:
            index = [e for e in index if e.get("agent_identifier") == agent_identifier]
        
        return index[:limit]


class AzureBlobStorage(ResultStorageBackend):
    """
    Azure Blob Storage backend for cloud deployments.
    
    Stores results as JSON blobs with date-based hierarchy.
    """
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        container_name: str = "test-results"
    ):
        """Initialize Azure Blob Storage backend."""
        self.connection_string = connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = container_name
        self._client = None
        self._container = None
        
        if not self.connection_string:
            logger.warning("Azure Storage connection string not configured")
    
    @property
    def is_available(self) -> bool:
        """Check if Azure Blob Storage is available."""
        return bool(self.connection_string)
    
    def _get_client(self):
        """Get or create blob container client."""
        if self._container is None:
            try:
                from azure.storage.blob import BlobServiceClient
                
                self._client = BlobServiceClient.from_connection_string(self.connection_string)
                self._container = self._client.get_container_client(self.container_name)
                
                # Create container if it doesn't exist
                try:
                    self._container.create_container()
                except Exception:
                    pass  # Container already exists
                    
            except ImportError:
                logger.error("Azure Storage SDK not installed. Install with: pip install azure-storage-blob")
                raise
        
        return self._container
    
    def _get_blob_name(self, result: TestRunResult) -> str:
        """Get blob name for a result."""
        date = datetime.fromisoformat(result.timestamp).strftime("%Y/%m/%d")
        return f"{result.environment}/{date}/{result.run_id}.json"
    
    def save(self, result: TestRunResult) -> str:
        """Save result to Azure Blob Storage."""
        if not self.is_available:
            raise ValueError("Azure Storage not configured")
        
        container = self._get_client()
        blob_name = self._get_blob_name(result)
        
        container.upload_blob(
            name=blob_name,
            data=result.to_json(),
            overwrite=True
        )
        
        logger.info(f"Saved test run to Azure Blob: {blob_name}")
        return blob_name
    
    def load(self, run_id: str) -> Optional[TestRunResult]:
        """Load result from Azure Blob Storage."""
        if not self.is_available:
            return None
        
        container = self._get_client()
        
        # Search for blob with matching run_id
        for blob in container.list_blobs():
            if run_id in blob.name:
                data = container.download_blob(blob.name).readall()
                result_dict = json.loads(data)
                return TestRunResult(**result_dict)
        
        return None
    
    def list_runs(
        self,
        environment: Optional[str] = None,
        agent_identifier: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List recent runs from Azure Blob Storage."""
        if not self.is_available:
            return []
        
        container = self._get_client()
        runs = []
        
        prefix = f"{environment}/" if environment else None
        
        for blob in container.list_blobs(name_starts_with=prefix):
            if len(runs) >= limit:
                break
            
            # Load blob to get details
            try:
                data = container.download_blob(blob.name).readall()
                result = json.loads(data)
                
                if agent_identifier and result.get("agent_identifier") != agent_identifier:
                    continue
                
                runs.append({
                    "run_id": result.get("run_id"),
                    "timestamp": result.get("timestamp"),
                    "environment": result.get("environment"),
                    "agent_name": result.get("agent_name"),
                    "agent_identifier": result.get("agent_identifier"),
                    "total_tests": result.get("total_tests"),
                    "passed_tests": result.get("passed_tests"),
                    "pass_rate": result.get("pass_rate"),
                    "blob_name": blob.name
                })
            except Exception as e:
                logger.warning(f"Failed to parse blob {blob.name}: {e}")
        
        # Sort by timestamp descending
        runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return runs


class ResultStorage:
    """
    Unified result storage interface.
    
    Automatically selects the appropriate backend based on configuration:
    - Azure Blob Storage (if AZURE_STORAGE_CONNECTION_STRING is set)
    - Local file storage (fallback)
    
    Usage:
        storage = ResultStorage()
        
        # Save results
        result = TestRunResult.from_test_results(...)
        storage.save(result)
        
        # List recent runs
        runs = storage.list_runs(environment="prod", limit=10)
        
        # Load specific run
        result = storage.load("run-id-here")
    """
    
    def __init__(
        self,
        backend: Optional[ResultStorageBackend] = None,
        local_path: str = "results",
        azure_container: str = "test-results"
    ):
        """Initialize result storage with appropriate backend."""
        if backend:
            self._backend = backend
        elif os.environ.get("AZURE_STORAGE_CONNECTION_STRING"):
            self._backend = AzureBlobStorage(container_name=azure_container)
            logger.info("Using Azure Blob Storage for results")
        else:
            self._backend = LocalFileStorage(base_path=local_path)
            logger.info("Using local file storage for results")
    
    def save(self, result: TestRunResult) -> str:
        """Save a test run result."""
        return self._backend.save(result)
    
    def load(self, run_id: str) -> Optional[TestRunResult]:
        """Load a test run result."""
        return self._backend.load(run_id)
    
    def list_runs(
        self,
        environment: Optional[str] = None,
        agent_identifier: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List recent test runs."""
        return self._backend.list_runs(
            environment=environment,
            agent_identifier=agent_identifier,
            limit=limit
        )
    
    def get_trend_data(
        self,
        environment: str,
        agent_identifier: str,
        limit: int = 30
    ) -> Dict[str, List[Any]]:
        """
        Get trend data for charts/analytics.
        
        Returns:
            Dictionary with arrays for timestamps, pass rates, scores, etc.
        """
        runs = self.list_runs(
            environment=environment,
            agent_identifier=agent_identifier,
            limit=limit
        )
        
        return {
            "timestamps": [r.get("timestamp") for r in runs],
            "pass_rates": [r.get("pass_rate", 0) for r in runs],
            "total_tests": [r.get("total_tests", 0) for r in runs],
            "passed_tests": [r.get("passed_tests", 0) for r in runs],
        }


def save_test_results(
    results: List[Dict[str, Any]],
    duration: float,
    environment: str,
    agent_name: str,
    agent_identifier: str,
    **kwargs
) -> str:
    """
    Convenience function to save test results.
    
    Returns:
        Storage path/identifier for the saved results
    """
    storage = ResultStorage()
    result = TestRunResult.from_test_results(
        results=results,
        duration=duration,
        environment=environment,
        agent_name=agent_name,
        agent_identifier=agent_identifier,
        **kwargs
    )
    return storage.save(result)
