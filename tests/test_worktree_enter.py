#!/usr/bin/env python3
"""Integration tests for PH worktree creation defaults."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "assets/scaffold/.agents/skills/ph-worktree-enter/scripts/ph_worktree.py"
TRASH_ROOT = Path.home() / "trash"


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, timeout=60)


class WorktreeEnterTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="ph-worktree-enter-"))
        self.repo = self.workspace / "repo"
        self.repo.mkdir()
        for args in (
            ("git", "init", "-q", "-b", "release/current", str(self.repo)),
            ("git", "-C", str(self.repo), "config", "user.name", "PH test"),
            ("git", "-C", str(self.repo), "config", "user.email", "ph-test@example.com"),
        ):
            proc = run(*args)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        (self.repo / ".gitignore").write_text("/.worktrees/\n", encoding="utf-8")
        (self.repo / "README.md").write_text("# fixture\n", encoding="utf-8")
        proc = run("git", "-C", str(self.repo), "add", ".gitignore", "README.md")
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        proc = run("git", "-C", str(self.repo), "commit", "-qm", "fixture")
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def tearDown(self):
        if not self.workspace.exists():
            return
        TRASH_ROOT.mkdir(parents=True, exist_ok=True)
        destination = TRASH_ROOT / f"ph-worktree-enter-{os.getpid()}-{time.time_ns()}"
        self.workspace.rename(destination)

    def invoke(self, branch: str, *, apply: bool = False) -> tuple[subprocess.CompletedProcess[str], dict]:
        args = [sys.executable, str(SCRIPT), "enter", "--repo", str(self.repo), "--branch", branch]
        if apply:
            args.append("--apply")
        proc = run(*args)
        payload = json.loads(proc.stdout)
        return proc, payload

    def test_plan_uses_main_worktree_current_branch_as_source(self):
        proc, plan = self.invoke("fix/login-timeout")
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertEqual(plan["sourceBranch"], "release/current")
        self.assertEqual(plan["sourceHead"], run("git", "-C", str(self.repo), "rev-parse", "HEAD").stdout.strip())
        self.assertEqual(plan["taskBranch"], "fix/login-timeout")
        self.assertFalse(plan["existingBranch"])
        self.assertFalse(plan["apply"])
        self.assertFalse((self.repo / ".worktrees").exists(), "dry-run must not create state")

    def test_apply_creates_new_branch_and_linked_worktree_in_one_step(self):
        source_head = run("git", "-C", str(self.repo), "rev-parse", "HEAD").stdout.strip()
        proc, result = self.invoke("fix/login-timeout", apply=True)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["sourceBranch"], "release/current")
        self.assertEqual(run("git", "-C", str(self.repo), "branch", "--show-current").stdout.strip(), "release/current")
        self.assertEqual(run("git", "-C", str(self.repo), "rev-parse", "HEAD").stdout.strip(), source_head)
        task_path = Path(result["taskPath"])
        self.assertTrue(task_path.is_dir())
        self.assertEqual(run("git", "-C", str(task_path), "branch", "--show-current").stdout.strip(), "fix/login-timeout")
        self.assertEqual(run("git", "-C", str(task_path), "rev-parse", "HEAD").stdout.strip(), source_head)
        self.assertEqual(run("git", "-C", str(self.repo), "show-ref", "--verify", "--quiet", "refs/heads/fix/login-timeout").returncode, 0)
        sessions = list((self.repo / ".worktrees/.ph/sessions").glob("*.json"))
        self.assertEqual(len(sessions), 1)
        session = json.loads(sessions[0].read_text(encoding="utf-8"))
        self.assertEqual(session["sourceBranch"], "release/current")
        self.assertEqual(session["taskBranch"], "fix/login-timeout")
        self.assertEqual(Path(session["taskPath"]), task_path)

    def test_shipped_skill_does_not_require_normal_creation_confirmation(self):
        skill = (REPO_ROOT / "assets/scaffold/.agents/skills/ph-worktree-enter/SKILL.md").read_text(encoding="utf-8")
        questions = (REPO_ROOT / "assets/scaffold/docs/约束规范/工程规范/对用户提问.md").read_text(encoding="utf-8")
        for text in (skill, questions):
            self.assertIn("主工作区当前", text)
            self.assertIn("任务分支", text)
            self.assertIn("不再", text)
        self.assertIn("代理结合当前任务语义", skill)
        self.assertIn("审查通过后直接加 `--apply`", skill)
        self.assertNotIn("确认后我才会真正创建", questions)
        self.assertNotIn("用新分支还是复用已有分支", skill)


if __name__ == "__main__":
    unittest.main()
