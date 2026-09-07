"""Exercise a real prepared Git snapshot and post-merge finalization offline."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = json.loads((ROOT / "release.json").read_text())["version"]
sys.path.insert(0, str(ROOT / "scripts"))
import ph_release


def command(*args, cwd=None):
    result = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout


def digest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and ".git" not in p.parts
            and "__pycache__" not in p.parts}


class LocalTransport(ph_release.GitTransport):
    def __init__(self, source):
        self.source = source

    def ls_remote_tags(self, source):
        assert source == ph_release.FIXED_SOURCE
        return command("git", "ls-remote", "--tags", str(self.source))

    def fetch_commit(self, source, commit, dest):
        assert source == ph_release.FIXED_SOURCE
        command("git", "init", "--bare", "--template=", str(dest))
        command("git", "-C", str(dest), "fetch", "--no-tags", str(self.source), commit)


class ReleaseIntegrationTests(unittest.TestCase):
    def test_prepared_snapshot_init_and_post_merge_finalize(self):
        workspace = Path(tempfile.mkdtemp(prefix="ph-release-integration-"))
        try:
            source = workspace / "source"
            shutil.copytree(ROOT, source, ignore=lambda directory, names: set(shutil.ignore_patterns(
                ".git", ".zcode", "__pycache__", "*.pyc", ".DS_Store"
            )(directory, names)) | ({"AGENTS.md", "CLAUDE.md"} if Path(directory) == ROOT else set()))
            command("git", "init", "-q", str(source))
            command("git", "-C", str(source), "add", ".")
            command("git", "-C", str(source), "-c", "user.name=PH fixture",
                    "-c", "user.email=fixture@example.com", "commit", "-qm", "fixture release")
            command("git", "-C", str(source), "tag", f"v{CURRENT}")
            prepared = ph_release.prepare_release("latest", transport=LocalTransport(source),
                                                   parent=workspace / "prepared")
            root = prepared.root
            for mode in ("portable", "symlink"):
                with self.subTest(mode=mode):
                    repo = workspace / mode
                    command("git", "init", "-q", str(repo))
                    init = root / "scripts/ph_init.py"
                    merge = root / "scripts/ph_merge_update.py"
                    before = digest(repo)
                    command(sys.executable, str(init), "init", "--mode", mode, "--repo", str(repo))
                    self.assertEqual(before, digest(repo))
                    command(sys.executable, str(init), "init", "--apply", "--mode", mode, "--repo", str(repo))
                    installed = repo / ".agents/skills/ph-init/scripts/ph_init.py"
                    command(sys.executable, str(installed), "check", "--repo", str(repo))
                    # Model the post-semantic-merge stage; this is not a test of
                    # an Agent reconstructing old project rules from scratch.
                    manifest = repo / ".agents/ph.json"
                    data = json.loads(manifest.read_text())
                    data["schema_version"] = data["template_version"] = "1.0.0"
                    data["skills"]["required_names"] = data["skills"]["required_names"][:6]
                    manifest.write_text(json.dumps(data) + "\n")
                    agents = repo / ".agents/AGENTS.md"
                    agents.write_text(agents.read_text() + "\nProject-specific command: make verify\n")
                    legacy = repo / "docs/意图/进行中/新特性/INT-keep.md"
                    legacy.parent.mkdir(parents=True)
                    legacy.write_text("# Original intent\nDo not reclassify.\n")
                    pending = repo / "docs/意图/待办/新特性/README.md"
                    pending.write_text(pending.read_text() + "\nCustom project index entry\n")
                    wiki = repo / "docs/项目Wiki/项目概述.md"
                    rules = repo / "docs/约束规范/后端规范/后端规范.md"
                    wiki.write_text(wiki.read_text() + "\nReviewed subagent project facts\n")
                    rules.write_text(rules.read_text() + "\nProject-specific approved exception\n")
                    retained_paths = (agents, legacy, pending, wiki, rules)
                    retained = tuple(path.read_bytes() for path in retained_paths)
                    inspected = json.loads(command(sys.executable, str(merge), "inspect", "--repo", str(repo)))
                    self.assertTrue(inspected["source"]["verified"], inspected["source"])
                    state = inspected["suggested_state"]
                    self.assertEqual(state["from_version"], "1.0.0")
                    self.assertEqual(state["source"]["commit"], prepared.commit)
                    for item in state["items"]:
                        item.update(status="applied", evidence="Post-merge fixture contains target assets; protected project bytes checked")
                    record = repo / ".agents/updates" / CURRENT
                    record.mkdir(parents=True)
                    (record / "state.json").write_text(json.dumps(state) + "\n")
                    (record / "report.md").write_text("# Local fixture\nPost-merge structural test, not public GitHub verification.\n")
                    command(sys.executable, str(merge), "verify", "--repo", str(repo))
                    before = digest(repo)
                    command(sys.executable, str(merge), "finalize", "--repo", str(repo))
                    self.assertEqual(before, digest(repo))
                    command(sys.executable, str(merge), "finalize", "--apply", "--repo", str(repo))
                    self.assertEqual(retained, tuple(path.read_bytes() for path in retained_paths))
                    command(sys.executable, str(installed), "check", "--repo", str(repo))
                    result = json.loads(command(sys.executable, str(merge), "inspect", "--repo", str(repo)))
                    self.assertTrue(result["up_to_date"])
                    self.assertIsNone(result["suggested_state"])
                    state = json.loads((record / "state.json").read_text())
                    state["status"] = "in_progress"
                    (record / "state.json").write_text(json.dumps(state) + "\n")
                    command(sys.executable, str(merge), "finalize", "--apply", "--repo", str(repo))
                    self.assertEqual(json.loads((record / "state.json").read_text())["status"], "complete")
        finally:
            trash = Path.home() / "trash"
            trash.mkdir(parents=True, exist_ok=True)
            workspace.rename(trash / f"ph-release-integration-{os.getpid()}-{time.time_ns()}")


if __name__ == "__main__":
    unittest.main()
