#!/usr/bin/env python3
"""Create and deliver PH-managed Git worktrees without stash or force operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SESSION_FIELDS = {
    "schemaVersion",
    "sessionId",
    "createdAt",
    "mainPath",
    "sourceBranch",
    "sourceHead",
    "taskBranch",
    "taskPath",
    "phase",
    "verifyCommands",
    "maxChangedFileBytes",
}
SAFE_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")
SECRET_NAME = re.compile(
    r"(^|/)(\.env(?:\..*)?|id_(?:rsa|dsa|ecdsa|ed25519)|credentials?|secrets?)(?:$|/)|"
    r"\.(?:pem|key|p12|pfx|keystore|jks)$",
    re.IGNORECASE,
)
SECRET_CONTENT = re.compile(
    r"AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"(?i:(?:password|passwd|token|secret|api[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,})"
)
DEFAULT_MAX_CHANGED_FILE_BYTES = 10 * 1024 * 1024


class PHError(Exception):
    """A safe, user-actionable refusal."""


def run(
    cwd: Path,
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    # Read-only Git queries must not refresh the index during dry-run.
    merged_env["GIT_OPTIONAL_LOCKS"] = "0"
    if env:
        merged_env.update(env)
    proc = subprocess.run(
        list(args),
        cwd=cwd,
        text=True,
        capture_output=True,
        env=merged_env,
    )
    if check and proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise PHError(f"command failed ({' '.join(args)}): {detail}")
    return proc


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(cwd, "git", *args, check=check)


def git_root(path: Path) -> Path:
    proc = git(path, "rev-parse", "--show-toplevel", check=False)
    if proc.returncode != 0:
        raise PHError(f"not a Git worktree: {path}")
    return Path(proc.stdout.strip()).resolve()


def worktrees(repo: Path) -> list[dict[str, str]]:
    proc = git(repo, "worktree", "list", "--porcelain")
    rows: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in proc.stdout.splitlines() + [""]:
        if not line:
            if current:
                rows.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return rows


def main_worktree(repo: Path) -> Path:
    rows = worktrees(repo)
    if not rows:
        raise PHError("Git reported no worktrees")
    return Path(rows[0]["worktree"]).resolve()


def current_branch(repo: Path) -> str:
    proc = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise PHError("detached HEAD is not supported")
    return proc.stdout.strip()


def current_head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def git_path(repo: Path, name: str) -> Path:
    raw = git(repo, "rev-parse", "--git-path", name).stdout.strip()
    path = Path(raw)
    return path if path.is_absolute() else (repo / path).resolve()


def ensure_no_operation(repo: Path) -> None:
    markers = (
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "rebase-merge",
        "rebase-apply",
    )
    active = [name for name in markers if git_path(repo, name).exists()]
    if active:
        raise PHError(f"Git operation already in progress: {', '.join(active)}")
    if git(repo, "ls-files", "-u", check=False).stdout:
        raise PHError("unmerged index entries exist")


def change_sets(repo: Path) -> tuple[list[str], list[str], list[str]]:
    def names(*args: str) -> list[str]:
        out = git(repo, *args).stdout
        return sorted({part for part in out.split("\0") if part})

    staged = names("diff", "--cached", "--name-only", "-z")
    unstaged = names("diff", "--name-only", "-z")
    untracked = names("ls-files", "--others", "--exclude-standard", "-z")
    return staged, unstaged, untracked


def ensure_clean(repo: Path, label: str) -> None:
    staged, unstaged, untracked = change_sets(repo)
    if staged or unstaged or untracked:
        raise PHError(
            f"{label} is not clean; staged={staged}, unstaged={unstaged}, "
            f"untracked={untracked}. PH never stashes or discards them."
        )


def ensure_main_repo(repo: Path) -> Path:
    root = git_root(repo)
    main = main_worktree(root)
    if root != main:
        raise PHError(f"enter must run from the main worktree: {main}")
    if git(root, "rev-parse", "--is-bare-repository").stdout.strip() == "true":
        raise PHError("bare repositories are not supported")
    if (root / ".gitmodules").exists():
        raise PHError("superprojects with submodules are not supported by PH worktree automation")
    return root


def validate_branch(repo: Path, branch: str) -> None:
    if not SAFE_BRANCH.fullmatch(branch) or not branch.isascii():
        raise PHError("branch must use ASCII letters, numbers, '.', '_', '-', and '/' only")
    proc = git(repo, "check-ref-format", "--branch", branch, check=False)
    if proc.returncode != 0:
        raise PHError(f"invalid branch name: {branch}")


def branch_exists(repo: Path, branch: str) -> bool:
    return git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0


def occupied_branches(repo: Path) -> dict[str, str]:
    occupied: dict[str, str] = {}
    for row in worktrees(repo):
        ref = row.get("branch", "")
        if ref.startswith("refs/heads/"):
            occupied[ref.removeprefix("refs/heads/")] = row["worktree"]
    return occupied


def require_local_path(main: Path, path: Path) -> Path:
    """Reject redirected path components before resolving a PH-managed path."""

    main = main.resolve()
    try:
        parts = path.absolute().relative_to(main).parts
    except ValueError as exc:
        raise PHError(f"PH path is outside the main worktree: {path}") from exc
    current = main
    for part in parts:
        if part in {"..", "."}:
            raise PHError(f"unsafe PH path component: {path}")
        current = current / part
        junction = getattr(current, "is_junction", lambda: False)()
        if current.is_symlink() or junction:
            raise PHError(f"PH path must not contain a symlink or junction: {current}")
    try:
        current.resolve().relative_to(main)
    except ValueError as exc:
        raise PHError(f"PH path resolves outside the main worktree: {path}") from exc
    return current


def managed_root(main: Path) -> Path:
    root = require_local_path(main, main / ".worktrees")
    if root.exists() and not root.is_dir():
        raise PHError(".worktrees must be a real directory")
    return root


@contextmanager
def delivery_lock(main: Path):
    """Serialize PH mutations sharing a main worktree, without a stale-lock takeover."""

    path = git_path(main, "ph-delivery.lock")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise PHError(
            f"another PH delivery owns {path}; if it crashed, verify the owner has stopped "
            "before manually archiving this lock"
        ) from exc
    try:
        owner = {"pid": os.getpid(), "createdAt": datetime.now(timezone.utc).isoformat()}
        os.write(descriptor, json.dumps(owner).encode("utf-8"))
        yield
    finally:
        os.close(descriptor)
        path.unlink()


def safe_task_path(main: Path, branch: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "--", branch).strip("-.").lower() or "task"
    slug = slug[:80].rstrip("-.")
    suffix = hashlib.sha256(branch.encode("utf-8")).hexdigest()[:8]
    root = managed_root(main)
    target = require_local_path(main, root / f"{slug}--{suffix}")
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise PHError("computed worktree path escapes .worktrees") from exc
    return target


def ensure_ignored(main: Path) -> None:
    probe = ".worktrees/.ph-ignore-probe"
    if git(main, "check-ignore", "--quiet", probe, check=False).returncode != 0:
        raise PHError(".worktrees/ is not ignored; run ph-init before creating a worktree")


def session_dirs(main: Path) -> tuple[Path, Path]:
    root = managed_root(main) / ".ph"
    sessions = require_local_path(main, root / "sessions")
    completed = require_local_path(main, root / "completed")
    for path in (root, sessions, completed):
        if path.exists() and not path.is_dir():
            raise PHError(f"PH state path must be a directory: {path}")
    return sessions, completed


def save_session(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load_session(linked: Path) -> tuple[Path, dict[str, Any]]:
    main = main_worktree(linked)
    sessions, _ = session_dirs(main)
    matches: list[tuple[Path, dict[str, Any]]] = []
    if sessions.is_dir():
        for path in sessions.glob("*.json"):
            require_local_path(main, path)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PHError(f"cannot recover corrupt PH session {path}: {exc}") from exc
            if not isinstance(data, dict):
                raise PHError(f"PH session must be a JSON object: {path}")
            if Path(str(data.get("taskPath", ""))).resolve() == linked.resolve():
                matches.append((path, data))
    if len(matches) != 1:
        raise PHError(f"expected one PH session for {linked}, found {len(matches)}")
    path, data = matches[0]
    missing = sorted(SESSION_FIELDS - data.keys())
    if missing:
        raise PHError(f"session is missing fields: {', '.join(missing)}")
    return path, data


def load_worktree_policy(main: Path) -> tuple[list[list[str]], int]:
    path = main / ".agents" / "ph.json"
    if not path.is_file():
        return [], DEFAULT_MAX_CHANGED_FILE_BYTES
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PHError(f"invalid .agents/ph.json: {exc}") from exc
    worktree = manifest.get("worktree", {})
    commands = worktree.get("verify_commands", [])
    if not isinstance(commands, list) or any(
        not isinstance(command, list)
        or not command
        or any(not isinstance(arg, str) or not arg for arg in command)
        for command in commands
    ):
        raise PHError("worktree.verify_commands must be an array of non-empty argv arrays")
    limit = worktree.get("max_changed_file_bytes", DEFAULT_MAX_CHANGED_FILE_BYTES)
    if not isinstance(limit, int) or limit < 1:
        raise PHError("worktree.max_changed_file_bytes must be a positive integer")
    return commands, limit


def session_policy(data: dict[str, Any]) -> tuple[list[list[str]], int]:
    commands = data.get("verifyCommands")
    limit = data.get("maxChangedFileBytes")
    if not isinstance(commands, list) or any(
        not isinstance(command, list)
        or not command
        or any(not isinstance(arg, str) or not arg for arg in command)
        for command in commands
    ):
        raise PHError("session verifyCommands are invalid")
    if not isinstance(limit, int) or limit < 1:
        raise PHError("session maxChangedFileBytes is invalid")
    return commands, limit


def worktree_state_digest(repo: Path) -> str:
    """Fingerprint all non-ignored Git-visible state around a verification run."""

    digest = hashlib.sha256()
    commands = (
        ("rev-parse", "HEAD"),
        ("symbolic-ref", "--quiet", "HEAD"),
        ("ls-files", "--stage", "-z"),
        ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        ("diff", "--binary", "--no-ext-diff", "--no-textconv"),
        ("diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv"),
    )
    for args in commands:
        proc = git(repo, *args, check=False)
        if proc.returncode and args[0] != "symbolic-ref":
            raise PHError("cannot snapshot Git-visible state: " + proc.stderr.strip())
        digest.update(str(proc.returncode).encode("ascii") + b"\0")
        digest.update(proc.stdout.encode("utf-8") + b"\0")
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z").stdout
    for rel in sorted(part for part in untracked.split("\0") if part):
        path = repo / rel
        digest.update(rel.encode("utf-8") + b"\0")
        if path.is_symlink():
            digest.update(b"link:" + os.fsencode(os.readlink(path)))
        elif path.is_file():
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            raise PHError(f"cannot fingerprint untracked path: {rel}")
        digest.update(b"\0")
    return digest.hexdigest()


def run_verification(repo: Path, commands: list[list[str]], phase: str) -> None:
    before = worktree_state_digest(repo)
    for command in commands:
        proc = run(repo, *command, check=False)
        if proc.returncode != 0:
            detail = proc.stderr.strip() or proc.stdout.strip()
            raise PHError(f"{phase} verification failed ({' '.join(command)}): {detail}")
    if worktree_state_digest(repo) != before:
        raise PHError(
            f"{phase} verification changed Git-visible files; inspect those changes before delivery"
        )


def risky_changes(
    repo: Path,
    paths: list[str],
    size_limit: int,
    staged: bool,
) -> list[str]:
    risks: list[str] = []
    for rel in sorted(set(paths)):
        normalized = rel.replace("\\", "/")
        if SECRET_NAME.search(normalized):
            risks.append(f"secret-like path: {rel}")
        path = repo / rel
        if path.is_file() and path.stat().st_size > size_limit:
            risks.append(f"large file ({path.stat().st_size} bytes): {rel}")
    diff_args = ["diff"]
    if staged:
        diff_args.append("--cached")
    diff_args.extend(["--no-ext-diff", "--unified=0", "--", *paths])
    diff = git(repo, *diff_args, check=False).stdout
    added = "\n".join(
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    if SECRET_CONTENT.search(added):
        risks.append("secret-like value in added content")
    return risks


def commit_task(linked: Path, message: str | None, size_limit: int, apply: bool) -> tuple[str, list[str]]:
    staged, unstaged, untracked = change_sets(linked)
    if not (staged or unstaged or untracked):
        return "clean", []
    if untracked:
        raise PHError(f"untracked files require an explicit user decision: {untracked}")
    if staged and unstaged:
        raise PHError(
            "staged and unstaged changes coexist; PH preserves partial staging and requires the user to choose"
        )
    changed = staged or unstaged
    risks = risky_changes(linked, changed, size_limit, staged=bool(staged))
    if risks:
        raise PHError("unsafe commit candidate: " + "; ".join(risks))
    if not message:
        raise PHError("a commit message is required when exit must create a commit")
    if not apply:
        return ("commit-staged" if staged else "stage-tracked-and-commit"), changed
    if unstaged:
        git(linked, "add", "-u", "--")
    proc = git(linked, "commit", "-m", message, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise PHError(f"commit failed; hooks and signing were not bypassed: {detail}")
    return "committed", changed


def validate_session_identity(linked: Path, data: dict[str, Any]) -> tuple[Path, str]:
    task_path = Path(data["taskPath"]).resolve()
    if linked.resolve() != task_path:
        raise PHError("current worktree does not match session taskPath")
    task_branch = current_branch(linked)
    if task_branch != data["taskBranch"]:
        raise PHError(f"task branch changed: expected {data['taskBranch']}, got {task_branch}")
    main = Path(data["mainPath"]).resolve()
    if main_worktree(linked) != main or not main.is_dir():
        raise PHError("session mainPath no longer matches Git's main worktree")
    validate_branch(main, task_branch)
    if require_local_path(main, Path(data["taskPath"])) != safe_task_path(main, task_branch):
        raise PHError("session task path is not the canonical PH worktree path")
    if data.get("phase") != "entered":
        ensure_clean(linked, "task worktree after session commit")
        task_head = data.get("taskHead")
        if not task_head or current_head(linked) != task_head:
            raise PHError("task HEAD changed after the session commit; start a new delivery decision")
    return main, task_branch


def validate_merge_target(main: Path, data: dict[str, Any]) -> None:
    if current_branch(main) != data["sourceBranch"]:
        raise PHError(
            f"source branch changed: expected {data['sourceBranch']}, got {current_branch(main)}"
        )
    ensure_clean(main, "source worktree")
    ensure_no_operation(main)
    if git(main, "merge-base", "--is-ancestor", data["sourceHead"], "HEAD", check=False).returncode != 0:
        raise PHError("source history was rewritten; enter-time sourceHead is no longer an ancestor")


def perform_merge(main: Path, data: dict[str, Any], session_path: Path) -> str:
    task_branch = data["taskBranch"]
    if git(main, "merge-base", "--is-ancestor", task_branch, "HEAD", check=False).returncode == 0:
        data["phase"] = "merged_unverified"
        save_session(session_path, data)
        return "already-contained"
    proc = git(
        main,
        "-c",
        "merge.autoStash=false",
        "merge",
        task_branch,
        check=False,
    )
    if proc.returncode != 0:
        if git_path(main, "MERGE_HEAD").exists():
            data["phase"] = "merge_conflict"
            save_session(session_path, data)
            raise PHError("merge conflict preserved; resolve and run continue, or run abort-merge")
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise PHError(f"merge failed without a resumable conflict: {detail}")
    data["phase"] = "merged_unverified"
    save_session(session_path, data)
    return "merged"


def validate_merged_target(main: Path, data: dict[str, Any]) -> None:
    if current_branch(main) != data["sourceBranch"]:
        raise PHError("source branch changed after merge; refusing to verify a different branch")
    ensure_no_operation(main)
    ensure_clean(main, "source worktree before post-merge verification")
    if git(
        main,
        "merge-base",
        "--is-ancestor",
        data["taskBranch"],
        "HEAD",
        check=False,
    ).returncode != 0:
        raise PHError("source branch no longer contains the delivered task branch")


def complete_verification(
    main: Path,
    data: dict[str, Any],
    session_path: Path,
    commands: list[list[str]],
) -> None:
    validate_merged_target(main, data)
    merged_head = current_head(main)
    run_verification(main, commands, "post-merge")
    validate_merged_target(main, data)
    if current_head(main) != merged_head:
        raise PHError("post-merge verification changed the source HEAD")
    data["phase"] = "merged"
    data["mergedHead"] = merged_head
    save_session(session_path, data)


def cleanup_session(main: Path, linked: Path, data: dict[str, Any], session_path: Path) -> None:
    if data.get("phase") != "merged":
        raise PHError("cleanup requires a successfully merged and verified session")
    validate_session_identity(linked, data)
    validate_merged_target(main, data)
    verified_head = data.get("mergedHead")
    if not verified_head or git(main, "merge-base", "--is-ancestor", verified_head, "HEAD", check=False).returncode:
        raise PHError("source history no longer contains the verified merge")
    ensure_no_operation(linked)
    ensure_clean(linked, "task worktree")
    ignored = git(linked, "ls-files", "--others", "--ignored", "--exclude-standard", "-z").stdout
    ignored_paths = [part for part in ignored.split("\0") if part]
    if ignored_paths:
        raise PHError(
            f"cleanup blocked by ignored files: {ignored_paths}. Preserve local data outside "
            "the worktree and review disposable artifacts before requesting cleanup again."
        )
    registered = {Path(row["worktree"]).resolve() for row in worktrees(main)}
    if linked.resolve() not in registered or linked.resolve() == main.resolve():
        raise PHError("cleanup target is not the registered linked worktree from this session")
    proc = git(main, "worktree", "remove", str(linked), check=False)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise PHError(f"safe worktree removal failed; PH will not force it: {detail}")
    data["phase"] = "cleaned"
    save_session(session_path, data)
    _, completed = session_dirs(main)
    completed.mkdir(parents=True, exist_ok=True)
    session_path.replace(completed / session_path.name)


def command_enter(args: argparse.Namespace) -> dict[str, Any]:
    main = ensure_main_repo(Path(args.repo).resolve())
    managed_root(main)
    session_dirs(main)
    ensure_no_operation(main)
    ensure_clean(main, "source worktree")
    ensure_ignored(main)
    validate_branch(main, args.branch)
    exists = branch_exists(main, args.branch)
    if exists != args.existing:
        if exists:
            raise PHError("branch already exists; pass --existing to reuse it")
        raise PHError("--existing was passed but the branch does not exist")
    occupied = occupied_branches(main)
    if args.branch in occupied:
        raise PHError(f"branch is already checked out at {occupied[args.branch]}")
    target = safe_task_path(main, args.branch)
    if target.exists():
        raise PHError(f"target path already exists: {target}")
    source_branch = current_branch(main)
    source_head = current_head(main)
    verify_commands, max_changed_file_bytes = load_worktree_policy(main)
    plan = {
        "action": "enter",
        "apply": args.apply,
        "mainPath": str(main),
        "sourceBranch": source_branch,
        "sourceHead": source_head,
        "taskBranch": args.branch,
        "taskPath": str(target),
        "existingBranch": exists,
        "verifyCommands": verify_commands,
        "maxChangedFileBytes": max_changed_file_bytes,
    }
    if not args.apply:
        return plan
    target.parent.mkdir(parents=True, exist_ok=True)
    if exists:
        git(main, "worktree", "add", str(target), args.branch)
    else:
        git(main, "worktree", "add", "-b", args.branch, str(target), source_head)
    session_id = str(uuid.uuid4())
    session = {
        "schemaVersion": 1,
        "sessionId": session_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "mainPath": str(main),
        "sourceBranch": source_branch,
        "sourceHead": source_head,
        "taskBranch": args.branch,
        "taskPath": str(target),
        "phase": "entered",
        "verifyCommands": verify_commands,
        "maxChangedFileBytes": max_changed_file_bytes,
    }
    sessions, _ = session_dirs(main)
    save_session(sessions / f"{session_id}.json", session)
    plan["sessionId"] = session_id
    plan["status"] = "created"
    return plan


def command_exit(args: argparse.Namespace) -> dict[str, Any]:
    linked = git_root(Path(args.repo).resolve())
    session_path, data = load_session(linked)
    main, _ = validate_session_identity(linked, data)
    commands, size_limit = session_policy(data)
    phase = data["phase"]
    result: dict[str, Any] = {"action": "exit", "apply": args.apply, "phase": phase}

    if not args.apply:
        if args.cleanup and phase != "merged":
            raise PHError("cleanup must be a separate call after the session is merged and verified")
        if phase == "entered":
            ensure_no_operation(linked)
            result["commit"], result["files"] = commit_task(linked, args.message, size_limit, False)
            validate_merge_target(main, data)
        elif phase == "committed":
            validate_merge_target(main, data)
        elif phase in {"merged_unverified", "merge_verify_failed", "merged"}:
            validate_merged_target(main, data)
        else:
            raise PHError(f"cannot plan exit from {phase}; use continue or abort-merge for conflicts")
        result["mergeTarget"] = f"{data['mainPath']}:{data['sourceBranch']}"
        result["verifyCommands"] = commands
        result["cleanupPlanned"] = bool(args.cleanup)
        return result

    if args.cleanup and phase != "merged":
        raise PHError(
            "cleanup must be a separate call after exit has merged and verified the session"
        )
    if phase == "merge_conflict":
        raise PHError("a merge conflict is active; use continue or abort-merge")
    if phase == "entered":
        ensure_no_operation(linked)
        run_verification(linked, commands, "pre-merge")
        commit_action, files = commit_task(linked, args.message, size_limit, args.apply)
        result["commit"] = commit_action
        result["files"] = files
        data["phase"] = "committed"
        data["taskHead"] = current_head(linked)
        save_session(session_path, data)
        phase = "committed"

    if phase == "committed":
        validate_merge_target(main, data)
        merge_action = perform_merge(main, data, session_path)
        result["merge"] = merge_action
        phase = data["phase"]

    if phase in {"merged_unverified", "merge_verify_failed"}:
        try:
            complete_verification(main, data, session_path, commands)
        except PHError:
            data["phase"] = "merge_verify_failed"
            save_session(session_path, data)
            raise
        phase = "merged"

    if phase == "merged":
        result["status"] = "merged"
        if args.cleanup:
            if not args.apply:
                result["cleanupPlanned"] = True
            else:
                cleanup_session(main, linked, data, session_path)
                result["status"] = "cleaned"
        else:
            result["cleanupRequiredConfirmation"] = True
        return result
    raise PHError(f"unsupported session phase for exit: {phase}")


def command_continue(args: argparse.Namespace) -> dict[str, Any]:
    linked = git_root(Path(args.repo).resolve())
    session_path, data = load_session(linked)
    main, _ = validate_session_identity(linked, data)
    if data["phase"] != "merge_conflict" or not git_path(main, "MERGE_HEAD").exists():
        raise PHError("no PH merge conflict is ready to continue")
    if git(main, "ls-files", "-u", check=False).stdout:
        raise PHError("unresolved merge entries remain")
    if not args.apply:
        return {"action": "continue", "apply": False, "mainPath": str(main)}
    proc = run(
        main,
        "git",
        "-c",
        "merge.autoStash=false",
        "merge",
        "--continue",
        check=False,
        env={"GIT_EDITOR": "true"},
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise PHError(f"merge --continue failed: {detail}")
    data["phase"] = "merged_unverified"
    save_session(session_path, data)
    commands, _ = session_policy(data)
    try:
        complete_verification(main, data, session_path, commands)
    except PHError:
        data["phase"] = "merge_verify_failed"
        save_session(session_path, data)
        raise
    result = {"action": "continue", "apply": True, "status": "merged"}
    result["cleanupRequiredConfirmation"] = True
    return result


def command_abort(args: argparse.Namespace) -> dict[str, Any]:
    linked = git_root(Path(args.repo).resolve())
    session_path, data = load_session(linked)
    main, _ = validate_session_identity(linked, data)
    if data["phase"] != "merge_conflict" or not git_path(main, "MERGE_HEAD").exists():
        raise PHError("no PH merge conflict is active")
    if not args.apply:
        return {"action": "abort-merge", "apply": False, "mainPath": str(main)}
    git(main, "merge", "--abort")
    data["phase"] = "committed"
    save_session(session_path, data)
    return {"action": "abort-merge", "apply": True, "status": "aborted", "phase": "committed"}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="PH worktree lifecycle")
    sub = root.add_subparsers(dest="command", required=True)

    enter = sub.add_parser("enter", help="Plan or create a PH linked worktree")
    enter.add_argument("--repo", required=True)
    enter.add_argument("--branch", required=True)
    enter.add_argument("--existing", action="store_true")
    enter.add_argument("--apply", action="store_true")

    exit_cmd = sub.add_parser("exit", help="Verify, commit, merge, and optionally clean a PH worktree")
    exit_cmd.add_argument("--repo", required=True)
    exit_cmd.add_argument("--message")
    exit_cmd.add_argument("--cleanup", action="store_true")
    exit_cmd.add_argument("--apply", action="store_true")

    cont = sub.add_parser("continue", help="Continue a resolved PH merge conflict")
    cont.add_argument("--repo", required=True)
    cont.add_argument("--apply", action="store_true")

    abort = sub.add_parser("abort-merge", help="Abort the PH merge while preserving task commits")
    abort.add_argument("--repo", required=True)
    abort.add_argument("--apply", action="store_true")
    return root


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "enter": command_enter,
        "exit": command_exit,
        "continue": command_continue,
        "abort-merge": command_abort,
    }[args.command](args)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.apply:
            main_repo = main_worktree(git_root(Path(args.repo).resolve()))
            with delivery_lock(main_repo):
                result = dispatch(args)
        else:
            result = dispatch(args)
    except PHError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"status": "ok", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
