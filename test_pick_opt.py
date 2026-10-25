import math
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_opt as p


def dp_oracle(tab, profile, sweep, first=None):
    scores = {}
    for stroke in ['D', 'U']:
        if first is None or first == stroke:
            scores[stroke] = 0.0
    for i in range(1, len(tab)):
        next_scores = {}
        for new in ['D', 'U']:
            best = math.inf
            for old, old_cost in scores.items():
                step, _ = p.picking_step(tab[i-1][0], tab[i][0], old, new, profile, sweep)
                best = min(best, old_cost + step)
            next_scores[new] = best
        scores = next_scores
    return min(scores.values())


class PickingChecks(unittest.TestCase):
    def test_same_string_alternates(self):
        self.assertEqual(p.picking_step(3, 3, 'D', 'U', 'USX', False)[0], 0)
        self.assertEqual(p.picking_step(3, 3, 'D', 'D', 'USX', True)[0], math.inf)

    def test_escape_uses_departing_stroke(self):
        self.assertEqual(p.picking_step(3, 2, 'U', 'D', 'USX', False)[0], .25)
        self.assertEqual(p.picking_step(3, 2, 'D', 'U', 'USX', False)[0], 5.25)
        self.assertEqual(p.picking_step(3, 2, 'D', 'U', 'DSX', False)[0], .25)

    def test_double_escape_and_skip(self):
        self.assertEqual(p.picking_step(4, 2, 'D', 'U', 'DBX', False)[0], .5)
        self.assertEqual(p.picking_step(4, 2, 'U', 'D', 'DBX', False)[0], .5)

    def test_sweep_direction(self):
        self.assertAlmostEqual(p.picking_step(4, 3, 'D', 'D', 'USX', True)[0], .85)
        self.assertAlmostEqual(p.picking_step(3, 4, 'U', 'U', 'DSX', True)[0], .85)
        for s1, s2, stroke in [(3, 4, 'D'), (4, 3, 'U'), (4, 2, 'D')]:
            self.assertEqual(p.picking_step(s1, s2, stroke, stroke, 'USX', True)[0], math.inf)
        self.assertEqual(p.picking_step(4, 3, 'D', 'D', 'USX', False)[0], math.inf)

    def test_start_direction_depends_on_profile(self):
        tab = [[3, 5], [3, 7], [2, 5], [2, 6]]
        self.assertEqual(p.best_picking(tab, 'USX', False)[0], ('D', 'U', 'D', 'U'))
        self.assertEqual(p.best_picking(tab, 'DSX', False)[0], ('U', 'D', 'U', 'D'))
        self.assertEqual(p.best_picking(tab, 'USX', False, 'U')[0][0], 'U')

    def test_single_note_has_no_transition_cost(self):
        self.assertEqual(p.best_picking([[1, 5]], 'USX', False), (('D',), 0))

    def test_same_melody_and_real_left_model(self):
        self.assertEqual(p.melody_of(p.layouts[0]), p.melody_of(p.layouts[1]))
        self.assertAlmostEqual(p.left_hand_cost(p.layouts[0]), 2.791051435391099, places=5)
        self.assertAlmostEqual(p.left_hand_cost(p.layouts[1]), 6.145091, places=5)

    def test_counterexample_and_modes(self):
        rows, left, joint = p.compare_layouts(p.layouts, 'USX', False, 1)
        self.assertEqual((left, joint), (0, 1))
        self.assertEqual([r[3] for r in rows], [5.5, .75])
        self.assertEqual(p.compare_layouts(p.layouts, 'USX', True, 1)[2], 0)
        self.assertEqual(p.compare_layouts(p.layouts, 'DBX', False, 1)[2], 0)
        self.assertEqual(p.compare_layouts(p.layouts, 'USX', False, 0)[2], 0)

    def test_invalid_inputs_fail(self):
        cases = [([], 'USX', False, 1), (p.layouts, 'other', False, 1),
                 (p.layouts, 'USX', False, -1), (p.layouts, 'USX', False, math.nan),
                 ([[[7, 1]]], 'USX', False, 1), ([[], []], 'USX', False, 1),
                 ([[[1, 1]], [[1, 2]]], 'USX', False, 1)]
        for args in cases:
            with self.assertRaises(ValueError):
                p.compare_layouts(*args)
        with self.assertRaises(ValueError):
            p.best_picking([[1, 0]]*17, 'USX', False)

    def test_search_against_different_dp_algorithm(self):
        rng = random.Random(20260921)
        checks = 0
        for length in range(1, 9):
            for repeat in range(10):
                tab = [[rng.randint(1, 6), 5] for _ in range(length)]
                for profile in ['USX', 'DSX', 'DBX']:
                    for sweep in [False, True]:
                        for first in [None, 'D', 'U']:
                            strokes, score = p.best_picking(tab, profile, sweep, first)
                            self.assertAlmostEqual(score, dp_oracle(tab, profile, sweep, first))
                            self.assertAlmostEqual(score, p.picking_cost(tab, strokes, profile, sweep))
                            if first:
                                self.assertEqual(strokes[0], first)
                            checks += 1
        self.assertEqual(checks, 1440)


if __name__ == '__main__':
    unittest.main(verbosity=2)
