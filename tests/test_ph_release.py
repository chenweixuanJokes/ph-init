#!/usr/bin/env python3
"""Unit tests for the isolated PH release downloader."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ph_release  # noqa: E402


TRASH_ROOT = Path.home() / "trash"
FIXED_SOURCE = ph_release.FIXED_SOURCE
DEFAULT_SKILLS = [
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
REAL_MIGRATIONS = {
    "format_version": 1,
    "migrations": [
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
            "items": [
                "intent-skill-names",
                "intent-lifecycle",
                "online-source",
                "merge-update",
                "schema-contract",
                "project-content",
            ],
        },
    ],
}


def run(argv, cwd=None, env=None):
    return subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True, timeout=60)


class DictTransport(ph_release.GitTransport):
    def __init__(self, tags=None, trees=None, blobs=None, types=None, ls_error=None, fetch_error=None):
        self.tags = tags or {}
        self.trees = trees or {}
        self.blobs = blobs or {}
        self.types = types or {}
        self.ls_error = ls_error
        self.fetch_error = fetch_error
        self.ls_calls = []
        self.fetch_calls = []

    def ls_remote_tags(self, source):
        self.ls_calls.append(source)
        if self.ls_error is not None:
            raise self.ls_error
        lines = []
        for tag, commit in self.tags.items():
            if isinstance(commit, tuple):
                tag_obj, peeled = commit
                lines.append(f"{tag_obj}\trefs/tags/{tag}")
                lines.append(f"{peeled}\trefs/tags/{tag}^{{}}")
            else:
                lines.append(f"{commit}\trefs/tags/{tag}")
        return "\n".join(lines) + "\n"

    def fetch_commit(self, source, commit, dest):
        self.fetch_calls.append((source, commit, dest))
        if self.fetch_error is not None:
            raise self.fetch_error
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "HEAD").write_text(commit + "\n", encoding="utf-8")

    def object_type(self, git_dir, object_id):
        return self.types.get(object_id, "commit")

    def ls_tree(self, git_dir, commit):
        return self.trees[commit]

    def cat_file(self, git_dir, object_id):
        return self.blobs[object_id]


class PhReleaseTests(unittest.TestCase):
    def setUp(self):
        self._temps = []

    def tearDown(self):
        if not self._temps:
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        dest = TRASH_ROOT / f"ph-release-{stamp}-{os.getpid()}"
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
            ["git", "config", "user.name", "ph-release-test"],
        ):
            proc = run(argv, cwd=root)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        return root

    def blob(self, data: bytes) -> tuple[str, bytes]:
        return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest(), data

    def commit_id(self, seed: str) -> str:
        return hashlib.sha1(seed.encode()).hexdigest()

    def release_files(self, version="1.1.1", *, schema_version=None, skills=None, extra=None, mutate=None):
        schema_version = schema_version or version
        skills = list(skills or DEFAULT_SKILLS)
        release = {
            "format_version": 1,
            "version": version,
            "schema_version": schema_version,
            "repository": FIXED_SOURCE,
            "required_skills": skills,
        }
        manifest = {
            "schema_version": schema_version,
            "template_version": version,
            "skills": {"required_names": skills},
        }
        schema = {"$id": f"urn:ph:schema:project-harness:{schema_version}"}
        files = {
            "release.json": json.dumps(release, indent=2) + "\n",
            "SKILL.md": "# ph-init\n",
            "scripts/ph_init.py": "print('init')\n",
            "scripts/ph_release.py": "print('release')\n",
            "scripts/ph_merge_update.py": "print('merge')\n",
            "assets/scaffold/.agents/ph.json": json.dumps(manifest, indent=2) + "\n",
            "assets/scaffold/.agents/ph.schema.json": json.dumps(schema, indent=2) + "\n",
            "assets/scaffold/.agents/AGENTS.md": "# agents\n",
            "migrations/index.json": json.dumps(REAL_MIGRATIONS, indent=2) + "\n",
            "migrations/1.0.0-to-1.1.0.md": "# 1.0.0 to 1.1.0\n",
            "migrations/1.1.0-to-1.1.1.md": "# 1.1.0 to 1.1.1\n",
        }
        for name in skills:
            if name == "ph-init":
                continue
            files[f"assets/scaffold/.agents/skills/{name}/SKILL.md"] = f"# {name}\n"
        if extra:
            files.update(extra)
        if mutate:
            mutate(files)
        return files

    def tree_from_files(self, files):
        blobs = {}
        records = []
        for path, text in files.items():
            data = text.encode() if isinstance(text, str) else text
            object_id, raw = self.blob(data)
            blobs[object_id] = raw
            records.append(f"100644 blob {object_id}\t{path}")
        return "\0".join(records) + "\0", blobs

    def transport_for(self, files, version="1.1.1", extra_tags=None):
        commit = self.commit_id(f"v{version}")
        tree, blobs = self.tree_from_files(files)
        tags = {f"v{version}": commit}
        if extra_tags:
            tags.update(extra_tags)
        return DictTransport(tags=tags, trees={commit: tree}, blobs=blobs), commit

    def prepare(self, transport, version="latest", repo=None):
        parent = self.temp_dir("ph-release-work-")
        return ph_release.prepare_release(version, repo=repo, transport=transport, parent=parent)

    def test_parse_ls_remote_prefers_peeled_annotated_commit(self):
        tag_obj = self.commit_id("tag-object")
        commit = self.commit_id("peeled-commit")
        lightweight = self.commit_id("light")
        payload = (
            f"{tag_obj}\trefs/tags/v1.1.1\n"
            f"{commit}\trefs/tags/v1.1.1^{{}}\n"
            f"{lightweight}\trefs/tags/v1.0.0\n"
            f"{self.commit_id('rc')}\trefs/tags/v1.2.0-rc.1\n"
            f"{self.commit_id('other')}\trefs/tags/not-a-version\n"
        )
        tags = ph_release.parse_ls_remote_tags(payload)
        self.assertEqual(tags["v1.1.1"], commit)
        self.assertEqual(tags["v1.0.0"], lightweight)
        self.assertNotIn("v1.2.0-rc.1", tags)
        self.assertNotIn("not-a-version", tags)

    def test_latest_selects_numeric_max_stable_tag(self):
        tags = {
            "v1.9.9": self.commit_id("199"),
            "v1.10.0": self.commit_id("1100"),
            "v2.0.0": self.commit_id("200"),
        }
        tag, commit = ph_release.select_tag("latest", tags)
        self.assertEqual((tag, commit), ("v2.0.0", tags["v2.0.0"]))

    def test_explicit_version_and_unsupported_metadata(self):
        tags = {"v1.1.1": self.commit_id("111")}
        self.assertEqual(ph_release.select_tag("1.1.1", tags)[0], "v1.1.1")
        with self.assertRaises(ph_release.PHReleaseError):
            ph_release.select_tag("1.1.1-rc.1", tags)
        with self.assertRaises(ph_release.PHReleaseError):
            ph_release.select_tag("v1.1.1", tags)
        with self.assertRaises(ph_release.PHReleaseError):
            ph_release.select_tag("1.1.1", {})
        with self.assertRaises(ph_release.PHReleaseError):
            ph_release.select_tag("latest", {})

    def test_prepare_writes_receipt_and_json_fields(self):
        files = self.release_files()
        transport, commit = self.transport_for(files)
        prepared = self.prepare(transport, "latest")
        self.assertEqual(prepared.version, "1.1.1")
        self.assertEqual(prepared.tag, "v1.1.1")
        self.assertEqual(prepared.commit, commit)
        self.assertEqual(prepared.source, FIXED_SOURCE)
        self.assertTrue(prepared.root.is_dir())
        receipt = json.loads((prepared.root / ".ph-source.json").read_text(encoding="utf-8"))
        self.assertEqual(
            receipt,
            {
                "version": "1.1.1",
                "tag": "v1.1.1",
                "commit": commit,
                "source": FIXED_SOURCE,
            },
        )
        self.assertNotIn("root", receipt)
        self.assertTrue((prepared.root / "scripts/ph_init.py").is_file())
        self.assertTrue((prepared.root / "SKILL.md").is_file())
        self.assertTrue((prepared.root / "migrations/1.1.0-to-1.1.1.md").is_file())
        self.assertEqual(transport.ls_calls, [FIXED_SOURCE])
        self.assertEqual(transport.fetch_calls[0][:2], (FIXED_SOURCE, commit))

    def test_explicit_version_uses_matching_tag(self):
        files_old = self.release_files("1.1.0")
        files_new = self.release_files("1.1.1")
        old_commit = self.commit_id("v1.1.0")
        new_commit = self.commit_id("v1.1.1")
        old_tree, old_blobs = self.tree_from_files(files_old)
        new_tree, new_blobs = self.tree_from_files(files_new)
        blobs = {**old_blobs, **new_blobs}
        transport = DictTransport(
            tags={"v1.1.0": old_commit, "v1.1.1": new_commit},
            trees={old_commit: old_tree, new_commit: new_tree},
            blobs=blobs,
        )
        prepared = self.prepare(transport, "1.1.0")
        self.assertEqual(prepared.tag, "v1.1.0")
        self.assertEqual(prepared.commit, old_commit)
        self.assertEqual(
            json.loads((prepared.root / "release.json").read_text(encoding="utf-8"))["version"],
            "1.1.0",
        )

    def test_rejects_symlink_and_submodule_and_escaped_path(self):
        files = self.release_files()
        transport, commit = self.transport_for(files)
        blob_id = next(iter(transport.blobs))
        bad_trees = [
            f"120000 blob {blob_id}\tscripts/ph_init.py\0",
            f"160000 commit {self.commit_id('sub')}\tvendor/lib\0",
            f"100644 blob {blob_id}\t../escape.txt\0",
            f"100644 blob {blob_id}\tfoo/../../escape.txt\0",
        ]
        for tree in bad_trees:
            transport.trees[commit] = tree
            with self.assertRaises(ph_release.PHReleaseError):
                self.prepare(transport, "1.1.1")

    def test_rejects_mismatched_meta_and_missing_required_files(self):
        def mutate_repo(files):
            data = json.loads(files["release.json"])
            data["repository"] = "https://example.com/other.git"
            files["release.json"] = json.dumps(data)

        transport, _ = self.transport_for(self.release_files(mutate=mutate_repo))
        with self.assertRaises(ph_release.PHReleaseError):
            self.prepare(transport, "1.1.1")

        def mutate_format(files):
            data = json.loads(files["release.json"])
            data["format_version"] = "1"
            files["release.json"] = json.dumps(data)

        transport, _ = self.transport_for(self.release_files(mutate=mutate_format))
        with self.assertRaises(ph_release.PHReleaseError):
            self.prepare(transport, "1.1.1")

        def drop_script(files):
            del files["scripts/ph_merge_update.py"]

        transport, _ = self.transport_for(self.release_files(mutate=drop_script))
        with self.assertRaises(ph_release.PHReleaseError):
            self.prepare(transport, "1.1.1")

        def bad_migration(files):
            data = json.loads(files["migrations/index.json"])
            data["migrations"][0]["path"] = "../outside.md"
            files["migrations/index.json"] = json.dumps(data)

        def duplicate_from(files):
            data = json.loads(files["migrations/index.json"])
            data["migrations"].append(data["migrations"][0])
            files["migrations/index.json"] = json.dumps(data)

        transport, _ = self.transport_for(self.release_files(mutate=duplicate_from))
        with self.assertRaises(ph_release.PHReleaseError):
            self.prepare(transport, "1.1.1")

        def empty_items(files):
            data = json.loads(files["migrations/index.json"])
            data["migrations"][0]["items"] = []
            files["migrations/index.json"] = json.dumps(data)

        transport, _ = self.transport_for(self.release_files(mutate=empty_items))
        with self.assertRaises(ph_release.PHReleaseError):
            self.prepare(transport, "1.1.1")

        def old_from_to_keys(files):
            data = json.loads(files["migrations/index.json"])
            hop = data["migrations"][0]
            hop["from"] = hop.pop("from_version")
            hop["to"] = hop.pop("to_version")
            files["migrations/index.json"] = json.dumps(data)

        transport, _ = self.transport_for(self.release_files(mutate=old_from_to_keys))
        with self.assertRaises(ph_release.PHReleaseError):
            self.prepare(transport, "1.1.1")

        transport, _ = self.transport_for(self.release_files(mutate=bad_migration))
        with self.assertRaises(ph_release.PHReleaseError):
            self.prepare(transport, "1.1.1")

        def mismatch_manifest(files):
            data = json.loads(files["assets/scaffold/.agents/ph.json"])
            data["template_version"] = "9.9.9"
            files["assets/scaffold/.agents/ph.json"] = json.dumps(data)

        transport, _ = self.transport_for(self.release_files(mutate=mismatch_manifest))
        with self.assertRaises(ph_release.PHReleaseError):
            self.prepare(transport, "1.1.1")

        def extra_meta(files):
            data = json.loads(files["release.json"])
            data["channel"] = "nightly"
            files["release.json"] = json.dumps(data)

        transport, _ = self.transport_for(self.release_files(mutate=extra_meta))
        with self.assertRaises(ph_release.PHReleaseError):
            self.prepare(transport, "1.1.1")

    def test_network_failure_does_not_fallback(self):
        transport = DictTransport(
            ls_error=ph_release.PHReleaseError(
                f"network failure talking to {FIXED_SOURCE}: could not resolve host"
            )
        )
        with self.assertRaises(ph_release.PHReleaseError) as ctx:
            self.prepare(transport, "latest")
        self.assertIn("network failure", str(ctx.exception))
        self.assertEqual(transport.fetch_calls, [])

    def test_fetch_timeout_is_captured(self):
        files = self.release_files()
        transport, _ = self.transport_for(files)
        transport.fetch_error = ph_release.PHReleaseError(
            "git fetch --no-tags --depth=1 --no-recurse-submodules -- "
            f"{FIXED_SOURCE} abc timed out after 60s"
        )
        with self.assertRaises(ph_release.PHReleaseError) as ctx:
            self.prepare(transport, "1.1.1")
        self.assertIn("timed out", str(ctx.exception))

    def test_prepare_does_not_mutate_target_repo(self):
        target = self.git_repo("ph-release-target-")
        (target / "keep.txt").write_text("keep\n", encoding="utf-8")
        before = {}
        for dirpath, dirnames, filenames in os.walk(target, followlinks=False):
            dirnames[:] = [n for n in dirnames if n != ".git"]
            for name in filenames:
                path = Path(dirpath) / name
                before[str(path.relative_to(target))] = path.read_bytes()
        transport, _ = self.transport_for(self.release_files())
        prepared = self.prepare(transport, "latest", repo=str(target))
        after = {}
        for dirpath, dirnames, filenames in os.walk(target, followlinks=False):
            dirnames[:] = [n for n in dirnames if n != ".git"]
            for name in filenames:
                path = Path(dirpath) / name
                after[str(path.relative_to(target))] = path.read_bytes()
        self.assertEqual(before, after)
        self.assertFalse(str(prepared.root.resolve()).startswith(str(target.resolve()) + os.sep))

    def test_allocate_temp_root_stays_outside_target(self):
        target = self.git_repo("ph-release-outside-")
        root = ph_release.allocate_temp_root(target)
        self._temps.append(root)
        self.assertFalse(str(root.resolve()).startswith(str(target.resolve()) + os.sep))

    def test_parent_inside_target_is_rejected(self):
        target = self.git_repo("ph-release-inside-")
        transport, _ = self.transport_for(self.release_files())
        with self.assertRaises(ph_release.PHReleaseError):
            ph_release.prepare_release(
                "latest",
                repo=str(target),
                transport=transport,
                parent=target / "nested-download",
            )

    def test_safe_rel_path_allows_unicode_and_rejects_escape(self):
        self.assertTrue(ph_release.is_safe_rel_path("docs/意图/README.md"))
        self.assertFalse(ph_release.is_safe_rel_path("../outside"))
        self.assertFalse(ph_release.is_safe_rel_path("foo/../../x"))
        self.assertFalse(ph_release.is_safe_rel_path("/abs"))
        self.assertFalse(ph_release.is_safe_rel_path("C:windows"))
        self.assertFalse(ph_release.is_safe_rel_path("https://evil.example/x"))

    def test_cli_prepare_json_with_monkeypatched_transport(self):
        files = self.release_files()
        transport, commit = self.transport_for(files)
        parent = self.temp_dir("ph-release-cli-")
        original_ctor = ph_release.GitTransport
        original_alloc = ph_release.allocate_temp_root

        class Patched(DictTransport):
            def __init__(self):
                super().__init__(
                    tags=transport.tags,
                    trees=transport.trees,
                    blobs=transport.blobs,
                )

        ph_release.GitTransport = Patched
        ph_release.allocate_temp_root = lambda target: parent
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                code = ph_release.main(["prepare", "--version", "latest"])
        finally:
            ph_release.GitTransport = original_ctor
            ph_release.allocate_temp_root = original_alloc
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["version"], "1.1.1")
        self.assertEqual(data["tag"], "v1.1.1")
        self.assertEqual(data["commit"], commit)
        self.assertEqual(data["source"], FIXED_SOURCE)
        self.assertTrue(Path(data["root"]).is_dir())
        receipt = json.loads((Path(data["root"]) / ".ph-source.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["commit"], commit)
        self.assertNotIn("root", receipt)

    def test_cli_rejects_unsupported_version_without_network(self):
        proc = run([sys.executable, str(SCRIPTS / "ph_release.py"), "prepare", "--version", "1.1.1-rc.1"])
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unsupported version", proc.stderr)

    def test_no_public_source_argument(self):
        parser = ph_release._build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["prepare", "--version", "latest", "--source", "https://evil.example/x.git"])
        self.assertFalse(hasattr(ph_release.prepare_release, "source"))

    def test_real_git_fixture_materializes_commit(self):
        source = self.git_repo("ph-release-src-")
        files = self.release_files()
        for rel, text in files.items():
            path = source / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        for argv in (
            ["git", "add", "."],
            ["git", "commit", "-m", "v1.1.1"],
            ["git", "tag", "-a", "v1.1.1", "-m", "v1.1.1"],
        ):
            proc = run(argv, cwd=source)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        commit = run(["git", "rev-parse", "v1.1.1^{}"], cwd=source).stdout.strip()
        self.assertEqual(len(commit), 40)

        class LocalTransport(ph_release.GitTransport):
            def ls_remote_tags(self, source_url):
                if source_url != FIXED_SOURCE:
                    raise ph_release.PHReleaseError(f"unexpected source {source_url}")
                return run(["git", "ls-remote", "--tags", str(source)], cwd=source).stdout

            def fetch_commit(self, source_url, want, dest):
                if source_url != FIXED_SOURCE:
                    raise ph_release.PHReleaseError(f"unexpected source {source_url}")
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "FETCH_HEAD").write_text(want + "\n", encoding="utf-8")

            def object_type(self, git_dir, want):
                proc = run(["git", "cat-file", "-t", want], cwd=source)
                if proc.returncode != 0:
                    raise ph_release.PHReleaseError(proc.stderr or proc.stdout)
                return proc.stdout.strip()

            def ls_tree(self, git_dir, want):
                proc = run(["git", "ls-tree", "-r", "-z", "--full-tree", want], cwd=source)
                if proc.returncode != 0:
                    raise ph_release.PHReleaseError(proc.stderr or proc.stdout)
                return proc.stdout

            def cat_file(self, git_dir, object_id):
                proc = subprocess.run(
                    ["git", "cat-file", "blob", object_id],
                    cwd=source,
                    capture_output=True,
                    timeout=60,
                )
                if proc.returncode != 0:
                    raise ph_release.PHReleaseError(proc.stderr.decode("utf-8", errors="replace"))
                return proc.stdout

        prepared = self.prepare(LocalTransport(), "latest")
        self.assertEqual(prepared.commit, commit)
        self.assertEqual(
            json.loads((prepared.root / "release.json").read_text(encoding="utf-8"))["version"],
            "1.1.1",
        )
        self.assertTrue((prepared.root / "scripts/ph_release.py").is_file())
        self.assertFalse((prepared.root / ".git").exists())

    def test_schema_is_independent_of_release_version(self):
        files = self.release_files("1.1.1", schema_version="1.2.0")
        transport, _ = self.transport_for(files)
        prepared = self.prepare(transport, "1.1.1")
        meta = json.loads((prepared.root / "release.json").read_text(encoding="utf-8"))
        manifest = json.loads((prepared.root / "assets/scaffold/.agents/ph.json").read_text(encoding="utf-8"))
        schema = json.loads((prepared.root / "assets/scaffold/.agents/ph.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["version"], "1.1.1")
        self.assertEqual(meta["schema_version"], "1.2.0")
        self.assertEqual(manifest["schema_version"], "1.2.0")
        self.assertEqual(schema["$id"], "urn:ph:schema:project-harness:1.2.0")

    def test_future_1_1_2_can_add_skill_and_prepare(self):
        skills = [*DEFAULT_SKILLS, "ph-future-skill"]
        files = self.release_files("1.1.2", schema_version="1.1.1", skills=skills)
        transport, _ = self.transport_for(files, version="1.1.2")
        prepared = self.prepare(transport, "1.1.2")
        self.assertEqual(prepared.version, "1.1.2")
        self.assertTrue(
            (prepared.root / "assets/scaffold/.agents/skills/ph-future-skill/SKILL.md").is_file()
        )

    def test_real_repo_tree_validates_and_uses_real_migration_schema(self):
        version = json.loads((REPO_ROOT / "release.json").read_text(encoding="utf-8"))["version"]
        ph_release.validate_prepared_tree(REPO_ROOT, version)
        index = json.loads((REPO_ROOT / "migrations/index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["format_version"], 1)
        self.assertEqual(index["migrations"][0]["from_version"], "1.0.0")
        self.assertIn("items", index["migrations"][0])
        self.assertNotIn("from", index["migrations"][0])

    def test_semver_fullmatch_rejects_newline_and_leading_zero(self):
        self.assertIsNone(ph_release.SEMVER.fullmatch("1.1.1\n"))
        self.assertIsNone(ph_release.SEMVER.fullmatch("01.1.1"))
        self.assertIsNone(ph_release.SEMVER.fullmatch("1.01.1"))
        self.assertIsNotNone(ph_release.SEMVER.fullmatch("1.1.1"))
        with self.assertRaises(ph_release.PHReleaseError):
            ph_release.select_tag("01.1.1", {"v01.1.1": self.commit_id("bad")})
        with self.assertRaises(ph_release.PHReleaseError):
            ph_release.select_tag("1.1.1\n", {"v1.1.1": self.commit_id("nl")})

    def test_pinned_object_must_be_commit(self):
        files = self.release_files()
        transport, commit = self.transport_for(files)
        transport.types[commit] = "tree"
        with self.assertRaises(ph_release.PHReleaseError) as ctx:
            self.prepare(transport, "1.1.1")
        self.assertIn("not commit", str(ctx.exception))
        transport.types[commit] = "blob"
        with self.assertRaises(ph_release.PHReleaseError):
            self.prepare(transport, "1.1.1")

    def test_run_git_strips_config_overrides_and_redacts_credential(self):
        captured = {}

        def fake_run(cmd, cwd=None, env=None, **kwargs):
            captured["cwd"] = Path(cwd) if cwd is not None else None
            captured["env"] = env
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

        original = subprocess.run
        extra = {
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": "Authorization: Bearer secret",
            "GIT_DIR": "/tmp/evil.git",
            "GIT_WORK_TREE": "/tmp/evil-work",
            "GIT_COMMON_DIR": "/tmp/evil-common",
            "GIT_OBJECT_DIRECTORY": "/tmp/evil-objects",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/tmp/evil-alt",
            "https_proxy": "http://127.0.0.1:7897",
        }
        previous = {key: os.environ.get(key) for key in extra}
        os.environ.update(extra)
        subprocess.run = fake_run
        try:
            ph_release._run_git(None, "ls-remote", "--tags", "--", FIXED_SOURCE)
        finally:
            subprocess.run = original
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        env = captured["env"]
        self.assertNotIn("GIT_CONFIG_COUNT", env)
        self.assertNotIn("GIT_CONFIG_KEY_0", env)
        self.assertNotIn("GIT_DIR", env)
        self.assertNotIn("GIT_WORK_TREE", env)
        self.assertNotIn("GIT_COMMON_DIR", env)
        self.assertNotIn("GIT_OBJECT_DIRECTORY", env)
        self.assertNotIn("GIT_ALTERNATE_OBJECT_DIRECTORIES", env)
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(env["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(env["https_proxy"], "http://127.0.0.1:7897")
        self.assertEqual(captured["cwd"], Path(tempfile.gettempdir()))
        self.assertIn("credential.helper=", captured["cmd"])

        failed = subprocess.CompletedProcess(
            ["git"],
            1,
            stdout="",
            stderr="fatal: credential helper leaked token=abc",
        )
        subprocess.run = lambda *a, **k: failed
        try:
            with self.assertRaises(ph_release.PHReleaseError) as ctx:
                ph_release._run_git(Path(tempfile.gettempdir()), "fetch", "origin")
        finally:
            subprocess.run = original
        self.assertNotIn("credential", str(ctx.exception).lower())
        self.assertNotIn("token=", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
