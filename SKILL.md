---
name: ph-init
description: "初始化、检查或同步本仓库的项目级 Harness（PH）：从唯一 GitHub 源准备正式发行版、安装 canonical 与十个 ph-* skills；存量项目在 init 会话中通过 subagent 按代码与实时官方资料补齐 Wiki、工程/前端/后端/测试规范。用户说“初始化 PH”“安装项目级 harness”“检查 PH”“同步 PH”“ph-init”“bootstrap harness”时必须使用。已初始化项目升正式版转交 ph-merge-update。不要把 ZCode 内置 /init、厂商脚手架、git init、目标仓 git pull、或 ph-memory-* / ph-worktree-* / ph-intent-* 误判为本技能。"
---

# ph-init

把正式发行版的 PH 模板落到尚未接入的 Git 仓库，并在初始化会话补齐项目文档；也可只检查 / 修复适配层。已接入项目的版本合并走 `ph-merge-update`，不要用 `init --apply` 覆盖定制。

## 何时用 / 何时不用

使用：

- 空仓库或尚未接入 PH 的存量仓库：先准备正式版，再安装与补全文档
- 检查 portable 副本 / symlink 是否与**项目已装** canonical 一致
- 同步适配层漂移（根 `AGENTS.md`、`CLAUDE.md`、Claude / Codex skill 镜像）
- 续做本次初始化未完成的文档：读已装指引、核对磁盘实态；不重跑安装、不借机升版本

不用：

- 已有 `.agents/ph.json` 且用户要升官方版 → `ph-merge-update`（可从新发行根 `assets/scaffold/.agents/skills/ph-merge-update/SKILL.md` 读取，不要求旧项目已安装它）
- ZCode `/init`、厂商脚手架、`git init` 本身
- 在目标仓库 `git pull` 当升级
- `ph-memory-*` / `ph-worktree-*` / `ph-intent-*`

## 唯一源与准备

正式源只有 `https://github.com/chenweixuanJokes/ph-init.git`。`latest` 取数值最大的稳定 tag（排除预发布与非版本标签），并固定到该 tag 的 commit。本批版本为 `1.1.3`（Schema `1.1.1`，十个必需 Skill）。Schema 与发布版本独立，本批不改 Schema。

当前这份 Skill 可能是旧用户入口或 shadow 副本。**初始化必须先准备发行根，再读该根的 `SKILL.md` 并只执行该根脚本**。不要用眼前这份本地 `assets/scaffold` 冒充最新版。离线内核可以安装它携带的确定版本，但不代表最新正式版。

```text
python3 <ph-init-root>/scripts/ph_release.py prepare --version latest|1.1.3 --repo <target>
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

`check` / `sync` 使用**目标项目已安装**的内核，保持离线，不重新 prepare，不 `git pull`，不触发文档补全：

```text
python3 <project-or-installed-ph-init>/scripts/ph_init.py check [--mode portable|symlink] [--repo <git-root>]
python3 <project-or-installed-ph-init>/scripts/ph_init.py sync [--apply] [--mode portable|symlink] [--repo <git-root>]
```

- `--mode` 缺省：`init` 为 `portable`；`check` / `sync` 从已有适配层推断。仓库级固定，工具内不做 mode 迁移。
- `portable`：根 `AGENTS.md` 与 canonical 字节一致；`CLAUDE.md` 为 `@.agents/AGENTS.md` stub；`.claude/skills/ph-*` 与 `.codex/skills/ph-*` 为完整受管镜像。
- `symlink`：上述入口是指向 canonical 的直接相对软链。禁止 hardlink / junction。`core.symlinks` 显式 false 时阻断。写入前探测软链能力。
- `init` 对 `docs/**` 的已有安全普通文件只保留，报告待会话审阅；这不是已合并。其余冲突 fail-closed。`sync --apply` 只覆盖结构化 `content_drift`，不改 canonical 或 docs。
- 嵌套 symlink/junction、仓外解析、hardlink、受管镜像中的未托管多余文件保持阻断。`sync` 不升级 canonical、不补缺失 Skill。

## 工作流

1. **确认动作与范围**：初始化 / 检查 / 同步 / 文档续做；是否写入；mode。已初始化且要升正式版 → 转 merge-update。只要是 check/sync 就不生成文档。
2. **初始化：准备发行根**。对目标跑 `prepare`。读该 `root` 的 `SKILL.md`，用该 root 的 `ph_init.py`。同时读该 root 的[初始化与文档补全](assets/scaffold/docs/约束规范/工程规范/初始化与文档补全.md)，不能先改准备好的发行树。
3. **只读盘点与 dry-run**：先核对 Git 状态、已有约束、代码、依赖版本、CI 和测试。再用同一 `root` 不加 `--apply`，把 `plan` / `skip` / `conflict` / `block` 给用户，并列出拟补全文档、证据来源与保留范围。仅预检时不写 docs。
4. **冲突**：已有安全 docs 保留待会话审阅；规则冲突停止受影响文档。非 docs 的不同文件不覆盖。根 `AGENTS.md` 在而 `.agents/AGENTS.md` 不在、受跟踪 `.worktrees/`、不安全链接或路径仍阻断，不能移走文件后偷偷强装。
5. **安装**：用户确认本轮安装与补全范围后，同一 `root` 加 `--apply`。缺失 docs 安装，已有 docs 不覆盖。`ph-init` 自装自身（含 scaffold、release 元数据、在线脚本、迁移资料）；scaffold 内不嵌套 `ph-init`。安装成功先跑已装内核的 `check`。
6. **同会话补全文档**：按上述指引分阶段派发 subagent。先取得真实栈与代码证据，再按独立文件归属补 Wiki、前端、后端、工程与测试规范。官方资料按目标实际版本实时查阅，记录 URL、版本、访问日期和采用理由；搜索只用通用技术名，不上传项目内容。已有规则、当前事实、待采纳建议与待核实项分开，主 Agent 统一合并索引。没有某端/组件则标不适用，不造意图、历史决策、记忆或已通过用例。没有 subagent 能力则如实报告限制并按相同步骤串行取证，不假称已派发。
7. **文档验收与适配同步**：核对条目落点、README、相对链接、Wiki 五字段、命令来源、执行证据与脱敏。`.agents/AGENTS.md` 只填项目摘要与导航；改 canonical 后使用已装内核按原 mode 先 dry-run 再在授权范围内 `sync --apply`，重新 `check`。不编辑包内 scaffold 来填目标项目事实。
8. **交付或续做**：分别报告“PH 安装检查”“文档补全”结果，列已核验、待采纳、待核实、不适用和冲突项。网络/子任务失败不抹掉已核验成果，也不宣称文档完成；续做读磁盘和上次记录，不再 `init --apply`。需要时用刚装好的包初始化临时另一仓，确认自包含。

## 完成标准

- 未调用 ZCode `/init`，未对目标 `git pull`。
- 初始化的 dry 与 apply 来自同一 prepare `commit`；dry-run 未改目标，准备失败未用本地旧模板装“最新”。
- `--apply` 后 `check` 通过；未创建 `.zcode/skills`；已有安全 docs 未被内核覆盖。
- 存量项目已按指引处理适用文档与索引；未核实内容未伪装成规范或事实，未执行命令未标通过。安装检查通过不代表文档补全完成。
- 已初始化升级未走 `init --apply`；文档补全和普通 check/sync 未擅自升版本。
- 未自动 commit / push / 公开仓库、部署或发送通知。
