"""Measure phases without logging arguments, credentials or exception bodies."""
from functools import wraps
import logging
from time import perf_counter
from flask import g, has_request_context


def timed(phase):
    def decorate(function):
        @wraps(function)
        def measure(*args, **kwargs):
            start = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                request_id = getattr(g, 'request_id', 'unknown') if has_request_context() else 'offline'
                logging.getLogger(__name__).info('phase=%s request_id=%s duration_ms=%.1f', phase, request_id, (perf_counter()-start)*1000)
        return measure
    return decorate
