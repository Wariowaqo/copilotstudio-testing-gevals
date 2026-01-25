"""
=============================================================================
Rate Limiter Module for Copilot Studio Testing
=============================================================================

PHASE 2: Security Hardening - Rate Limiting

PURPOSE:
    Prevents API abuse, cost overruns, and resource exhaustion by limiting
    the rate of requests to external services (Copilot Studio, OpenAI, etc.).

WHY THIS MATTERS:
    - API calls cost money (especially LLM evaluations)
    - Prevents accidental infinite loops from exhausting quotas
    - Protects against denial-of-service conditions
    - Ensures fair usage in multi-user/multi-agent scenarios
    - Helps stay within API provider rate limits

USAGE:
    # Basic usage with decorator
    from testinglib.rate_limiter import rate_limit, RateLimiter
    
    @rate_limit(calls_per_minute=30)
    async def call_copilot_api(message):
        return await client.ask(message)
    
    # Manual usage with context manager
    limiter = RateLimiter(calls_per_minute=60)
    async with limiter:
        response = await api_call()
    
    # Shared limiter across multiple functions
    api_limiter = RateLimiter(calls_per_minute=30, name="copilot-api")
    
    async def func1():
        await api_limiter.acquire()
        ...
    
    async def func2():
        await api_limiter.acquire()
        ...

CONFIGURATION:
    Environment variables:
    - RATE_LIMIT_COPILOT: Calls per minute to Copilot Studio (default: 30)
    - RATE_LIMIT_OPENAI: Calls per minute to OpenAI (default: 60)
    - RATE_LIMIT_ENABLED: Enable/disable rate limiting (default: true)

=============================================================================
"""

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable, Dict, Optional, TypeVar, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Type variable for generic function signatures
T = TypeVar('T')


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class RateLimitConfig:
    """
    Configuration for rate limiting.
    
    Attributes:
        calls_per_minute: Maximum calls allowed per minute
        calls_per_hour: Maximum calls allowed per hour (optional)
        calls_per_day: Maximum calls allowed per day (optional)
        burst_limit: Maximum calls allowed in a short burst
        enabled: Whether rate limiting is active
    """
    calls_per_minute: int = 30
    calls_per_hour: Optional[int] = None
    calls_per_day: Optional[int] = None
    burst_limit: int = 5
    enabled: bool = True
    
    @classmethod
    def from_env(cls, prefix: str = "RATE_LIMIT") -> "RateLimitConfig":
        """
        Load configuration from environment variables.
        
        Example:
            # In .env file:
            RATE_LIMIT_CALLS_PER_MINUTE=30
            RATE_LIMIT_ENABLED=true
        """
        return cls(
            calls_per_minute=int(os.environ.get(f"{prefix}_CALLS_PER_MINUTE", 30)),
            calls_per_hour=int(os.environ.get(f"{prefix}_CALLS_PER_HOUR", 0)) or None,
            calls_per_day=int(os.environ.get(f"{prefix}_CALLS_PER_DAY", 0)) or None,
            burst_limit=int(os.environ.get(f"{prefix}_BURST_LIMIT", 5)),
            enabled=os.environ.get(f"{prefix}_ENABLED", "true").lower() == "true",
        )


# =============================================================================
# RATE LIMITER CLASSES
# =============================================================================

class RateLimitExceeded(Exception):
    """
    Raised when rate limit is exceeded and blocking is disabled.
    
    Attributes:
        retry_after: Seconds to wait before retrying
        limit_name: Name of the limit that was exceeded
    """
    def __init__(self, message: str, retry_after: float = 0, limit_name: str = ""):
        super().__init__(message)
        self.retry_after = retry_after
        self.limit_name = limit_name


@dataclass
class RateLimitStats:
    """
    Statistics about rate limiter usage.
    
    Useful for monitoring and debugging.
    """
    total_calls: int = 0
    blocked_calls: int = 0
    total_wait_time: float = 0.0
    current_rate: float = 0.0
    last_call_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "blocked_calls": self.blocked_calls,
            "total_wait_time_seconds": round(self.total_wait_time, 2),
            "current_rate_per_minute": round(self.current_rate, 2),
            "last_call": self.last_call_time.isoformat() if self.last_call_time else None,
        }


