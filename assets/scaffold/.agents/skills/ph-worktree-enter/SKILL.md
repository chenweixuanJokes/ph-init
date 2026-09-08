---
name: ph-worktree-enter
description: 为当前 Git 项目创建 PH 管理的隔离 worktree，并记录退出时必须使用的源工作区、源分支与任务分支。只要用户明确要求“进入 worktree”“开隔离工作区”“并行开发这个任务”或调用 ph-worktree-enter，都必须使用本技能。普通切换分支、只询问 Git 用法、仅录入或规划意图、未授权创建 worktree 时不要使用；源工作区不干净时不要擅自提交、stash 或丢弃改动。
---

# ph-worktree-enter

为一个已经获用户明确授权的并行任务创建 linked worktree。它只负责隔离和登记上下文，不启动服务、不安装依赖，也不修改业务代码。

## 执行前约束

1. 先读项目根 `.agents/AGENTS.md` 与 [`docs/约束规范/工程规范/Git与并行开发.md`](../../../docs/约束规范/工程规范/Git与并行开发.md)。
2. 创建 Git worktree 是有副作用的操作；用户没有明确要求时只说明方案，不执行。
3. 禁止 `git stash`、`--force`、`reset --hard`。源工作区有 staged、unstaged 或 untracked 内容时停止，把清单交给用户处理，并说明“主目录还有未提交改动，现在不能开隔离工作区”。
4. 首版只支持从仓库的 main worktree、attached branch 创建一级 linked worktree；裸仓库、子模块 superproject 和 linked worktree 再嵌套均阻断。

## 执行步骤

1. 确认任务分支名称。新分支与复用已有分支必须明确区分；分支名只能使用 ASCII 字母、数字、`.`、`_`、`-`、`/`。对用户问“用新分支还是复用已有分支”，见 [对用户提问](../../../docs/约束规范/工程规范/对用户提问.md) 第 4 节。
2. 先运行只读计划：

   ```bash
   python3 .agents/skills/ph-worktree-enter/scripts/ph_worktree.py \
     enter --repo <main-worktree> --branch <task-branch>
   ```

   复用已有分支时增加 `--existing`。
3. 向用户说明来源分支、来源提交、任务分支、隔离工作区路径，以及将会用来验收的命令。验证命令会作为仓库代码执行，必须先审查；对用户问“确认后我才会真正创建”，不要把内部会话名当主语。确认与用户意图一致后加 `--apply`。
4. 进入脚本输出的 `taskPath` 开发。不要手工移动该目录或修改 `.worktrees/.ph/sessions/`。
5. 完成时调用 `ph-worktree-exit`，不要自行把任务分支合并到另一个临时目标。

## 路径与状态

- worktree 路径由“可读分支 slug + SHA-256 前八位”生成，不直接把分支名当文件路径。
- session 存在 `.worktrees/.ph/sessions/<session-id>.json`，不会入 Git；记录 enter 时的 main worktree、source branch/head 与 task worktree/branch。
- `.worktrees/` 未被忽略、分支已被其他 worktree 占用或目标路径已存在时必须停止。
- `.worktrees/`、`.worktrees/.ph/` 及 session 路径必须是真实仓库内目录，禁止经软链或 junction 重定向；不能把移动到其它路径的 worktree 冒充原 session。
- PH 写操作按 main worktree 加独占交付锁；dry-run 不创建锁，也不刷新 Git index。锁冲突直接停止，崩溃残锁不得自动抢占。

## 完成标准

- Git 登记中只有一个新的目标 linked worktree；
- session 与 worktree 路径、分支一一对应；
- main worktree 的分支、HEAD 和工作区内容没有被修改；
- 输出后续 `ph-worktree-exit` 的执行位置。
