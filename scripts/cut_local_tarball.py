"""Build a brain tarball from git HEAD — cross-platform helper.

Plan 08 Task 8. Mirrors ``scripts/cut-local-tarball.sh`` but in pure
Python so it runs identically on Mac / Linux / Windows (PowerShell can
invoke it without needing bash).

Usage::

    python scripts/cut_local_tarball.py              # writes to ./dist/
    python scripts/cut_local_tarball.py /tmp/brain   # writes to /tmp/brain/

Output::

    <dest>/brain-dev-<sha>.tar.gz
    <dest>/brain-dev-<sha>.tar.gz.sha256
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


def _short_sha() -> str:
    """Return the short git SHA for the current HEAD (or ``nosha``)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or "nosha"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "nosha"


def _sha256_of(path: Path) -> str:
    """SHA256 hex digest of ``path``."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def cut_tarball(dest_dir: Path) -> tuple[Path, str]:
    """Build a tarball from git HEAD into ``dest_dir``.

    Returns ``(tarball_path, sha256)``. Writes both the tarball and a
    ``<tarball>.sha256`` sidecar file. Raises ``CalledProcessError`` if
    ``git archive`` fails (e.g. not inside a repo).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    sha = _short_sha()
    tarball = dest_dir / f"brain-dev-{sha}.tar.gz"

    # ``git archive`` works identically on Windows + Unix.
    subprocess.run(
        [
            "git",
            "archive",
            "--format=tar.gz",
            f"--output={tarball}",
            "HEAD",
        ],
        check=True,
    )

    digest = _sha256_of(tarball)
    sidecar = dest_dir / f"{tarball.name}.sha256"
    sidecar.write_text(f"{digest}  {tarball.name}\n", encoding="utf-8")

    return tarball, digest


def main(argv: list[str]) -> int:
    dest = Path(argv[1]) if len(argv) >= 2 else Path("dist")
    try:
        tarball, digest = cut_tarball(dest)
    except subprocess.CalledProcessError as exc:
        print(f"error: git archive failed (rc={exc.returncode})", file=sys.stderr)
        return 1

    print("==> Cut tarball from git HEAD")
    print(f"tarball: {tarball}")
    print(f"sha256:  {digest}")
    print("")
    print("to install from this tarball:")
    abs_tarball = tarball.resolve()
    # Use forward slashes for the file:// URL on both platforms.
    as_url = "file:///" + str(abs_tarball).replace("\\", "/").lstrip("/")
    print(f"  BRAIN_RELEASE_URL={as_url}")
    print(f"  BRAIN_RELEASE_SHA256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
