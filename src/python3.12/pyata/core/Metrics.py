#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-
from __future__ import annotations
from abc import ABC
from time import perf_counter_ns, time_ns
from typing import Any, ClassVar, Final, Iterable, Iterator, Protocol, Self, cast

import numpy          as NP
import more_itertools as MI
import scipy.stats    as SS  # pyright: ignore[reportMissingTypeStubs]

from  .Types      import ( Ctx, isBroadcastKey, HookEventCB #
                         , HookBroadcastCB, BroadcastKey    )
from  .Facets     import   FacetABC, HooksEvents, HooksBroadcasts
from ..immutables import   Map, Cel, cons_to_iterable
from ..config     import   Settings


DEBUG: Final[bool] = Settings().DEBUG


__all__: list[str] = [
    'MetricsObsBuf', 'MetricsPerSec', 'MetricsRegistry', 'Metrics'
]


################################################################################
#
# ---------- Metrics Facets ---------------------------------------------------
#
#  Sensor performance on my 2018 laptop and Python 3.12.1 sustains
#  250k observations per second (with minimal hooks), providing any
#  number of latest seconds summaries of observations as timeseries.
#

# Numpy Structured Records (dtype) for per-second summaries of observations.
# 64 bytes per second per sensor for summaries timeseries.
int_dtype: Final[NP.dtype[Any]] = NP.dtype([
    ( 'time', 'datetime64[ns]' ),  # timestamp of the second collected
    ( 'nobs', 'int64'      ),  # number of observations in the second
    ( 'min' , 'int64'      ),  # minimum
    ( 'max' , 'int64'      ),  # maximum
    ( 'mean', 'float64'    ),  # mean
    ( 'var' , 'float64'    ),  # variance
    ( 'skew', 'float64'    ),  # skewness
    ( 'kurt', 'float64'    )   # kurtosis
])

float_dtype: Final[NP.dtype[Any]] = NP.dtype([
    ( 'time', 'datetime64[ns]' ),
    ( 'nobs', 'int64'      ),
    ( 'min' , 'float64'    ),
    ( 'max' , 'float64'    ),
    ( 'mean', 'float64'    ),
    ( 'var' , 'float64'    ),
    ( 'skew', 'float64'    ),
    ( 'kurt', 'float64'    )
])

nan: NP.float64 = NP.float64(NP.nan)


class DescribeResults(Protocol):
    """Typing helper for scipy.stats.describe() results."""
    nobs    : int
    minmax  : tuple[Any, Any]
    mean    : NP.float64
    variance: NP.float64
    skewness: NP.float64
    kurtosis: NP.float64


class MetricsObsBuf(FacetABC[Any, tuple[int, Cel[Any]]]):
    """Facet for buffering observations per sensor."""
    default: ClassVar[tuple[int, Cel[Any]]] = (0, ())
    
    @classmethod
    def observation(cls: type[Self], ctx: Ctx, key: Any, val: Any) -> Ctx:
        """Add key observation to sensor buffer in a metrics context."""
        nobs: int
        cell: Cel[Any]
        nobs, cell = cls.get(ctx, key)
        return cls.set(ctx, key, (nobs + 1, (val, cell)))


class MetricsPerSec[R: NP.ndarray[Any, Any]](FacetABC[Any, Cel[R]]):
    """Facet for per-second summaries of observations per sensor."""
    default: ClassVar[Cel[NP.ndarray[Any, Any]]] = ()

    @classmethod
    def add_data(cls: type[Self], ctx: Ctx, key: Any, rec: R) -> Ctx:
        """Add data to per-second summaries of observations per sensor."""
        return cls.set(ctx, key, (rec, cls.get(ctx, key)))
    
    @classmethod
    def get_latest_seconds(cls: type[Self], ctx: Ctx, key: Any, n: int = 0
    ) -> Iterable[R]:
        if n < 1:
            return cons_to_iterable(cls.get(ctx, key))
        else:
            return MI.take(n, cons_to_iterable(cls.get(ctx, key)))

    @classmethod
    def get_keys(cls: type[Self], ctx: Ctx) -> Iterable[Any]:
        yield from cls.get_whole(ctx).keys()


