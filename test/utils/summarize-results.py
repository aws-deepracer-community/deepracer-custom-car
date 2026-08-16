#!/usr/bin/env python3
"""summarize-results.py  —  pretty-print a DeepRacer equivalency test result file.

Usage:
    python3 summarize-results.py results-<timestamp>.json [--no-frames] [--csv]
"""

import argparse
import json
import os
import shutil
import statistics
import sys


# ── ANSI colours (disabled automatically when not a tty) ─────────────────────
def _ansi(code: str) -> str:
    return code if sys.stdout.isatty() else ""


RESET  = _ansi("\033[0m")
BOLD   = _ansi("\033[1m")
GREEN  = _ansi("\033[32m")
RED    = _ansi("\033[31m")
YELLOW = _ansi("\033[33m")
CYAN   = _ansi("\033[36m")
DIM    = _ansi("\033[2m")

ENGINES = ["tflite", "ov", "tf"]
ENGINE_LABELS = {"tflite": "TFLite", "ov": "OpenVINO", "tf": "TF (native)"}


# ── helpers ───────────────────────────────────────────────────────────────────

def ms(ns: int) -> float:
    return ns / 1_000_000.0


def bar(value: float, max_value: float, width: int = 20) -> str:
    filled = int(round(value / max_value * width)) if max_value > 0 else 0
    return "█" * filled + "░" * (width - filled)


def action_label(action_space: list, idx) -> str:
    """Return a short human-readable label for an action index."""
    try:
        a = action_space[int(idx)]
        return f"{a['steering_angle']:+.1f}° {a['speed']:.1f}m/s"
    except (IndexError, KeyError, TypeError, ValueError):
        return f"#{idx}"


