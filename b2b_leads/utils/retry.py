# utils/retry.py
import time
import functools
import requests
from typing import Optional, Callable, Any
from .logger import get_logger

logger = get_logger("retry")


def retry_request(
    func: Callable,
    *args,
    max_retries: int = 3,
    backoff_base: float = 2.0,
    exceptions: tuple = (requests.RequestException, TimeoutError),
    **kwargs
) -> Any:
    """
    Führt eine Funktion mit exponentiellem Backoff aus.

    Args:
        func: Aufzurufende Funktion
        max_retries: Maximale Anzahl Wiederholungen
        backoff_base: Basis für exponentiellen Backoff (Sekunden)
        exceptions: Ausnahmen die einen Retry auslösen
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt == max_retries:
                logger.error(f"Alle {max_retries} Versuche fehlgeschlagen: {e}")
                raise
            wait_time = backoff_base ** attempt
            logger.warning(
                f"Versuch {attempt + 1}/{max_retries} fehlgeschlagen: {e}. "
                f"Warte {wait_time:.1f}s..."
            )
            time.sleep(wait_time)

    raise last_exception


def with_retry(max_retries: int = 3, backoff_base: float = 2.0):
    """Decorator für automatische Retry-Logik."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return retry_request(
                func, *args,
                max_retries=max_retries,
                backoff_base=backoff_base,
                **kwargs
            )
        return wrapper
    return decorator


def safe_get(url: str, session: Optional[requests.Session] = None, timeout: int = 10, **kwargs) -> Optional[requests.Response]:
    """HTTP GET mit Retry und Fehlerbehandlung."""
    s = session or requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; B2BLeadBot/1.0; "
            "+https://github.com/your-org/b2b-leads)"
        )
    }
    try:
        response = retry_request(
            s.get, url,
            max_retries=3,
            timeout=timeout,
            headers=headers,
            **kwargs
        )
        response.raise_for_status()
        return response
    except Exception as e:
        logger.warning(f"GET {url} fehlgeschlagen: {e}")
        return None
