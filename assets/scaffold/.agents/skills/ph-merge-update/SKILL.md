---
name: ph-merge-update
description: "已装 PH 项目升到正式发行版的步骤：从唯一 GitHub 源准备固定 tag/commit，按迁移链审阅合并，验收后再推进项目版本。用户说“升级 PH”“初始化 PH”“安装 harness”“合并更新 PH”且目标已装旧版时，由 ph-init 会话读本文件并执行，不另开技能。不要把未初始化仓库的安装、普通 check/sync、git pull、录入/实施/废弃意图、记忆或 worktree 误判为本文件的步骤。"
---

# ph-merge-update

已接入 PH 的仓库跟官方发行版对齐。这是 **`ph-init` 会话**在已装旧版上要执行的步骤，不是对外另开的分流技能。Agent 按迁移说明做语义合并；脚本只读状态、验收结构和收尾。不要用 `init --apply` 覆盖定制，不要在目标仓库 `git pull`。

旧项目可以没有本目录。从准备好的发行根读取：

`assets/scaffold/.agents/skills/ph-merge-update/SKILL.md`

然后由当前 `ph-init` 会话按该副本执行。

## 何时用 / 何时不用

使用：项目已有 `.agents/ph.json` 与 `.agents/AGENTS.md`，用户要升到正式版或恢复未完成升级。用户即使说的是「初始化 / 安装」，已装旧版也走本文件步骤。

不用：

- 空仓库或尚未接入 PH：仍由 `ph-init` 走安装 / adopt，本文件只描述已装升级步骤
- 只检查 / 同步适配层：项目已装的 `ph-init` `check` / `sync`
- 目标仓库拉远端、提交、推送、改可见性
- 记忆、worktree、录入 / 实施 / 废弃意图

## 来源与命令

唯一源：`https://github.com/chenweixuanJokes/ph-init.git`。`latest` = 数值最大的稳定 tag（排除预发布与非版本标签），并固定到该 tag 的 commit。无 tag、网络失败、tag/commit/元数据不一致则停止；不拿本地 `assets/scaffold` 或 `main` 冒充最新。

准备（下载在目标仓库外）：

```text
python3 <ph-init-root>/scripts/ph_release.py prepare --version latest|1.1.5 --repo <target>
```

stdout JSON 字段：`root` `version` `tag` `commit` `source`。`source` 是固定仓库 URL 字符串。本地已有该 commit 的检查不访问网络。

同一次预检与写入复用这个 `root`。读该 root 的本 Skill 与 `migrations/`。升级工具在发行根，不在目标旧包：

```text
python3 <release-root>/scripts/ph_merge_update.py inspect --repo <target>
python3 <release-root>/scripts/ph_merge_update.py verify --repo <target>
python3 <release-root>/scripts/ph_merge_update.py finalize [--apply] --repo <target>
```

`inspect` 只读，不走会提前拒绝旧版本的 `load_repo_manifest()`。`finalize` 才按原 adapter mode 同步候选适配层并在验收通过后写版本。默认 dry-run；用户明确要求写入才 `--apply`。

禁止：目标仓库 `git pull`、自动 `git commit` / `push`、`rm`（退役文件移 `~/trash/` 或 `.agents/updates/<ver>/backup/`）。

## 进度文件

`.agents/updates/<to_version>/state.json` 与同目录 `report.md`。`state.json`：

```json
{
  "from_version": "1.1.2",
  "to_version": "1.1.3",
  "source": {
    "repository": "https://github.com/chenweixuanJokes/ph-init.git",
    "tag": "v1.1.3",
    "commit": "<40-hex>"
  },
  "status": "in_progress",
  "items": [
    {
      "id": "init-docs-workflow",
      "status": "pending",
      "evidence": ""
    },
    {
      "id": "docs-guidance",
      "status": "pending",
      "evidence": ""
    },
    {
      "id": "docs-project-preserve",
      "status": "pending",
      "evidence": ""
    }
  ]
}
```

`status` 仅 `in_progress` | `complete`。每项 `id` 与迁移 `items` 一致；项状态仅 `pending` | `applied` | `not_applicable` | `blocked`；`evidence` 为字符串。链上每一跳的项都要出现（从 1.0.0 出发须含 `intent-domain`）。

`report.md` 写实际差异、保留内容、验证证据、未解决项；不含凭证或个人敏感信息。脚本成功 ≠ 语义合并正确。

## 工作流

1. **确认**。已初始化才继续。未初始化回到 `ph-init` 的安装 / adopt，不要在本步骤里装新仓。确认目标版本（默认 `latest`）与是否允许写入。
2. **准备发行根**。对目标跑 `prepare`（`ph-init` 会话通常已经做过，复用同一 `root`）。失败则停。记下 `root/version/tag/commit`。
3. **只读 inspect**。结合 manifest、真实 Skill 目录名、意图目录判定布局。可核实历史：
   - `1.0.0` 六 Skill，意图在 `进行中/`
   - `1.1.0` 旧名：`ph-intent-capture` / `plan` / `abandon`
   - `1.1.0` 新名：`ph-intent-new` / `impl` / `drop`，目录可能仍是 `进行中/`
   - 工作区已有 `待办/` `实施/`，版本锁仍可能是 `1.1.0`
   不能因 `template_version=1.1.0` 猜是哪一套。未知布局或缺迁移记录则阻断。
