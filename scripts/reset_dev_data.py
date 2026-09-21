#!/usr/bin/env python3
"""Delete only this checkout's default local object directory after confirmation.

Stop the server first. Restarting clears the in-memory session/document stores;
this utility removes the default local files left behind by those stores.
It deliberately does not read .env, accept a target path, or contact cloud storage.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="confirm removal of default local dev files")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    backend = root / "backend"
    data_dir = backend / ".data"
    objects = data_dir / "objects"
    if not args.yes:
        parser.error(f"Stop the backend, then pass --yes to remove only {objects}")
    if any(path.is_symlink() for path in (backend, data_dir, objects)):
        parser.error("Refusing to delete through a symlink in the default data path")
    if objects.exists():
        if not objects.is_dir():
            parser.error(f"Expected a directory at {objects}")
        shutil.rmtree(objects)
        print(f"Removed local development objects: {objects}")
    else:
        print(f"No local development objects at {objects}")
    print("Restart the backend to clear in-memory metadata. Custom paths and cloud buckets were not touched.")


if __name__ == "__main__":
    main()
