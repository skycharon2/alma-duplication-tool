"""Opt-in stage timings, kept separate from scientific reports and progress."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter, thread_time

_recorder = ContextVar('assessment_performance', default=None)


@dataclass
class StageTiming:
    name: str
    wall_seconds: float
    thread_cpu_seconds: float
    failed: bool


class PerformanceRecorder:
    def __init__(self, *, wall_clock=perf_counter, cpu_clock=thread_time):
        self.wall_clock, self.cpu_clock = wall_clock, cpu_clock
        self.stages = []

    @contextmanager
    def record(self):
        token = _recorder.set(self)
        try:
            yield self
        finally:
            _recorder.reset(token)


@contextmanager
def measure_stage(name):
    recorder = _recorder.get()
    if recorder is None:
        yield
        return
    wall, cpu = recorder.wall_clock(), recorder.cpu_clock()
    failed = True
    try:
        yield
        failed = False
    finally:
        recorder.stages.append(StageTiming(name, recorder.wall_clock() - wall,
                                           recorder.cpu_clock() - cpu, failed))
