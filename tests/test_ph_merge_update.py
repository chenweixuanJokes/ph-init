#!/usr/bin/env python3
"""Fixture tests for ph_merge_update inspect/verify/finalize."""

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
SCAFFOLD = REPO_ROOT / "assets" / "scaffold"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ph_init  # noqa: E402
import ph_merge_update  # noqa: E402

TRASH_ROOT = Path.home() / "trash"
FIXED_SOURCE = ph_merge_update.FIXED_SOURCE
COMMIT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CURRENT, CURRENT_SCHEMA, TARGET_SKILLS_TUPLE = ph_merge_update.release_contract()
TARGET_SKILLS = list(TARGET_SKILLS_TUPLE)
BASE_SKILLS = list(ph_merge_update.BASE_SKILLS)
OLD_ALIASES = list(ph_merge_update.OLD_ALIASES)
NEW_INTENT = list(ph_merge_update.NEW_INTENT)
CHAIN_110 = [
    "intent-skill-names",
    "intent-lifecycle",
    "online-source",
    "merge-update",
    "schema-contract",
    "project-content",
    "intent-no-completed",
    "intent-legacy-inprogress",
    "init-docs-workflow",
    "docs-guidance",
    "docs-project-preserve",
    "adopt-plan-init",
    "adopt-existing-content",
    "init-report-coverage",
    "init-unified-entry",
    "plain-user-questions",
    "prepare-star-fork",
]
CHAIN_100 = ["intent-domain", *CHAIN_110]
CHAIN_112 = [
    "init-docs-workflow",
    "docs-guidance",
    "docs-project-preserve",
]


def run(argv, cwd=None):
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=60)


def copy_tree(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        src,
        dest,
        symlinks=False,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"),
    )


