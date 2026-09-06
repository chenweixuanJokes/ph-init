# ph-init

PH（Project Harness）1.1.0 的分发入口：**一个 Skill 自举整套项目级 Harness**。

对已有 Git 仓库执行一次初始化，可落地 canonical `.agents/`、九个 `ph-*` Skill、三域文档与三层记忆。本仓库是安装包，不是实施模板全集；`tests/` 包含本包的目录与安装回归测试，不含作者侧研究记录。

`init` / `check` / `sync` **只做安装、检查与适配层同步，不是升级器**。已按 1.0.0 / 六 Skill 落地的仓库不会被自动改成 1.1.0。

## 它安装什么

- `.agents/` 唯一规范源：`AGENTS.md`、`ph.json` + `ph.schema.json`（`schema_version` / `template_version` = `1.1.0`）
- 九个 `ph-*` Skill：
  - `ph-init`：自装后常驻，提供 check / sync
  - `ph-worktree-enter` / `ph-worktree-exit`：进入 / 退出 worktree
  - `ph-memory-capture` / `ph-memory-archive` / `ph-memory-ask`：临时捕获 / 结构化归档 / 只读提问
  - `ph-intent-new`：新建意图进入待办，补充已有意图保持原目录，同时保存访谈纪要
  - `ph-intent-impl`：可写时先将意图迁入实施，再准备交接材料并进入**宿主原生计划模式**（本包不提供、也不模拟该切换）
  - `ph-intent-drop`：在用户给出真实原因后废弃意图并修复引用
- `docs/` 三域：`约束规范/`、`意图/`、`项目Wiki/`
- `.agents/memory/`：`temporary/`、`structured/`、`archive/`
- 多客户端适配层：
  - `portable`（默认）：根 `AGENTS.md` 受管字节副本 + `CLAUDE.md` import stub + `.claude/skills`、`.codex/skills` 受管镜像。这保证**无需操作系统软链**即可看到同一份约束源；**不是**已在 Windows 或各厂商客户端做过开箱实测。
  - `symlink`（可选）：入口为仓库内相对软链；初始化前探测能力，不满足即阻断。未开 Developer Mode、`core.symlinks=false`、网络盘等场景可能失败，PH 不把“全平台软链可用”写成承诺。

三个意图 Skill 的分工：`new` 新建入 `docs/意图/待办/新特性/` 或 `待办/问题记录/`，补充已有意图不改变阶段；`impl` 在可写且目标唯一时先迁入对应的 `实施/` 分类，核实状态、引用和索引后再调研与交接计划模式；`drop` 在原因明确时移入已废弃并修链。实施包含准备、规划、开发与验收，不表示计划获批或自动授权实现。已在实施时重复调用不重复启动记录；切换失败或暂停不退回待办；只读时不迁移，按实际位置报告并将待迁移项交给恢复可写后的执行阶段。已完成目录保留，本次不引入自动关闭。

### 已安装项目

本次调整保持九 Skill 与 manifest 结构，版本锁仍为 `1.1.0`；版本号或 `check` 通过不代表已采用新目录规则。`sync` 只同步现有 canonical 的适配层，不更新项目 Skill、规范或意图目录，不能用 `init --apply` 覆盖定制项目。

采用新机制时，需审阅合并三个意图 Skill、`.agents/AGENTS.md`、意图模板、工程规范和相关 README，补齐待办/实施两组分类目录；同时更新项目内 `ph-init` 自包含分发包，再运行 `sync` 与 `check`。不要直接整目录覆盖已有 `docs/` 或 canonical。

旧 `进行中/` 不批量改派：`new` 补充旧意图时保持原位；明确对单条调用 `impl` 时迁入实施；明确废弃时由 `drop` 处理。保留旧编号、历史纪要与有效引用。

## 安装（不是升级）

方式一：装为用户级 Skill（之后在项目里说“初始化 PH”）：

```bash
git clone https://github.com/chenweixuanJokes/ph-init.git ~/.agents/skills/ph-init
```

方式二：不装 Skill，直接对目标仓库跑脚本：

```bash
git clone https://github.com/chenweixuanJokes/ph-init.git /tmp/ph-init
python3 /tmp/ph-init/scripts/ph_init.py init --repo /path/to/target-repo          # dry-run，不写盘
python3 /tmp/ph-init/scripts/ph_init.py init --apply --repo /path/to/target-repo  # 实际写入
```

只对**已有 Git 仓库根**执行。空目录先 `git init`。不要用 ZCode `/init` 或其它厂商脚手架代替。

已是 1.0.0 六 Skill 的仓库：`init` / `check` / `sync` 遇到版本锁会失败关闭、不写文件、不补三个意图 Skill。需要 1.1.0 时按实施模板 `docs/PH-1.1.0升级说明.md` **人工**改清单与复制 Skill，再 `check`。`sync` 只修适配层漂移，不升级 canonical。

## 命令

```bash
python3 scripts/ph_init.py init  [--apply] [--mode portable|symlink] [--repo <git-root>]
python3 scripts/ph_init.py check [--mode portable|symlink] [--repo <git-root>]
python3 scripts/ph_init.py sync  [--apply] [--mode portable|symlink] [--repo <git-root>]
```

- `init` / `sync` 默认 dry-run，只有明确要求写入时才加 `--apply`
- `--mode` 仓库级锁定：首次 init 后切换模式会被拒绝，工具内不做 mode 迁移
- `check` 只读；`sync --apply` 只覆盖结构化的 `content_drift`

## 安全

- 不加 `--apply` 不写盘
- fail-closed：未知冲突保持阻断
- 拒绝嵌套 symlink / junction、仓外路径、hardlink 充当软链、受跟踪的 `.worktrees/`
- 已存在的不同内容一律 conflict，不自动覆盖
- 不 push、不删分支、不改 `core.symlinks`

## 已知跨客户端限制

本机验证在 macOS + Python 标准库 + 临时 Git 仓库上完成。以下**未**作为开箱保证：

- 真实 Windows / 网络盘 / 未开 Developer Mode 的软链行为
- Claude / Codex / ZCode 等客户端的 Skill 自动触发、上下文拼接或原生 `EnterPlanMode`
- 自然语言全量触发评测、跨厂商端到端、CI 平台实测
- 已安装 1.0.0 仓库的自动升级

`evals/` 定义触发与行为场景，不代表这些场景已在各客户端完成全量评测。目录、文档链接、适配层与真实安装回归可运行：

```bash
python3 -m unittest discover -s tests -v
```

测试使用临时 Git 仓库，结束后移入 `~/trash/`；不修改实际项目的意图。

## 仓库结构

```text
ph-init/
├── README.md           # 本文件（仓级说明，不同步自实施模板）
├── SKILL.md            # Skill 入口
├── scripts/
│   ├── ph_init.py                 # init / check / sync
│   ├── build_scaffold.py          # 模板作者工具，安装时不需要
│   └── build_project_template.py  # 模板作者工具，安装时不需要
├── assets/scaffold/    # 脚手架：.agents（另外八个 Skill）+ docs 三域 + .gitignore
├── tests/              # 目录、链接、安装与适配层回归
└── evals/              # 触发与行为评测定义
```

`scaffold` 不含 `ph-init` 自身，避免递归套娃；自装时从本 Skill 目录复制本体。

## 版本与来源

除根 `README.md` 与 `.gitignore` 外，其余内容与作者侧实施包 `distribution/ph-init` 对齐。功能验证在实施包内执行后做本地同步，本副本默认不自动 commit / push。
