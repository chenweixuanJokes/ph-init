---
name: ph-init
description: "初始化、检查或同步本仓库的项目级 Harness（PH）：从唯一 GitHub 源准备正式发行版、安装 canonical 与十个 ph-* skills。存量项目用旧内容接入：盘点后在仓外生成 sources 快照与合并候选，经 init --adopt-plan 安装，不先装模板盖旧正文；init 会话按代码与实时官方资料逐项补全文档并产出覆盖报告。用户说“初始化 PH”“安装项目级 harness”“检查 PH”“同步 PH”“升级 PH”“ph-init”“bootstrap harness”时必须使用。已装项目的安装、检查、同步、升正式版都由本 Skill 接；口误说成 init 也在本会话按 merge-update 步骤做完升级，不另开技能。不要把 ZCode 内置 /init、厂商脚手架、git init、目标仓 git pull、或 ph-memory-* / ph-worktree-* / ph-intent-* 误判为本技能。"
---

# ph-init

把正式发行版的 PH 落到 Git 仓库：空仓库安装脚手架，存量项目用旧内容接入（已有正文优先引用，不复制第二套），并在初始化会话逐项补全文档；也可只检查 / 修复适配层。已接入且版本旧于发行根时，**同一会话**按发行根的 merge-update 步骤做完升级，不要用 `init --apply` 覆盖定制，不要另开技能。

## 何时用 / 何时不用

使用：

- 空仓库或尚未接入 PH 的存量仓库：先准备正式版，再盘点、整合、经仓外合并候选安装与补全文档
- 已装且要跟官方包对齐（含用户说初始化 / 安装 / 升级）
- 检查 portable 副本 / symlink 是否与**项目已装** canonical 一致
- 同步适配层漂移（根 `AGENTS.md`、`CLAUDE.md`、Claude / Codex skill 镜像）
- 续做本次初始化未完成的文档：读已装指引、`.agents/init-report.md` 与磁盘实态；不重跑安装、不借机升版本

不用：

- ZCode `/init`、厂商脚手架、`git init` 本身
- 在目标仓库 `git pull` 当升级
- `ph-memory-*` / `ph-worktree-*` / `ph-intent-*`

## 唯一源与准备

正式源只有 `https://github.com/chenweixuanJokes/ph-init.git`。`latest` 取数值最大的稳定 tag（排除预发布与非版本标签），并固定到该 tag 的 commit。本批版本为 `1.1.5`（Schema `1.1.1`，十个必需 Skill）。Schema 与发布版本独立，本批不改 Schema。

当前这份 Skill 可能是旧用户入口或 shadow 副本。**初始化必须先准备发行根，再读该根的 `SKILL.md` 并只执行该根脚本**。不要用眼前这份本地 `assets/scaffold` 冒充最新版。离线内核可以安装它携带的确定版本，但不代表最新正式版。

```text
python3 <ph-init-root>/scripts/ph_release.py prepare --version latest|1.1.5 --repo <target>
```

stdout JSON：`root` `version` `tag` `commit` `source`（`source` 是固定仓库 URL 字符串）。材料下在目标仓库外的隔离目录，不读不传目标内容。同一 commit 已在本地时检查可不访问网络。无 tag、网络失败、tag/commit/`release.json` 不一致：停止，不回退到未准备的本地包。

记下 JSON 里的 `root`。后续 dry-run 与 apply 固定同一 `version`/`commit`。预检可以下载，不得改目标。

旧入口（例如 `~/.agents/skills/ph-init` 仍是 1.1.0 九 Skill）没有 `ph_release.py` 时，先把唯一 GitHub 源 clone 到一个新的仓外目录，从新 clone 运行 prepare；不覆盖旧项目入口。用输出的 `root` 读取新 Skill 并执行，不继续跑旧目录的 `ph_init.py init` 充当最新安装。已经持有本次 prepare 的固定 root 时，读取其中 Skill 后直接进入分流，不再次 prepare。

`build_scaffold.py` / `build_project_template.py` 是旧 monorepo 作者工具，不是发布源，安装与升级不要跑它们。

## 命令

准备完成后，安装内核在发行根，默认 dry-run：

```text
python3 <release-root>/scripts/ph_init.py init [--apply] [--adopt-plan <plan.json>] [--mode portable|symlink] [--repo <git-root>]
```

