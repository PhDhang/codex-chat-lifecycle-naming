import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "chat-lifecycle-naming"
HELPER = SKILL_ROOT / "scripts" / "chat_lifecycle.py"
SKILL_MD = SKILL_ROOT / "SKILL.md"


def load_helper():
    spec = importlib.util.spec_from_file_location("chat_lifecycle", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper: {HELPER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ChatLifecycleAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = load_helper()

    def test_A_new_task_uses_exact_in_progress_title(self):
        actual = self.helper.normalize_title(
            "测试项目｜会话命名验证", "IN_PROGRESS"
        )
        self.assertEqual(actual, "☀️测试项目｜会话命名验证")

    def test_B_blocked_task_remains_in_progress(self):
        decision = self.helper.validate_gate(
            phase_status="IN_PROGRESS",
            acceptance=None,
            blockers="交付物缺失",
            basename="测试项目｜会话命名验证",
            next_action="补齐交付物并重新验证",
        )
        self.assertEqual(decision.phase_status, "IN_PROGRESS")
        self.assertEqual(decision.chat_prefix, "☀️")
        self.assertEqual(decision.title, "☀️测试项目｜会话命名验证")
        self.assertIn("PHASE_STATUS=IN_PROGRESS", decision.status_block)
        self.assertIn("CHAT_PREFIX=☀️", decision.status_block)

    def test_C_complete_gate_changes_only_prefix(self):
        decision = self.helper.validate_gate(
            phase_status="COMPLETE",
            acceptance="PASS",
            blockers="NONE",
            basename="☀️测试项目｜会话命名验证",
            next_action=None,
        )
        self.assertEqual(decision.phase_status, "COMPLETE")
        self.assertEqual(decision.chat_prefix, "✅️")
        self.assertEqual(decision.basename, "测试项目｜会话命名验证")
        self.assertEqual(decision.title, "✅️测试项目｜会话命名验证")
        self.assertEqual(
            decision.status_block,
            "\n".join(
                [
                    "PHASE_STATUS=COMPLETE",
                    "CHAT_PREFIX=✅️",
                    "CHAT_BASENAME=测试项目｜会话命名验证",
                    "ACCEPTANCE=PASS",
                    "BLOCKERS=NONE",
                ]
            ),
        )

    def test_C_rejects_inconsistent_complete_gate(self):
        with self.assertRaisesRegex(ValueError, "COMPLETE requires"):
            self.helper.validate_gate(
                phase_status="COMPLETE",
                acceptance="PASS",
                blockers="测试失败",
                basename="测试项目｜会话命名验证",
                next_action=None,
            )

    def test_D_prefix_normalization_is_idempotent(self):
        contaminated = [
            "☀️☀️测试项目｜会话命名验证",
            "✅️✅️测试项目｜会话命名验证",
            "☀️✅️测试项目｜会话命名验证",
            "✅️☀️测试项目｜会话命名验证",
            "🚦测试项目｜会话命名验证",
            "🚥测试项目｜会话命名验证",
        ]
        for value in contaminated:
            with self.subTest(value=value):
                in_progress = self.helper.normalize_title(value, "IN_PROGRESS")
                complete = self.helper.normalize_title(value, "COMPLETE")
                self.assertEqual(in_progress, "☀️测试项目｜会话命名验证")
                self.assertEqual(complete, "✅️测试项目｜会话命名验证")
                self.assertEqual(
                    self.helper.normalize_title(in_progress, "IN_PROGRESS"),
                    in_progress,
                )
                self.assertEqual(
                    self.helper.normalize_title(complete, "COMPLETE"), complete
                )

    def test_E_skill_preserves_native_title_and_fallback_contract(self):
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        for required in [
            "set_thread_title",
            "read back",
            "/rename",
            "PHASE_STATUS=COMPLETE",
            "ACCEPTANCE=PASS",
            "BLOCKERS=NONE",
            "Never mass-rename historical tasks",
        ]:
            self.assertIn(required, skill_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
