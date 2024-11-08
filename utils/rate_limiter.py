# utils/rate_limiter.py
import asyncio
import time
import logging
from typing import Dict

class RateLimit:
    def __init__(self):
        self.rate_limits: Dict[str, float] = {}
        self.global_rate_limit: float = None
        self.lock = asyncio.Lock()

    async def check_rate_limit(self, bucket: str) -> float:
        """Check if we need to wait for rate limit
        Args:
            bucket (str): The rate limit bucket to check
        Returns:
            float: Time to wait (0 if no wait needed)
        """
        async with self.lock:
            now = time.time()
            
            # Check global rate limit
            if self.global_rate_limit and now < self.global_rate_limit:
                return self.global_rate_limit - now
                
            # Check bucket-specific rate limit
            if bucket in self.rate_limits:
                reset_time = self.rate_limits[bucket]
                if now < reset_time:
                    return reset_time - now
                    
            return 0

    async def update_rate_limit(self, bucket: str, reset_after: float, is_global: bool = False):
        """Update rate limit information
        Args:
            bucket (str): The rate limit bucket to update
            reset_after (float): Time in seconds until the rate limit resets
            is_global (bool): Whether this is a global rate limit
        """
        async with self.lock:
            reset_time = time.time() + reset_after
            if is_global:
                self.global_rate_limit = reset_time
            else:
                self.rate_limits[bucket] = reset_time

    async def clear_bucket(self, bucket: str):
        """Clear rate limit for a specific bucket
        Args:
            bucket (str): The rate limit bucket to clear
        """
        async with self.lock:
            if bucket in self.rate_limits:
                del self.rate_limits[bucket]

    async def clear_all(self):
        """Clear all rate limits"""
        async with self.lock:
            self.rate_limits.clear()
            self.global_rate_limit = None