已装且仓内 `template_version` 与本包不同时，`init`（含 `--apply` / `--adopt-plan`）退出 1，并写出本会话接着要跑的 inspect 命令。不要把这次失败当成可以改用 `init --apply` 盖过去。

`check` / `sync` 使用**目标项目已安装**的内核，保持离线，不重新 prepare，不 `git pull`，不触发文档补全，不升版本：

```text
python3 <project-or-installed-ph-init>/scripts/ph_init.py check [--mode portable|symlink] [--repo <git-root>]
python3 <project-or-installed-ph-init>/scripts/ph_init.py sync [--apply] [--mode portable|symlink] [--repo <git-root>]
```

- `--mode` 缺省：先读 `.agents/ph.json` 声明，再从已有适配层推断，仍推断不出才用 `portable`；init / check / sync 一致。仓库级固定，工具内不做 mode 迁移。
- `portable`：根 `AGENTS.md` 与 canonical 字节一致；`CLAUDE.md` 为 `@.agents/AGENTS.md` stub；`.claude/skills/ph-*` 与 `.codex/skills/ph-*` 为完整受管镜像。
- `symlink`：上述入口是指向 canonical 的直接相对软链。禁止 hardlink / junction。`core.symlinks` 显式 false 时阻断。写入前探测软链能力。
- 未带 `--adopt-plan` 的 `init` 对 `docs/**` 已有安全普通文件只保留并报告待会话审阅，这不是已合并；**不得用这种安装先落模板再盖旧正文**，存量内容一律走 `--adopt-plan` 合并候选。其余冲突 fail-closed。`sync --apply` 只覆盖结构化 `content_drift`，不改 canonical 或 docs。

`--adopt-plan` 契约（仅当目标尚无 `.agents/ph.json`；已装旧版由本会话按 merge-update 步骤升级，不走 adopt）：

- `version` 固定 `1`；`repo` 是目标仓绝对路径；`release_version` 是本发行包版本。
- `sources`：合并基准快照，`{仓内相对路径: 正文 SHA256，文件缺失为 null}`；必含 `.agents/AGENTS.md`、`AGENTS.md`、`CLAUDE.md` 三个入口，以及 `files` 的全部目标路径。
- `files`：候选 UTF-8 正文，只允许 canonical `.agents/AGENTS.md`（必需）与 `docs/**`。候选由已有正文与脚手架整合：已有正文优先原样保留或引用登记，不复制第二套。
- plan 文件由会话在目标仓外生成：不进项目、不改发行树、不写秘密 / 令牌 / 完整连接串。脚本核对 `sources` 哈希与目标实态一致才落盘；哈希护栏只防错仓、错时点与中途变更，**不证明候选内容完整正确**，语义由会话 Agent 负责。

- 嵌套 symlink/junction、仓外解析、hardlink、受管镜像中的未托管多余文件保持阻断。`sync` 不升级 canonical、不补缺失 Skill。

## 工作流

1. **确认动作与范围并分流**。读目标 `.agents/ph.json`（没有就当未安装）。对目标跑 `prepare`，记下发行根。只要是 check/sync 就不生成文档、不升版本。然后：
   1. 已装且仓内版本**小于**发行根：读该根 `assets/scaffold/.agents/skills/ph-merge-update/SKILL.md`，**本会话按那份执行**（inspect → 按迁移说明语义合并 → verify → finalize）。旧项目没装这个 Skill 也以发行根这份为准。禁止 `init --apply` / `--adopt-plan`，不另开技能，不自动 finalize。
   2. 已装且版本相同：报告已接入；要 check / sync / 续做文档就走对应分支，不重跑安装、不升版本。
   3. 已装且仓内版本**大于**本包：停止，说明不要降级；换匹配或更新的正式包。
   4. 没装：继续下列安装 / adopt。
