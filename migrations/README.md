# 迁移说明

相邻正式版本之间的变化与适配步骤。`index.json` 是顺序源；升级必须读完起点到目标的完整链。后来覆盖的中间变化可以合并成最终操作，但不能跳过未知版本或缺失记录。

`1.0.0` 与两套 `1.1.0` 命名是仓库可追溯的历史布局，不是已发布 tag。首个正式 tag 是 `v1.1.1`，不追认旧 `1.1.0` tag。

## 维护

- 每个对外批次写一份 `migrations/<from>-to-<to>.md`，并在 `index.json` 追加一条相邻记录。
- `items` 使用稳定 id，与项目 `.agents/updates/<to_version>/state.json` 的 `items[].id` 一致。
- 无需存量迁移的批次也要有说明，写明“无存量项”。
- 链接用有效相对路径。不要把 `main` 或本地 `assets/scaffold` 写成已发布最新版。

## 说明模板

每份迁移说明使用下列标题，缺一不可：

```md
# <from_version> → <to_version>

## why
为什么有这次变化。历史补录须标明不是新发布。

## from
起点的真实行为、Skill 名、目录和版本锁。按文件实态识别，不靠口口相传。

## to
目标行为。可把后续覆盖的中间态写成最终操作。

## affected
会被动到的路径、Skill、厂商入口、索引。只列迁移要求改的范围。

## preserve
默认保留：项目事实、访谈原话、业务编号、旧进行中条目、无关 Wiki/记忆、adapter mode。

## conflict
与项目显式规则或本地定制冲突时停止受影响项，备份后请用户决定。禁止 `rm`。

## verify
可检查的完成标准。未完成不得推进 `template_version`。
```

当前链：

| 段 | 说明 | 项 |
| --- | --- | --- |
| [1.0.0 → 1.1.0](./1.0.0-to-1.1.0.md) | 历史补录：意图域与三 Skill | `intent-domain` |
| [1.1.0 → 1.1.1](./1.1.0-to-1.1.1.md) | 首个正式发布批次 | `intent-skill-names` `intent-lifecycle` `online-source` `merge-update` `schema-contract` `project-content` |
| [1.1.1 → 1.1.2](./1.1.1-to-1.1.2.md) | 意图交付留实施，取消旧状态目录 | `intent-no-completed` `intent-legacy-inprogress` |
| [1.1.2 → 1.1.3](./1.1.2-to-1.1.3.md) | init 会话补全文档与项目内容保护 | `init-docs-workflow` `docs-guidance` `docs-project-preserve` |
| [1.1.3 → 1.1.4](./1.1.3-to-1.1.4.md) | 存量约束合并接入与全量文档取证 | `adopt-plan-init` `adopt-existing-content` `init-report-coverage` |
| [1.1.4 → 1.1.5](./1.1.4-to-1.1.5.md) | 已装旧版由 ph-init 会话做完升级 | `init-unified-entry` |
| [1.1.5 → 1.1.6](./1.1.5-to-1.1.6.md) | 对用户提问改成日常用语，内部字段名仍留在代理侧 | `plain-user-questions` |
| [1.1.6 → 1.1.7](./1.1.6-to-1.1.7.md) | 准备成功后已登录则加星并建账号副本，不改下载源 | `prepare-star-fork` |
