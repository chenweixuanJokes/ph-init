#!/usr/bin/env python3
"""Copy approved project-template canonical files into the installer scaffold.

Why a build-time copy: the installed `ph-init` must be self-contained. Runtime
code reads `assets/scaffold` next to the skill, never a proposal-repo absolute
path. Tests compare content digests so the two trees cannot silently drift.

This script is a maintainer tool. It is not part of the self-install payload
and does not upgrade or migrate an already-initialized repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path


APPROVED_DOC_DIRS = ("约束规范", "意图", "项目Wiki")
SKIP_DIR_NAMES = {"__pycache__", ".git"}
SKIP_FILE_NAMES = {".DS_Store"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def implementation_root() -> Path:
    distribution = Path(__file__).resolve().parents[1]
    root = distribution.parent.parent
    if distribution.parent.name != "distribution" or not (root / "project-template").is_dir():
        raise SystemExit("legacy template builder requires distribution/ph-init and project-template; do not run in the standalone release repository")
    return root


def template_root() -> Path:
    return implementation_root() / "project-template"


def scaffold_root() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "scaffold"


def is_link(path: Path) -> bool:
    """True for a POSIX symlink or a Windows junction at this exact node."""

    if path.is_symlink():
        return True
    if os.name == "nt":
        try:
            attrs = getattr(os.lstat(path), "st_file_attributes", 0)
            return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except OSError:
            return False
    return False


def reject_nested_links(root: Path, label: str) -> None:
    """Derived trees stay byte-reproducible only if the source is a real tree."""

    if is_link(root):
        raise SystemExit(f"{label} is a symlink or junction: {root}")
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        for name in list(dirnames) + list(filenames):
            child = current / name
            if name in SKIP_DIR_NAMES or name in SKIP_FILE_NAMES or Path(name).suffix in SKIP_SUFFIXES:
                continue
            if is_link(child):
                raise SystemExit(f"{label} contains nested symlink or junction: {child}")


def iter_files(root: Path):
    reject_nested_links(root, f"tree {root}")
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in dirnames:
            child = current / name
            if is_link(child):
                raise SystemExit(f"tree contains nested symlink or junction: {child}")
        for name in sorted(filenames):
            if name in SKIP_FILE_NAMES or Path(name).suffix in SKIP_SUFFIXES:
                continue
            path = current / name
            if is_link(path):
                raise SystemExit(f"tree contains nested symlink or junction: {path}")
            if path.is_file():
                yield path


def relposix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def digest_tree(root: Path, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for path in iter_files(root):
        rel = relposix(root, path)
        if prefix:
            rel = f"{prefix}/{rel}"
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def canonical_digest(src: Path) -> dict[str, str]:
    """Digest of the files the installer is allowed to treat as canonical."""

    digest: dict[str, str] = {}
    agents = src / ".agents"
    for path in iter_files(agents):
        rel = relposix(src, path)
        if rel.startswith(".agents/skills/ph-init/") or rel == ".agents/skills/ph-init":
            continue
        digest[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    docs = src / "docs"
    digest.update(digest_tree(docs, "docs"))
    gitignore = src / ".gitignore"
    if gitignore.is_file():
        digest[".gitignore"] = hashlib.sha256(gitignore.read_bytes()).hexdigest()
    return digest


def assert_approved_names(src: Path) -> None:
    docs = src / "docs"
    missing = [name for name in APPROVED_DOC_DIRS if not (docs / name).is_dir()]
    if missing:
        raise SystemExit(
            "project-template docs are not using approved names "
            f"{APPROVED_DOC_DIRS}: missing {missing}"
        )
    forbidden = {"约束", "项目wiki"}
    present = {p.name for p in docs.iterdir() if p.is_dir()}
    clash = present & forbidden
    if clash:
        raise SystemExit(f"project-template still has pre-approval directory names: {sorted(clash)}")


def copy_canonical(src: Path, dest: Path) -> dict[str, str]:
    assert_approved_names(src)
    reject_nested_links(src / ".agents", "project-template .agents")
    reject_nested_links(src / "docs", "project-template docs")
    gitignore = src / ".gitignore"
    if gitignore.exists() and is_link(gitignore):
        raise SystemExit(f"project-template .gitignore is a symlink or junction: {gitignore}")
    copied = canonical_digest(src)
    dest.mkdir(parents=True, exist_ok=True)
    for rel in copied:
        source = src / rel
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    leftover = [relposix(dest, path) for path in iter_files(dest) if relposix(dest, path) not in copied]
    if leftover:
        raise SystemExit(
            "scaffold has leftover files not in the approved canonical set: "
            + ", ".join(leftover[:20])
        )
    nested = dest / ".agents" / "skills" / "ph-init"
    if nested.exists():
        raise SystemExit("refusing to publish a recursive scaffold that contains ph-init")
    return copied


def main(argv: list[str] | None = None) -> int:
    del argv
    src = template_root()
    dest = scaffold_root()
    if not src.is_dir():
        raise SystemExit(f"missing project-template: {src}")
    copied = copy_canonical(src, dest)
    sys.stdout.write(json.dumps({"files": len(copied), "dest": str(dest)}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
