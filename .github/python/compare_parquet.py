#!/usr/bin/env python3
"""
compare_parquet.py — parquet output comparison for outputs-diff.yml

Reports bulk statistics per numeric column so broken outputs (all NaN, all zero,
large value shifts) are immediately visible in CI logs. Structure mismatches
(unexpected column or row count differences) are flagged as anomalies since
the data structure should be identical between baseline and test runs.

Always exits 0 — informational only, never blocks a PR.
"""

import argparse
import os

import numpy as np
import pandas as pd


def collect_parquet_files(root_dir):
    result = {}
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith(".parquet"):
                abs_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(abs_path, root_dir)
                result[rel_path] = abs_path
    return result


def fmt_val(v):
    """Format a scalar for the report table."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "NaN"
    if isinstance(v, (int, np.integer)):
        return str(v)
    return f"{v:.5g}"


def pct_change(old, new):
    """Return formatted % change string, handling zero / NaN baselines."""
    try:
        if np.isnan(old) or np.isnan(new):
            return "N/A"
        if old == 0:
            return "0->0" if new == 0 else f"0->{new:.4g}"
        pct  = (new - old) / abs(old) * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def col_stats(series):
    """Compute bulk statistics for one column."""
    num      = pd.to_numeric(series, errors="coerce")
    non_nan  = num.dropna()
    n_total  = len(num)
    n_nan    = int(num.isna().sum())
    n_nonnan = len(non_nan)
    return {
        "mean":      float(non_nan.mean())  if n_nonnan else float("nan"),
        "std":       float(non_nan.std())   if n_nonnan else float("nan"),
        "max":       float(non_nan.max())   if n_nonnan else float("nan"),
        "min":       float(non_nan.min())   if n_nonnan else float("nan"),
        "nan_count": n_nan,
        "zero_count": int((non_nan == 0).sum()),
        "all_nan":   n_nonnan == 0,
        "all_zero":  n_nonnan > 0 and bool((non_nan == 0).all()),
        "any_neg":   n_nonnan > 0 and bool((non_nan < 0).any()),
    }


def report_numeric_col(col, bl, tl):
    """Print per-column stats table. Return True if any issue was found."""
    bs = col_stats(bl)
    ts = col_stats(tl)

    warnings = []
    if ts["all_nan"]:
        warnings.append("ALL NaN IN TEST — model likely failed")
    elif ts["nan_count"] > bs["nan_count"]:
        warnings.append(f"NaN count increased {bs['nan_count']} -> {ts['nan_count']}")
    elif bs["nan_count"] > 0 or ts["nan_count"] > 0:
        warnings.append(f"NaN values present (baseline={bs['nan_count']}, test={ts['nan_count']})")
    if ts["all_zero"]:
        warnings.append("ALL ZERO IN TEST — suspicious, check model output")
    if ts["any_neg"] and not bs["any_neg"]:
        warnings.append("negative values appeared in test (not in baseline)")

    prefix = "  *** " if warnings else "  "
    print(f"{prefix}{col}" + (f"  [{'  |  '.join(warnings)}]" if warnings else ""))

    # Table rows: (label, bl_val, tl_val, show_pct)
    rows = [
        ("Mean",       bs["mean"],       ts["mean"],       True),
        ("Std dev",    bs["std"],        ts["std"],        True),
        ("Max",        bs["max"],        ts["max"],        True),
        ("Min",        bs["min"],        ts["min"],        True),
        ("NaN count",  bs["nan_count"],  ts["nan_count"],  False),
        ("Zero count", bs["zero_count"], ts["zero_count"], False),
    ]

    print(f"    {'Metric':<12}  {'Baseline':>14}  {'Test':>14}  {'Change':>12}")
    print(f"    {'-'*12}  {'-'*14}  {'-'*14}  {'-'*12}")
    for label, bv, tv, show_pct in rows:
        chg = pct_change(bv, tv) if show_pct else ""
        print(f"    {label:<12}  {fmt_val(bv):>14}  {fmt_val(tv):>14}  {chg:>12}")

    return bool(warnings) or any(
        bv != tv for _, bv, tv, _ in rows
        if not (isinstance(bv, float) and np.isnan(bv))
        and not (isinstance(tv, float) and np.isnan(tv))
    )


def compare_file(rel_path, bl_path, tl_path):
    """Print the full comparison for one file. Return True if anything changed."""
    print(f"\n{'='*72}")
    print(f"  {rel_path}")
    print(f"{'='*72}")

    bl = pd.read_parquet(bl_path)
    tl = pd.read_parquet(tl_path)

    bl = bl.reindex(sorted(bl.columns), axis=1).reset_index(drop=True)
    tl = tl.reindex(sorted(tl.columns), axis=1).reset_index(drop=True)

    print(f"  Rows: {len(bl)} baseline / {len(tl)} test")

    # Structure checks — should not happen, but flag clearly if they do
    if set(bl.columns) != set(tl.columns):
        only_bl = sorted(set(bl.columns) - set(tl.columns))
        only_tl = sorted(set(tl.columns) - set(bl.columns))
        print(f"  *** UNEXPECTED COLUMN MISMATCH ***")
        if only_bl: print(f"      baseline only: {only_bl}")
        if only_tl: print(f"      test only:     {only_tl}")
        return True

    if len(bl) != len(tl):
        print(f"  *** UNEXPECTED ROW COUNT MISMATCH: {len(bl)} vs {len(tl)} ***")
        return True

    any_change = False
    for col in sorted(bl.columns):
        is_numeric = pd.api.types.is_numeric_dtype(bl[col]) or pd.api.types.is_numeric_dtype(tl[col])
        if is_numeric:
            changed = report_numeric_col(col, bl[col], tl[col])
        else:
            if bl[col].equals(tl[col]):
                print(f"  {col}: [non-numeric, identical]")
                changed = False
            else:
                n_diff = (bl[col] != tl[col]).sum()
                print(f"  {col}: [non-numeric, {n_diff} value(s) differ]")
                changed = True
        if changed:
            any_change = True

    return any_change


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-dir", required=True)
    parser.add_argument("--test-dir",     required=True)
    args = parser.parse_args()

    baseline_files = collect_parquet_files(args.baseline_dir)
    test_files     = collect_parquet_files(args.test_dir)
    all_keys       = sorted(set(baseline_files) | set(test_files))

    if not all_keys:
        print("WARNING: No parquet files found in either directory.")
        return

    print(f"Outputs Diff — comparing {len(all_keys)} parquet file(s)\n")

    changed   = []
    unchanged = []

    for rel in all_keys:
        if rel not in baseline_files or rel not in test_files:
            print(f"\nUNEXPECTED: {rel} present in only one of baseline/test")
            changed.append(rel)
        elif compare_file(rel, baseline_files[rel], test_files[rel]):
            changed.append(rel)
        else:
            unchanged.append(rel)

    print(f"\n{'='*72}")
    print(f"SUMMARY  ({len(all_keys)} file(s))")
    print(f"  Identical : {len(unchanged)}")
    print(f"  Changed   : {len(changed)}")
    if changed:
        for f in changed:
            print(f"    - {f}")
    print()
    print("Output changes are informational — review whether they are expected.")


if __name__ == "__main__":
    main()
