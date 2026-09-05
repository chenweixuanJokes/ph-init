# ph-init

PH（Project Harness）标准化体系的唯一分发入口：**一个 Skill 自举整套项目级 Harness**。

对任意 Git 仓库执行一次初始化，即可落地完整体系——无需预装其它任何 Skill。

## 它安装什么

- `.agents/` 唯一规范源：`AGENTS.md`（项目约束单源）、`ph.json` + `ph.schema.json`（仓库级 manifest）
- 六个 `ph-*` Skill：
  - `ph-init`（自装，初始化后常驻，提供 check / sync）
  - `ph-worktree-enter` / `ph-worktree-exit`（并行开发：进入 / 退出 worktree，安全提交与合并回源）
  - `ph-memory-capture` / `ph-memory-archive` / `ph-memory-ask`（项目记忆：临时捕获 / 结构化归档 / 只读提问）
- `docs/` 三域文档模板：`约束规范/`、`意图/`（按状态目录移动管理）、`项目Wiki/`
- `.agents/memory/` 三层项目记忆：`temporary/`、`structured/`、`archive/`
- 多 Coding Agent 适配层：
  - `portable`（默认）：根 `AGENTS.md` 受管字节副本 + `CLAUDE.md` import stub + `.claude/skills`、`.codex/skills` 受管镜像——Windows、ZIP 解压、受限 CI 开箱即用
  - `symlink`（可选）：入口全部为仓库内相对软链，初始化前探测能力，不满足即阻断

## 安装

方式一：装为用户级 Skill（之后任何项目里说"初始化 PH"即可触发）：

```bash
git clone https://github.com/chenweixuanJokes/ph-init.git ~/.agents/skills/ph-init
```

方式二：不装 Skill，直接对目标仓库运行脚本：

```bash
git clone https://github.com/chenweixuanJokes/ph-init.git /tmp/ph-init
python3 /tmp/ph-init/scripts/ph_init.py init --repo /path/to/target-repo          # dry-run 预检，不写盘
python3 /tmp/ph-init/scripts/ph_init.py init --apply --repo /path/to/target-repo  # 实际写入
```

初始化安装了 `ph-init` 自身后，目标仓库即具备链式自举能力——里面的 `.agents/skills/ph-init` 仍带完整脚手架，可以继续初始化下一个仓库。

## 命令

```bash
python3 scripts/ph_init.py init  [--apply] [--mode portable|symlink] [--repo <git-root>]
python3 scripts/ph_init.py check [--mode portable|symlink] [--repo <git-root>]
python3 scripts/ph_init.py sync  [--apply] [--mode portable|symlink] [--repo <git-root>]
```

- `init`：预检并创建缺失结构（先 dry-run，加 `--apply` 才写盘）
- `check`：只读校验 manifest、frontmatter、索引、适配层漂移（SHA-256 字节级判定）
- `sync`：显式执行后按 `ph.json` 重建受管副本 / 镜像 / 软链
- `--mode` 仓库级锁定：首次 init 后切换模式会被拒绝，不在工具内做 mode 迁移

## 安全设计

- 一律先 dry-run：不加 `--apply` 不产生任何写入
- fail-closed：未知类型冲突保持阻断，`sync` 只修复结构化的 `content_drift`（适配层字节漂移），不按报错文案关键词放行
- 显式拒绝：嵌套 symlink / junction、仓外路径解析、hardlink 充当软链、受跟踪的 `.worktrees/` 内容
- 已存在的不同内容文件一律 conflict 阻断，不自动覆盖、不自动拼接
- 初始化不 push、不删分支、不改 Git / OS 权限设置（如 `core.symlinks`）

## 仓库结构

```text
ph-init/
├── SKILL.md            # Skill 定义（Agent 阅读的入口）
├── scripts/
│   ├── ph_init.py              # init / check / sync 自举脚本（安装时实际运行的唯一脚本）
│   ├── build_scaffold.py       # 模板作者工具：从实施包重建 assets/scaffold（安装时不需要）
│   └── build_project_template.py  # 模板作者工具：发布 ph-init 到实施包 canonical（安装时不需要）
├── assets/scaffold/    # 完整脚手架：.agents（含另外五个 Skill）+ docs 三域 + .gitignore
└── evals/              # Skill 触发评测定义
```

`scaffold` 刻意不含 `ph-init` 自身（避免递归套娃）；自装时从 Skill 所在目录复制本体。

## 版本与来源

本仓库即 `ph-init` 的分发本体：除根 `README.md` 与 `.gitignore` 为仓库级说明外，其余内容与作者侧实施包的 `distribution/ph-init` 保持一致。功能验证（62 项单测 + 结构校验）在作者侧实施包内执行后发布。
