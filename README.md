# ph-init

PH（Project Harness）的正式分发入口。唯一源：

`https://github.com/chenweixuanJokes/ph-init.git`

本批版本为 **1.1.5**（Schema **1.1.1**，十个必需 Skill）。`latest` 取数值最大的稳定 tag，排除预发布与非版本标签，并固定到该 tag 的 commit。尚无稳定 tag 或查询失败时，初始化必须停止，不能把 `main`、工作区或眼前这份本地 `assets/scaffold` 当成最新正式版。

本仓库是安装、升级与初始化文档材料。用户只说「初始化 PH」「安装 harness」「升级 PH」都走 `ph-init`。Python 的 `init` / `check` / `sync` 只做确定性的安装、检查与适配层同步；`ph-init` Skill 在安装后的同一会话中通过 subagent 补齐项目文档。存量项目接入不先落模板盖旧正文：会话在仓外生成 `sources` 快照与合并候选，经 `init --adopt-plan` 受控安装。已接入且版本旧于发行根时，同一会话按 merge-update 步骤升级，不要 `init --apply` 覆盖定制，不要另开技能，不要在目标仓库 `git pull`。

Schema 与发布版本独立维护。1.1.1 引入十 Skill 契约；本批保留该 Schema，不新增必需 Skill。

## 它安装什么

- `.agents/` 唯一规范源：`AGENTS.md`、`ph.json` + `ph.schema.json`
- 十个 `ph-*` Skill：
  - `ph-init`：用户入口；自装后常驻，提供 check / sync，已装旧版由该会话按升级步骤做完
  - `ph-merge-update`：已安装项目按迁移链合并升级的步骤（由 ph-init 会话执行）
  - `ph-worktree-enter` / `ph-worktree-exit`
  - `ph-memory-capture` / `ph-memory-archive` / `ph-memory-ask`
  - `ph-intent-new` / `ph-intent-impl` / `ph-intent-drop`
- `docs/` 三域与 `.agents/memory/` 三层
- portable（默认）或 symlink 适配层，规则与安全边界同发行根 `SKILL.md`

意图目录现行为 `待办/` 与 `实施/`；不设 `已完成/`，交付的意图留在 `实施/` 并在记录注明结果。旧 `进行中/` 状态取消，存量条目按是否已启动迁入待办或实施。细则在项目文档，不在本 README 展开生命周期。

## 存量项目文档补全

初始化会话先盘点代码、实际依赖版本、CI、已有规范与测试，再按独立范围派发 subagent：补齐项目 Wiki，以及工程／前端／后端／测试规范。目标技术栈的官方资料在实际 init 时实时查阅，保留来源、版本与访问日期；本分发仓不预装特定业务栈规则。

详见随包安装的[初始化与文档补全](./assets/scaffold/docs/约束规范/工程规范/初始化与文档补全.md)，其中包含项目级 harness 内容清单的逐项落点；新增[安全与配置](./assets/scaffold/docs/约束规范/工程规范/安全与配置.md)、[构建发布与运维](./assets/scaffold/docs/约束规范/工程规范/构建发布与运维.md)，并细化各端、用例和 Wiki 模板。

- 存量内容用旧内容接入：会话盘点七类证据（模块、代码、配置、真实依赖、测试、CI、旧约束）后在**目标仓外**生成合并候选 plan，`init --adopt-plan` 校验 `sources` 哈希一致才落盘；已有正文优先复用 / 引用登记，不复制第二套。
- `--adopt-plan` 仅用于尚无 `.agents/ph.json` 的目标；已安装仓库拒绝 adopt。已装旧版由 ph-init 会话按 merge-update 步骤做完升级，不另开技能。已安装同版重跑 init 保留定制 canonical。
- 接入前的旧文档目录（如 `docs/specs/`、`docs/domains/`、`docs/plans/`）按内容归并进 `约束规范/`、`意图/`、`项目Wiki/`，不留旧目录、空壳或软链；摘要 + 深链指向归并后的正文，被引用旧规范保持效力。写入或移走前把原文备份到 `.agents/archived/`。内核 adopt 不自动搬移或删除。
- 已有安全普通 `docs/**` 文件由安装内核保留，缺失才安装；会话按段落补缺并维护索引，不整树覆盖。
- 区分已接受规则、当前事实、待采纳建议和待核实项；不编造负责人、历史决策、意图、记忆或测试通过记录。
- 补全过程记录在 `.agents/init-report.md` 覆盖报告：矩阵每个独立 id 一行（落点、仓内证据、结果、说明），结果只用已核验 / 复用 / 不适用 / 待核实 / 冲突。
- 安装 check 通过不等于文档补全完成。网络或子任务失败要单独记录，文档可按磁盘实态与 `init-report` 续做，不重跑 init。
- 升级只引入本次迁移要求的指引，保护既有正文和 subagent 产物；完整文档重建不属于普通 merge-update。

