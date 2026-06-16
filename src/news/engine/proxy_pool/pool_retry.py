# INFRASTRUCTURE

import time

_sleep   = time.sleep     # patchable in tests — patch pool_retry._sleep, not time.sleep
_BACKOFF = (1, 2, 4, 8)  # inter-attempt waits (s); 5 attempts total, ~90s max at FETCH_TIMEOUT=15


# FUNCTIONS

# Call fn() up to 5 times with exponential backoff; re-raise last exception on final failure
def fetch_with_retry(fn):
    """Retry fn() up to 5 times: sleep 1/2/4/8s between attempts. Re-raises last exception."""
    last_exc = None
    for delay in (None, *_BACKOFF):
        if delay is not None:
            _sleep(delay)
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
    raise last_exc
