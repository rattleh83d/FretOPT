"""CLI: python3 run.py 64 66 69 67 --model all --json result.json"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from fretopt import CostConfig, Position, diagnostics, solve_baseline, solve_greedy, solve_hand


def render(result, cfg):
    path = [s.played if hasattr(s, "played") else s for s in result.path]
    lines = [f"{result.model}: {result.cost:.6f}",
             " → ".join(f"s{p.string}f{p.fret}" for p in path)]
    if result.model.startswith(("M2", "M3")):
        lines.append("i MIDI str/fret palm_mm span_frets span_mm Δpalm stretch string repos note cumulative")
        for row in diagnostics(result, cfg):
            s, c = row["new_hand"], row["costs"]
            lines.append(f'{row["index"]:2} {row["midi"]:3} '
                         f'{s["played"]["string"]}/{s["played"]["fret"]:<2} '
                         f'{s["palm_ref_mm"]:7.1f} {s["low_fret"]:2}–{s["high_fret"]:<2} '
                         f'{row["required_span_mm"]:7.2f} {row["palm_displacement_mm"]:6.1f} '
                         f'{c["stretch"]:.4f} {c["string"]:.4f} {c["reposition"]:.4f} '
                         f'{c["note_movement"]:.4f} {row["cumulative_cost"]:.4f}')
    return "\n".join(lines)


def serialize(result, cfg):
    payload = asdict(result)
    if result.model.startswith(("M2", "M3")):
        payload["diagnostics"] = diagnostics(result, cfg)
    else:
        from fretopt import baseline_edge
        total, rows = 0.0, []
        for i, p in enumerate(result.path):
            step = baseline_edge(result.path[i - 1], p, result.model, cfg) if i else 0.0
            total += step
            rows.append(dict(index=i, midi=p.midi, position=asdict(p), step_cost=step, cumulative_cost=total))
        payload["diagnostics"] = rows
    return payload


def main():
    parser = argparse.ArgumentParser(description="FretOpt v0.1 research prototype (MIDI pitch list, no .mid parser)")
    parser.add_argument("notes", nargs="+", type=int)
    parser.add_argument("--model", choices=("M0", "M1", "M2", "M3", "all"), default="all")
    parser.add_argument("--config", type=Path, help="JSON object overriding CostConfig defaults")
    parser.add_argument("--json", type=Path, help="Save full config, paths and transition diagnostics")
    parser.add_argument("--positions", nargs="+", help="Pin each note as string:fret, e.g. 1:12 1:15 1:17")
    args = parser.parse_args()
    try:
        cfg = CostConfig(**(json.loads(args.config.read_text()) if args.config else {}))
        constraints = [(Position(*map(int, p.split(":"))),) for p in args.positions] if args.positions else None
        results = []
        for name in (("M0", "M1", "M2", "M3") if args.model == "all" else (args.model,)):
            result = (solve_baseline(args.notes, name, cfg, constraints) if name in ("M0", "M1")
                      else solve_greedy(args.notes, cfg, constraints) if name == "M2"
                      else solve_hand(args.notes, cfg, constraints))
            results.append(result)
        print("Scores use different units across baselines; compare paths, not raw M0/M1/M3 numbers.\n")
        print("\n\n".join(render(result, cfg) for result in results))
        if args.json:
            args.json.write_text(json.dumps(dict(notes=args.notes, config=asdict(cfg),
                                                results=[serialize(r, cfg) for r in results]), indent=2) + "\n")
    except (ValueError, TypeError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