## 根安装入口（clone 后准备正式版）

先有 Git 仓库。空目录先 `git init`。不要用 ZCode `/init` 或其它厂商脚手架。

```bash
git clone https://github.com/chenweixuanJokes/ph-init.git /tmp/ph-init
python3 /tmp/ph-init/scripts/ph_release.py prepare --version latest --repo /path/to/target-repo
```

stdout 为 JSON：`root` `version` `tag` `commit` `source`。材料在目标仓库外。然后**读取该 `root` 里最新的 `SKILL.md`**，并用该 root 的内核：

```bash
python3 <root>/scripts/ph_init.py init --repo /path/to/target-repo
python3 <root>/scripts/ph_init.py init --apply --repo /path/to/target-repo
```

dry-run 与 apply 必须是同一次 prepare 的 `version`/`commit`。预检可下载，不得改目标。无正式 tag、网络失败、tag/commit/`release.json` 不一致：停止。

装成用户级入口后，在项目里说“初始化 PH”也应先 prepare，再执行发行根，而不是直接跑 clone 目录里可能过期的 `ph_init.py init`。

```bash
git clone https://github.com/chenweixuanJokes/ph-init.git ~/.agents/skills/ph-init
```

用户级目录只是入口，仍以 prepare 给出的 `root` 为准。

## 旧 shadow 入口

旧副本（例如仍停在 1.1.0 九 Skill 的 `~/.agents/skills/ph-init`，或项目内自包含旧包）**不是**最新正式版。初始化或升级时：

1. 用入口中的 `ph_release.py` 对目标 `prepare`。旧 1.1.0 入口没有此脚本时，先将固定 GitHub 源 clone 到新的仓外目录，从新 clone 运行 prepare，不覆盖旧项目入口。
2. 只读 JSON 的 `root`。
3. 读 `<root>/SKILL.md`。已装旧版则同一会话再读 `<root>/assets/scaffold/.agents/skills/ph-merge-update/SKILL.md`，不要求旧项目已经有该 Skill，也不另开技能。
4. 未安装执行 `<root>/scripts/ph_init.py`；已装旧版执行 `<root>/scripts/ph_merge_update.py`。
5. 不要继续用 shadow 目录的 `assets/scaffold` 当最新模板，不要对目标 `git pull`。

本地检查 / 同步用项目已装内核，无需网络：

```bash
python3 <installed-ph-init>/scripts/ph_init.py check --repo /path/to/target-repo
python3 <installed-ph-init>/scripts/ph_init.py sync --repo /path/to/target-repo
```

离线内核只能保证它携带的那一版能 check/sync，不能证明那一版是当前 `latest`。

## 已安装项目升级

对外入口仍是 `ph-init`。已装且版本旧于发行根时，同一会话按发行根 `ph-merge-update` 步骤做完，不要另开技能，不要 `init --apply`。摘要：

```bash
python3 <root>/scripts/ph_release.py prepare --version latest --repo /path/to/target-repo
python3 <root>/scripts/ph_merge_update.py inspect --repo /path/to/target-repo
# Agent 按 migrations/ 合并；inspect 只读
python3 <root>/scripts/ph_merge_update.py verify --repo /path/to/target-repo
python3 <root>/scripts/ph_merge_update.py finalize --repo /path/to/target-repo          # dry-run
python3 <root>/scripts/ph_merge_update.py finalize --apply --repo /path/to/target-repo
```

