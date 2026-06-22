from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class DecisionModelTest(unittest.TestCase):
    def test_fake_llm_satisfies_decision_model_protocol(self) -> None:
        from min_agent.decision_model import DecisionModel
        from min_agent.fake_llm import FakeLLM

        model: DecisionModel = FakeLLM()

        self.assertTrue(hasattr(model, "decide"))


if __name__ == "__main__":
    unittest.main()
