#!/usr/bin/env python3
"""Publish ph-init into canonical and generate the portable example adapters."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

SKIP_NAMES = {"__pycache__", ".DS_Store"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def implementation_root() -> Path:
    return Path(__file__).resolve().parents[3]


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
    if is_link(root):
        raise SystemExit(f"{label} is a symlink or junction: {root}")
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        for name in list(dirnames) + list(filenames):
            child = current / name
            rel_parts = child.relative_to(root).parts
            if any(part in SKIP_NAMES for part in rel_parts):
                continue
            if Path(name).suffix in SKIP_SUFFIXES:
                continue
            if is_link(child):
                raise SystemExit(f"{label} contains nested symlink or junction: {child}")


def inventory(root: Path) -> set[str]:
    files: set[str] = set()
    if not root.exists():
        return files
    reject_nested_links(root, f"managed tree {root}")
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES]
        for name in filenames:
            if name in SKIP_NAMES or Path(name).suffix in SKIP_SUFFIXES:
                continue
            files.add((current / name).relative_to(root).as_posix())
    return files


def require_no_leftovers(target: Path, expected: set[str], label: str) -> None:
    extras = sorted(inventory(target) - expected)
    if extras:
        raise SystemExit(f"{label} contains stale generated files: {', '.join(extras[:20])}")


def copy_tree(source: Path, target: Path, *, reject_leftovers: bool = True) -> None:
    reject_nested_links(source, f"source tree {source}")
    expected = inventory(source)
    if reject_leftovers:
        require_no_leftovers(target, expected, f"published tree {target}")
    for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES]
        rel_dir = current.relative_to(source)
        (target / rel_dir).mkdir(parents=True, exist_ok=True)
        for name in filenames:
            if name in SKIP_NAMES or Path(name).suffix in SKIP_SUFFIXES:
                continue
            path = current / name
            if is_link(path):
                raise SystemExit(f"source tree contains nested symlink or junction: {path}")
            dest = target / path.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)


def main() -> int:
    impl = implementation_root()
    distribution = impl / "distribution" / "ph-init"
    template = impl / "project-template"

    build_scaffold = distribution / "scripts" / "build_scaffold.py"
    proc = subprocess.run([sys.executable, str(build_scaffold)], text=True, capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout)
        return proc.returncode

    canonical_init = template / ".agents" / "skills" / "ph-init"
    canonical_init.mkdir(parents=True, exist_ok=True)
    expected_init = {"SKILL.md", "scripts/ph_init.py"}
    for rel in ("evals", "assets"):
        expected_init.update(f"{rel}/{path}" for path in inventory(distribution / rel))
    require_no_leftovers(canonical_init, expected_init, "published canonical ph-init")
    for rel in ("SKILL.md", "scripts/ph_init.py", "evals", "assets"):
        source = distribution / rel
        target = canonical_init / rel
        if source.is_dir():
            copy_tree(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    canonical_agents = template / ".agents" / "AGENTS.md"
    shutil.copyfile(canonical_agents, template / "AGENTS.md")
    (template / "CLAUDE.md").write_text("@.agents/AGENTS.md\n", encoding="utf-8")

    canonical_skills = template / ".agents" / "skills"
    skill_names = {
        skill.name
        for skill in canonical_skills.glob("ph-*")
        if skill.is_dir() and (skill / "SKILL.md").is_file()
    }
    for vendor in (".claude", ".codex"):
        vendor_root = template / vendor / "skills"
        vendor_root.mkdir(parents=True, exist_ok=True)
        stale_skills = sorted(
            child.name
            for child in vendor_root.glob("ph-*")
            if child.name not in skill_names
        )
        if stale_skills:
            raise SystemExit(
                f"published {vendor} skills contain stale generated directories: "
                + ", ".join(stale_skills)
            )
        for name in sorted(skill_names):
            copy_tree(canonical_skills / name, vendor_root / name)

    print("published=project-template portable")
    print(f"skills={len(list(canonical_skills.glob('ph-*')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
