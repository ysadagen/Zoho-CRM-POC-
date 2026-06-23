"""Exponential backoff with jitter — pure helper, no I/O.

The Zoho client sleeps for :func:`backoff_delay_seconds` between retry
attempts on transient failures. Full jitter (a uniform draw over the whole
``[0, capped_exponential]`` window) is used because it spreads concurrent
retriers most evenly and is the AWS-recommended default.
"""

from __future__ import annotations

import random

# Hard ceiling so an unlucky high attempt number can't schedule a multi-minute
# sleep. The Zoho client's bounded attempt count keeps us well under this.
_MAX_DELAY_SECONDS = 30.0


def backoff_delay_seconds(*, attempt: int, base_ms: int) -> float:
    """Return the delay before retry ``attempt`` (1-based), in seconds.

    The exponential window doubles each attempt — ``base * 2**(attempt-1)`` —
    then full jitter draws uniformly within it. ``attempt`` is clamped to ``>=
    1`` so a mis-call can never produce a negative exponent.
    """
    safe_attempt = max(attempt, 1)
    exponential_ms = base_ms * (2 ** (safe_attempt - 1))
    capped_seconds = min(exponential_ms / 1000.0, _MAX_DELAY_SECONDS)
    return random.uniform(0.0, capped_seconds)
