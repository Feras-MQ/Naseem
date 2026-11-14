"""Beginner launcher: a fresh offline demo by default, or any explicit CLI command."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
# Anchor imports to this checkout even when launched from Explorer or another cwd.
sys.path.insert(0, str(ROOT))


def main(argv=None):
    # Windows redirects commonly default to a legacy code page. Keep paths and
    # machine-readable output UTF-8 even when stdout/stderr are captured.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")
    if sys.version_info < (3, 10):
        print("Naseem needs Python 3.10 or newer. Install Python, then try again.", file=sys.stderr)
        return 2
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        from naseem.cli import main as cli_main
        return cli_main(args)
    from naseem.demo import create_demo
    output = ROOT / "data" / "demos" / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    try:
        summary = create_demo(output)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"Demo could not finish: {exc}\nCheck this folder: {output}", file=sys.stderr)
        return 2
    print("SYNTHETIC DEMO ONLY. No device was opened; these are not air measurements.")
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    print(f"\nOpen this offline report in your browser:\n{output / 'report.html'}")
    print(f"All demo files:\n{output}")
    print("Later: run Start-Naseem.cmd --help for database and USB commands.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