def _stats(values: list) -> dict:
    if not values:
        return {"min": 0, "max": 0, "mean": 0, "median": 0, "stdev": 0}
    return {
        "min":    min(values),
        "max":    max(values),
        "mean":   statistics.mean(values),
        "median": statistics.median(values),
        "stdev":  statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def hline(width: int = 0, char: str = "─") -> str:
    w = width or shutil.get_terminal_size((120, 40)).columns
    return char * w


# ── main sections ─────────────────────────────────────────────────────────────

def print_header(data: dict) -> None:
    W = shutil.get_terminal_size((120, 40)).columns
    print()
    print(BOLD + "═" * W + RESET)
    print(BOLD + f"  DeepRacer Model Equivalency Report" + RESET)
    print(BOLD + "═" * W + RESET)
    print(f"  Model : {data.get('model', 'n/a')}")
    meta = data.get("model_metadata", {})
    print(f"  Sensor: {', '.join(meta.get('sensor', ['?']))}")
    print(f"  Algo  : {meta.get('training_algorithm', '?')}")
    print(f"  NN    : {meta.get('neural_network', '?')}")
    print(f"  Actions in space: {len(meta.get('action_space', []))}")
    print()


def print_summary(data: dict) -> None:
    s = data.get("summary", {})
    total = s.get("match", 0) + s.get("mismatch", 0)
    match_pct = (s["match"] / total * 100) if total > 0 else 0.0

    colour = GREEN if match_pct == 100 else (YELLOW if match_pct >= 80 else RED)

    print(BOLD + "  SUMMARY" + RESET)
    print(hline())
    for eng in ENGINES:
        count = s.get(eng, "—")
        print(f"  {ENGINE_LABELS[eng]:<14} frames received : {count}")
    print()
    print(f"  Total frames evaluated : {total}")
    print(f"  {'All-engine agreement':22}: "
          + colour + BOLD + f"{s.get('match', 0)}/{total}  ({match_pct:.1f}%)" + RESET)
    print(f"  {'Disagreements':22}: {RED}{s.get('mismatch', 0)}{RESET}")
    print()


def print_latency(frames: dict) -> None:
    latencies: dict[str, list[float]] = {e: [] for e in ENGINES}

    for frame in frames.values():
        for eng in ENGINES:
            d = frame.get(eng, {}).get("time", {}).get("diff")
            if d is not None and d > 0:
                latencies[eng].append(ms(d))

    print(BOLD + "  LATENCY / INFERENCE TIME" + RESET)
    print(hline())

    col = 10
    header = (f"  {'Engine':<14}  {'Samples':>{col}}  {'Min ms':>{col}}"
              f"  {'Mean ms':>{col}}  {'Median ms':>{col}}"
              f"  {'Max ms':>{col}}  {'Stdev ms':>{col}}")
    print(DIM + header + RESET)
    print(DIM + hline() + RESET)

    max_mean = max((statistics.mean(v) for v in latencies.values() if v), default=1)

    for eng in ENGINES:
        vals = latencies[eng]
        if not vals:
            print(f"  {ENGINE_LABELS[eng]:<14}  {'—':>{col}}  {'—':>{col}}"
                  f"  {'—':>{col}}  {'—':>{col}}  {'—':>{col}}  {'—':>{col}}")
            continue
        st = _stats(vals)
        sparkbar = bar(st["mean"], max_mean, 18)
        print(f"  {ENGINE_LABELS[eng]:<14}  {len(vals):>{col}}  {st['min']:>{col}.1f}"
              f"  {st['mean']:>{col}.1f}  {st['median']:>{col}.1f}"
              f"  {st['max']:>{col}.1f}  {st['stdev']:>{col}.1f}  {DIM}{sparkbar}{RESET}")
    print()


def print_frames(frames: dict, action_space: list) -> None:
    print(BOLD + "  PER-FRAME RESULTS" + RESET)
    print(hline())

    # Column widths
    file_w = max((len(os.path.basename(f.get("filename", ""))) for f in frames.values()), default=8)
    file_w = max(file_w, 8)

    act_w  = 3   # minimum 3 so "Act" header fits without overflowing the column
    prob_w = 9
    ms_w   = 7
    idx_w  = 4

    # Two-row spanning header so engine labels don't overflow narrow act column
    # Row 1: engine names centred over their (act + prob + ms) block
    # Row 2: sub-column labels
    block_w  = 2 + act_w + 2 + prob_w + 2 + ms_w   # width of one engine's full block incl. leading sep
    prefix1  = f"  {'':>{idx_w}}  {'':>{file_w}}"   # blank prefix for engine-name row
    prefix2  = f"  {'#':>{idx_w}}  {'File':<{file_w}}"  # labelled prefix for sub-column row
    eng_row1 = "".join(f"{ENGINE_LABELS[e]:^{block_w}}" for e in ENGINES)
    eng_row2 = "".join(f"  {'Act':>{act_w}}  {'Prob':>{prob_w}}  {'ms':>{ms_w}}" for e in ENGINES)
    agree_hdr = f"  {'Agree':>5}"
    print(DIM + prefix1 + eng_row1 + agree_hdr + RESET)
    print(DIM + prefix2 + eng_row2 + agree_hdr + RESET)
    print(DIM + hline() + RESET)

    for idx, (ts, frame) in enumerate(sorted(frames.items()), start=1):
        fname = os.path.basename(frame.get("filename", ""))
        best  = frame.get("summary", {}).get("best", {})

        best_actions = [best.get(e, {}).get("action") for e in ENGINES if e in best]
        valid  = [a for a in best_actions if a is not None and a != -1]
        agree  = len(set(valid)) <= 1 and len(valid) > 0
        colour = GREEN if agree else RED
        agree_mark = (GREEN + "✓" + RESET) if agree else (RED + "✗" + RESET)

        row = f"  {idx:>{idx_w}}  {fname:<{file_w}}"
        for eng in ENGINES:
            eng_best  = best.get(eng, {})
            act       = eng_best.get("action", None)
            prob      = eng_best.get("value",  None)
            diff_ns   = frame.get(eng, {}).get("time", {}).get("diff", 0) or 0
            act_str   = str(act) if act is not None and act != -1 else "—"
            prob_str  = f"{prob:.5f}" if prob is not None else "—"
            ms_str    = f"{ms(diff_ns):.1f}" if diff_ns > 0 else "—"
            row += (f"  {colour}{act_str:>{act_w}}{RESET}"
                    f"  {prob_str:>{prob_w}}"
                    f"  {ms_str:>{ms_w}}")
        row += f"  {agree_mark:>5}"
        print(row)

    print()


def print_action_distribution(frames: dict, action_space: list) -> None:
    print(BOLD + "  ACTION DISTRIBUTION (chosen action per engine)" + RESET)
    print(hline())

    counts: dict[str, dict] = {e: {} for e in ENGINES}
    for frame in frames.values():
        best = frame.get("summary", {}).get("best", {})
        for eng in ENGINES:
            act = best.get(eng, {}).get("action")
            if act is not None and act != -1:
                counts[eng][act] = counts[eng].get(act, 0) + 1

    all_actions = sorted({a for e in ENGINES for a in counts[e]})
    max_count = max((c for e in ENGINES for c in counts[e].values()), default=1)

    bar_w   = 8
    cnt_w   = 4
    # Each engine column: 2 sep + cnt_w + 2 sep + bar_w  =  16 chars
    col_w   = 2 + cnt_w + 2 + bar_w

    print(DIM + f"  {'Action':<24}" + "".join(f"  {ENGINE_LABELS[e]:<{col_w - 2}}" for e in ENGINES) + RESET)
    print(DIM + hline() + RESET)

    for act in all_actions:
        label = action_label(action_space, act)
        row = f"  {f'[{act}] {label}':<24}"
        for eng in ENGINES:
            cnt = counts[eng].get(act, 0)
            sparkbar = bar(cnt, max_count, bar_w)
            row += f"  {cnt:>{cnt_w}}  {DIM}{sparkbar}{RESET}"
        print(row)
    print()


def export_csv(frames: dict, action_space: list, path: str) -> None:
    import csv
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp_ns", "filename",
            "tflite_action", "tflite_prob", "tflite_ms",
            "ov_action",     "ov_prob",     "ov_ms",
            "tf_action",     "tf_prob",     "tf_ms",
            "agree",
        ])
        for ts, frame in sorted(frames.items()):
            best = frame.get("summary", {}).get("best", {})
            best_actions = [best.get(e, {}).get("action") for e in ENGINES if e in best]
            valid = [a for a in best_actions if a is not None and a != -1]
            agree = len(set(valid)) <= 1 and len(valid) > 0
            row = [ts, frame.get("filename", "")]
            for eng in ENGINES:
                eb = best.get(eng, {})
                diff_ns = frame.get(eng, {}).get("time", {}).get("diff", 0) or 0
                row += [eb.get("action", ""), eb.get("value", ""), f"{ms(diff_ns):.2f}"]
            row.append("yes" if agree else "no")
            writer.writerow(row)
    print(f"  CSV written to {path}")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize a DeepRacer equivalency test results JSON file.")
    parser.add_argument("results", help="Path to results-<timestamp>.json")
    parser.add_argument("--no-frames", action="store_true",
                        help="Skip the per-frame table")
    parser.add_argument("--no-dist", action="store_true",
                        help="Skip the action distribution table")
    parser.add_argument("--csv", metavar="FILE",
                        help="Also export results to a CSV file")
    args = parser.parse_args()

    if not os.path.isfile(args.results):
        print(f"Error: file not found: {args.results}", file=sys.stderr)
        sys.exit(1)

    with open(args.results) as f:
        data = json.load(f)

    action_space = data.get("model_metadata", {}).get("action_space", [])
    frames = data.get("frames", {})

    print_header(data)
    print_summary(data)
    print_latency(frames)

    if not args.no_frames:
        print_frames(frames, action_space)

    if not args.no_dist:
        print_action_distribution(frames, action_space)

    if args.csv:
        export_csv(frames, action_space, args.csv)

    W = shutil.get_terminal_size((120, 40)).columns
    print("═" * W)
    print()


if __name__ == "__main__":
    main()
