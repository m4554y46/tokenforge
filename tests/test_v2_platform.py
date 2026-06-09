"""Tests TokenForge Intelligence Platform v2."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# DB isolée pour les tests
_test_db = os.path.join(tempfile.gettempdir(), "tokenforge_v2_test.db")
if os.path.exists(_test_db):
    os.remove(_test_db)
os.environ["DATABASE_URL"] = _test_db


class TestMemoryLayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.core.database_v2 import init_v2_db
        init_v2_db()

    def test_user_memory_crud(self):
        from backend.memory.user_memory_service import UserMemoryService
        svc = UserMemoryService()
        svc.set_preference("default", "user1", "language", "fr")
        svc.set_preference("default", "user1", "tone", "professional")
        profile = svc.get_profile("default", "user1")
        self.assertEqual(profile["preferences"]["language"]["value"], "fr")
        exported = svc.export_profile("default", "user1")
        self.assertIn("exported_at", exported)
        svc.delete_profile("default", "user1")
        self.assertEqual(len(svc.get_profile("default", "user1")["preferences"]), 0)

    def test_tenant_memory(self):
        from backend.memory.tenant_memory_service import TenantMemoryService
        svc = TenantMemoryService()
        svc.add_term("default", "acronym", "RFP", "Request for Proposal")
        svc.validate_term("default", "acronym", "RFP")
        knowledge = svc.get_validated_knowledge("default")
        self.assertTrue(any(k["term"] == "RFP" for k in knowledge))

    def test_memory_updater(self):
        from backend.memory.memory_updater import MemoryUpdater
        updater = MemoryUpdater()
        result = updater.learn_from_interaction(
            "default", "user1",
            "Réponds toujours en français avec un ton professionnel format tableau",
            model="gpt-4o",
        )
        self.assertIn("updates", result)
        self.assertTrue(len(result["updates"]) > 0)

    def test_memory_retriever(self):
        from backend.memory.memory_retriever import MemoryRetriever
        retriever = MemoryRetriever()
        ctx = retriever.retrieve_for_prompt("default", "user1", "Analyse ce RFP")
        self.assertIn("context_prefix", ctx)


class TestFinOps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.core.database_v2 import init_v2_db
        init_v2_db()

    def test_cost_registry_and_roi(self):
        from backend.finops.cost_registry import CostRegistry
        from backend.finops.roi_engine import ROIEngine
        registry = CostRegistry()
        registry.record_event("default", "user1", "Test prompt for cost", "gpt-4o-mini", compressed=True, savings_percent=30)
        summary = registry.get_cost_summary("default")
        self.assertIn("total_cost_usd", summary)
        roi = ROIEngine().calculate("default")
        self.assertIn("net_roi_usd", roi)

    def test_budget_engine(self):
        from backend.finops.budget_engine import BudgetEngine
        engine = BudgetEngine()
        engine.set_budget("default", "tenant", "default", 1000.0)
        check = engine.check_budget("default", "tenant", "default", 50)
        self.assertTrue(check["allowed"])

    def test_forecast(self):
        from backend.finops.forecast_engine import ForecastEngine
        result = ForecastEngine().forecast("default", "monthly")
        self.assertIn("projected_usd", result)

    def test_anomaly_detection(self):
        from backend.finops.anomaly_detection import AnomalyDetector
        result = AnomalyDetector().scan("default")
        self.assertIn("status", result)


class TestGovernance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.core.database_v2 import init_v2_db
        init_v2_db()

    def test_rule_engine(self):
        from backend.governance.rule_engine import RuleEngine
        engine = RuleEngine()
        engine.create_policy("default", "No GPT-5 RH", "deny_model", {"models": ["gpt-5"]})
        result = engine.evaluate("default", "gpt-5", "openai")
        self.assertFalse(result["allowed"])
        result_ok = engine.evaluate("default", "gpt-4o", "openai")
        self.assertTrue(result_ok["allowed"])

    def test_compliance(self):
        from backend.governance.compliance import ComplianceManager
        mgr = ComplianceManager()
        result = mgr.check_compliance({"compliance_tags": ["RGPD"], "data_residency": "EU", "audit_trail": True})
        self.assertIn("overall_compliant", result)


class TestPrompts(unittest.TestCase):
    def test_prompt_diff(self):
        from backend.prompts.prompt_diff import PromptDiffExplorer
        diff = PromptDiffExplorer().compare("Hello world test", "Hello test")
        self.assertLess(diff["tokens_b"], diff["tokens_a"])

    def test_explainability(self):
        from backend.prompts.prompt_explainability import PromptExplainability
        exp = PromptExplainability().explain_optimization(100, 60, "balanced")
        self.assertEqual(exp["gain"]["savings_percent"], 40.0)

    def test_similarity(self):
        from backend.prompts.prompt_similarity import PromptSimilarityEngine
        engine = PromptSimilarityEngine()
        dups = engine.find_exact_duplicates(["hello", "hello", "world"])
        self.assertEqual(len(dups), 1)


class TestGateway(unittest.TestCase):
    def test_circuit_breaker(self):
        from backend.gateway.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("test", failure_threshold=2)
        self.assertTrue(cb.allow_request())
        cb.record_failure()
        cb.record_failure()
        self.assertFalse(cb.allow_request())

    def test_predictive_router(self):
        from backend.gateway.predictive_router import PredictiveRouter
        router = PredictiveRouter()
        result = router.route("default", "user1", "x" * 300, "gpt-4o")
        self.assertIn(result["action"], ("compress", "cache_hit", "bypass", "deny"))


class TestExperiments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.core.database_v2 import init_v2_db
        init_v2_db()

    def test_experiment_lifecycle(self):
        from backend.experiments.experiment_manager import ExperimentManager
        mgr = ExperimentManager()
        exp = mgr.create("default", "compression-ab", "original", "compressed")
        exps = mgr.list_experiments("default")
        self.assertTrue(len(exps) >= 1)


class TestAPIv2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.core.database_v2 import init_v2_db
        init_v2_db()
        from fastapi.testclient import TestClient
        from backend.app import app
        cls.client = TestClient(app)

    def test_v2_health(self):
        r = self.client.get("/api/v2/health")
        self.assertEqual(r.status_code, 200)
        self.assertIn("2.0.0", r.json()["version"])

    def test_v1_health_regression(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_v2_dashboard(self):
        r = self.client.get("/api/v2/dashboard", headers={"X-Tenant-ID": "default", "X-User-ID": "test"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("finops", r.json())

    def test_v2_memory_profile(self):
        r = self.client.put(
            "/api/v2/memory/user/profile",
            json={"updates": {"language": "fr"}},
            headers={"X-Tenant-ID": "default", "X-User-ID": "api_test"},
        )
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
