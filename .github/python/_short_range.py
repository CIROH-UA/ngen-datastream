"""Shared short_range/00/ substitution — imported by detect_changes.py and build_exec_json.py."""
import re

SHORT_RANGE_VARS = {
    "$RUN_TYPE_L": "short_range",
    "$RUN_TYPE_H": "SHORT_RANGE",
    "$INIT":       "00",
    "$FCST":       "f001_f018",
    "$MEMBER":     "",   # no ensemble member for short_range
    "$NPROCS":     "7",  # default; doesn't affect outputs
}


def apply_short_range_vars(text, vpu=""):
    """Substitute short_range/00/ variables and a VPU into a template string."""
    for k, v in SHORT_RANGE_VARS.items():
        text = text.replace(k, v)
    if vpu:
        text = text.replace("$VPU", vpu)
    # Clean double slashes in S3 paths produced by empty $MEMBER
    text = re.sub(r"(?<!:)//", "/", text)
    return text
