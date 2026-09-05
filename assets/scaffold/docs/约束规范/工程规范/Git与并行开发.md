# Git 与并行开发

Last verified: <填写：YYYY-MM-DD>

> 适用范围：本仓库全部模块。摘要入口在 `.agents/AGENTS.md`，细节只写在本文。把本仓库的基线分支名、发布通道和通知方式填进占位符，不要从其它项目照抄环境名。

## 1. 分支

- **基线**：`<填写：例如 main / release/prod>`。新特性从最新基线检出，不从个人分支或未验证的集成分支再开分支。
- **命名**：英文 `<类型>/<主题>` 或仓库已声明的等价格式。类型建议 `feature` / `fix` / `refactor` / `docs` / `chore`。禁止中文分支名。
- **合入**：`<填写：何种评审、合入哪条集成分支、生产是否单向通道>`。
- **禁令**：`<填写：例如禁止特性分支直合生产>`。

## 2. WIP 与 stash

- 禁止 `git stash`。
- 切换分支、进入 / 退出 worktree、合并或删除隔离环境前，若工作区有未提交改动，先提交：

  ```text
  wip: <说明>
  ```

- WIP 不得静默执行。提交前列出 staged、unstaged、untracked 清单；未跟踪文件、疑似密钥与异常大文件必须由用户明确决定，ignored 文件不得强制加入。
- WIP 默认保留，不自动 squash。是否在合入前整理由本仓库发布约定决定，写在本节，不另起文档。

## 3. Worktree

- 并行任务的隔离目录固定为仓库根下 `.worktrees/<slug>--<hash>/`。`.worktrees/` 是真实目录，不是软链。`slug` 由英文任务分支生成，短 hash 防止大小写、截断与同名冲突；脚本必须校验 Git ref 和目标路径不越出 `.worktrees/`。
- `.worktrees/` 由仓库根 `.gitignore` 的 PH marker `/.worktrees/` 忽略。不要把隔离目录或本机会话状态提交进版本库。
- worktree 是执行环境，不是第二份知识库。约束、Wiki、记忆仍以已入库版本为准；在隔离环境里改这些文件时，随该任务一并提交。
- 进入流程由 `ph-worktree-enter` 执行，只允许从 clean main worktree 创建一级 linked worktree，并记录源目录、源分支、源提交、任务分支、任务路径，以及此刻审核过的验证命令。验证命令会在任务树和合并后的 source 树执行，等同仓库代码，必须经过评审；任务分支后续改写清单不影响本 session。验证命令若改变 staged、tracked 或 untracked 状态，流程必须停止，由用户审查变化。
- 退出流程由 `ph-worktree-exit` 执行：先跑项目门禁，再安全提交任务改动，合并回进入时记录的源目录与源分支，再次验证。合并采用 Git 默认 fast-forward / merge 策略并显式禁用 autostash。修复或重跑必须覆盖全部 phase 的 dry-run，不能只复验其中一个 phase。
- 退出提交遵守安全分级：只有 staged 时只提交 index；只有 tracked unstaged 时可 `git add -u`；两者并存或存在 untracked 时必须停止让用户选择。向用户展示时至少给出 HEAD、当前 branch、index 与 untracked 摘要。ignored 文件一律阻断清理，并提醒先自行保全；不得加入提交或静默丢弃。不得使用 `--no-verify` 绕过 hooks。
- 同一 main 工作区上的 enter/exit 交付互斥：已有未完成交付时不得并行再开或再收另一条。
- 合并成功后必须另行征得用户同意，才能普通移除本 session 的 clean linked worktree；默认保留任务分支，不 push、不删分支、不 prune 其它 worktree，也不使用 force。

## 4. 异常处理

| 情况 | 处理 |
| --- | --- |
| 隔离环境做不下去 | 先 `wip:`，保留实验分支，删除本地 worktree，在对应意图里记录原因 |
| 主工作区与 worktree 都有未提交改动 | 两侧分别 `wip:`，禁止 stash 互搬 |
| `.worktrees/` 被误提交 | 从版本库移出并确认 ignore 仍在，不改其它忽略规则 |
| 分支名含中文或空格 | 停下来改名，不继续进 worktree |

## 5. 通知（可选）

若本仓库在推送共享分支后需要通知团队，把通道、触发点（仅推送，不合入即通知）和文案要求写在本节。没有该需求则删去本小节，不必另开“通知规范”空文档。