class MergeUpdateTests(unittest.TestCase):
    def setUp(self):
        self._temps = []
        self.receipt_patch = None

    def tearDown(self):
        if self.receipt_patch is not None:
            self.receipt_patch.stop()
        if not self._temps:
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        dest = TRASH_ROOT / f"ph-merge-update-{stamp}-{os.getpid()}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.mkdir(parents=True, exist_ok=False)
        for i, path in enumerate(self._temps):
            if Path(path).exists():
                Path(path).rename(dest / f"{i:02d}-{Path(path).name}")

    def temp_dir(self, prefix):
        root = Path(tempfile.mkdtemp(prefix=prefix))
        self._temps.append(root)
        return root

    def git_repo(self, prefix):
        root = self.temp_dir(prefix)
        for argv in (
            ["git", "init"],
            ["git", "config", "user.email", "t@example.com"],
            ["git", "config", "user.name", "ph-merge-test"],
        ):
            proc = run(argv, cwd=root)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        return root

    def write_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_skill(self, repo: Path, name: str) -> None:
        dest = repo / ".agents" / "skills" / name
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n# {name}\n", encoding="utf-8")

    def write_manifest(self, repo: Path, *, version="1.1.0", mode="portable", names=None, extra=None) -> dict:
        data = json.loads((SCAFFOLD / ".agents" / "ph.json").read_text(encoding="utf-8"))
        data["schema_version"] = version
        data["template_version"] = version
        data["adapter_mode"] = mode
        if mode == "symlink":
            data["adapters"]["root_agents"]["mode"] = "symlink"
            data["adapters"]["claude_entry"]["mode"] = "symlink"
            data["adapters"]["claude_skills"]["mode"] = "symlink"
            data["adapters"]["codex_skills"]["mode"] = "symlink"
        data["skills"]["required_names"] = list(names or NEW_INTENT and (BASE_SKILLS + NEW_INTENT))
        if extra:
            data.update(extra)
        self.write_json(repo / ".agents" / "ph.json", data)
        schema_src = SCAFFOLD / ".agents" / "ph.schema.json"
        (repo / ".agents" / "ph.schema.json").write_bytes(schema_src.read_bytes())
        return data

    def write_agents(self, repo: Path, text="# agents\nproject_fact: keep-me\n") -> None:
        path = repo / ".agents" / "AGENTS.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_intent_layout(self, repo: Path, *, pending=True, in_progress=False) -> None:
        _dirs, files = ph_merge_update.target_paths()
        for rel in files:
            dest = repo / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            src = SCAFFOLD / rel
            if rel.startswith("docs/意图/待办/") and src.is_file():
                dest.write_bytes(src.read_bytes())
            elif not dest.exists():
                dest.write_bytes(src.read_bytes() if src.is_file() else f"# {rel}\n".encode("utf-8"))
        if in_progress:
            legacy = repo / "docs/意图/进行中/新特性"
            legacy.mkdir(parents=True, exist_ok=True)
            (legacy / "INT-keep.md").write_text("# INT-keep\nuser body\n", encoding="utf-8")
        if not pending:
            return

    def seed_target_skills(self, repo: Path) -> None:
        for name in TARGET_SKILLS:
            if name == "ph-init":
                copy_tree(REPO_ROOT, repo / ".agents" / "skills" / "ph-init")
            else:
                src = SCAFFOLD / ".agents" / "skills" / name
                if src.is_dir():
                    copy_tree(src, repo / ".agents" / "skills" / name)
                else:
                    self.write_skill(repo, name)

    def seed_legacy_names(self, repo: Path) -> None:
        for name in BASE_SKILLS + OLD_ALIASES:
            self.write_skill(repo, name)

    def seed_v100(self, repo: Path) -> None:
        for name in BASE_SKILLS:
            self.write_skill(repo, name)

    def seed_adapters(self, repo: Path, mode: str, names) -> None:
        canonical = repo / ".agents" / "AGENTS.md"
        if mode == "portable":
            (repo / "AGENTS.md").write_bytes(canonical.read_bytes())
            (repo / "CLAUDE.md").write_text("@.agents/AGENTS.md\n", encoding="utf-8")
            for name in names:
                src = repo / ".agents" / "skills" / name
                if src.is_dir():
                    copy_tree(src, repo / ".claude" / "skills" / name)
                    copy_tree(src, repo / ".codex" / "skills" / name)
            return
        (repo / "AGENTS.md").symlink_to(".agents/AGENTS.md")
        (repo / "CLAUDE.md").symlink_to(".agents/AGENTS.md")
        for name in names:
            src = Path("../../.agents/skills") / name
            for vendor in (".claude", ".codex"):
                dest = repo / vendor / "skills" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(src)

    def seed_gitignore(self, repo: Path) -> None:
        (repo / ".gitignore").write_text("/.worktrees/\n", encoding="utf-8")

    def update_dir(self, repo: Path, version=None) -> Path:
        return repo / ".agents" / "updates" / (version or CURRENT)

    def receipt(self, version=None):
        version = version or CURRENT
        return {"version": version, "tag": f"v{version}", "commit": COMMIT, "source": FIXED_SOURCE}

    def install_receipt(self, verified=True, can_finalize=True, receipt=None, reason="ok"):
        payload = {
            "verified": verified,
            "can_finalize": can_finalize,
            "reason": reason,
            "receipt": receipt if receipt is not None else (self.receipt() if verified else None),
        }
        self.receipt_patch = mock.patch.object(ph_merge_update, "source_status", return_value=payload)
        self.receipt_patch.start()
        return payload

    def write_state(self, repo: Path, *, from_version="1.1.0", to_version=None, items=None, status="in_progress", receipt=None):
        to_version = to_version or CURRENT
        receipt = receipt or self.receipt()
        ids = items or CHAIN_110
        data = {
            "from_version": from_version,
            "to_version": to_version,
            "source": {"repository": FIXED_SOURCE, "tag": receipt["tag"], "commit": receipt["commit"]},
            "status": status,
            "items": [{"id": i, "status": "applied", "evidence": f"ok:{i}"} for i in ids],
        }
        dest = self.update_dir(repo, to_version)
        dest.mkdir(parents=True, exist_ok=True)
        self.write_json(dest / "state.json", data)
        (dest / "report.md").write_text("# report\nkept project_fact\n", encoding="utf-8")
        return data

    def invoke(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = ph_merge_update.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def load(self, stdout):
        return json.loads(stdout)

    def test_custom_pending_index_survives_finalize_and_completed_inspect(self):
        self.install_receipt()
        repo = self.fixture_110_current()
        self.write_state(repo)
        index = repo / "docs/意图/待办/新特性/README.md"
        custom = index.read_text(encoding="utf-8") + "\n[用户需求](INT-custom.md)\n"
        index.write_text(custom, encoding="utf-8")
        intent = index.parent / "INT-custom.md"
        intent.write_text("# 用户需求\n保留原文\n", encoding="utf-8")
        ph_merge_update.finalize_payload(repo, True)
        result = ph_merge_update.inspect_payload(repo)
        self.assertTrue(result["up_to_date"])
        self.assertFalse(result["can_finalize"])
        self.assertIsNone(result["suggested_state"])
        self.assertEqual(index.read_text(encoding="utf-8"), custom)
        self.assertEqual(intent.read_text(encoding="utf-8"), "# 用户需求\n保留原文\n")

    def test_docs_migration_from_112_preserves_project_content(self):
        self.install_receipt()
        repo = self.fixture_110_current()
        manifest_path = repo / ".agents/ph.json"
        manifest = json.loads(manifest_path.read_text())
        manifest.update(template_version="1.1.2", schema_version="1.1.1")
        self.write_json(manifest_path, manifest)
        retained = {}
        for rel, text in (
            ("docs/项目Wiki/项目概述.md", "# 已核验 Wiki\nsubagent 产物与人工定制\n"),
            ("docs/约束规范/后端规范/后端规范.md", "# 后端规范\n已批准项目例外\n"),
        ):
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            retained[path] = path.read_bytes()
        inspected = ph_merge_update.inspect_payload(repo)
        ids = [item["id"] for item in inspected["suggested_state"]["items"]]
        self.assertEqual(ids, ["init-docs-workflow", "docs-guidance", "docs-project-preserve",
                               "adopt-plan-init", "adopt-existing-content", "init-report-coverage",
                               "init-unified-entry", "plain-user-questions",
                               "prepare-star-fork"])
        state = self.write_state(repo, from_version="1.1.2", items=ids)
        before_manifest = manifest_path.read_bytes()
        for status in ("pending", "blocked"):
            state["items"][1]["status"] = status
            self.write_json(self.update_dir(repo) / "state.json", state)
            with self.assertRaises(ph_init.PHError):
                ph_merge_update.finalize_payload(repo, True)
            self.assertEqual(manifest_path.read_bytes(), before_manifest)
            self.assertEqual({p: p.read_bytes() for p in retained}, retained)
        state["items"][1]["status"] = "applied"
        self.write_json(self.update_dir(repo) / "state.json", state)
        ph_merge_update.finalize_payload(repo, True)
        self.assertTrue(ph_merge_update.inspect_payload(repo)["up_to_date"])
        ph_merge_update.finalize_payload(repo, True)
        self.assertEqual({p: p.read_bytes() for p in retained}, retained)

    def test_completed_inspect_rechecks_content(self):
        self.install_receipt()
        repo = self.fixture_110_current()
        self.write_state(repo)
        ph_merge_update.finalize_payload(repo, True)
        template = repo / "docs/意图/_模板.md"
        template.write_text("status_dir: 进行中/新特性\n", encoding="utf-8")
        with self.assertRaisesRegex(ph_init.PHError, "must default status_dir"):
            ph_merge_update.inspect_payload(repo)

    def fixture_110_current(self, mode="portable"):
        repo = self.git_repo(f"ph-merge-{mode}-")
        names = BASE_SKILLS + NEW_INTENT + ["ph-merge-update"]
        self.write_manifest(repo, mode=mode, names=names)
        self.write_agents(repo)
        self.seed_target_skills(repo)
        self.write_intent_layout(repo, in_progress=True)
        self.seed_adapters(repo, mode, names)
        self.seed_gitignore(repo)
        return repo

    def test_inspect_dev_tree_unverified_source(self):
        repo = self.git_repo("ph-merge-inspect-")
        self.write_manifest(repo, names=BASE_SKILLS + NEW_INTENT)
        self.write_agents(repo)
        for name in BASE_SKILLS + NEW_INTENT:
            self.write_skill(repo, name)
        code, out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 0, err)
        data = self.load(out)
        self.assertEqual(data["from"], "1.1.0")
        self.assertEqual(data["to"], CURRENT)
        self.assertEqual(data["profile"], "1.1.0-current-names")
        self.assertEqual([h["from"] for h in data["chain"]], [h["from"] for h in ph_merge_update.chain_between("1.1.0", CURRENT)])
        self.assertFalse(data["source"]["verified"])
        self.assertFalse(data["can_finalize"])
        self.assertIn("cannot finalize", data["source"]["reason"])
        self.assertEqual([i["id"] for i in data["suggested_state"]["items"]], CHAIN_110)
        self.assertEqual(data["suggested_state"]["status"], "in_progress")

    def test_inspect_identifies_legacy_and_v100(self):
        legacy = self.git_repo("ph-merge-legacy-")
        self.write_manifest(legacy, names=BASE_SKILLS + OLD_ALIASES)
        self.write_agents(legacy)
        self.seed_legacy_names(legacy)
        code, out, err = self.invoke("inspect", "--repo", str(legacy))
        self.assertEqual(code, 0, err)
        data = self.load(out)
        self.assertEqual(data["profile"], "1.1.0-legacy-names")
        self.assertEqual(data["from"], "1.1.0")
        self.assertEqual([i["id"] for i in data["suggested_state"]["items"]], CHAIN_110)

        v100 = self.git_repo("ph-merge-v100-")
        self.write_manifest(v100, version="1.0.0", names=BASE_SKILLS)
        self.write_agents(v100)
        self.seed_v100(v100)
        code, out, err = self.invoke("inspect", "--repo", str(v100))
        self.assertEqual(code, 0, err)
        data = self.load(out)
        self.assertEqual(data["profile"], "1.0.0")
        self.assertEqual(data["from"], "1.0.0")
        self.assertEqual([i["id"] for i in data["suggested_state"]["items"]], CHAIN_100)

    def test_inspect_lists_mixed_intent_names(self):
        repo = self.git_repo("ph-merge-mixed-")
        self.write_manifest(repo, names=BASE_SKILLS)
        self.write_agents(repo)
        for name in BASE_SKILLS + ["ph-intent-capture", "ph-intent-new"]:
            self.write_skill(repo, name)
        code, out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 0, err)
        data = self.load(out)
        self.assertEqual(data["from"], "1.1.0")
        self.assertEqual(data["profile"], "mixed-intent-names")
        self.assertTrue(data["conflicts"])
        self.assertFalse(data["can_finalize"])

    def test_inspect_unknown_layout_blocks(self):
        repo = self.git_repo("ph-merge-unknown-")
        self.write_manifest(repo, names=BASE_SKILLS)
        self.write_agents(repo)
        for name in BASE_SKILLS + ["ph-custom-extra"]:
            self.write_skill(repo, name)
        code, _out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("unknown PH skill layout", err)

    def test_inspect_rejects_skill_symlink(self):
        repo = self.git_repo("ph-merge-symlink-skill-")
        self.write_manifest(repo, names=BASE_SKILLS + NEW_INTENT)
        self.write_agents(repo)
        for name in BASE_SKILLS + NEW_INTENT:
            self.write_skill(repo, name)
        skill = repo / ".agents" / "skills" / "ph-intent-new" / "SKILL.md"
        outside = self.temp_dir("ph-merge-outside-") / "SKILL.md"
        outside.write_text("escaped\n", encoding="utf-8")
        skill.unlink()
        skill.symlink_to(outside)
        code, _out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertTrue("regular file" in err or "nested symlink" in err, err)

    def test_verify_blocks_pending_and_empty_evidence(self):
        repo = self.fixture_110_current()
        self.install_receipt()
        state = self.write_state(repo)
        state["items"][0]["status"] = "pending"
        self.write_json(self.update_dir(repo) / "state.json", state)
        code, _out, err = self.invoke("verify", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("intent-skill-names", err)

        state["items"][0]["status"] = "applied"
        state["items"][0]["evidence"] = "   "
        self.write_json(self.update_dir(repo) / "state.json", state)
        code, _out, err = self.invoke("verify", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("evidence", err)

    def test_verify_blocks_live_old_alias(self):
        repo = self.fixture_110_current()
        self.install_receipt()
        self.write_state(repo)
        dest = repo / ".claude" / "skills" / "ph-intent-capture"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text("# leftover alias\n", encoding="utf-8")
        code, _out, err = self.invoke("verify", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("old intent aliases still live", err)

    def test_finalize_dry_run_keeps_disk(self):
        repo = self.fixture_110_current("portable")
        self.install_receipt()
        self.write_state(repo)
        before = (repo / ".agents" / "ph.json").read_bytes()
        fact = (repo / ".agents" / "AGENTS.md").read_text(encoding="utf-8")
        legacy = (repo / "docs/意图/进行中/新特性/INT-keep.md").read_bytes()
        code, out, err = self.invoke("finalize", "--repo", str(repo))
        self.assertEqual(code, 0, err)
        data = self.load(out)
        self.assertFalse(data["apply"])
        self.assertFalse(data["complete"])
        self.assertEqual((repo / ".agents" / "ph.json").read_bytes(), before)
        self.assertIn("keep-me", (repo / ".agents" / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual((repo / "docs/意图/进行中/新特性/INT-keep.md").read_bytes(), legacy)
        self.assertEqual(json.loads((self.update_dir(repo) / "state.json").read_text())["status"], "in_progress")
        self.assertEqual(fact, (repo / ".agents" / "AGENTS.md").read_text(encoding="utf-8"))

    def test_finalize_apply_portable_and_recovery(self):
        repo = self.fixture_110_current("portable")
        self.install_receipt()
        self.write_state(repo)
        manifest = json.loads((repo / ".agents" / "ph.json").read_text(encoding="utf-8"))
        manifest["project_note"] = "keep-user-field"
        self.write_json(repo / ".agents" / "ph.json", manifest)
        code, out, err = self.invoke("finalize", "--apply", "--repo", str(repo))
        self.assertEqual(code, 0, err)
        data = self.load(out)
        self.assertTrue(data["complete"])
        written = json.loads((repo / ".agents" / "ph.json").read_text(encoding="utf-8"))
        self.assertEqual(written["template_version"], CURRENT)
        self.assertEqual(written["schema_version"], CURRENT_SCHEMA)
        self.assertEqual(written["adapter_mode"], "portable")
        self.assertEqual(written["project_note"], "keep-user-field")
        self.assertEqual(written["skills"]["required_names"], TARGET_SKILLS)
        self.assertEqual(json.loads((self.update_dir(repo) / "state.json").read_text())["status"], "complete")
        self.assertIn("keep-me", (repo / ".agents" / "AGENTS.md").read_text(encoding="utf-8"))

        # complete rerun must re-verify live files
        (repo / "docs/意图/待办/README.md").unlink()
        code, _out, err = self.invoke("verify", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("docs/意图/待办/README.md", err)

        # versions written, state not complete -> recover
        (repo / "docs/意图/待办/README.md").write_bytes((SCAFFOLD / "docs/意图/待办/README.md").read_bytes())
        state = json.loads((self.update_dir(repo) / "state.json").read_text())
        state["status"] = "in_progress"
        self.write_json(self.update_dir(repo) / "state.json", state)
        code, out, err = self.invoke("finalize", "--apply", "--repo", str(repo))
        self.assertEqual(code, 0, err)
        self.assertTrue(self.load(out)["complete"])

    def test_finalize_apply_symlink_mode(self):
        repo = self.fixture_110_current("symlink")
        self.install_receipt()
        self.write_state(repo)
        code, out, err = self.invoke("finalize", "--apply", "--repo", str(repo))
        self.assertEqual(code, 0, err)
        data = self.load(out)
        self.assertEqual(data["mode"], "symlink")
        written = json.loads((repo / ".agents" / "ph.json").read_text(encoding="utf-8"))
        self.assertEqual(written["adapter_mode"], "symlink")
        self.assertEqual(written["template_version"], CURRENT)
        self.assertTrue((repo / "AGENTS.md").is_symlink())

    def test_finalize_blocked_does_not_mark_complete(self):
        repo = self.fixture_110_current("portable")
        self.install_receipt()
        self.write_state(repo)
        original = (repo / ".agents" / "ph.json").read_bytes()

        def boom(*_a, **_k):
            raise ph_init.PHError("candidate check failed")

        with mock.patch.object(ph_merge_update, "cmd_check", side_effect=boom):
            with mock.patch.object(ph_merge_update, "cmd_sync", return_value=ph_init.Report("sync", "portable", False)):
                with mock.patch.object(ph_merge_update, "load_repo_manifest", return_value={}):
                    code, _out, err = self.invoke("finalize", "--apply", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("candidate check failed", err)
        self.assertEqual((repo / ".agents" / "ph.json").read_bytes(), original)
        self.assertEqual(json.loads((self.update_dir(repo) / "state.json").read_text())["status"], "in_progress")

    def test_finalize_without_receipt_is_blocked(self):
        repo = self.fixture_110_current()
        self.write_state(repo)
        code, _out, err = self.invoke("finalize", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("cannot finalize", err)
        self.assertEqual(json.loads((repo / ".agents" / "ph.json").read_text())["template_version"], "1.1.0")

    def test_inspect_does_not_call_locked_loader(self):
        repo = self.git_repo("ph-merge-noload-")
        self.write_manifest(repo, version="1.0.0", names=BASE_SKILLS)
        self.write_agents(repo)
        self.seed_v100(repo)

        def locked(*_a, **_k):
            raise AssertionError("inspect must not call load_repo_manifest")

        with mock.patch.object(ph_merge_update, "load_repo_manifest", side_effect=locked):
            code, out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 0, err)
        self.assertEqual(self.load(out)["from"], "1.0.0")

    def test_candidate_preserves_user_fields(self):
        data = {
            "schema_version": "1.1.0",
            "template_version": "1.1.0",
            "adapter_mode": "portable",
            "project_note": "keep",
            "skills": {"root": ".agents/skills", "required_names": BASE_SKILLS + NEW_INTENT},
        }
        cand = ph_merge_update.build_candidate(data, CURRENT, CURRENT_SCHEMA, tuple(TARGET_SKILLS))
        self.assertEqual(cand["project_note"], "keep")
        self.assertEqual(cand["adapter_mode"], "portable")
        self.assertEqual(cand["skills"]["required_names"], TARGET_SKILLS)
        self.assertEqual(data["template_version"], "1.1.0")
        self.assertEqual(data["skills"]["required_names"], BASE_SKILLS + NEW_INTENT)

    def test_inspect_uses_manifest_version_not_skill_guess(self):
        repo = self.git_repo("ph-merge-partial-")
        names = BASE_SKILLS + NEW_INTENT + ["ph-merge-update"]
        self.write_manifest(repo, version="1.0.0", names=names)
        self.write_agents(repo)
        self.seed_target_skills(repo)
        self.write_intent_layout(repo)
        code, out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 0, err)
        data = self.load(out)
        self.assertEqual(data["from"], "1.0.0")
        self.assertEqual(data["profile"], "1.1.0-current-names")
        self.assertEqual([i["id"] for i in data["suggested_state"]["items"]], CHAIN_100)
        self.assertFalse(data["up_to_date"])

    def test_inspect_complete_target_is_up_to_date(self):
        repo = self.git_repo("ph-merge-current-")
        names = TARGET_SKILLS
        self.write_manifest(repo, version=CURRENT, names=names, extra={"schema_version": CURRENT_SCHEMA})
        self.write_agents(repo)
        self.seed_target_skills(repo)
        self.write_intent_layout(repo)
        self.seed_adapters(repo, "portable", names)
        self.seed_gitignore(repo)
        code, out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 0, err)
        data = self.load(out)
        self.assertEqual(data["from"], CURRENT)
        self.assertEqual(data["to"], CURRENT)
        self.assertTrue(data["up_to_date"])
        self.assertIsNone(data["suggested_state"])
        self.assertFalse(data["can_finalize"])
        self.assertFalse((self.update_dir(repo) / "state.json").exists())

    def test_inspect_keeps_state_from_and_rejects_unrelated_disk_version(self):
        repo = self.git_repo("ph-merge-interrupt-")
        names = BASE_SKILLS + NEW_INTENT
        self.write_manifest(repo, version="1.0.0", names=names)
        self.write_agents(repo)
        for name in names:
            self.write_skill(repo, name)
        self.write_state(repo, from_version="1.1.0")
        code, out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("neither from", err)

        self.write_manifest(repo, version=CURRENT, names=names, extra={"schema_version": CURRENT_SCHEMA})
        code, out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 0, err)
        data = self.load(out)
        self.assertEqual(data["from"], "1.1.0")
        self.assertFalse(data["up_to_date"])
        self.assertEqual(data["existing_state"]["from_version"], "1.1.0")

    def test_inspect_unknown_version_must_be_on_chain(self):
        repo = self.git_repo("ph-merge-unknown-ver-")
        self.write_manifest(repo, version="1.2.0", names=BASE_SKILLS + NEW_INTENT)
        self.write_agents(repo)
        for name in BASE_SKILLS + NEW_INTENT:
            self.write_skill(repo, name)
        code, _out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertTrue("downgrade" in err or "missing migration chain" in err, err)

    def test_verify_blocks_mixed_names_before_retire(self):
        repo = self.fixture_110_current()
        self.install_receipt()
        self.write_state(repo)
        self.write_skill(repo, "ph-intent-capture")
        code, _out, err = self.invoke("verify", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("retire old intent aliases", err)

    def test_verify_requires_target_schema_and_runtime(self):
        repo = self.fixture_110_current()
        self.install_receipt()
        self.write_state(repo)
        (repo / ".agents" / "ph.schema.json").write_text("{}\n", encoding="utf-8")
        code, _out, err = self.invoke("verify", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("ph.schema.json", err)

        (repo / ".agents" / "ph.schema.json").write_bytes((SCAFFOLD / ".agents" / "ph.schema.json").read_bytes())
        (repo / ".agents" / "skills" / "ph-init" / "release.json").write_text(
            json.dumps({"version": "9.9.9", "schema_version": "9.9.9", "required_skills": TARGET_SKILLS}) + "\n",
            encoding="utf-8",
        )
        code, _out, err = self.invoke("verify", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("ph-init", err)

        (repo / ".agents" / "skills" / "ph-init" / "release.json").write_bytes((REPO_ROOT / "release.json").read_bytes())
        (repo / "docs/意图/_模板.md").write_text("status_dir: 进行中/新特性\n", encoding="utf-8")
        code, _out, err = self.invoke("verify", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("must default status_dir", err)

    def test_verify_surfaces_sync_plan_block(self):
        repo = self.fixture_110_current()
        self.install_receipt()
        self.write_state(repo)
        blocked = ph_init.Report("sync", "portable", False)
        blocked.add("conflict", "AGENTS.md", "destination is a symlink", ph_init.PROBLEM_DEST_SYMLINK)
        with mock.patch.object(ph_merge_update, "cmd_sync", return_value=blocked):
            code, _out, err = self.invoke("verify", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("candidate sync plan", err)
        self.assertIn("AGENTS.md", err)
        self.assertIn("symlink", err)

    def test_path_safety_rejects_docs_updates_and_index_escape(self):
        repo = self.git_repo("ph-merge-path-")
        self.write_manifest(repo, names=BASE_SKILLS + NEW_INTENT)
        self.write_agents(repo)
        for name in BASE_SKILLS + NEW_INTENT:
            self.write_skill(repo, name)
        outside = self.temp_dir("ph-merge-docs-out-")
        (outside / "docs").mkdir()
        (repo / "docs").symlink_to(outside / "docs")
        with self.assertRaises(ph_init.PHError) as ctx:
            ph_merge_update.assert_real_dir(repo, repo / "docs" / "意图" / "待办", "docs/意图/待办")
        self.assertIn("symlink", str(ctx.exception))

        in_repo_docs = repo / ".agents" / "docs-target"
        in_repo_docs.mkdir()
        linked_docs = repo / "docs-inrepo"
        linked_docs.symlink_to(in_repo_docs)
        with self.assertRaises(ph_init.PHError) as ctx:
            ph_merge_update.assert_real_dir(repo, linked_docs / "意图", "docs-inrepo/意图")
        self.assertIn("symlink", str(ctx.exception))

        updates_out = outside / "updates"
        updates_out.mkdir()
        (repo / ".agents" / "updates").symlink_to(updates_out)
        with self.assertRaises(ph_init.PHError) as ctx:
            ph_merge_update.updates_dir(repo, CURRENT)
        self.assertIn("symlink", str(ctx.exception))
        code, _out, err = self.invoke("inspect", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("error=", err)
        self.assertIn("symlink", err)

        hops = [{"from_version": "1.1.0", "to_version": "1.1.1", "path": "migrations/../release.json", "items": ["x"]}]
        with mock.patch.object(ph_merge_update, "read_json", side_effect=lambda path: {"format_version": 1, "migrations": hops} if path.name == "index.json" else ph_init.read_json(path)):
            with self.assertRaises(ph_init.PHError) as ctx:
                ph_merge_update.load_index()
        self.assertIn("path", str(ctx.exception))

        hops = [
            {"from_version": "1.0.0", "to_version": "1.1.0", "path": "migrations/1.0.0-to-1.1.0.md", "items": ["a"]},
            {"from_version": "1.1.0", "to_version": "1.0.0", "path": "migrations/1.1.0-to-1.1.1.md", "items": ["b"]},
        ]
        with mock.patch.object(ph_merge_update, "read_json", side_effect=lambda path: {"format_version": 1, "migrations": hops} if path.name == "index.json" else ph_init.read_json(path)):
            with self.assertRaises(ph_init.PHError) as ctx:
                ph_merge_update.load_index()
        self.assertTrue("increase" in str(ctx.exception) or "unique" in str(ctx.exception), str(ctx.exception))

    def test_dump_json_uses_unique_temp_and_trash_on_failure(self):
        dest = self.temp_dir("ph-merge-dump-") / "state.json"
        dest.write_text("{}\n", encoding="utf-8")
        seen = []
        real_mkstemp = tempfile.mkstemp

        def fake_mkstemp(prefix, suffix, dir):
            fd, name = real_mkstemp(prefix=prefix, suffix=suffix, dir=dir)
            seen.append(name)
            return fd, name

        with mock.patch.object(tempfile, "mkstemp", side_effect=fake_mkstemp):
            ph_merge_update.dump_json(dest, {"ok": True})
        self.assertTrue(seen)
        self.assertEqual(json.loads(dest.read_text())["ok"], True)
        self.assertTrue(Path(seen[0]).name.startswith(".state.json."))

        def fail_replace(*_a, **_k):
            raise OSError("replace failed")

        dest2 = self.temp_dir("ph-merge-dump-fail-") / "state.json"
        with mock.patch.object(os, "replace", side_effect=fail_replace):
            with self.assertRaises(OSError):
                ph_merge_update.dump_json(dest2, {"ok": False})
        leftovers = list(dest2.parent.glob(".state.json.*.tmp"))
        self.assertEqual(leftovers, [])

    def test_failed_regular_check_does_not_keep_complete(self):
        repo = self.fixture_110_current()
        self.install_receipt()
        self.write_state(repo, status="complete")
        original = (repo / ".agents" / "ph.json").read_bytes()
        ok = ph_init.Report("check", "portable", False)
        blocked = ph_init.Report("check", "portable", False)
        blocked.add("error", ".agents/ph.json", "regular check failed")
        calls = {"n": 0}

        def check(_repo, _mode, *, candidate=None):
            calls["n"] += 1
            return ok if candidate is not None else blocked

        with mock.patch.object(ph_merge_update, "cmd_check", side_effect=check):
            with mock.patch.object(ph_merge_update, "cmd_sync", return_value=ph_init.Report("sync", "portable", False)):
                with mock.patch.object(ph_merge_update, "load_repo_manifest", return_value={}):
                    code, _out, err = self.invoke("finalize", "--apply", "--repo", str(repo))
        self.assertEqual(code, 2)
        self.assertIn("regular check", err)
        self.assertEqual(json.loads((self.update_dir(repo) / "state.json").read_text())["status"], "in_progress")
        self.assertNotEqual((repo / ".agents" / "ph.json").read_bytes(), original)

    def test_source_receipt_requires_git_objects(self):
        fake_root = self.temp_dir("ph-merge-prepared-")
        receipt = self.receipt()
        (fake_root / ".ph-source.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        (fake_root / "release.json").write_text("{}\n", encoding="utf-8")
        with mock.patch.object(ph_merge_update, "SOURCE_ROOT", fake_root):
            status = ph_merge_update.source_status(CURRENT)
        self.assertFalse(status["verified"])
        self.assertIn("prepared git objects", status["reason"])

        workspace = self.temp_dir("ph-merge-workspace-")
        git_dir = workspace / "git"
        root = workspace / "root"
        git_dir.mkdir()
        copy_tree(REPO_ROOT, root)
        run(["git", "init", "--bare", "--template="], cwd=git_dir)
        (root / ".ph-source.json").write_text(json.dumps(self.receipt("9.9.9")) + "\n", encoding="utf-8")
        with mock.patch.object(ph_merge_update, "SOURCE_ROOT", root):
            status = ph_merge_update.source_status(CURRENT)
        self.assertFalse(status["verified"])

    def _seed_release_tree(self, root: Path, version=None) -> None:
        version = version or CURRENT
        files = {
            "release.json": json.dumps({"version": version}) + "\n",
            "SKILL.md": "# skill\n",
            "scripts/ph_init.py": "print(1)\n",
            "scripts/ph_release.py": "print(2)\n",
            "scripts/ph_merge_update.py": "print(3)\n",
            "migrations/index.json": '{"format_version":1,"migrations":[]}\n',
            "assets/scaffold/.agents/ph.json": "{}\n",
            "assets/scaffold/.agents/ph.schema.json": "{}\n",
            "assets/scaffold/docs/意图/_模板.md": "status_dir: 待办/新特性\n",
            "README.md": "extra\n",
        }
        for rel, text in files.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")

    def test_prepared_root_receipt_matches_bare_tree(self):
        workspace = self.temp_dir("ph-merge-prepared-ok-")
        src = workspace / "src"
        src.mkdir()
        self._seed_release_tree(src)
        for argv in (
            ["git", "init"],
            ["git", "config", "user.email", "t@example.com"],
            ["git", "config", "user.name", "ph-merge-test"],
        ):
            self.assertEqual(run(argv, cwd=src).returncode, 0)
        self.assertEqual(run(["git", "add", "."], cwd=src).returncode, 0)
        self.assertEqual(run(["git", "commit", "-m", f"v{CURRENT}"], cwd=src).returncode, 0)
        self.assertEqual(run(["git", "tag", f"v{CURRENT}"], cwd=src).returncode, 0)
        commit = run(["git", "rev-parse", "HEAD"], cwd=src).stdout.strip()
        git_dir = workspace / "git"
        cloned = run(["git", "clone", "--bare", "--template=", str(src), str(git_dir)])
        self.assertEqual(cloned.returncode, 0, cloned.stderr)
        root = workspace / "root"
        copy_tree(src, root)
        receipt = {"version": CURRENT, "tag": f"v{CURRENT}", "commit": commit, "source": FIXED_SOURCE}
        (root / ".ph-source.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        with mock.patch.object(ph_merge_update, "SOURCE_ROOT", root):
            status = ph_merge_update.source_status(CURRENT)
            self.assertTrue(status["verified"], status["reason"])
            (root / "assets/scaffold/docs/意图/_模板.md").write_text('status_dir: 已废弃\n', encoding="utf-8")
            status = ph_merge_update.source_status(CURRENT)
        self.assertFalse(status["verified"])
        self.assertIn("does not match commit", status["reason"])

    def test_development_root_receipt_matches_head_and_tag(self):
        src = self.git_repo("ph-merge-devsrc-")
        self._seed_release_tree(src)
        self.assertEqual(run(["git", "add", "."], cwd=src).returncode, 0)
        self.assertEqual(run(["git", "commit", "-m", f"v{CURRENT}"], cwd=src).returncode, 0)
        self.assertEqual(run(["git", "tag", f"v{CURRENT}"], cwd=src).returncode, 0)
        commit = run(["git", "rev-parse", "HEAD"], cwd=src).stdout.strip()
        receipt = {"version": CURRENT, "tag": f"v{CURRENT}", "commit": commit, "source": FIXED_SOURCE}
        (src / ".ph-source.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        with mock.patch.object(ph_merge_update, "SOURCE_ROOT", src):
            status = ph_merge_update.source_status(CURRENT)
            self.assertTrue(status["verified"], status["reason"])
            (src / "SKILL.md").write_text("# dirty\n", encoding="utf-8")
            status = ph_merge_update.source_status(CURRENT)
        self.assertFalse(status["verified"])
        self.assertIn("does not match commit", status["reason"])


if __name__ == "__main__":
    unittest.main()
