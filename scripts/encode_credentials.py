#!/usr/bin/env python3
"""Print base64-encoded credentials for Railway GOOGLE_CREDENTIALS_JSON_B64."""

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "credentials.json"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        print("Usage: uv run python scripts/encode_credentials.py [credentials.json]", file=sys.stderr)
        raise SystemExit(1)

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    print("Add this to Railway as GOOGLE_CREDENTIALS_JSON_B64:\n")
    print(encoded)


if __name__ == "__main__":
    main()