进度在项目 `.agents/updates/<to_version>/state.json` 与 `report.md`。candidate check 通过前不改磁盘 `ph.json` 版本。旧 `进行中/` 存量条目按是否已启动迁入待办或实施。冲突停止受影响项。不自动 commit / push / 公开仓库。

历史六 Skill、两套 1.1.0 命名、已提前落地的待办/实施，都必须按文件实态识别。迁移说明：[migrations/README.md](./migrations/README.md)。

## 命令

```bash
python3 scripts/ph_release.py prepare --version latest|1.1.5 --repo <git-root>
python3 scripts/ph_init.py init  [--apply] [--adopt-plan <plan.json>] [--mode portable|symlink] [--repo <git-root>]
python3 scripts/ph_init.py check [--mode portable|symlink] [--repo <git-root>]
python3 scripts/ph_init.py sync  [--apply] [--mode portable|symlink] [--repo <git-root>]
python3 scripts/ph_merge_update.py inspect --repo <git-root>
python3 scripts/ph_merge_update.py verify --repo <git-root>
python3 scripts/ph_merge_update.py finalize [--apply] --repo <git-root>
```

初始化请对 **prepare 的 root** 调 `ph_init.py`。上面写 `scripts/` 时，指当前正在执行的那份发行根，不是任意 shadow 路径。

## 安全

- 不加 `--apply` 不写目标
- 非 docs 冲突 fail-closed；已有安全普通 docs 保留待会话审阅，不安全路径仍阻断
- `--adopt-plan` 的候选只允许 canonical `.agents/AGENTS.md` 与 `docs/**`；plan 在仓外生成，不写秘密 / 令牌；已装仓库拒绝 adopt
- 拒绝嵌套 symlink / junction、仓外路径、hardlink 充当软链、受跟踪的 `.worktrees/`
- 不 push、不删分支、不改 `core.symlinks`、不对目标 `git pull`

## 发布与校验

面向用户的版本摘要：[CHANGELOG.md](./CHANGELOG.md)。发布元数据：`release.json`。

修改发行内容或准备发布前，必须遵循本仓 [版本与合并升级约束](./docs/约束规范/工程规范/版本与合并升级.md)：每个对外小改动批次递增 `1.1.x`，同时提交相邻版本的合并升级方案；缺任一项不得发布。此规则由 `.agents/AGENTS.md` 引用，区别于下游 scaffold 约束。

本独立仓库用 Git 标签发布。作者侧旧 monorepo 的 `scripts/build_scaffold.py` 与 `scripts/build_project_template.py` **不是**安装或发布源；不要在本仓为了“出包”去跑它们，也不要把仓外实施模板布局当成前置条件。

发布检查与回归（在本仓库根）：

```bash
python3 scripts/check_release.py
python3 -m unittest discover -s tests -v
```

CI 只检查，不自动打 tag、不改仓库可见性。`evals/` 是触发与行为定义，**不宣称这些场景已实测**。

## 已知限制

- 首个正式标签为 `v1.1.1`；若发布源尚无稳定标签或网络不可达，`prepare --version latest` 会阻断，不回退到开发分支。
- 本机验证面与跨客户端限制见发行说明；Windows / 网络盘 / 各厂商 Skill 触发未作为开箱保证。
- 测试应使用临时 Git 仓，结束后移入 `~/trash/`。

## 仓库结构

```text
ph-init/
├── README.md
├── SKILL.md
├── CHANGELOG.md
├── release.json
├── migrations/         # 相邻版本说明与 index.json
├── scripts/            # ph_release / ph_init / ph_merge_update；build_* 非发布源
├── assets/scaffold/    # 脚手架（含另外九个 Skill，不含嵌套 ph-init）
├── tests/
├── evals/
└── docs/               # 分发仓维护文档（不进发行树）
```
