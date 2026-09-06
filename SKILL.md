---
name: ph-init
description: "初始化、检查或同步本仓库的项目级 Harness（PH）：从唯一 GitHub 源准备正式发行版、写入 canonical `.agents/`、生成 portable/symlink 适配层、安装十个 ph-* skills。用户说“初始化 PH”“安装项目级 harness”“检查 PH”“同步 PH”“ph-init”“bootstrap harness”时必须使用。已初始化项目要升正式版时转交 ph-merge-update。不要把 ZCode 内置 /init、厂商仓库初始化向导、git init、目标仓 git pull、或 ph-memory-* / ph-worktree-* / ph-intent-* 误判为本技能。"
---

# ph-init

把正式发行版的 PH 模板落到尚未接入的 Git 仓库，或检查 / 修复适配层。已接入项目的版本合并走 `ph-merge-update`，不要用本技能 `--apply` 覆盖定制。

## 何时用 / 何时不用

使用：

- 空仓库或尚未接入 PH 的仓库：先准备正式版，再安装
- 检查 portable 副本 / symlink 是否与**项目已装** canonical 一致
- 同步适配层漂移（根 `AGENTS.md`、`CLAUDE.md`、Claude / Codex skill 镜像）

不用：

- 已有 `.agents/ph.json` 且用户要升官方版 → `ph-merge-update`（可从新发行根 `assets/scaffold/.agents/skills/ph-merge-update/SKILL.md` 读取，不要求旧项目已安装它）
- ZCode `/init`、厂商脚手架、`git init` 本身
- 在目标仓库 `git pull` 当升级
- `ph-memory-*` / `ph-worktree-*` / `ph-intent-*`

## 唯一源与准备

正式源只有 `https://github.com/chenweixuanJokes/ph-init.git`。`latest` 取数值最大的稳定 tag（排除预发布与非版本标签），并固定到该 tag 的 commit。本批发布为 `1.1.1`（Schema `1.1.1`，十个必需 Skill）。Schema 与发布版本独立维护，本批因契约变化而一起升。

当前这份 Skill 可能是旧用户入口或 shadow 副本。**初始化必须先准备发行根，再读该根的 `SKILL.md` 并只执行该根脚本**。不要用眼前这份本地 `assets/scaffold` 冒充最新版。离线内核可以安装它携带的确定版本，但不代表最新正式版。

```text
python3 <ph-init-root>/scripts/ph_release.py prepare --version latest|1.1.1 --repo <target>
```

stdout JSON：`root` `version` `tag` `commit` `source`（`source` 是固定仓库 URL 字符串）。材料下在目标仓库外的隔离目录，不读不传目标内容。同一 commit 已在本地时检查可不访问网络。无 tag、网络失败、tag/commit/`release.json` 不一致：停止，不回退到未准备的本地包。

记下 JSON 里的 `root`。后续 dry-run 与 apply 固定同一 `version`/`commit`。预检可以下载，不得改目标。

旧入口（例如 `~/.agents/skills/ph-init` 仍是 1.1.0 九 Skill）没有 `ph_release.py` 时，先把唯一 GitHub 源 clone 到一个新的仓外目录，从新 clone 运行 prepare；不覆盖旧项目入口。用输出的 `root` 读取新 Skill 并执行，不继续跑旧目录的 `ph_init.py init` 充当最新安装。已经持有本次 prepare 的固定 root 时，读取其中 Skill 后直接进入安装步骤，不再次 prepare。

`build_scaffold.py` / `build_project_template.py` 是旧 monorepo 作者工具，不是发布源，安装与升级不要跑它们。

## 命令

准备完成后，安装内核在发行根，默认 dry-run：

```text
python3 <release-root>/scripts/ph_init.py init [--apply] [--mode portable|symlink] [--repo <git-root>]
```

`check` / `sync` 使用**目标项目已安装**的内核，保持离线，不重新 prepare，不 `git pull`：

```text
python3 <project-or-installed-ph-init>/scripts/ph_init.py check [--mode portable|symlink] [--repo <git-root>]
python3 <project-or-installed-ph-init>/scripts/ph_init.py sync [--apply] [--mode portable|symlink] [--repo <git-root>]
```

- `--mode` 缺省：`init` 为 `portable`；`check` / `sync` 从已有适配层推断。仓库级固定，工具内不做 mode 迁移。
- `portable`：根 `AGENTS.md` 与 canonical 字节一致；`CLAUDE.md` 为 `@.agents/AGENTS.md` stub；`.claude/skills/ph-*` 与 `.codex/skills/ph-*` 为完整受管镜像。
- `symlink`：上述入口是指向 canonical 的直接相对软链。禁止 hardlink / junction。`core.symlinks` 显式 false 时阻断。写入前探测软链能力。
- `init` / `sync` fail-closed。`sync --apply` 只覆盖结构化 `content_drift`。嵌套 symlink/junction、仓外解析、hardlink、未托管多余文件保持阻断。
- 本批契约：PH `1.1.1`、Schema `1.1.1`、十个必需 Skill。旧仓库升版本走 merge-update。`check` 只读。`sync` 不升级 canonical、不补缺失 Skill。

## 工作流

1. **确认动作**：初始化 / 检查 / 同步；是否写入；mode。已初始化且要升正式版 → 停，转 merge-update。
2. **初始化：准备发行根**。对目标跑 `prepare`。读该 `root` 的 `SKILL.md`，用该 root 的 `ph_init.py`。
3. **先 dry-run**：同一 `root` 不加 `--apply`。把 `plan` / `skip` / `conflict` / `block` 给用户。
4. **冲突**：已有不同文件不覆盖。根 `AGENTS.md` 在而 `.agents/AGENTS.md` 不在 → 阻断。受跟踪 `.worktrees/`、仓外软链、嵌套 symlink/junction → 阻断。
5. **写入**：用户确认后同一 `root` 加 `--apply`。相同字节跳过。`ph-init` 自装自身（含 scaffold、release 元数据、在线脚本、迁移资料）；scaffold 内不嵌套 `ph-init`。
6. **验收**：对同一仓库跑已装内核的 `check`。需要时用刚装好的包初始化另一仓库，确认自包含。

## 完成标准

- 未调用 ZCode `/init`，未对目标 `git pull`。
- 初始化的 dry 与 apply 来自同一 prepare `commit`；dry-run 未改目标。
- 准备失败未用本地旧模板装“最新”。
- `--apply` 后 `check` 通过；未创建 `.zcode/skills`。
- 已初始化升级未走 `init --apply`。
- 未自动 commit / push / 公开仓库。