class MetricsRegistry(FacetABC[Any, 'Metrics.Sensor[Any] | None']):
    default: ClassVar[Metrics.Sensor[Any] | None] = None
    
    class MetricsSensorMapKey(FacetABC['Metrics.Sensor[Any]', Any]):
        default: ClassVar[Any] = None
        
        @classmethod
        def register(cls: type[Self], ctx: Ctx,
            sensor: Metrics.Sensor[Any],
            key: Any
        ) -> Ctx:
            stored = cls.get(ctx, sensor)
            if stored:
                # If there's no need to, don't update immutable context.
                if stored != key:
                    raise RuntimeError(
                        f"Can't register {sensor}: "
                        f"registered already under: {stored}")
                return ctx
            return cls.set(ctx, sensor, key)
        
        @classmethod
        def get_key(cls: type[Self], ctx: Ctx, sensor: Metrics.Sensor[Any]
                    ) -> Any:
            return cls.get(ctx, sensor)

    @classmethod
    def register(cls: type[Self], ctx: Ctx,
                 key: Any, sensor: Metrics.Sensor[Any]
    ) -> Ctx:
        stored = cls.get(ctx, key)
        if stored:
            # If there's no need to, don't update immutable context.
            if stored != sensor:
                raise RuntimeError(
                    f"Can't register {sensor}: "
                    f"{key} registered already to: {stored}")
            return ctx
        ctx = cls.MetricsSensorMapKey.register(ctx, sensor, key)
        return cls.set(ctx, key, sensor)
    
    @classmethod
    def get_sensor(cls: type[Self], ctx: Ctx, key: Any
                   ) -> Metrics.Sensor[Any] | None:
        return cls.get(ctx, key)
    
    @classmethod
    def get_key(cls: type[Self], ctx: Ctx, sensor: Metrics.Sensor[Any]
                ) -> Any | None:
        return cls.MetricsSensorMapKey.get_key(ctx, sensor)

