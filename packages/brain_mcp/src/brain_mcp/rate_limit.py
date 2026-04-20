"""brain_mcp.rate_limit — re-export from brain_core.rate_limit.

Plan 05 Task 14 moved the real implementation to brain_core. This module
exists for backwards compatibility with any brain_mcp consumer that
imports from the Plan 04 location.
"""

from brain_core.rate_limit import RateLimitConfig, RateLimiter, RateLimitError

__all__ = ["RateLimitConfig", "RateLimitError", "RateLimiter"]
