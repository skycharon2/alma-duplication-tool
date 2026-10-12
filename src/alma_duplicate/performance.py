"""Opt-in stage timings, kept separate from scientific reports and progress."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
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
    stage = StageTiming(name, 0, 0, True, recorder._next_id,
                        stack[-1].stage_id if stack else None)
    recorder._next_id += 1
    token = _stack.set((*stack, stage))
    failed = True
    try:
        yield
        failed = False
    finally:
        stage.wall_seconds = recorder.wall_clock() - wall
        stage.thread_cpu_seconds = recorder.cpu_clock() - cpu
        stage.failed = failed
        # Children subtract their inclusive duration from the parent's own time.
        stage.self_wall_seconds += stage.wall_seconds
        stage.self_thread_cpu_seconds += stage.thread_cpu_seconds
        if stack:
            stack[-1].self_wall_seconds -= stage.wall_seconds
            stack[-1].self_thread_cpu_seconds -= stage.thread_cpu_seconds
        _stack.reset(token)
        recorder.stages.append(stage)