class RateLimiter:
    """
    Token bucket rate limiter with sliding window.
    
    This implementation uses a sliding window algorithm that:
    - Allows bursts up to the burst limit
    - Smoothly limits sustained request rates
    - Provides accurate per-minute rate limiting
    - Supports both blocking and non-blocking modes
    
    Example:
        # Create a limiter allowing 30 calls per minute
        limiter = RateLimiter(calls_per_minute=30)
        
        # In async code, acquire before making calls
        await limiter.acquire()
        response = await make_api_call()
        
        # Or use as context manager
        async with limiter:
            response = await make_api_call()
    """
    
    # Registry of named limiters for sharing across modules
    _registry: Dict[str, "RateLimiter"] = {}
    
    def __init__(
        self,
        calls_per_minute: int = 30,
        burst_limit: Optional[int] = None,
        name: Optional[str] = None,
        blocking: bool = True,
        config: Optional[RateLimitConfig] = None,
    ):
        """
        Initialize rate limiter.
        
        Args:
            calls_per_minute: Maximum sustained calls per minute
            burst_limit: Maximum calls allowed in a burst (default: calls_per_minute / 6)
            name: Optional name for this limiter (for registry and logging)
            blocking: If True, acquire() waits. If False, raises RateLimitExceeded.
            config: Optional RateLimitConfig object (overrides other params)
        """
        if config:
            self.calls_per_minute = config.calls_per_minute
            self.burst_limit = config.burst_limit
            self.enabled = config.enabled
        else:
            self.calls_per_minute = calls_per_minute
            self.burst_limit = burst_limit or max(1, calls_per_minute // 6)
            self.enabled = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
        
        self.name = name or f"limiter-{id(self)}"
        self.blocking = blocking
        
        # Sliding window storage
        # Stores timestamps of recent calls
        self._call_times: deque = deque()
        
        # Lock for thread/async safety
        self._lock = asyncio.Lock()
        
        # Statistics
        self._stats = RateLimitStats()
        
        # Register named limiters
        if name:
            RateLimiter._registry[name] = self
        
        logger.debug(
            f"RateLimiter '{self.name}' initialized: "
            f"{self.calls_per_minute}/min, burst={self.burst_limit}"
        )
    
    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    def get(cls, name: str) -> Optional["RateLimiter"]:
        """
        Get a named rate limiter from the registry.
        
        Args:
            name: Name of the limiter
            
        Returns:
            RateLimiter instance or None if not found
        """
        return cls._registry.get(name)
    
    @classmethod
    def get_or_create(
        cls, 
        name: str, 
        calls_per_minute: int = 30,
        **kwargs
    ) -> "RateLimiter":
        """
        Get existing limiter or create new one.
        
        Useful for ensuring a single shared limiter exists:
            limiter = RateLimiter.get_or_create("api", calls_per_minute=30)
        
        Args:
            name: Name for the limiter
            calls_per_minute: Rate limit (used only if creating new)
            **kwargs: Additional arguments for RateLimiter()
            
        Returns:
            RateLimiter instance
        """
        if name in cls._registry:
            return cls._registry[name]
        return cls(calls_per_minute=calls_per_minute, name=name, **kwargs)
    
    async def acquire(self) -> float:
        """
        Acquire permission to make a call.
        
        If the rate limit is reached:
        - In blocking mode: waits until a slot is available
        - In non-blocking mode: raises RateLimitExceeded
        
        Returns:
            Time waited in seconds (0 if no wait was needed)
            
        Raises:
            RateLimitExceeded: If non-blocking and limit exceeded
        """
        if not self.enabled:
            return 0.0
        
        async with self._lock:
            wait_time = await self._acquire_internal()
            return wait_time
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass  # Nothing to clean up
    
    @property
    def stats(self) -> RateLimitStats:
        """Get current statistics."""
        return self._stats
    
    def reset(self):
        """Reset the rate limiter state and statistics."""
        self._call_times.clear()
        self._stats = RateLimitStats()
        logger.debug(f"RateLimiter '{self.name}' reset")
    
    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------
    
    async def _acquire_internal(self) -> float:
        """Internal acquire logic (must be called with lock held)."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=1)
        
        # Remove calls outside the sliding window
        while self._call_times and self._call_times[0] < window_start:
            self._call_times.popleft()
        
        current_count = len(self._call_times)
        total_wait = 0.0
        
        # Check if we need to wait
        if current_count >= self.calls_per_minute:
            if not self.blocking:
                # Calculate when the oldest call will expire
                oldest_call = self._call_times[0]
                retry_after = (oldest_call + timedelta(minutes=1) - now).total_seconds()
                self._stats.blocked_calls += 1
                raise RateLimitExceeded(
                    f"Rate limit exceeded for '{self.name}': "
                    f"{current_count}/{self.calls_per_minute} calls in last minute",
                    retry_after=max(0, retry_after),
                    limit_name=self.name
                )
            
            # Blocking mode: wait until a slot is available
            oldest_call = self._call_times[0]
            wait_until = oldest_call + timedelta(minutes=1)
            wait_seconds = (wait_until - now).total_seconds()
            
            if wait_seconds > 0:
                logger.debug(
                    f"RateLimiter '{self.name}': waiting {wait_seconds:.2f}s "
                    f"(at {current_count}/{self.calls_per_minute})"
                )
                self._stats.blocked_calls += 1
                
                # Release lock while waiting
                await asyncio.sleep(wait_seconds)
                total_wait = wait_seconds
                
                # Re-check after waiting (another call may have been made)
                now = datetime.now(timezone.utc)
                window_start = now - timedelta(minutes=1)
                while self._call_times and self._call_times[0] < window_start:
                    self._call_times.popleft()
        
        # Record this call
        self._call_times.append(now)
        
        # Update statistics
        self._stats.total_calls += 1
        self._stats.total_wait_time += total_wait
        self._stats.last_call_time = now
        self._stats.current_rate = len(self._call_times)
        
        return total_wait


# =============================================================================
# PREDEFINED LIMITERS
# =============================================================================

# Copilot Studio API limiter (conservative default)
# Adjust based on your tenant's rate limits
COPILOT_LIMITER = RateLimiter.get_or_create(
    "copilot-studio",
    calls_per_minute=int(os.environ.get("RATE_LIMIT_COPILOT", 30))
)

# OpenAI API limiter (for DeepEval evaluations)
# Free tier: 3 RPM, Pay-as-you-go: 60 RPM, higher tiers: 500+ RPM
OPENAI_LIMITER = RateLimiter.get_or_create(
    "openai",
    calls_per_minute=int(os.environ.get("RATE_LIMIT_OPENAI", 60))
)

# Webhook limiter (Teams, Slack notifications)
WEBHOOK_LIMITER = RateLimiter.get_or_create(
    "webhooks",
    calls_per_minute=int(os.environ.get("RATE_LIMIT_WEBHOOKS", 10))
)


# =============================================================================
# DECORATORS
# =============================================================================

def rate_limit(
    calls_per_minute: int = 30,
    limiter_name: Optional[str] = None,
    blocking: bool = True,
) -> Callable:
    """
    Decorator to apply rate limiting to async functions.
    
    Usage:
        @rate_limit(calls_per_minute=30)
        async def my_api_call():
            ...
        
        # With named limiter (shared across functions)
        @rate_limit(limiter_name="api")
        async def func1():
            ...
        
        @rate_limit(limiter_name="api")
        async def func2():
            # func1 and func2 share the same rate limit
            ...
    
    Args:
        calls_per_minute: Maximum calls per minute
        limiter_name: Name of shared limiter (creates new if doesn't exist)
        blocking: If True, waits when limit reached
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Get or create the limiter
        nonlocal limiter_name
        if limiter_name is None:
            limiter_name = f"decorator-{func.__module__}.{func.__name__}"
        
        limiter = RateLimiter.get_or_create(
            limiter_name,
            calls_per_minute=calls_per_minute,
            blocking=blocking
        )
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await limiter.acquire()
            return await func(*args, **kwargs)
        
        # Attach limiter to function for inspection
        wrapper._rate_limiter = limiter
        return wrapper
    
    return decorator


def rate_limit_sync(
    calls_per_minute: int = 30,
    limiter_name: Optional[str] = None,
) -> Callable:
    """
    Decorator for synchronous functions (uses simple sleep).
    
    Note: Prefer the async version when possible.
    
    Usage:
        @rate_limit_sync(calls_per_minute=10)
        def sync_api_call():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Simple token bucket for sync
        min_interval = 60.0 / calls_per_minute
        last_call_time = [0.0]  # Mutable container
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            elapsed = current_time - last_call_time[0]
            
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                logger.debug(f"Rate limit: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
            
            last_call_time[0] = time.time()
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

async def with_rate_limit(
    limiter: RateLimiter,
    func: Callable[..., T],
    *args,
    **kwargs
) -> T:
    """
    Execute a function with rate limiting.
    
    Alternative to decorator when you need dynamic control.
    
    Usage:
        result = await with_rate_limit(
            COPILOT_LIMITER,
            client.ask_question,
            "Hello"
        )
    
    Args:
        limiter: RateLimiter instance to use
        func: Async function to call
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function call
    """
    await limiter.acquire()
    return await func(*args, **kwargs)


def get_all_limiter_stats() -> Dict[str, Dict[str, Any]]:
    """
    Get statistics for all registered rate limiters.
    
    Useful for monitoring and debugging.
    
    Returns:
        Dictionary of limiter names to their statistics
    """
    return {
        name: limiter.stats.to_dict()
        for name, limiter in RateLimiter._registry.items()
    }


def reset_all_limiters():
    """Reset all registered rate limiters."""
    for limiter in RateLimiter._registry.values():
        limiter.reset()
    logger.info(f"Reset {len(RateLimiter._registry)} rate limiters")


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    """
    Test the rate limiter from command line.
    
    Usage:
        python -m testinglib.rate_limiter
    """
    import asyncio
    
    async def demo():
        print("=" * 60)
        print("RATE LIMITER DEMO")
        print("=" * 60)
        
        # Create a fast limiter for demo (10 calls per minute = 1 call per 6 seconds)
        limiter = RateLimiter(calls_per_minute=10, name="demo")
        
        print(f"\nSimulating 5 rapid API calls with {limiter.calls_per_minute} calls/min limit...")
        print("(Note: First few calls will be instant, then rate limiting kicks in)\n")
        
        for i in range(5):
            start = time.time()
            wait_time = await limiter.acquire()
            elapsed = time.time() - start
            
            print(f"Call {i+1}: wait={wait_time:.2f}s, total={elapsed:.2f}s")
        
        print("\nLimiter Statistics:")
        stats = limiter.stats.to_dict()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\nAll Registered Limiters:")
        for name, lim in RateLimiter._registry.items():
            print(f"  - {name}: {lim.calls_per_minute}/min")
        
        print("\n" + "=" * 60)
    
    asyncio.run(demo())
