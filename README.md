# FretOPT

A personal project built out of curiosity: is there a mathematically justified "best" fingering pattern for guitar?

I combined nearly a decade of playing experience across acoustic, electric, and bass guitar with a bit of mathematical reasoning and some coding to explore the question. The goal is not to replace taste or feel, but to test whether a compact optimization model can generate playable, efficient fingerings from musical input alone.

> AI was used to help refactor code, help explore novel mathematical algorythms, and write tests during the early stages of the project. Future development is being written by hand as I continue learning and improving my programming skills. 

## Main idea

The core idea behind FretOPT is simple:

- small finger movements are usually cheaper than large repositioning moves
- keeping the hand within a narrow fret range can reduce strain and effort
- fingering choices should account for both note selection and movement cost

In other words, the project tries to model the tradeoff between:

- choosing the most natural note
- choosing the most efficient hand movement
- keeping the result comfortable and playable in real life

## Real-world application

This project is motivated by practical guitar playing, not abstract theory alone. The model is meant to reflect how a guitarist actually moves while playing:

- how often do you shift hand position?
- does a small movement save more effort than a more "obvious" fingering?
- can a better route be found by optimizing the hand path, not just the notes?

The goal is to see whether these choices can be described with a usable cost function and whether the result is genuinely helpful in real playing situations.

FretOPT's real-world experience: 
- used by professional band " Валентин Прекрасный " to extrapolate MIDI melodies to tabulatures
- used by peer guitarists to test applicability
## Technical overview

**FretOpt** formulates monophonic guitar fingering generation as an exact shortest-path problem on a state-augmented DAG. Instead of treating transitions as memoryless point-to-point jumps in fret indices, FretOpt models physical fretboard geometry in millimeters, tracks a discretized palm reference coordinate, and penalizes within-position fret/string bounding envelopes.

### Core formulation

#### 1. Physical geometry
{ NOTE: GUITAR MEASUREMENTS WERE TAKEN OFF MY OWN GUITAR, JACKSON KELLY}

For a 6-string guitar in standard tuning with open-string pitches p_open = (64, 59, 55, 50, 45, 40), scale length L = 647.7 mm, and string spacing d_str = 7.0 mm, fret f in [0, 24] is mapped to its physical longitudinal coordinate:

x(f) = L * (1 - 2^(-f / 12))
Delta x(f_a, f_b) = |x(f_b) - x(f_a)|

#### 2. Left-hand state and transitions

The fretboard is discretized into a palm reference grid G with step Delta g = 5.0 mm. At note t, the hand state is a 6-tuple:

q_t = (p_t, c_t, f_min, f_max, s_min, s_max)

where p_t = (s_t, f_t) is the played note, c_t in G is the palm center, and [f_min, f_max] x [s_min, s_max] is the bounding box of notes played since the last palm shift.

- stay (stationary hand): keeps c_t = c_(t-1) and expands the segment envelope [f_min, f_max] and [s_min, s_max], valid if Delta x(f_min, f_max) <= S_max (85.0 mm)
- reset (paid shift): moves the palm to c_t != c_(t-1), pays a shift penalty, and resets the envelope bounds to (f_t, f_t, s_t, s_t)

#### 3. Step cost decomposition

Each transition q_(t-1) -> q_t minimizes the additive objective:

C(q_(t-1), q_t) = C_state(q_t) + C_str(p_(t-1), p_t) + C_repo(c_(t-1), c_t) + C_move(p_(t-1), p_t)

- C_state (stretch and diagonal span): a C^0-continuous piecewise-quadratic function of S = Delta x(f_min, f_max) across comfortable (S <= 55 mm) and extended (55 < S <= 85 mm) regimes, scaled by cross-string width 1 + gamma_str * max(0, s_max - s_min - 1)
- C_str (string crossing): piecewise-linear penalty for adjacent (Delta s = 1) vs. skipped (Delta s >= 2) string transitions
- C_repo (subadditive shift): c_shift + w_shift * |c_t - c_(t-1)| for c_t != c_(t-1) (c_shift = 1.5), preventing artificial path fragmentation into micro-shifts
- C_move (local motion): w_note * Delta x(f_(t-1), f_t)

### Model hierarchy (M0 - M3)

| Model | Solver | State space | Description |
| --- | --- | --- | --- |
| **M0** | `solve_baseline(..., "M0")` | Position (s, f) | Exact Viterbi DP over Manhattan index distance |Delta f| + |Delta s| |
| **M1** | `solve_baseline(..., "M1")` | Position (s, f) | Exact Viterbi DP over 2D Euclidean distance in millimeters |
| **M2** | `solve_greedy(...)` | 6-tuple `State` | Myopic step-wise greedy search over the full hand cost C |
| **M3** | `solve_hand(...)` | 6-tuple `State` | Exact layered DP over C with shift-equivalence reduction |

**Exact shift factorization (`shift_sources`)**: because `reset` discards historical envelope bounds, its transition cost depends on q_(t-1) solely through (p_(t-1), c_(t-1)). Prior to expanding shift transitions at each layer, `solve_hand` retains only the minimum-cost witness per (p_(t-1), c_(t-1)) equivalence class, compressing branching complexity without approximation.

### Model assumptions and scope limits (v0.1)

1. **Envelope memory vs. explicit fingerings**: `State` tracks the segment bounding box [f_min, f_max] x [s_min, s_max] rather than individual finger assignments (1, 2, 3, 4). Consequently, C_state is charged at each step within a stationary segment until a shift (`reset`) resets the bounds.
2. **Open-string geometry (f = 0)**: fret 0 is mapped to x(0) = 0.0 mm without a left-hand bypass; playing an open string from a high position forces a palm shift.
3. **Tempo invariance**: costs depend on spatial geometry rather than inter-onset intervals (Delta t).
4. **Exactness guarantee**: solvers never silently beam-prune. Exceeding `max_states` (default 200,000 per layer) raises an explicit `RuntimeError`.

### Usage and verification

```python
from fretopt import CostConfig, diagnostics, solve_baseline, solve_greedy, solve_hand

notes = [64, 66, 69, 67]  # MIDI pitches (40..88)
cfg = CostConfig()

result = solve_hand(notes, cfg)
print(f"{result.model} | cost={result.cost:.4f} | path={[s.played for s in result.path]}")

for step in diagnostics(result, cfg):
    print(step["index"], step["position"], f"palm={step['new_hand']['palm_ref_mm']}mm", f"cost={step['step_cost']:.4f}")
```

Run the unit and oracle verification suite (C^0 continuity, monotonicity, subadditivity, greedy counterexample, and exact equivalence against `brute_force_hand`):

```bash
python3 -m unittest -v test_fretopt.py
```

## Current status

- exploratory research project
- personal project with practical guitar focus
- still under active development
