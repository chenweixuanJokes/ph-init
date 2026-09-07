"""Static coverage of the distributable initialization guide and wiki templates."""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / "assets/scaffold"
DOCS = SCAFFOLD / "docs"
ENGINEERING = DOCS / "约束规范/工程规范"


class DocsTemplateTests(unittest.TestCase):
    def test_engineering_guides_are_indexed_and_skill_reachable(self):
        index = (ENGINEERING / "README.md").read_text(encoding="utf-8")
        for name in ("初始化与文档补全.md", "安全与配置.md", "构建发布与运维.md"):
            self.assertTrue((ENGINEERING / name).is_file())
            self.assertIn(f"./{name}", index)
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("assets/scaffold/docs/约束规范/工程规范/初始化与文档补全.md", skill)

    def test_workbook_test_cases_and_conditional_components_are_mapped(self):
        guide = (ENGINEERING / "初始化与文档补全.md").read_text(encoding="utf-8")
        self.assertIn("F29 / F31 / F33", guide)
        self.assertIn("F30 / F32 / F34", guide)
        for component in ("Kong", "Eureka", "Apollo"):
            self.assertIn(component, guide)
        self.assertIn("仅实际使用", guide)
        for topic in ("D39 完成", "D58 同步", "D59 纠正", "D60 问答", "D54 记忆纠正"):
            self.assertIn(topic, guide)

    def test_all_wiki_templates_keep_honest_governance_fields(self):
        for path in (DOCS / "项目Wiki").rglob("*.md"):
            if path.name == "README.md":
                continue
            with self.subTest(path=path.relative_to(DOCS)):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"))
                frontmatter = text.split("---", 2)[1]
                for key in ("owner", "status", "last_verified", "verified_against", "refresh_trigger"):
                    self.assertRegex(frontmatter, rf"(?m)^{key}:")
                self.assertIn("status: draft", frontmatter)
                self.assertIn('last_verified: ""', frontmatter)
                self.assertIn('verified_against: ""', frontmatter)

    def test_each_docs_directory_indexes_direct_children(self):
        for directory in (DOCS, *(p for p in DOCS.rglob("*") if p.is_dir())):
            with self.subTest(directory=directory.relative_to(SCAFFOLD)):
                index = directory / "README.md"
                self.assertTrue(index.is_file())
                text = index.read_text(encoding="utf-8")
                links = re.findall(r"\]\(([^)]+)\)", text)
                targets = {(directory / link.split("#", 1)[0]).resolve()
                           for link in links if "://" not in link}
                for child in directory.iterdir():
                    if child.is_dir():
                        self.assertIn((child / "README.md").resolve(), targets)
                    elif child.suffix == ".md" and child != index:
                        self.assertIn(child.resolve(), targets)

    def test_docs_migration_keeps_schema_and_skill_contract(self):
        release = json.loads((ROOT / "release.json").read_text())
        self.assertEqual(release["schema_version"], "1.1.1")
        self.assertEqual(len(release["required_skills"]), 10)
        hops = json.loads((ROOT / "migrations/index.json").read_text())["migrations"]
        hop = next(h for h in hops if h["from_version"] == "1.1.2")
        self.assertEqual(hop["items"], ["init-docs-workflow", "docs-guidance", "docs-project-preserve"])


if __name__ == "__main__":
    unittest.main()
