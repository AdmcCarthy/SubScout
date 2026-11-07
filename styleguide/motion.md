# Motion

Motion follows d3 practice, not dashboard design systems: things move when the **state changes in a
way that carries meaning**.

- **Object constancy:** marks are keyed, so a bar, line, row or point is the same object before and
  after a transition.
- **Staging:** axes first, then marks (staggered), then labels and annotation.
- **Tokens:** `--ss-dur-fast` 180 ms, `--ss-dur` 450 ms, `--ss-dur-slow` 850 ms, `--ss-stagger` 35 ms,
  easing ≈ `d3.easeCubicInOut`. JavaScript reads them via `motion()` so CSS and d3 agree.
- **Reduced motion:** `prefers-reduced-motion` sets all durations to zero; the state still changes.
- **Read and Present share one state sequence:** transitions are written once.
- **Never** animate decoration, loop attention-seeking effects, or animate values in a way that
  passes through misleading intermediate states (e.g. a bar briefly exceeding its value).
- Outcrop may choreograph (explode and regroup, force layouts) for the hook; the steady state must
  still pass the truth gate.