4. **建或恢复清单**。读 `<release-root>/migrations/index.json` 与从 `from_version` 到目标的说明。已有 `state.json` 时对照文件实态：已落地不重做、不重复插入章节。版本已写成目标但 `report` / 项未完成 → 继续验收，不跳过。
5. **按项合并**（用户确认后才写盘）。框架资产更新到目标态。AGENTS、规范、README 按段落合并，保留已填项目事实。业务文档只做迁移要求的调整，不改访谈原话、历史代码块、业务编号、无关 Wiki/记忆。init 会话中 subagent 生成的文档同样属于项目定制；不因升级重新生成 Wiki、全网调研或替换技术栈。新指引补缺与项目正文分开审阅，只有另行授权补全时才执行扩展调研。旧意图目录按完整链的最终迁移要求处理，不能仅按旧模板猜业务状态。
6. **冲突**。与项目显式规则或本地定制相反 → 该项 `blocked`，停受影响写入，请用户决定。旧 Skill 重命名退役须审阅备份；有定制不静默删。根 AGENTS 在而 canonical 不在、仓外软链、嵌套 symlink/junction、受跟踪 `.worktrees/`：fail-closed。
7. **verify**。项无 `pending`/`blocked`，十 Skill 与目录实态符合目标，`report.md` 完整。不通过不 finalize。
8. **finalize**。先 dry-run。用户确认后 `--apply`：同步候选适配层（不改 mode），candidate check 通过前不改磁盘 `ph.json` 版本；通过后再写 `template_version`/`schema_version` 并跑常规 `check`。失败保持 `in_progress`，不宣称完成。

更新项目内 `ph-init` payload 用本次 `release-root`，保留该副本上的项目定制。`check` / `sync` 用项目已装内核，离线，不重新 `prepare`。

## 1.1.1 项（按实态勾）

完整条文读 `<release-root>/migrations/1.1.0-to-1.1.1.md`；从 1.0.0 出发先读 `<release-root>/migrations/1.0.0-to-1.1.0.md`。索引是 `<release-root>/migrations/index.json`。

| id | 做完的样子 |
| --- | --- |
| `intent-domain` | 已有意图三 Skill（旧名或新名）及意图与访谈规范；否则从六 Skill 补齐。已有则 `not_applicable` |
| `intent-skill-names` | 目录与入口为 `new/impl/drop`；旧名已备份退役 |
| `intent-lifecycle` | 存在 `待办/` `实施/` 及 README；导航已改。不搬业务 `进行中/` |
| `online-source` | 项目内 ph-init 入口改为 prepare → 该 root 的 init；失败阻断写清楚 |
| `merge-update` | 本 Skill 已安装；`.agents/updates/<ver>/` 有 state/report |
| `schema-contract` | 目标契约十 Skill / Schema 1.1.1；版本字段只在 finalize 后写 |
| `project-content` | 混合文件已合并 PH 入口；项目事实仍在 |

## 1.1.2 意图状态项

读 `<release-root>/migrations/1.1.1-to-1.1.2.md`。`intent-no-completed` 将存量已完成条目保留结果记录后迁入对应实施分类；`intent-legacy-inprogress` 按真实启动情况处理旧进行中条目，不凭目录猜业务状态。信息不足则 blocked，不能跳过这两项而只勾前后版本表。

## 1.1.3 文档补全项

完整条文读 `<release-root>/migrations/1.1.2-to-1.1.3.md`，从更早版本出发仍须读完整链。

| id | 做完的样子 |
| --- | --- |
| `init-docs-workflow` | 项目已装 ph-init 包携带新工作流、保留同名 docs 的内核与完整指导材料；check/sync 不生成文档 |
| `docs-guidance` | 新增工程指导、各端／测试细节及索引按段落补缺；已拆专文的等价落点有证据，不复制规则 |
| `docs-project-preserve` | 已审阅并记录项目正文、用例、核验历史与定制保留证据；未授权的全文补全只记录缺口，不执行 |

项目资料仍有占位不阻止这次指导升级，但不能把“升级完成”说成“文档补全完成”。发生规则冲突则对应项 blocked，不 finalize。重复执行先读磁盘与进度，已有章节不重复追加。

## 完成标准

- 未对目标 `git pull`，未当最新源用 `main` 或未准备的本地 scaffold。
- dry-run / `inspect` 不写目标；冲突项保持原文件。
- `state.status=complete` 仅当 verify + finalize 成功且常规 `check` 通过。
- adapter mode 未变；`进行中/` 业务条目未被批量改派。
- 未自动 commit / push / 公开仓库。
