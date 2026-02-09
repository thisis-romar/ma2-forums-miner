"""
Response telemetry and adaptive throttling for the MA2 Forums Miner.

This module implements:
- Response classification (2xx/3xx/4xx/5xx counters)
- Retry exhaustion tracking
- Adaptive throttling with token bucket and jitter
"""

import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ResponseStats:
    """
    Statistics for HTTP response tracking.
    
    Tracks response counts by status code category and specific codes
    for monitoring scraper health and behavior.
    """
    # Response counts by category
    success_2xx: int = 0
    redirect_3xx: int = 0
    client_error_4xx: int = 0
    server_error_5xx: int = 0
    
    # Detailed status code counts
    status_codes: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    
    # Retry tracking
    retry_exhausted: int = 0
    retry_reasons: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Rate limit tracking
    rate_limited_429: int = 0
    service_unavailable_503: int = 0
    
    def record_response(self, status_code: int):
        """Record a successful HTTP response."""
        self.status_codes[status_code] += 1
        
        if 200 <= status_code < 300:
            self.success_2xx += 1
        elif 300 <= status_code < 400:
            self.redirect_3xx += 1
        elif 400 <= status_code < 500:
            self.client_error_4xx += 1
            if status_code == 429:
                self.rate_limited_429 += 1
        elif 500 <= status_code < 600:
            self.server_error_5xx += 1
            if status_code == 503:
                self.service_unavailable_503 += 1
    
    def record_retry_exhausted(self, reason: str):
        """Record a failed request after all retries exhausted."""
        self.retry_exhausted += 1
        self.retry_reasons[reason] += 1
    
    def get_summary(self) -> str:
        """
        Get a human-readable summary of response statistics.
        
        Returns:
            Formatted string with key statistics
        """
        total = self.success_2xx + self.redirect_3xx + self.client_error_4xx + self.server_error_5xx
        
        summary = [
            f"Total Responses: {total}",
            f"  Success (2xx): {self.success_2xx}",
            f"  Redirect (3xx): {self.redirect_3xx}",
            f"  Client Error (4xx): {self.client_error_4xx}",
            f"  Server Error (5xx): {self.server_error_5xx}",
        ]
        
        if self.rate_limited_429 > 0:
            summary.append(f"  Rate Limited (429): {self.rate_limited_429}")
        
        if self.service_unavailable_503 > 0:
            summary.append(f"  Service Unavailable (503): {self.service_unavailable_503}")
        
        if self.retry_exhausted > 0:
            summary.append(f"Retries Exhausted: {self.retry_exhausted}")
            for reason, count in self.retry_reasons.items():
                summary.append(f"  {reason}: {count}")
        
        return "\n".join(summary)


class TokenBucket:
    """
    Token bucket rate limiter for adaptive throttling.
    
    Implements a token bucket algorithm with:
    - Configurable token generation rate
    - Burst capacity
    - Jitter for avoiding thundering herd
    
    The token bucket fills at a steady rate and consumes tokens for each request.
    When the bucket is empty, requests must wait for new tokens.
    """
    
    def __init__(self, tokens_per_second: float = 1.0, capacity: int = 10):
        """
        Initialize token bucket.
        
        Args:
            tokens_per_second: Rate at which tokens are added to bucket
            capacity: Maximum number of tokens bucket can hold
        """
        self.tokens_per_second = tokens_per_second
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.time()
    
    def consume(self, tokens: int = 1) -> float:
        """
        Consume tokens from the bucket.
        
        If insufficient tokens are available, returns the time to wait
        before tokens will be available.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            Seconds to wait before token is available (0 if token consumed immediately)
        """
        # Refill tokens based on time elapsed
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.tokens_per_second)
        self.last_update = now
        
        # Check if we have enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return 0.0
        
        # Calculate wait time for tokens to refill
        tokens_needed = tokens - self.tokens
        wait_time = tokens_needed / self.tokens_per_second
        return wait_time
    
    def add_jitter(self, base_delay: float, jitter_factor: float = 0.1) -> float:
        """
        Add random jitter to a delay value.
        
        Jitter helps avoid synchronized requests from multiple clients
        (thundering herd problem).
        
        Args:
            base_delay: Base delay in seconds
            jitter_factor: Maximum jitter as fraction of base_delay (default: 0.1 = 10%)
            
        Returns:
            Delay with jitter applied
            
        Example:
            # With base_delay=1.0 and jitter_factor=0.1:
            # Returns random value between 0.9 and 1.1
            delay = bucket.add_jitter(1.0, 0.1)
        """
        jitter = base_delay * jitter_factor * (2 * random.random() - 1)
        return max(0, base_delay + jitter)


class AdaptiveThrottler:
    """
    Adaptive request throttler with token bucket and cool-off periods.
    
    Combines token bucket rate limiting with adaptive behavior:
    - Normal operation: Token bucket controls request rate
    - Rate limited (429): Enters cool-off period with exponential backoff
    - Service unavailable (503): Enters cool-off period
    
    This helps the scraper automatically adapt to server load conditions.
    """
    
    def __init__(
        self,
        tokens_per_second: float = 0.67,  # ~1 request per 1.5 seconds
        capacity: int = 8,
        initial_backoff: float = 2.0,
        max_backoff: float = 60.0
    ):
        """
        Initialize adaptive throttler.
        
        Args:
            tokens_per_second: Normal request rate (tokens per second)
            capacity: Maximum burst capacity
            initial_backoff: Initial cool-off delay for rate limits
            max_backoff: Maximum cool-off delay
        """
        self.token_bucket = TokenBucket(tokens_per_second, capacity)
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.current_backoff = initial_backoff
        self.in_cooloff = False
        self.cooloff_until = 0.0
    
    async def acquire(self) -> float:
        """
        Acquire permission to make a request.
        
        Returns the time to wait before making the request.
        
        Returns:
            Delay in seconds before request should be made
        """
        # Check if we're in a cool-off period
        if self.in_cooloff:
            now = time.time()
            if now < self.cooloff_until:
                return self.cooloff_until - now
            else:
                # Cool-off period ended
                self.in_cooloff = False
                self.current_backoff = self.initial_backoff
        
        # Normal token bucket throttling with jitter
        base_wait = self.token_bucket.consume()
        return self.token_bucket.add_jitter(base_wait)
    
    def report_rate_limit(self):
        """
        Report that a rate limit (429) was encountered.
        
        Enters cool-off mode with exponential backoff.
        """
        self.in_cooloff = True
        self.cooloff_until = time.time() + self.current_backoff
        self.current_backoff = min(self.max_backoff, self.current_backoff * 2)
    
    def report_service_unavailable(self):
        """
        Report that service unavailable (503) was encountered.
        
        Enters cool-off mode with backoff.
        """
        self.in_cooloff = True
        self.cooloff_until = time.time() + self.current_backoff
        self.current_backoff = min(self.max_backoff, self.current_backoff * 1.5)
    
    def report_success(self):
        """
        Report a successful request.
        
        Gradually reduces backoff if we're recovering from rate limits.
        """
        if not self.in_cooloff and self.current_backoff > self.initial_backoff:
            # Gradually reduce backoff on successful requests
            self.current_backoff = max(self.initial_backoff, self.current_backoff * 0.9)
