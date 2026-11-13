"""Calculate anchored scores and NA bounds. Does not assess evidence or feasibility."""

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path


def check(ok, message):
    if not ok:
        raise ValueError(message)


def calculate(data):
    check(isinstance(data, dict), "Input must be an object.")
    groups = data.get("groups")
    check(isinstance(groups, dict) and groups, "groups must be a nonempty object.")
    all_keys, weights = [], {}
    for name, group in groups.items():
        check(isinstance(group, dict), f"Invalid group {name}")
        keys, weight = group.get("criteria"), group.get("weight")
        check(isinstance(keys, list) and keys and
              all(isinstance(k, str) and k.strip() for k in keys), f"Invalid criteria in {name}")
        check(type(weight) in (int, float) and math.isfinite(weight) and weight >= 0,
              f"Invalid weight in {name}")
        all_keys.extend(keys)
        weights[name] = Fraction(str(weight))
    check(len(all_keys) == len(set(all_keys)), "Criteria must be unique across groups.")
    check(sum(weights.values()) == 100, "Weights must sum to 100.")
    candidates = data.get("candidates")
    check(isinstance(candidates, list) and candidates, "candidates must be nonempty.")
    rows, complete, ids = [], [], set()
    for candidate in candidates:
        check(isinstance(candidate, dict), "Each candidate must be an object.")
        identifier = candidate.get("id")
        check(isinstance(identifier, str) and identifier.strip() and identifier not in ids,
              "Candidate ids must be nonempty and unique.")
        ids.add(identifier)
        scope = candidate.get("scope")
        check(isinstance(scope, str) and scope.strip(), f"Missing scope for {identifier}")
        scores = candidate.get("scores")
        check(isinstance(scores, dict) and set(scores) == set(all_keys),
              f"Specify every criterion for {identifier}; null means unknown.")
        for key, value in scores.items():
            check(value is None or (type(value) is int and 0 <= value <= 4),
                  f"Rating {identifier}/{key} must be integer 0..4 or null.")
        lower, upper = Fraction(0), Fraction(0)
        blocks, missing = {}, []
        for name, group in groups.items():
            absent = [k for k in group["criteria"] if scores[k] is None]
            known = sum(scores[k] for k in group["criteria"] if scores[k] is not None)
            maximum = 4 * len(group["criteria"])
            lower += weights[name] * known / maximum
            upper += weights[name] * (known + 4 * len(absent)) / maximum
            blocks[name] = {"sum": None if absent else known, "known_sum": known,
                            "maximum": maximum, "missing": absent}
            missing.extend(absent)
        rows.append({"id": identifier, "scope": scope, "groups": blocks,
                     "score": None if missing else round(float(lower), 1),
                     "unknown_bounds": [round(float(lower), 1), round(float(upper), 1)],
                     "missing": missing, "rank_among_complete_only": None})
        if not missing:
            complete.append((lower, len(rows) - 1))
    previous, rank = None, None
    for position, (score, index) in enumerate(sorted(complete, key=lambda v: v[0], reverse=True), 1):
        if score != previous:
            rank = position
        rows[index]["rank_among_complete_only"] = rank
        previous = score
    return {"note": "Weights express preferences. Bounds are mathematical, not confidence intervals. "
                    "Incomplete candidates are excluded from ranking, not judged inferior.",
            "weights": {key: float(value) for key, value in weights.items()}, "candidates": rows}


def example():
    groups = {name: {"weight": weight, "criteria": [f"{name}{i}" for i in range(1, count + 1)]}
              for name, weight, count in [("A", 35, 4), ("T", 45, 4), ("R", 20, 3)]}
    return {"note": "Illustrative weights and ratings only; replace after defining scope and anchors.",
            "groups": groups, "candidates": [{"id": "example", "scope": "frozen-core-v1",
            "scores": {key: (None if key == "R3" else 2)
                       for group in groups.values() for key in group["criteria"]}}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path)
    parser.add_argument("--example", action="store_true", help="Print illustrative input JSON.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.example and args.input:
        parser.error("Use --example without an input file.")
    if not args.example and not args.input:
        parser.error("Provide input.json or --example.")
    try:
        result = example() if args.example else calculate(json.loads(args.input.read_text(encoding="utf-8-sig")))
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            check(not args.input or args.output.resolve() != args.input.resolve(), "Output cannot replace input.")
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
