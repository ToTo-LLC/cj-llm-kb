"""Plan 16 Task 36 / D29 — perf benchmark for ``validate_assignment=True``.

This test is INFORMATIONAL, not a gate. The locked decision (1.B + 3.A) is
to enable :class:`Config.model_config[validate_assignment]` unconditionally
regardless of the measured overhead; the benchmark exists so the cost is a
reproducible number on the record. Captured to ``tasks/lessons.md`` Plan 16
section per the task brief.

Methodology:

* Build two Pydantic models that mirror :class:`Config`'s assignment-side
  hot path: a "guarded" model with ``validate_assignment=True`` and a
  "baseline" model with ``validate_assignment=False``. Same field shapes,
  same constraints — the delta is the per-assignment validation cost.
* Time 1000 valid field assignments on each (deterministic PRNG seed so
  CI runs are reproducible). A valid assignment exercises the per-field
  validators end-to-end without short-circuiting on a raise.
* Print the wall-clock delta + percent overhead via ``capsys`` so the
  number is visible with ``pytest -s`` AND captured in the test record.
* Sanity-assert the delta is non-negative — validation is not free, so
  ``validate_assignment=True`` should never be faster than off. Anything
  else would mean the timing approach is broken.
* Do NOT assert anything about the magnitude of the delta. Per the
  locked decision, a 50% (or 500%) overhead does not gate the rollout.

Why a separate test model rather than instantiating :class:`Config` with
the flag toggled: the production :class:`Config` ships with the flag ON
(per the locked decision), and Pydantic v2 caches its validator on the
class — toggling at instance time isn't supported. Mirroring the field
shapes in a parallel test model gives a fair like-for-like comparison
without test-only mutation of the production schema.
"""

from __future__ import annotations

import random
import time

import pytest
from pydantic import BaseModel, ConfigDict, Field

# Number of round-trip assignments per measurement. 1000 is enough that
# each measurement is well above per-call clock noise (~10ns) but small
# enough that the test runs in <1s on CI. The PRNG seed is fixed so the
# same sequence of valid values is exercised on every run.
_N_ASSIGNMENTS = 1000
_PRNG_SEED = 0xBEEF


class _GuardedModel(BaseModel):
    """Mirrors :class:`Config`'s assignment-shape with ``validate_assignment=True``."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    web_port: int = Field(default=4317, ge=1024, le=65535)
    daily_usd: float = Field(default=5.0, ge=0.0)
    autonomous_mode: bool = False
    log_llm_payloads: bool = False
    alert_threshold_pct: int = Field(default=80, ge=0, le=100)


class _BaselineModel(BaseModel):
    """Mirrors :class:`_GuardedModel` exactly with ``validate_assignment=False``."""

    model_config = ConfigDict(extra="forbid", validate_assignment=False)
    web_port: int = Field(default=4317, ge=1024, le=65535)
    daily_usd: float = Field(default=5.0, ge=0.0)
    autonomous_mode: bool = False
    log_llm_payloads: bool = False
    alert_threshold_pct: int = Field(default=80, ge=0, le=100)


def _generate_assignments(rng: random.Random) -> list[tuple[str, object]]:
    """Build a deterministic list of (field, valid_value) pairs.

    Every value is INSIDE its field's constraint window so no assignment
    raises (the benchmark measures the success path). Mix of types so
    the validator exercises ints, floats, and bools.
    """
    fields = ("web_port", "daily_usd", "autonomous_mode", "log_llm_payloads", "alert_threshold_pct")
    pairs: list[tuple[str, object]] = []
    for _ in range(_N_ASSIGNMENTS):
        field = rng.choice(fields)
        value: object
        if field == "web_port":
            value = rng.randint(1024, 65535)
        elif field == "daily_usd":
            value = rng.uniform(0.0, 1000.0)
        elif field == "alert_threshold_pct":
            value = rng.randint(0, 100)
        else:
            # autonomous_mode / log_llm_payloads
            value = bool(rng.getrandbits(1))
        pairs.append((field, value))
    return pairs


def _time_assignments(model: BaseModel, pairs: list[tuple[str, object]]) -> float:
    """Return wall-clock seconds to apply every (field, value) via setattr."""
    start = time.perf_counter()
    for field, value in pairs:
        setattr(model, field, value)
    return time.perf_counter() - start


def test_validate_assignment_perf(capsys: pytest.CaptureFixture[str]) -> None:
    """Measure overhead of ``validate_assignment=True`` vs ``False`` over
    1000 random valid field assignments. Informational only — see module
    docstring + Plan 16 D29 for the locked rollout decision.
    """
    rng = random.Random(_PRNG_SEED)
    pairs = _generate_assignments(rng)

    # Construct fresh instances per measurement so the assignment hot
    # path is the only thing being measured (no cached state reuse).
    baseline = _BaselineModel()
    guarded = _GuardedModel()

    baseline_secs = _time_assignments(baseline, pairs)
    guarded_secs = _time_assignments(guarded, pairs)

    # Sanity: validation isn't free, so guarded should never be FASTER
    # than baseline by more than clock noise. If this assertion ever
    # fails the timing approach itself is wrong (e.g., JIT warmup
    # ordering, accidental no-op). 1us absolute slack absorbs
    # sub-microsecond ``time.perf_counter`` noise — at 1000 assignments,
    # both timings are typically O(100us-1ms), so 1us is well below the
    # signal floor.
    clock_noise_floor_s = 1e-6
    assert guarded_secs >= baseline_secs - clock_noise_floor_s, (
        f"validate_assignment=True ({guarded_secs:.6f}s) was FASTER than "
        f"baseline ({baseline_secs:.6f}s) — timing methodology is broken"
    )

    delta_secs = guarded_secs - baseline_secs
    overhead_pct = (delta_secs / baseline_secs) * 100.0 if baseline_secs > 0 else float("inf")
    overhead_per_call_us = (delta_secs / _N_ASSIGNMENTS) * 1e6

    # Print via capsys.readouterr-friendly stdout so the number is
    # visible with ``pytest -s`` AND captured in the test record. No
    # assertion on the magnitude — per locked 1.B + 3.A, the flag ships
    # regardless of the measured cost.
    print(
        f"\n[Plan 16 Task 36] validate_assignment perf benchmark "
        f"({_N_ASSIGNMENTS} random valid field assignments, seed={_PRNG_SEED:#x}):\n"
        f"  baseline (validate_assignment=False): {baseline_secs * 1000:.3f} ms\n"
        f"  guarded  (validate_assignment=True):  {guarded_secs * 1000:.3f} ms\n"
        f"  delta:                                {delta_secs * 1000:.3f} ms "
        f"({overhead_pct:.1f}% overhead, {overhead_per_call_us:.2f} us/call)\n"
    )

    captured = capsys.readouterr()
    assert "validate_assignment perf benchmark" in captured.out
