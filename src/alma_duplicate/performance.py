"""Opt-in stage timings, kept separate from scientific reports and progress."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock, get_ident
from time import perf_counter, thread_time

_recorder = ContextVar('assessment_performance', default=None)
_stack = ContextVar('assessment_performance_stack', default=())


@dataclass
class StageTiming:
    name: str
    wall_seconds: float
    thread_cpu_seconds: float
    failed: bool
    stage_id: int
    parent_id: int | None
    self_wall_seconds: float = 0
    self_thread_cpu_seconds: float = 0


class PerformanceRecorder:
    def __init__(self, *, wall_clock=perf_counter, cpu_clock=thread_time):
        self.wall_clock, self.cpu_clock = wall_clock, cpu_clock
        self.stages = []
        self._next_id = 0
        self._lock = Lock()

    @contextmanager
    def record(self):
        token = _recorder.set(self)
        stack_token = _stack.set(())
        try:
            yield self
        finally:
            _stack.reset(stack_token)
            _recorder.reset(token)


@contextmanager
def measure_stage(name):
    recorder = _recorder.get()
    if recorder is None:
        yield
        return
    wall, cpu = recorder.wall_clock(), recorder.cpu_clock()
    stack = _stack.get()
    thread_id = get_ident()
    parent_thread, parent = stack[-1] if stack else (None, None)
    with recorder._lock:
        stage = StageTiming(name, 0, 0, True, recorder._next_id,
                            parent.stage_id if parent is not None else None)
        recorder._next_id += 1
    token = _stack.set((*stack, (thread_id, stage)))
    failed = True
    try:
        yield
        failed = False
    finally:
        stage.wall_seconds = recorder.wall_clock() - wall
        stage.thread_cpu_seconds = recorder.cpu_clock() - cpu
        stage.failed = failed
        stage.self_wall_seconds += stage.wall_seconds
        stage.self_thread_cpu_seconds += stage.thread_cpu_seconds
        _stack.reset(token)
        with recorder._lock:
            # A copied context preserves the parent ID, but worker stages can
            # overlap the parent's work and consume CPU on a different thread.
            if parent is not None and parent_thread == thread_id:
                parent.self_wall_seconds -= stage.wall_seconds
                parent.self_thread_cpu_seconds -= stage.thread_cpu_seconds
            recorder.stages.append(stage)
