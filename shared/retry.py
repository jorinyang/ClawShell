"""Retry helper — exponential backoff for network calls."""
import time, logging
from functools import wraps

logger = logging.getLogger(__name__)

def with_retry(max_attempts=3, base_delay=1.0, backoff=2.0):
    """Decorator: retry with exponential backoff."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        logger.warning(f"Retry exhausted after {max_attempts} attempts: {e}")
                        raise
                    logger.debug(f"Retry {attempt}/{max_attempts} after {delay}s: {e}")
                    time.sleep(delay)
                    delay *= backoff
            return None
        return wrapper
    return decorator
