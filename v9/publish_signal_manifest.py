"""Generate the public Octopus signal manifest independently of Bark delivery."""
from __future__ import annotations

import os
import sys

from ntfy_notifier import load_report, write_public_signal_state


def main() -> int:
    report_path = sys.argv[1] if len(sys.argv) > 1 else "v9/scan-report.json"
    output_path = os.environ.get("V9_PUBLIC_SIGNAL_PATH", "").strip()
    if not output_path:
        print("ERROR: V9_PUBLIC_SIGNAL_PATH is required.", file=sys.stderr)
        return 2
    try:
        report = load_report(report_path)
        write_public_signal_state(report)
    except (OSError, ValueError) as exc:
        print(f"ERROR: public signal manifest generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Public signal manifest generated independently at {output_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
