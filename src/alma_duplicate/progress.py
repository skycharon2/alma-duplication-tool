"""Optional execution-local telemetry; never part of scientific evidence."""
from contextlib import contextmanager
from contextvars import ContextVar

_observer = ContextVar('assessment_progress_observer', default=None)


@contextmanager
def observe_progress(observer):
    token = _observer.set(observer)
    try:
        yield
    finally:
        _observer.reset(token)


def emit_progress(stage, completed=None, total=None, unit=None):
    observer = _observer.get()
    if observer is not None:
        try:
            observer(dict(stage=stage, completed=completed, total=total, unit=unit))
        except Exception:
            # A broken progress consumer must not change evaluation or exports.
            pass
