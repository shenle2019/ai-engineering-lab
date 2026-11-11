"""Run Mealie's frontend type generator inside WSL.

`dev/code-generation/gen_ts_types.py` finishes by shelling out to `yarn lint --fix`,
which is not available inside WSL (the frontend toolchain lives on Windows).
We stub that single subprocess call and run ESLint from Windows afterwards.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEALIE_DIR = REPO_ROOT / "mealie"
sys.path.insert(0, str(MEALIE_DIR / "dev" / "code-generation"))

import gen_ts_types  # noqa: E402


def _skip_lint(*args, **kwargs) -> subprocess.CompletedProcess:
    print(f"[skip] subprocess.run -> {args[0] if args else '<no args>'}")
    return subprocess.CompletedProcess(args=[], returncode=0)


def main() -> None:
    gen_ts_types.subprocess.run = _skip_lint
    gen_ts_types.main()


if __name__ == "__main__":
    main()
