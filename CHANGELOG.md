# Changelog

本仓库用户可见的正式版本摘要。相邻版本的适配步骤见 [migrations/README.md](./migrations/README.md)。

Schema 与发布版本独立。本批因版本锁与必需 Skill 清单变化，Schema 同为 `1.1.1`。以后只改 Skill 正文或文档时，不必自动升 Schema。

尚未打过历史 tag。`1.0.0` 与两套 `1.1.0` 命名是可追溯提交，不是已发布 tag。首个正式 tag 预定 `v1.1.1`，不追认 `v1.1.0`。

## 1.1.1

正式源：`https://github.com/chenweixuanJokes/ph-init.git`。`latest` 按稳定 tag 数值排序并固定 commit。

- Init：先 `scripts/ph_release.py prepare`，再执行该发行根的 `ph_init.py`。无 tag、网络失败或元数据不一致则阻断；不把本地 `assets/scaffold` 或 `main` 当成最新版。
- 新增第十个 Skill `ph-merge-update`：inspect 只读、Agent 按迁移链合并、verify / finalize 验收后才写项目版本。不在目标仓库 `git pull`。
- 意图 Skill 名：`capture/plan/abandon` → `new/impl/drop`（若项目仍是旧名）。
- 意图目录：新增 `待办/` 与 `实施/`；旧 `进行中/` 业务条目按需兼容，不批量改派。
- 发布元数据 `release.json`；迁移链见 [migrations/index.json](./migrations/index.json)。
- `build_scaffold.py` / `build_project_template.py` 仍是旧 monorepo 作者工具，不是本独立仓的发布源。

升级项：`intent-skill-names` `intent-lifecycle` `online-source` `merge-update` `schema-contract` `project-content`。从 1.0.0 出发还要做历史项 `intent-domain`。

## 1.1.0（历史，无 tag）

补录。同一版本锁下先后存在：

1. 九 Skill 旧名 `ph-intent-capture` / `ph-intent-plan` / `ph-intent-abandon`，意图目录仍为 `进行中/`。
2. 改名为 `ph-intent-new` / `ph-intent-impl` / `ph-intent-drop`。
3. 工作区已有待办/实施目录调整，版本锁仍可能是 `1.1.0`。

详见 [migrations/1.0.0-to-1.1.0.md](./migrations/1.0.0-to-1.1.0.md) 与 [migrations/1.1.0-to-1.1.1.md](./migrations/1.1.0-to-1.1.1.md)。

## 1.0.0（历史，无 tag）

六 Skill：`ph-init`、worktree 一对、memory 三个。意图只有 `进行中/`。`init` / `check` / `sync` 不是升级器。