2. **初始化：准备发行根**。读该 `root` 的 `SKILL.md`，用该 root 的 `ph_init.py`。同时读该 root 的[初始化与文档补全](assets/scaffold/docs/约束规范/工程规范/初始化与文档补全.md)，不能先改准备好的发行树。
3. **只读盘点**：核对 Git 状态与已有内容，汇总七类证据：模块、代码、配置、真实依赖（锁文件）、测试、CI、旧约束（含 `docs/` 下非 PH 命名的旧文档目录）。已有正文优先引用登记，不复制第二套；待核实项与已定性为规则 / 事实 / 建议的条目分开，不臆造 ADR、意图、访谈、记忆或测试通过。
4. **dry-run 与报告整合**：同一 `root` 不加 `--apply` 跑 dry-run；`plan` / `skip` / `conflict` / `block` 是待整合材料，不是施工单。向用户交整合结果：直接落地、复用引用、冲突待裁决、不适用与保留范围。仅预检时不写 docs。根 `AGENTS.md` 在而 `.agents/AGENTS.md` 不在、受跟踪 `.worktrees/`、不安全链接或路径仍阻断，不能移走文件后偷偷强装。
5. **仓外合并候选**：获得本轮授权后，会话在目标仓外生成 `sources` 快照与合并候选 plan JSON（契约见命令节）。内核 adopt 只写 canonical 与 `docs/**`，不自动搬移或删除。已有正文优先复用 / 引用登记，不复制第二套、不重写已有证据的正确内容。
6. **adopt 安装**：用户确认候选后，同一 `root` 执行 `init --adopt-plan <plan>`，先 dry-run 再 `--apply`。`ph-init` 自装自身（含 scaffold、release 元数据、在线脚本、迁移资料）；scaffold 内不嵌套 `ph-init`。安装成功立即跑已装内核的 `check`。
7. **逐项补全与覆盖报告**：按已装指引分阶段派发 subagent。旧目录与顶层正文按指引 1.1 归并进三域：同主题合成单一正文，附件随所属正文走，旧计划不推定评审或通过；写前把原文备份到 `.agents/archived/<日期>-pre-init/`，修活动引用与索引后再移出活树旧文件，仓内快照即是可恢复原件，未授权或冲突记未完成。先取真实栈与代码证据，再按独立文件归属补 Wiki、前端、后端、工程与测试规范；官方资料按目标实际版本实时查阅并记录 URL、版本、访问日期与采用理由，搜索只用通用技术名，不上传项目内容。主会话维护 `.agents/init-report.md` 覆盖报告：矩阵每个独立 id 一行（落点、仓内证据、结果、说明），结果只用已核验 / 复用 / 不适用 / 待核实 / 冲突；PH 通用流程条目写采用声明，不编造项目记录。改 canonical 后按原 mode 先 dry-run 再在授权范围内 `sync --apply`，重新 `check`。没有 subagent 能力则如实报告限制并串行取证。
8. **交付或续做**：分别报告“PH 安装检查”“文档补全”结果，列已核验、复用、待采纳、待核实、不适用和冲突项。网络/子任务失败不抹掉已核验成果，也不宣称文档完成；续做读磁盘、`init-report` 与上次记录，不再 `init --apply`。需要时用刚装好的包初始化临时另一仓，确认自包含。

## 完成标准

- 未调用 ZCode `/init`，未对目标 `git pull`。
- 初始化的 dry 与 apply 来自同一 prepare `commit`；dry-run 未改目标，准备失败未用本地旧模板装“最新”。
- 未先安装模板再盖旧正文：存量内容经仓外合并候选接入，`sources` 快照与 plan 均在仓外生成，发行树未被改动；已有正文以复用 / 引用登记，未复制第二套，冲突未擅自裁决。
- `--adopt-plan` 仅用于尚无 `.agents/ph.json` 的目标；`--apply` 后已装内核 `check` 通过；未创建 `.zcode/skills`。
- `.agents/init-report.md` 覆盖指引第 5 节全部独立 id；未核实内容未伪装成规范或事实，未执行命令未标通过，未臆造 ADR / 意图 / 访谈 / 记忆 / 测试通过。安装检查通过不代表文档补全完成。最终 `docs/` 只留 `README.md` 与三域；未获迁移授权或存在冲突的旧目录记未完成，不把长期并存当完成。
- 已装旧版未走 `init --apply`；升级在本会话用发行根 `ph_merge_update.py` 做完，未另开技能、未自动 finalize。文档补全和普通 check/sync 未擅自升版本。
- 未自动 commit / push / 公开仓库、部署或发送通知。
