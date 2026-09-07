#!/usr/bin/env python3
"""Unit tests for scripts/check_release.py."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_release  # noqa: E402


TRASH_ROOT = Path.home() / "trash"
REQUIRED_SKILLS = [
    "ph-init",
    "ph-worktree-enter",
    "ph-worktree-exit",
    "ph-memory-capture",
    "ph-memory-archive",
    "ph-memory-ask",
    "ph-intent-new",
    "ph-intent-impl",
    "ph-intent-drop",
    "ph-merge-update",
]


def run(argv, cwd=None):
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=60)


def copy_repo(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        src,
        dest,
        symlinks=False,
        ignore=lambda directory, names: set(shutil.ignore_patterns(
            ".git", "__pycache__", ".zcode", ".DS_Store", "*.pyc"
        )(directory, names)) | ({"AGENTS.md", "CLAUDE.md"} if Path(directory) == src else set()),
    )


class CheckReleaseTests(unittest.TestCase):
    def setUp(self):
        self._temps = []

    def tearDown(self):
        if not self._temps:
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        dest = TRASH_ROOT / f"ph-check-release-{stamp}-{os.getpid()}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.mkdir(parents=True, exist_ok=False)
        for i, path in enumerate(self._temps):
            if Path(path).exists():
                Path(path).rename(dest / f"{i:02d}-{Path(path).name}")

    def test_prepared_tree_errors_are_not_swallowed(self):
        with mock.patch.object(check_release.ph_release, "validate_prepared_tree", side_effect=check_release.ph_release.PHReleaseError("illegal manifest: skills.required_names mismatch")):
            with self.assertRaisesRegex(check_release.CheckError, "skills.required_names mismatch"):
                check_release._call_prepared_tree(REPO_ROOT, "1.1.2", REQUIRED_SKILLS)

    def temp_dir(self, prefix):
        root = Path(tempfile.mkdtemp(prefix=prefix))
        self._temps.append(root)
        return root

    def git_repo(self, prefix, *, with_files=True):
        parent = self.temp_dir(prefix)
        root = parent / "repo"
        if with_files:
            copy_repo(REPO_ROOT, root)
        else:
            root.mkdir()
        for argv in (
            ["git", "init"],
            ["git", "config", "user.email", "t@example.com"],
            ["git", "config", "user.name", "ph-check-test"],
        ):
            proc = run(argv, cwd=root)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        return root

    def commit_all(self, repo: Path, message: str) -> str:
        proc = run(["git", "add", "-A"], cwd=repo)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        proc = run(["git", "commit", "-m", message], cwd=repo)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        return run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    def write_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def mutate_release(self, repo: Path, **fields) -> None:
        path = repo / "release.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(fields)
        self.write_json(path, data)

    def mutate_manifest(self, repo: Path, **fields) -> None:
        path = repo / "assets/scaffold/.agents/ph.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(fields)
        self.write_json(path, data)

    def mutate_schema_id(self, repo: Path, schema_id: str) -> None:
        path = repo / "assets/scaffold/.agents/ph.schema.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["$id"] = schema_id
        self.write_json(path, data)

    def set_index(self, repo: Path, hops: list[dict]) -> None:
        self.write_json(repo / "migrations/index.json", {"format_version": 1, "migrations": hops})

    def assert_fails(self, root: Path, needle: str, tag=None):
        with self.assertRaises(check_release.CheckError) as ctx:
            check_release.validate_tree(root, repo=root, tag=tag)
        self.assertIn(needle, str(ctx.exception))

    def test_current_tree_passes_without_tags(self):
        result = check_release.validate_tree(REPO_ROOT, repo=REPO_ROOT, tag=None)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["version"], "1.1.2")
        self.assertEqual(result["schema_version"], "1.1.1")
        self.assertEqual(result["required_skills"], REQUIRED_SKILLS)

    def test_cli_current_tree(self):
        buf = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            code = check_release.main(["--root", str(REPO_ROOT)])
        self.assertEqual(code, 0, err.getvalue())
        data = json.loads(buf.getvalue())
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["version"], "1.1.2")

    def test_root_skill_codeblock_placeholder_is_not_a_broken_link(self):
        repo = self.git_repo("ph-check-fence-")
        skill = repo / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        text += (
            "\n```text\n"
            "see [missing](./definitely-not-there.md)\n"
            "python3 <ph-init-root>/scripts/ph_release.py prepare --version latest\n"
            "```\n"
        )
        skill.write_text(text, encoding="utf-8")
        check_release.validate_tree(repo, repo=repo, tag=None)

    def test_rejects_mismatched_metadata(self):
        repo = self.git_repo("ph-check-meta-")
        self.mutate_release(repo, schema_version="9.9.9")
        self.assert_fails(repo, "$id")

        repo = self.git_repo("ph-check-schema-id-")
        self.mutate_schema_id(repo, "urn:ph:schema:project-harness:0.0.1")
        self.assert_fails(repo, "$id")

        repo = self.git_repo("ph-check-manifest-")
        self.mutate_manifest(repo, template_version="0.0.1")
        self.assert_fails(repo, "template_version")

        repo = self.git_repo("ph-check-skills-")
        data = json.loads((repo / "release.json").read_text(encoding="utf-8"))
        data["required_skills"] = REQUIRED_SKILLS[:-1]
        self.write_json(repo / "release.json", data)
        self.assert_fails(repo, "required_skills")

    def test_rejects_broken_markdown_link_outside_codeblock(self):
        repo = self.git_repo("ph-check-link-")
        readme = repo / "migrations/README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\n[gone](./no-such-file.md)\n", encoding="utf-8")
        self.assert_fails(repo, "broken markdown link")

    def test_rejects_empty_skill_description(self):
        repo = self.git_repo("ph-check-front-")
        path = repo / "assets/scaffold/.agents/skills/ph-merge-update/SKILL.md"
        path.write_text("---\nname: ph-merge-update\ndescription: \"\"\n---\n# x\n", encoding="utf-8")
        self.assert_fails(repo, "description")

    def test_rejects_invalid_evals_json(self):
        repo = self.git_repo("ph-check-evals-")
        (repo / "evals/evals.json").write_text("{not-json", encoding="utf-8")
        self.assert_fails(repo, "illegal")

    def test_temp_git_same_version_non_payload_change_passes(self):
        repo = self.git_repo("ph-check-nonpayload-")
        self.commit_all(repo, "v1.1.2")
        proc = run(["git", "tag", "-a", "v1.1.2", "-m", "v1.1.2"], cwd=repo)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        (repo / "README.md").write_text("# docs only\n", encoding="utf-8")
        (repo / ".github").mkdir(exist_ok=True)
        (repo / ".github/workflows").mkdir(exist_ok=True)
        (repo / ".github/workflows/check.yml").write_text("name: check\n", encoding="utf-8")
        (repo / ".agents").mkdir(exist_ok=True)
        (repo / ".agents/AGENTS.md").write_text("# Maintainer rules\n", encoding="utf-8")
        (repo / "docs").mkdir(exist_ok=True)
        (repo / "docs/release-rules.md").write_text("# Version discipline\n", encoding="utf-8")
        result = check_release.validate_tree(repo, repo=repo, tag=None)
        self.assertEqual(result["status"], "ok")

    def test_temp_git_same_version_payload_change_rejected(self):
        repo = self.git_repo("ph-check-payload-")
        self.commit_all(repo, "v1.1.2")
        proc = run(["git", "tag", "-a", "v1.1.2", "-m", "v1.1.2"], cwd=repo)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        skill = repo / "assets/scaffold/.agents/skills/ph-merge-update/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nextra payload line\n", encoding="utf-8")
        self.assert_fails(repo, "already tagged")

    def test_new_patch_without_migration_record_rejected(self):
        repo = self.git_repo("ph-check-missing-hop-")
        self.commit_all(repo, "v1.1.2")
        proc = run(["git", "tag", "-a", "v1.1.2", "-m", "v1.1.2"], cwd=repo)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.mutate_release(repo, version="1.1.3")
        self.mutate_manifest(repo, template_version="1.1.3")
        self.assert_fails(repo, "missing migration record 1.1.2 -> 1.1.3")

    def test_new_patch_with_complete_record_passes(self):
        repo = self.git_repo("ph-check-next-")
        self.commit_all(repo, "v1.1.2")
        proc = run(["git", "tag", "-a", "v1.1.2", "-m", "v1.1.2"], cwd=repo)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.mutate_release(repo, version="1.1.3")
        self.mutate_manifest(repo, template_version="1.1.3")
        hops = json.loads((repo / "migrations/index.json").read_text(encoding="utf-8"))["migrations"]
        hops.append(
            {
                "from_version": "1.1.2",
                "to_version": "1.1.3",
                "path": "migrations/1.1.2-to-1.1.3.md",
                "items": ["docs-only"],
            }
        )
        self.set_index(repo, hops)
        (repo / "migrations/1.1.2-to-1.1.3.md").write_text(
            "# 1.1.2 → 1.1.3\n\n"
            "## why\npatch\n\n## from\n1.1.2\n\n## to\n1.1.3\n\n"
            "## affected\ndocs-only\n\n## preserve\nnone\n\n"
            "## conflict\nnone\n\n## verify\nok\n",
            encoding="utf-8",
        )
        result = check_release.validate_tree(repo, repo=repo, tag=None)
        self.assertEqual(result["version"], "1.1.3")

    def test_tag_validation_requires_matching_commit_and_meta(self):
        repo = self.git_repo("ph-check-tag-")
        commit = self.commit_all(repo, "v1.1.2")
        proc = run(["git", "tag", "-a", "v1.1.2", "-m", "v1.1.2"], cwd=repo)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        result = check_release.validate_tree(repo, repo=repo, tag="v1.1.2")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(run(["git", "rev-parse", "v1.1.2^{}"], cwd=repo).stdout.strip(), commit)

        self.mutate_release(repo, version="1.1.3")
        self.mutate_manifest(repo, template_version="1.1.3")
        hops = json.loads((repo / "migrations/index.json").read_text(encoding="utf-8"))["migrations"]
        hops.append(
            {
                "from_version": "1.1.2",
                "to_version": "1.1.3",
                "path": "migrations/1.1.2-to-1.1.3.md",
                "items": ["docs-only"],
            }
        )
        self.set_index(repo, hops)
        (repo / "migrations/1.1.2-to-1.1.3.md").write_text(
            "# 1.1.2 → 1.1.3\n\n## why\n\n## from\n\n## to\n\n## affected\ndocs-only\n\n## preserve\n\n## conflict\n\n## verify\n",
            encoding="utf-8",
        )
        self.assert_fails(repo, "does not match release.json version", tag="v1.1.2")

        repo = self.git_repo("ph-check-tag-head-")
        self.commit_all(repo, "v1.1.2")
        proc = run(["git", "tag", "-a", "v1.1.2", "-m", "v1.1.2"], cwd=repo)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        (repo / "README.md").write_text("# later\n", encoding="utf-8")
        later = self.commit_all(repo, "later")
        self.assertNotEqual(later, run(["git", "rev-parse", "v1.1.2^{}"], cwd=repo).stdout.strip())
        self.assert_fails(repo, "does not match HEAD", tag="v1.1.2")

    def test_mocked_git_tags_reject_payload_rewrite_of_published_version(self):
        repo = self.temp_dir("ph-check-mock-")
        published = {"release.json": b'{"version":"1.1.1"}\n', "SKILL.md": b"old\n"}
        current = dict(published)
        current["SKILL.md"] = b"changed\n"
        hops = [
            {
                "from_version": "1.0.0",
                "to_version": "1.1.0",
                "path": "migrations/1.0.0-to-1.1.0.md",
                "items": ["intent-domain"],
            },
            {
                "from_version": "1.1.0",
                "to_version": "1.1.1",
                "path": "migrations/1.1.0-to-1.1.1.md",
                "items": ["merge-update"],
            },
        ]
        release = {
            "version": "1.1.1",
            "schema_version": "1.1.1",
            "required_skills": REQUIRED_SKILLS,
        }
        with mock.patch.object(check_release, "list_published_tags", return_value={"v1.1.1": "a" * 40}), \
             mock.patch.object(check_release, "payload_map_from_tree", return_value=current), \
             mock.patch.object(check_release, "payload_map_from_git", return_value=published):
            with self.assertRaises(check_release.CheckError) as ctx:
                check_release.validate_version_discipline(
                    repo, repo, release, hops, {"v1.1.1": "a" * 40}, None
                )
        self.assertIn("already tagged", str(ctx.exception))

    def test_cli_rejects_bad_tag_flag(self):
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            try:
                check_release.main(["--root", str(REPO_ROOT), "--tag", "1.1.1"])
            except check_release.CheckError as exc:
                sys.stderr.write(f"error: {exc}\n")
                raise SystemExit(1)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("unsupported --tag", err.getvalue())


if __name__ == "__main__":
    unittest.main()
