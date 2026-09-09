"""Static contract tests for the documented init workflow (skill + scaffold docs).

These checks keep the workflow requirements explicit in the shipped text:
adopt-plan contract, legacy-content onboarding, evidence-based completion and
the init-report coverage convention. They assert concepts and structure, not
exact prose, and never execute the installer.
"""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / "assets/scaffold"
GUIDE = SCAFFOLD / "docs/约束规范/工程规范/初始化与文档补全.md"
GOVERNANCE = SCAFFOLD / "docs/约束规范/工程规范/文档治理.md"
AGENTS = SCAFFOLD / ".agents/AGENTS.md"
EVALS = ROOT / "evals/evals.json"

RESULT_STATES = ("已核验", "复用", "不适用", "待核实", "冲突")
EVIDENCE_KINDS = ("模块", "代码", "配置", "真实依赖", "测试", "CI", "旧约束")
ADOPT_SOURCES_ENTRIES = (".agents/AGENTS.md", "AGENTS.md", "CLAUDE.md")


def scaffold_docs_texts():
    for path in sorted((SCAFFOLD / "docs").rglob("*.md")):
        yield path, path.read_text(encoding="utf-8")


class SkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    def test_batch_version_single_ph_version_contract(self):
        self.assertIn("1.1.8", self.skill)
        self.assertNotIn("1.1.7", self.skill)
        self.assertNotIn("1.1.1", self.skill)  # separate schema version is gone
        self.assertIn("urn:ph:schema:project-harness", self.skill)
        self.assertIn("不再有独立的 Schema 版本", self.skill)

    def test_one_time_entry_switch_documented(self):
        # old (<=1.1.7) prepare necessarily rejects the schema-less package
        self.assertIn("必然拒绝本包", self.skill)
        self.assertIn("不假称自动恢复", self.skill)
        self.assertIn("v1.1.8", self.skill)
        self.assertIn("新的仓外安全目录", self.skill)
        self.assertIn("不覆盖用户级入口与目标项目", self.skill)
        self.assertIn("prepare --version 1.1.8", self.skill)
        # old schema_version field is removed only after finalize passes
        self.assertIn("仅在 finalize", self.skill)

    def test_skill_keeps_upgrade_in_same_session(self):
        self.assertIn("本会话按那份执行", self.skill)
        self.assertIn("ph_merge_update.py", self.skill)
        self.assertIn("不另开技能", self.skill)
        self.assertNotIn("转交", self.skill)
        self.assertNotIn("转 merge-update", self.skill)

    def test_mode_default_infers_before_portable(self):
        mode_lines = [line for line in self.skill.splitlines() if "--mode" in line]
        self.assertTrue(mode_lines, "skill must document the --mode default")
        bullet = next(line for line in mode_lines if "缺省" in line)
        self.assertIn("推断", bullet)
        self.assertIn("portable", bullet)
        self.assertNotIn("`init` 为 `portable`", self.skill)  # old wrong claim

    def test_adopt_plan_cli_contract_is_explicit(self):
        self.assertIn("--adopt-plan", self.skill)
        for term in ("version", "repo", "release_version", "sources", "files"):
            self.assertIn(term, self.skill)
        self.assertIn("三个入口", self.skill)
        for entry in ADOPT_SOURCES_ENTRIES:
            self.assertIn(entry, self.skill)
        self.assertIn("docs/**", self.skill)
        self.assertIn("必需", self.skill)  # canonical file is required
        self.assertIn("仓外", self.skill)
        self.assertIn("ph.json", self.skill)  # only for not-yet-initialized targets
        self.assertIn("不证明", self.skill)  # hash guard != semantic proof

    def test_skill_forbids_template_over_legacy_content(self):
        self.assertIn("盖旧正文", self.skill)
        self.assertIn(".agents/init-report.md", self.skill)
        for state in RESULT_STATES:
            self.assertIn(state, self.skill)

    def test_skill_merges_legacy_dirs_instead_of_keeping_them(self):
        self.assertNotIn("保留原位", self.skill)
        self.assertNotIn("不搬旧文档", self.skill)
        self.assertIn("归并", self.skill)
        self.assertIn("不自动搬移或删除", self.skill)
        self.assertIn("未完成", self.skill)


class GuideContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guide = GUIDE.read_text(encoding="utf-8")

    def test_legacy_content_onboarding_rules(self):
        self.assertIn("用旧内容接入", self.guide)
        self.assertIn("复用", self.guide)
        self.assertIn("不复制第二套", self.guide)
        for legacy in ("specs", "domains", "plans"):
            self.assertIn(legacy, self.guide)
        self.assertIn("归并", self.guide)
        self.assertIn("深链", self.guide)
        self.assertIn("效力", self.guide)
        self.assertNotIn("保留原位", self.guide)

    def test_docs_finish_in_three_domains(self):
        for term in ("README.md", "约束规范", "意图", "项目Wiki", "旧路径 → 新落点",
                     "附件", "活动引用", "空壳", "软链"):
            self.assertIn(term, self.guide)
        self.assertIn("只允许", self.guide)

    def test_migration_requires_authorization_and_preserves_sources(self):
        for term in ("本轮授权", ".agents/archived", "哈希", "未完成", "不自动搬移或删除"):
            self.assertIn(term, self.guide)
        self.assertIn("旧正文", self.guide)
        self.assertIn("历史记录", self.guide)
        self.assertNotIn("仓外备份", self.guide)

    def test_legacy_plans_are_not_fabricated_intents(self):
        self.assertIn("已有计划", self.guide)
        self.assertIn("不推定评审", self.guide)
        self.assertIn("交付", self.guide)
        self.assertIn("实施", self.guide)
        self.assertIn("不造纪要", self.guide)

    def test_same_topic_merges_into_one_body(self):
        self.assertIn("同主题", self.guide)
        self.assertIn("一个正文", self.guide)
        self.assertIn("不是把两个版本全文拼在一起", self.guide)
        self.assertIn("不以“代码为准”擅自废止规则", self.guide)

    def test_attachments_follow_body_and_are_not_executed(self):
        self.assertIn("附件", self.guide)
        self.assertIn("不因整理而执行", self.guide)
        self.assertIn(".agents/archived", self.guide)
        self.assertIn("可恢复原件", self.guide)

    def test_archived_snapshot_convention_is_in_repo(self):
        archived = SCAFFOLD / ".agents/archived/README.md"
        self.assertTrue(archived.is_file(), "scaffold must ship .agents/archived/README.md")
        text = archived.read_text(encoding="utf-8")
        for term in (".agents/archived", "pre-init", "原样", "可恢复", "memory/archive", "不自动"):
            self.assertIn(term, text)
        self.assertIn(".agents/archived", self.guide)
        self.assertIn("可恢复原件", self.guide)
        self.assertIn("plan JSON", self.guide)
        # adopt plan stays outside the repo; source-file backup does not
        self.assertIn("目标仓外", self.guide)

    def test_inventory_requires_all_evidence_kinds(self):
        self.assertTrue(all(kind in self.guide for kind in EVIDENCE_KINDS),
                        "guide must enumerate every evidence kind")

    def test_snapshot_inventory_accounts_for_ignored_build_inputs(self):
        for term in ("git ls-files", ".gitignore", ".java-version", "哈希", "非凭据"):
            self.assertIn(term, self.guide)
        self.assertIn("副本缺失不代表原项目不存在", self.guide)

    def test_report_does_not_hide_unresolved_items(self):
        self.assertIn("不能只在页脚", self.guide)
        self.assertIn("不表示问题全部解决", self.guide)
        self.assertIn("不以“代码为准”擅自废止规则", self.guide)

    def test_dry_run_output_requires_integration(self):
        self.assertIn("施工单", self.guide)
        self.assertIn("待整合", self.guide)
        for category in ("直接落地", "复用引用", "冲突待裁决", "不适用与保留"):
            self.assertIn(category, self.guide)

    def test_adopt_plan_flow_documented_with_snapshot(self):
        self.assertIn("init --adopt-plan", self.guide)
        for key in ('"version": 1', '"repo"', '"release_version"', '"sources"', '"files"'):
            self.assertIn(key, self.guide)  # the shipped JSON example
        self.assertIn("SHA256", self.guide)
        self.assertIn("仓外", self.guide)
        self.assertIn("ph.json", self.guide)
        self.assertIn("不证明候选内容正确", self.guide)

    def test_init_report_convention(self):
        self.assertIn("`.agents/init-report.md`", self.guide)
        self.assertIn("实现记录", self.guide)
        for column in ("`id`", "`落点`", "`仓内证据`", "`结果`", "`说明`"):
            self.assertIn(column, self.guide)
        for state in RESULT_STATES:
            self.assertIn(state, self.guide)
        self.assertIn("每个独立 id", self.guide)
        self.assertIn("采用声明", self.guide)
        # the matrix itself still enumerates the boundary ids of each group
        for ident in ("E1", "E2", "C61", "C65", "F3", "F34", "D35", "D39",
                      "D40", "D44", "C45", "C50", "D51", "D60"):
            self.assertIn(ident, self.guide)

    def test_section_references_into_guide_resolve(self):
        headings = {int(m.group(1)) for m in re.finditer(r"(?m)^## (\d+)\. ", self.guide)}
        self.assertTrue(headings)
        for path, text in scaffold_docs_texts():
            for m in re.finditer(r"初始化与文档补全\.md\)\s*§(\d+)", text):
                self.assertIn(int(m.group(1)), headings,
                              f"{path.name} references a missing guide section")
            for m in re.finditer(r"初始化与文档补全\.md#(\d+)-", text):
                self.assertIn(int(m.group(1)), headings,
                              f"{path.name} references a missing guide anchor")


class EntryPointsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.governance = GOVERNANCE.read_text(encoding="utf-8")
        cls.agents = AGENTS.read_text(encoding="utf-8")

    def test_governance_declares_init_report_and_legacy_dirs(self):
        self.assertIn("init-report", self.governance)
        self.assertIn("归并", self.governance)
        self.assertNotIn("保留原位", self.governance)
        self.assertIn("深链", self.governance)
        self.assertIn(".agents/archived", self.governance)

    def test_canonical_agents_navigation_mentions_both(self):
        self.assertIn("init-report", self.agents)
        self.assertIn("深链", self.agents)
        self.assertIn("归并", self.agents)
        self.assertNotIn("保留原位", self.agents)
        self.assertIn(".agents/archived", self.agents)


class EvalsCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(EVALS.read_text(encoding="utf-8"))
        cls.items = data["evals"]

    def test_ids_unique_and_scenarios_present(self):
        ids = [item["id"] for item in self.items]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 14)
        blob = "\n".join(item["prompt"] + item["expected_output"] for item in self.items)
        # legacy docs, merge, attachments, same-topic, unapproved plan, pure-code, stale-conflict
        self.assertIn("specs", blob)
        self.assertIn("归并", blob)
        self.assertIn("附件", blob)
        self.assertIn("同主题", blob)
        self.assertIn("不推定评审", blob)
        self.assertIn("一个 .md 都没有", blob)
        self.assertIn("Gradle", blob)
        self.assertIn("复用", blob)
        self.assertIn(".agents/archived", blob)
        self.assertNotIn("仓外备份", blob)
        self.assertNotIn("保留原位", blob)
        self.assertGreaterEqual(len(ids), 18)
        self.assertIn("不另开技能", blob)
        self.assertNotIn("转交 ph-merge-update", blob)

    def test_every_eval_disclaims_actual_execution(self):
        for item in self.items:
            if item["id"] < 8:
                continue  # legacy trigger-negative items predate the convention
            with self.subTest(id=item["id"]):
                self.assertTrue(item["prompt"].strip())
                self.assertTrue(item["expected_output"].strip())
                self.assertIn("本 eval 不表示已实测", item["expected_output"])


if __name__ == "__main__":
    unittest.main()
