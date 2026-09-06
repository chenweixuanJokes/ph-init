---
name: ph-init
description: "初始化、检查或同步本仓库的项目级 Harness（PH）：写入 canonical `.agents/`、生成 portable/symlink 适配层、安装 ph-* skills。用户说“初始化 PH”“安装项目级 harness”“检查 PH”“同步 PH”“ph-init”“bootstrap harness”时必须使用。不要把 ZCode 内置 /init、厂商仓库初始化向导、git init、或 ph-memory-* / ph-worktree-* / ph-intent-* 误判为本技能。"
---

# ph-init

把 PH 模板落到目标 Git 仓库，或检查 / 修复适配层。本技能是 PH 初始化结构与适配层的受管写入入口；不要改用 ZCode `/init` 或其它厂商脚手架，那些会分叉 `.agents` 布局。

## 何时用 / 何时不用

使用：

- 在空仓库或尚未接入 PH 的仓库安装 harness
- 检查 portable 副本 / symlink 是否与 canonical 一致
- 同步适配层漂移（根 `AGENTS.md`、`CLAUDE.md`、Claude / Codex skill 镜像）

不用：

- ZCode 内置 `/init` 或“初始化这个对话/仓库向导”
- `git init` 本身
- 记住 / 归档 / 查记忆 → `ph-memory-*`
- 进入 / 退出 worktree → `ph-worktree-*`
- 录入 / 规划 / 废弃意图 → `ph-intent-*`

## 路径与自包含

1. 从当前工作目录向上找 Git 仓库根。
2. 本技能目录是 `scripts/ph_init.py` 的上一级。安装后仍用**本目录**的 `assets/scaffold`，不要去读提案仓库的绝对路径。
3. Canonical 源是 `.agents/`。ZCode 直接发现 `.agents/skills`，不要创建 `.zcode/skills`。

## 命令

一律用仓库内解释器调用脚本。`init` / `sync` 默认 dry-run，只有用户明确要求写入时才加 `--apply`。

```text
python3 <this-skill>/scripts/ph_init.py init [--apply] [--mode portable|symlink] [--repo <git-root>]
python3 <this-skill>/scripts/ph_init.py check [--mode portable|symlink] [--repo <git-root>]
python3 <this-skill>/scripts/ph_init.py sync [--apply] [--mode portable|symlink] [--repo <git-root>]
```

- `--mode` 缺省：`init` 为 `portable`；`check` / `sync` 从已有适配层推断。仓库级固定，不在本工具里做 mode 迁移。
- `portable`：根 `AGENTS.md` 与 canonical 字节一致（不加 header）；`CLAUDE.md` 为 `@.agents/AGENTS.md` stub；`.claude/skills/ph-*` 与 `.codex/skills/ph-*` 为完整受管镜像。scaffold/canonical 的既有差异始终阻断；只有上述受管 adapter 才能产生可同步的 `content_drift`。
- `symlink`：上述入口全部是指向 canonical 的直接相对软链。禁止 hardlink / junction。`core.symlinks` 显式为 false 时阻断，不自动改 Git 或 OS 权限；写入前在目标所在文件系统探测软链能力。
- `init` / `sync` 一律 fail-closed。`sync --apply` 只覆盖结构化的 `content_drift`（已有常规文件字节漂移）；仓外解析、嵌套 symlink/junction、hardlink、未托管多余文件等其它 conflict 保持阻断，不按文案关键词放行。
- Skill 资源递归遍历显式拒绝嵌套 symlink / junction（目录和文件）。`check` 只读，不写。
- 本版契约为 PH 1.1.0、九个必需 Skill。旧 1.0.0 仓库需要人工审阅合并规范与清单；`init` 不覆盖定制内容，`sync` 不升级 canonical 或安装缺失的新 Skill。版本不匹配时停止，不强行重跑 `--apply`。

## 工作流

1. **确认动作**：初始化 / 检查 / 同步；是否允许写入；mode。
2. **先 dry-run**：不加 `--apply` 跑一遍，把 `plan` / `skip` / `conflict` / `block` 给用户看。
3. **冲突与阻断**：已有不同文件不覆盖。根 `AGENTS.md` 已在而 `.agents/AGENTS.md` 不在 → 迁移阻断，不自动合并。受跟踪的 `.worktrees/` 内容 → 阻断。厂商父目录或 Skill 树被换成仓外软链 / 含嵌套 symlink 或 junction → 阻断，不得把 conflict 当成 write。
4. **写入**：用户确认后 `--apply`。相同字节跳过。`ph-init` 自安装自身（含 `assets/scaffold`），但 scaffold 内不再嵌套一份 `ph-init`，避免无限递归。
5. **验收**：对同一仓库再跑 `check`（只读）。需要的话用刚装好的脚本初始化另一仓库，确认自包含。

## 完成标准

- 未调用 ZCode `/init`。
- dry-run 未改任何文件。
- `--apply` 后 `check` 通过；未创建 `.zcode/skills`。
- 冲突或阻断时文件保持原样，并报告路径。
- 未做 schema upgrade / 历史迁移。