class Metrics:
    ctx: Ctx  # Metrics needs to own own context.
    
    # Designed to be singleton, but not limited to be so.
    _Singleton: Self | None = None
    
    # time.perf_counter_ns() threshold to next time.time() second tick.
    _perf_ns_sec_threshold: int
    
    def __init__(self: Self, ctx: Ctx | None = None) -> None:
        self.ctx = ctx if ctx else Map()
        self._perf_ns_sec_threshold = self._compute_perf_ns_sec_threshold(
            perf_counter_ns(), time_ns())
    
    @classmethod
    def Singleton(cls: type[Self], ctx: Ctx | None = None) -> Self:
        if cls._Singleton is None:
            self: Self = cls(ctx)
            cls._Singleton = self
            return self
        else:
            return cls._Singleton

    @staticmethod
    def _compute_perf_ns_sec_threshold(perf_ns: int, time_ns: int) -> int:
        """Compute perf_counter_ns() threshold to next time() second tick."""
        # NOTE: The reason we don't call time functions here is
        #       to make it easy for numba to compile.
        return perf_ns - time_ns + (time_ns // 10**9 + 1) * 10**9
    
    # NOTE: Use self._perf_ns() if it doesn't matter.
    #       These two methods are wrapping time.perf_counter_ns(),
    #       providing a choice of where to account for hooks time.
    def _perf_ns_after_hooks(self: Self) -> int:
        perf_ns = perf_counter_ns()
        threshold = self._perf_ns_sec_threshold
        if threshold <= perf_ns:
            time_ns_: int = time_ns()
            ticks_passed: int = (perf_ns - threshold) // 10**9 + 1
            self._perf_ns_sec_threshold = (
                # NOTE: inlined _compute_perf_ns_sec_threshold()
                perf_ns - time_ns_ + (time_ns_ // 10**9 + 1) * 10**9)
            # Handle own hooks first, so others get updated context.
            self.ctx = HooksEvents.run(self.ctx, self._hook_per_sec, (
                ticks_passed, time_ns_))
            # Now broadcast seconds ticks to other hooks.
            self.ctx = HooksEvents.run(self.ctx, self.hook_ticks, (
                ticks_passed, 1e-9 * time_ns_))
            # get a fresh perf_ns                  #  ◁──────────────────────╮
            perf_ns = perf_counter_ns()            #  This part is different │
        return perf_ns                             #                         │
                                                    #                        │
    def _perf_ns(self: Self) -> int:                  #                      │
        perf_ns = perf_counter_ns()                      #                   │
        threshold = self._perf_ns_sec_threshold             #                │
        if threshold <= perf_ns:                                #            │
            time_ns_: int = time_ns()                              #         │
            ticks_passed: int = (perf_ns - threshold) // 10**9 + 1     #     │
            self._perf_ns_sec_threshold = (                              #   │
                # NOTE: inlined _compute_perf_ns_sec_threshold()          #  │
                perf_ns - time_ns_ + (time_ns_ // 10**9 + 1) * 10**9)     #  │
            # Handle own hooks first, so others get updated context.      #  │
            self.ctx = HooksEvents.run(self.ctx, self._hook_per_sec, (    #  │
                ticks_passed, time_ns_))                                  #  │
            # Now broadcast seconds ticks to other hooks.                 #  │
            self.ctx = HooksEvents.run(self.ctx, self.hook_ticks, (       #  │
                ticks_passed, 1e-9 * time_ns_))                           #  │
        return perf_ns  # ───────────────────────────────────────────────────╯
    
    def _hook_per_sec(
        self: Self,
        cb: HookEventCB[tuple[int, int]]
    ) -> None:
        """Internal hook for per-second summaries."""
        self.ctx = HooksEvents.hook(self.ctx, self._hook_per_sec, cb)
    
    def hook_ticks(
        self: Self,
        cb: HookEventCB[tuple[int, float]]
    ) -> None:
        """Hook for seconds ticks.  Cb: tuple(ticks_passed: int, time: float) -> None."""
        self.ctx = HooksEvents.hook(self.ctx, self.hook_ticks, cb)

    class Sensor[N: (int, float)](ABC):
        key: Any
        ini: NP.dtype[Any]
        obs_dtype: Any
        per_sec_stats_rec_dtype: NP.dtype[Any]
        _metrics: Metrics
        skip_stats_timeseries: bool

        def __init__(
            self: Self,
            ini: N,
            key: Any | None = None,
            metrics: Metrics | None = None,
            *,
            skip_stats_timeseries: bool = False
        ) -> None:
            typ = type(ini)
            if typ is int:
                self.per_sec_stats_rec_dtype = int_dtype
                self.obs_dtype = NP.int64
            elif typ is float:
                self.per_sec_stats_rec_dtype = float_dtype
                self.obs_dtype = NP.float64
            else:
                raise TypeError(f"Unsupported type: {typ}")
            self.ini = self.obs_to_dtype(ini)
            self.key = key if key else self
            self._metrics = metrics if metrics else Metrics.Singleton()
            self._metrics.ctx = MetricsRegistry.register(
                self._metrics.ctx, self.key, self)
            
            self.skip_stats_timeseries = skip_stats_timeseries
            self._metrics._hook_per_sec(self._per_sec_hook)

        def obs_to_dtype(self: Self, obs: N) -> NP.dtype[Any]:
            return self.obs_dtype(obs)

            #       ╭────────────────────────────────────────────────────────╮
        if DEBUG: # │ -- BEGIN IF DEBUG SECTION -- BEGIN IF DEBUG SECTION -- │
            #       ╰────────────────────────────────────────────────────────╯ 
            
            def __call__(self: Self, val: N) -> N:
                ctx = self._metrics.ctx
                self._metrics._perf_ns()
                if not self.skip_stats_timeseries:
                    ctx = MetricsObsBuf.observation(ctx, self.key, val)
                ctx = HooksBroadcasts.run(
                    ctx, (Metrics.Sensor, type(self)), (self.key, val))
                if isBroadcastKey(self.key):
                    ctx = HooksBroadcasts.run(ctx, self.key, val)
                else:
                    ctx = HooksEvents.run(ctx, self.key, val)
                self._metrics.ctx = ctx
                return val

            #       ╭────────────────────────────────────────────────────────╮
        else: #     │ --- ELSE IF DEBUG SECTION --- ELSE IF DEBUG SECTION -- │
            #       ╰────────────────────────────────────────────────────────╯ 
            
            def __call__(self: Self, val: N) -> N:
                self._metrics._perf_ns()
                if not self.skip_stats_timeseries:
                    self._metrics.ctx = MetricsObsBuf.observation(
                        self._metrics.ctx, self.key, val)
                return val
        
        #           ╭────────────────────────────────────────────────────────╮
        #           │ ---  END IF DEBUG SECTION --- END IF DEBUG SECTION --- │
        #           ╰────────────────────────────────────────────────────────╯ 
        
        def _per_sec_hook(self: Self, ctx: Ctx, data: tuple[int, int]) -> Ctx:
            if self.skip_stats_timeseries:
                return ctx
            t_took, t_ns = data
            key, ctx, ini = self.key, self._metrics.ctx, self.ini
            nobs: int
            cons: Cel[Any]
            nobs, cons = MetricsObsBuf.get(ctx, key)
            for n in range(t_took, (1 if nobs > 0 else 0), -1):
                # handle empty seconods, including this second if empty
                MetricsPerSec.add_data(ctx, key,
                    NP.array([
                        NP.datetime64(t_ns - n * 10**9, 'ns'),
                        NP.int64(0),  # nobs (number of observations)
                        ini,  # min
                        ini,  # max
                        nan,  # mean
                        nan,  # variance
                        nan,  # skewness
                        nan   # kurtosis
                    ], dtype=self.per_sec_stats_rec_dtype))
            if nobs == 0:
                return ctx  # no observations
            elif nobs == 1:
                val = cons[0]  # pyright: ignore[reportGeneralTypeIssues]
                ctx = MetricsPerSec.add_data(ctx, key, 
                    NP.array([
                        NP.datetime64(t_ns, 'ns'),
                        NP.int64(1),     # nobs (number of observations)
                        val,             # min
                        val,             # max
                        NP.float64(val), # mean
                        nan,             # variance
                        nan,             # skewness
                        nan              # kurtosis
                    ], dtype=self.per_sec_stats_rec_dtype))
            else:
                # Avoiding any temporary structures while creating ndarray
                # for efficient computation of summary statistics.
                obs_iter: Iterator[N] = iter(cons_to_iterable(cons))
                vals = NP.fromiter(obs_iter, self.obs_dtype, nobs)
                summary = cast(DescribeResults,
                    SS.describe(vals)) # pyright: ignore[reportUnknownMemberType]
                ctx = MetricsPerSec.add_data(ctx, key,
                    NP.array([
                        NP.datetime64(t_ns, 'ns'),
                        NP.int64(nobs),     # nobs (number of observations)
                        summary.minmax[0],  # min
                        summary.minmax[1],  # max
                        summary.mean,       # mean
                        summary.variance,   # variance
                        summary.skewness,   # skewness
                        summary.kurtosis    # kurtosis
                    ], dtype=self.per_sec_stats_rec_dtype))
            return MetricsObsBuf.set(ctx, key, MetricsObsBuf.default)
    
    def _hook_all_sensors(self: Self,
        cb: HookBroadcastCB[tuple[Any, Any]],
        sensor_type: type[Metrics.Sensor[Any]] | None = None
    ) -> None:
        key: BroadcastKey = (
            Metrics.Sensor, sensor_type) if sensor_type else (Metrics.Sensor,)
        self.ctx = HooksBroadcasts.hook(self.ctx, key, cb)

    class Gauge[N: (int, float)](Sensor[N]):
        _last: N
        
        def __init__(
            self: Self,
            ini: N,
            key: Any | None = None,
            metrics: 'Metrics | None' = None,
            *,
            skip_stats_timeseries: bool = False
        ) -> None:
            super().__init__(ini, key, metrics,
                skip_stats_timeseries=skip_stats_timeseries)
            self._last = ini
        
        def __call__(self: Self, val: N) -> N:
            last = self._last
            self._last = super().__call__(val)
            return last

    class Counter[N: (int, float)](Sensor[N]):
        _acc: N
        
        def __init__(
            self: Self,
            ini: N,
            key: Any | None = None,
            metrics: 'Metrics | None' = None,
            *,
            skip_stats_timeseries: bool = False
        ) -> None:
            super().__init__(ini, key, metrics,
                skip_stats_timeseries=skip_stats_timeseries)
            if NP.isnan(ini):
                raise ValueError(f"Invalid value: {ini}")
            self._acc = ini
        
        def get(self: Self) -> N:
            return self._acc
        
        def __call__(self: Self, val: N) -> N:
            # We don't want to pay for this check, especually since it
            # doesn't help with the "int*" typing bug.
            # if isinstance(val, float64) and isnan(val):
            #    raise ValueError(f"Invalid value: {val}")
            # TODO: Pyright infers type "int*", why?
            self._acc = cast(N, self._acc + super().__call__(val))
            return self._acc

    class Stopwatch(Sensor[int]):
        _total: int
        _last : int
        _running: bool
        _start_perf_ns: int

        def __init__(
            self: Self,
            ini: int = 0,
            key: Any | None = None,
            metrics: 'Metrics | None' = None,
            *,
            skip_stats_timeseries: bool = False
        ) -> None:
            super().__init__(ini, key, metrics,
                skip_stats_timeseries=skip_stats_timeseries)
            self._total = ini
            self._last  = ini
            self._running = False

        def last_or_running_ns(self: Self) -> int:
            perf_ns = self._metrics._perf_ns()
            if self._running:
                return perf_ns - self._start_perf_ns
            return self._last
        
        def total_ns(self: Self) -> int:
            perf_ns = self._metrics._perf_ns()
            if self._running:
                return perf_ns - self._start_perf_ns + self._total
            return self._total
        
        def __call__(self: Self, val: int) -> int:
            raise TypeError(
                "Stopwatch ContextManager cannot take samples.")

        def __enter__(self: Self) -> Self:
            self._running = True
            self._start_perf_ns = self._metrics._perf_ns_after_hooks()
            return self
        
        def __exit__(self: Self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
            self._last = self._metrics._perf_ns() - self._start_perf_ns
            self._total = (
                self._total + super().__call__(self._last))
            self._running = False
            return False  # don't suppress exceptions
    
    def get_latest_seconds_of_sensor(
        self: Self,
        sensor: Metrics.Sensor[Any],
        n: int = 0
    ) -> Iterable[NP.ndarray[Any, Any]]:
        return MetricsPerSec[NP.ndarray[Any, Any]].get_latest_seconds(
            self.ctx, MetricsRegistry.get_key(self.ctx, sensor), n)
