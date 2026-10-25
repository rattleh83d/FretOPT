import math
import random
import unittest
from dataclasses import replace

from fretopt import (CostConfig, HandModel, Position, State, brute_force_hand,
                     diagnostics, find_note_positions, fret_x_mm,
                     physical_fret_span_mm, position_layers, reposition_cost,
                     solve_baseline, solve_greedy, solve_hand, state_cost,
                     stretch_cost, string_transition_cost)


def pinned(frets, string=1):
    positions = [Position(string, f) for f in frets]
    return [p.midi for p in positions], [(p,) for p in positions]


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.cfg = CostConfig()

    def test_positions_all_pitches_and_boundaries(self):
        for midi in range(40, 89):
            positions = find_note_positions(midi)
            self.assertTrue(positions)
            self.assertEqual(len(positions), len(set(positions)))
            for p in positions:
                self.assertEqual(p.midi, midi)
        self.assertEqual(find_note_positions(40), (Position(6, 0),))
        self.assertEqual(find_note_positions(88), (Position(1, 24),))

    def test_invalid_inputs(self):
        for value in (39, 89, 60.0, True, "60"):
            with self.assertRaises(ValueError):
                find_note_positions(value)
        with self.assertRaises(ValueError):
            solve_hand([])
        with self.assertRaises(ValueError):
            position_layers([60], [(Position(1, 1),)])
        with self.assertRaises(ValueError):
            solve_baseline([60], "unknown")
        for changes in ({"hard_stretch_mm": 55}, {"palm_grid_mm": 0},
                        {"extended_weight": math.nan}, {"reposition_base_cost": -1}):
            with self.assertRaises(ValueError):
                replace(self.cfg, **changes)
        with self.assertRaises(ValueError):
            HandModel(replace(self.cfg, palm_grid_mm=1000))

    def test_fret_geometry(self):
        self.assertAlmostEqual(fret_x_mm(12), 647.7 / 2)
        low = physical_fret_span_mm(1, 6, self.cfg)
        high = physical_fret_span_mm(15, 20, self.cfg)
        self.assertGreater(low, 2 * high)
        self.assertAlmostEqual(physical_fret_span_mm(12, 17, self.cfg), 81.2, delta=.15)
        self.assertEqual(stretch_cost(low, self.cfg), math.inf)
        self.assertTrue(math.isfinite(stretch_cost(high, self.cfg)))

    def test_continuity_monotonicity_cutoff(self):
        c = self.cfg.comfortable_span_mm
        self.assertAlmostEqual(stretch_cost(c - 1e-8, self.cfg), stretch_cost(c + 1e-8, self.cfg))
        costs = [stretch_cost(i / 10, self.cfg) for i in range(851)]
        self.assertEqual(costs, sorted(costs))
        self.assertTrue(math.isfinite(stretch_cost(85, self.cfg)))
        self.assertEqual(stretch_cost(85.0001, self.cfg), math.inf)

    def test_string_symmetry_and_span_modifier(self):
        a, b, c = Position(2, 12), Position(1, 12), Position(3, 12)
        self.assertEqual(string_transition_cost(a, b, self.cfg), string_transition_cost(a, c, self.cfg))
        narrow = State(a, 365, 12, 17, 1, 2)
        wide = replace(narrow, low_string=1, high_string=6)
        self.assertGreater(state_cost(wide, self.cfg), state_cost(narrow, self.cfg))

    def test_micro_shifts_cannot_discount_motion(self):
        points = [150, 155, 160, 165, 170]
        small = sum(reposition_cost(a, b, self.cfg) for a, b in zip(points, points[1:]))
        self.assertGreaterEqual(small, reposition_cost(points[0], points[-1], self.cfg))
        self.assertEqual(reposition_cost(150, 150, self.cfg), 0)

    def test_hand_not_first_note_or_lowest_fret(self):
        model = HandModel(self.cfg)
        for frets in ([12, 10, 14, 11], [14, 12, 10], [12, 15, 17]):
            centre = (model.x[min(frets)] + model.x[max(frets)]) / 2
            grid_centre = min(model.grid, key=lambda c: abs(c - centre))
            state = model.reset(Position(1, frets[0]), grid_centre)
            for fret in frets[1:]:
                state = model.stay(state, Position(1, fret))
                self.assertIsNotNone(state)
            self.assertEqual((state.low_fret, state.high_fret), (min(frets), max(frets)))
            notes, constraints = pinned(frets)
            result = solve_hand(notes, self.cfg, constraints)
            self.assertEqual(len({s.palm_ref_mm for s in result.path}), 1)

    def test_hard_cutoff_forces_reposition(self):
        notes, constraints = pinned([1, 6])
        result = solve_hand(notes, self.cfg, constraints)
        self.assertNotEqual(result.path[0].palm_ref_mm, result.path[1].palm_ref_mm)
        self.assertGreater(diagnostics(result, self.cfg)[1]["costs"]["reposition"], 0)

    def test_open_string_has_no_discount(self):
        notes, constraints = pinned([12, 0, 12])
        result = solve_hand(notes, self.cfg, constraints)
        rows = diagnostics(result, self.cfg)
        self.assertGreater(rows[1]["costs"]["reposition"], 0)
        self.assertGreater(rows[2]["costs"]["reposition"], 0)

    def test_diagnostics_reconcile_and_paths_play_notes(self):
        notes = [64, 66, 69, 67]
        result = solve_hand(notes)
        rows = diagnostics(result, self.cfg)
        self.assertAlmostEqual(sum(r["step_cost"] for r in rows), result.cost)
        self.assertAlmostEqual(rows[-1]["cumulative_cost"], result.cost)
        self.assertEqual([s.played.midi for s in result.path], notes)

    def test_baseline_dp_equals_product_oracle(self):
        rng = random.Random(18)
        for _ in range(20):
            notes = [rng.randrange(40, 89) for _ in range(rng.randrange(3, 7))]
            for model in ("M0", "M1"):
                self.assertAlmostEqual(solve_baseline(notes, model).cost,
                                       solve_baseline(notes, model, brute=True).cost)

    def test_hand_dp_equals_exhaustive_state_paths(self):
        # Small configurable grid bounds the exhaustive oracle, not the DP result.
        cfg = replace(self.cfg, palm_grid_mm=40)
        rng = random.Random(9)
        for _ in range(12):
            notes = [rng.randrange(58, 89) for _ in range(3)]
            self.assertAlmostEqual(solve_hand(notes, cfg).cost, brute_force_hand(notes, cfg).cost)
        for frets in ([12, 15, 17, 12], [10, 14, 11, 10, 12, 13]):
            notes, constraints = pinned(frets)
            self.assertAlmostEqual(solve_hand(notes, cfg, constraints).cost,
                                   brute_force_hand(notes, cfg, constraints).cost)

    def test_oracle_default_grid(self):
        notes, constraints = pinned([12, 15, 17])
        self.assertAlmostEqual(solve_hand(notes, self.cfg, constraints).cost,
                               brute_force_hand(notes, self.cfg, constraints).cost)

    def test_greedy_failure_with_same_initial_state(self):
        cfg = replace(self.cfg, palm_grid_mm=50)
        notes, constraints = pinned([0, 2, 4], string=6)
        greedy, dp = solve_greedy(notes, cfg, constraints), solve_hand(notes, cfg, constraints)
        self.assertEqual(greedy.path[0], dp.path[0])
        self.assertGreater(greedy.cost, dp.cost)
        self.assertGreater(dp.path[1].palm_ref_mm, greedy.path[1].palm_ref_mm)

    def test_limits_fail_explicitly(self):
        with self.assertRaises(RuntimeError):
            brute_force_hand([60, 62], max_visits=1)
        with self.assertRaises(RuntimeError):
            solve_baseline([60, 62], brute=True, max_paths=1)
        with self.assertRaises(RuntimeError):
            solve_hand([60, 62], max_states=1)


if __name__ == "__main__":
    unittest.main()
