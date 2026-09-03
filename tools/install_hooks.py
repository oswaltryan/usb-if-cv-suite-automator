"""Install pre-commit and pre-push hooks for this repository."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    try:
        subprocess.run(["uv", "sync", "--locked", "--dev"], check=True)
        for hook_type in ("pre-commit", "pre-push"):
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pre_commit",
                    "install",
                    "--install-hooks",
                    "--hook-type",
                    hook_type,
                ],
                check=True,
            )
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
