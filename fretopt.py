"""FretOpt v0.1: exact search over an explicitly approximate hand model.

MODEL ASSUMPTIONS and limits are documented in README.md. Standard library only.
"""
from dataclasses import asdict, dataclass, fields
from itertools import product
import math

OPEN_STRINGS = (64, 59, 55, 50, 45, 40)


@dataclass(frozen=True)
class CostConfig:
    scale_length_mm: float = 647.7
    string_spacing_mm: float = 7.0
    comfortable_span_mm: float = 55.0
    hard_stretch_mm: float = 85.0
    palm_grid_mm: float = 5.0
    comfortable_cost: float = 0.03
    extended_weight: float = 0.8
    comfortable_power: float = 2.0
    extended_power: float = 2.0
    adjacent_string_cost: float = 0.02
    multi_string_base_cost: float = 0.06
    multi_string_slope: float = 0.02
    string_span_modifier: float = 0.15
    reposition_base_cost: float = 1.5
    reposition_distance_weight: float = 0.01
    note_distance_weight: float = 0.005

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field.name} must be numeric")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{field.name} must be finite and nonnegative")
        if not 0 < self.comfortable_span_mm < self.hard_stretch_mm:
            raise ValueError("Require 0 < comfortable_span_mm < hard_stretch_mm")
        for name in ("scale_length_mm", "string_spacing_mm", "palm_grid_mm",
                     "comfortable_power", "extended_power"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.multi_string_base_cost < self.adjacent_string_cost:
            raise ValueError("multi_string_base_cost must be >= adjacent_string_cost")


@dataclass(frozen=True, order=True)
class Position:
    string: int
    fret: int

    def __post_init__(self):
        if type(self.string) is not int or type(self.fret) is not int:
            raise ValueError("string and fret must be integers")
        if not 1 <= self.string <= 6 or not 0 <= self.fret <= 24:
            raise ValueError("Require string 1..6 and fret 0..24")

    @property
    def midi(self) -> int:
        return OPEN_STRINGS[self.string - 1] + self.fret


@dataclass(frozen=True, order=True)
class State:
    played: Position
    palm_ref_mm: float
    low_fret: int
    high_fret: int
    low_string: int
    high_string: int


@dataclass(frozen=True)
class Costs:
    stretch: float = 0.0
    string: float = 0.0
    reposition: float = 0.0
    note_movement: float = 0.0

    @property
    def total(self) -> float:
        return self.stretch + self.string + self.reposition + self.note_movement


@dataclass(frozen=True)
class Result:
    model: str
    path: tuple
    cost: float
    layer_sizes: tuple[int, ...] = ()


def fret_x_mm(fret: float, scale_length_mm: float = 647.7) -> float:
    return scale_length_mm * (1 - 2 ** (-fret / 12))


def physical_fret_span_mm(a: int, b: int, cfg: CostConfig) -> float:
    return abs(fret_x_mm(b, cfg.scale_length_mm) - fret_x_mm(a, cfg.scale_length_mm))


def find_note_positions(note: int) -> tuple[Position, ...]:
    if type(note) is not int or not 40 <= note <= 88:
        raise ValueError(f"MIDI note must be an integer in 40..88: {note!r}")
    return tuple(Position(s, note - pitch) for s, pitch in enumerate(OPEN_STRINGS, 1)
                 if 0 <= note - pitch <= 24)


def position_layers(notes, constraints=None) -> tuple:
    """Optional layer constraints pin realizations, for isolated experiments."""
    notes = tuple(notes)
    if not notes:
        raise ValueError("Supply at least one MIDI note")
    layers = tuple(find_note_positions(n) for n in notes)
    if constraints is None:
        return layers
    if len(constraints) != len(notes):
        raise ValueError("One constraint layer is required per note")
    result = []
    for legal, allowed in zip(layers, constraints):
        chosen = tuple(sorted(set(allowed)))
        if not chosen or any(p not in legal for p in chosen):
            raise ValueError("Constraint has an empty layer or wrong-pitch position")
        result.append(chosen)
    return tuple(result)


def stretch_cost(span_mm: float, cfg: CostConfig) -> float:
    if span_mm > cfg.hard_stretch_mm + 1e-9:
        return math.inf
    if span_mm <= cfg.comfortable_span_mm:
        return cfg.comfortable_cost * (span_mm / cfg.comfortable_span_mm) ** cfg.comfortable_power
    t = (span_mm - cfg.comfortable_span_mm) / (cfg.hard_stretch_mm - cfg.comfortable_span_mm)
    return cfg.comfortable_cost + cfg.extended_weight * t ** cfg.extended_power


def string_transition_cost(a: Position, b: Position, cfg: CostConfig) -> float:
    delta = abs(a.string - b.string)
    if delta == 0:
        return 0.0
    if delta == 1:
        return cfg.adjacent_string_cost
    return cfg.multi_string_base_cost + cfg.multi_string_slope * (delta - 2)


def reposition_cost(old_mm: float, new_mm: float, cfg: CostConfig) -> float:
    distance = abs(new_mm - old_mm)
    return 0.0 if distance == 0 else cfg.reposition_base_cost + cfg.reposition_distance_weight * distance


def state_cost(state: State, cfg: CostConfig) -> float:
    span = physical_fret_span_mm(state.low_fret, state.high_fret, cfg)
    modifier = 1 + cfg.string_span_modifier * max(0, state.high_string - state.low_string - 1)
    return stretch_cost(span, cfg) * modifier


def transition_cost(old: State | None, new: State, cfg: CostConfig) -> Costs:
    if old is None:
        return Costs(stretch=state_cost(new, cfg))
    return Costs(
        stretch=state_cost(new, cfg),
        string=string_transition_cost(old.played, new.played, cfg),
        reposition=reposition_cost(old.palm_ref_mm, new.palm_ref_mm, cfg),
        note_movement=cfg.note_distance_weight * physical_fret_span_mm(old.played.fret, new.played.fret, cfg),
    )


class HandModel:
    """A segment keeps its palm reference; a paid shift resets segment history.

    MODEL ASSUMPTION: symmetric reach hard_stretch/2 around a grid coordinate.
    Required bounds describe notes already used in this segment, not capacity.
    """
    def __init__(self, cfg: CostConfig):
        self.cfg = cfg
        self.x = tuple(fret_x_mm(f, cfg.scale_length_mm) for f in range(25))
        end = self.x[-1]
        grid = tuple(i * cfg.palm_grid_mm for i in range(math.floor(end / cfg.palm_grid_mm) + 1))
        self.grid = tuple(sorted(set((*grid, end))))
        self.centres = tuple(tuple(c for c in self.grid if abs(x - c) <= cfg.hard_stretch_mm / 2 + 1e-9)
                             for x in self.x)
        if any(not centres for centres in self.centres):
            raise ValueError("Palm grid is too coarse: some frets have no reachable centre")

    def reset(self, position: Position, centre: float) -> State:
        return State(position, centre, position.fret, position.fret, position.string, position.string)

    def initial(self, position: Position) -> tuple[State, ...]:
        return tuple(self.reset(position, c) for c in self.centres[position.fret])

    def stay(self, old: State, position: Position) -> State | None:
        if abs(self.x[position.fret] - old.palm_ref_mm) > self.cfg.hard_stretch_mm / 2 + 1e-9:
            return None
        low, high = min(old.low_fret, position.fret), max(old.high_fret, position.fret)
        if self.x[high] - self.x[low] > self.cfg.hard_stretch_mm + 1e-9:
            return None
        return State(position, old.palm_ref_mm, low, high,
                     min(old.low_string, position.string), max(old.high_string, position.string))

    def successors(self, old: State, position: Position):
        kept = self.stay(old, position)
        if kept is not None:
            yield kept
        for c in self.centres[position.fret]:
            if c != old.palm_ref_mm:
                yield self.reset(position, c)


def _trace(last, parents) -> tuple:
    path = []
    for layer in reversed(parents):
        path.append(last)
        last = layer[last]
    return tuple(reversed(path))


def solve_hand(notes, cfg: CostConfig = CostConfig(), constraints=None, *, max_states=200_000) -> Result:
    """Exact layered DP; the resource limit raises, never silently beam-prunes."""
    layers, model = position_layers(notes, constraints), HandModel(cfg)
    scores = {s: transition_cost(None, s, cfg).total for p in layers[0] for s in model.initial(p)}
    if type(max_states) is not int or max_states < len(scores):
        raise RuntimeError("State limit exceeded at initial layer")
    parents = [{s: None for s in scores}]
    sizes = [len(scores)]
    for positions in layers[1:]:
        next_scores, parent = {}, {}

        def relax(old, new):
            value = scores[old] + transition_cost(old, new, cfg).total
            if value < next_scores.get(new, math.inf):
                next_scores[new], parent[new] = value, old

        # Staying preserves every history variable, so no history may be dropped.
        # A shift resets bounds: only old played position and palm affect its cost.
        shift_sources = {}
        for old, value in scores.items():
            for p in positions:
                kept = model.stay(old, p)
                if kept is not None:
                    relax(old, kept)
            key = (old.played, old.palm_ref_mm)
            previous = shift_sources.get(key)
            if previous is None or value < scores[previous]:
                shift_sources[key] = old
        for old in shift_sources.values():
            for p in positions:
                for centre in model.centres[p.fret]:
                    if centre != old.palm_ref_mm:
                        relax(old, model.reset(p, centre))
        if not next_scores:
            raise ValueError("No feasible state path")
        if len(next_scores) > max_states:
            raise RuntimeError("State limit exceeded; shorten melody or change grid explicitly")
        scores = next_scores
        parents.append(parent)
        sizes.append(len(scores))
    last = min(scores, key=scores.get)
    return Result("M3 hand DP", _trace(last, parents), scores[last], tuple(sizes))


def solve_greedy(notes, cfg: CostConfig = CostConfig(), constraints=None) -> Result:
    """M2: same costs, immediate decisions. Initial tie = lowest string/centre."""
    layers, model = position_layers(notes, constraints), HandModel(cfg)
    old, path, total = None, [], 0.0
    for positions in layers:
        candidates = [s for p in positions for s in (model.initial(p) if old is None else model.successors(old, p))]
        new = min(candidates, key=lambda s: (transition_cost(old, s, cfg).total, s))
        total += transition_cost(old, new, cfg).total
        path.append(new)
        old = new
    return Result("M2 hand greedy", tuple(path), total)


def brute_force_hand(notes, cfg: CostConfig = CostConfig(), constraints=None, *, max_visits=2_000_000) -> Result:
    """Enumerate state paths without DP merging; fail explicitly at visit budget."""
    layers, model = position_layers(notes, constraints), HandModel(cfg)
    best_cost, best_path, visits = math.inf, (), 0

    def visit(i, old, path, total):
        nonlocal best_cost, best_path, visits
        visits += 1
        if visits > max_visits:
            raise RuntimeError("Brute-force visit limit exceeded")
        if i == len(layers):
            if total < best_cost:
                best_cost, best_path = total, path
            return
        for p in layers[i]:
            states = model.initial(p) if old is None else model.successors(old, p)
            for new in states:
                visit(i + 1, new, path + (new,), total + transition_cost(old, new, cfg).total)

    visit(0, None, (), 0.0)
    return Result("hand brute force", best_path, best_cost)


def baseline_edge(a: Position, b: Position, model: str, cfg: CostConfig) -> float:
    if model == "M0":
        return abs(a.fret - b.fret) + abs(a.string - b.string)
    if model == "M1":
        return math.hypot(physical_fret_span_mm(a.fret, b.fret, cfg),
                          (a.string - b.string) * cfg.string_spacing_mm)
    raise ValueError("Baseline model must be M0 or M1")


def solve_baseline(notes, model="M0", cfg: CostConfig = CostConfig(), constraints=None, *, brute=False, max_paths=2_000_000) -> Result:
    layers = position_layers(notes, constraints)
    if model not in ("M0", "M1"):
        raise ValueError("Baseline model must be M0 or M1")
    if brute:
        if math.prod(map(len, layers)) > max_paths:
            raise RuntimeError("Position brute-force path limit exceeded")
        path = min(product(*layers), key=lambda ps: sum(baseline_edge(a, b, model, cfg) for a, b in zip(ps, ps[1:])))
        return Result(model, path, sum(baseline_edge(a, b, model, cfg) for a, b in zip(path, path[1:])))
    scores = {p: 0.0 for p in layers[0]}
    parents = [{p: None for p in scores}]
    for layer in layers[1:]:
        parent = {p: min(scores, key=lambda q: scores[q] + baseline_edge(q, p, model, cfg)) for p in layer}
        scores = {p: scores[parent[p]] + baseline_edge(parent[p], p, model, cfg) for p in layer}
        parents.append(parent)
    last = min(scores, key=scores.get)
    return Result(model, _trace(last, parents), scores[last], tuple(map(len, layers)))


def diagnostics(result: Result, cfg: CostConfig) -> list[dict]:
    rows, old, cumulative = [], None, 0.0
    for i, new in enumerate(result.path):
        costs = transition_cost(old, new, cfg)
        cumulative += costs.total
        rows.append(dict(index=i, midi=new.played.midi, position=asdict(new.played),
                         old_hand=asdict(old) if old else None, new_hand=asdict(new),
                         fret_distance_mm=physical_fret_span_mm(old.played.fret, new.played.fret, cfg) if old else 0,
                         string_delta=abs(old.played.string - new.played.string) if old else 0,
                         required_span_mm=physical_fret_span_mm(new.low_fret, new.high_fret, cfg),
                         palm_displacement_mm=abs(old.palm_ref_mm - new.palm_ref_mm) if old else 0,
                         costs=asdict(costs), step_cost=costs.total, cumulative_cost=cumulative))
        old = new
    return rows
