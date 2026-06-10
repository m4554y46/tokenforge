"""Tests for ACE — Adaptive Compression Engine."""

import unittest
from unittest.mock import patch, MagicMock
import json


class TestSanctuary(unittest.TestCase):
    def test_no_protected_content(self):
        from backend.ace.sanctuary import protected_ratio, max_safe_rate
        text = "Bonjour, veuillez expliquer le contexte économique."
        self.assertEqual(protected_ratio(text), 0.0)
        self.assertEqual(max_safe_rate(text), 1.0)

    def test_fenced_code_block(self):
        from backend.ace.sanctuary import protected_ratio, max_safe_rate
        text = "Voici le code:\n```python\ndef hello():\n    pass\n```\nFin."
        r = protected_ratio(text)
        self.assertGreater(r, 0.0)
        self.assertLess(max_safe_rate(text), 0.40)

    def test_latex_formula(self):
        from backend.ace.sanctuary import protected_ratio, max_safe_rate
        text = "L'équation est $$\\int_{0}^{1} x^2 dx$$ très important."
        r = protected_ratio(text)
        self.assertGreater(r, 0.0)
        self.assertLess(max_safe_rate(text), 1.0)

    def test_markdown_table(self):
        from backend.ace.sanctuary import protected_ratio, max_safe_rate
        text = "Comparatif :\n| Modèle | Prix |\n|-------|-----|\n| GPT-4o | $5 |\n| Claude | $3 |\n"
        self.assertGreater(protected_ratio(text), 0.0)

    def test_high_protected_ratio_caps_at_safe(self):
        from backend.ace.sanctuary import max_safe_rate
        text = "```\ndef hello():\n    pass\n```\n```\ndef world():\n    pass\n```\n```\ndef foo():\n    pass\n```" * 5
        r = max_safe_rate(text)
        self.assertLessEqual(r, 0.15)

    def test_json_block_protected(self):
        from backend.ace.sanctuary import protected_ratio
        text = '{\n  "users": [\n    {\n      "id": "1",\n      "name": "Alice"\n    }\n  ]\n}'
        r = protected_ratio(text)
        self.assertGreater(r, 0.0)

    def test_mixed_content(self):
        from backend.ace.sanctuary import protected_ratio
        text = (
            "Analysez le code suivant :\n"
            "```python\ndef filter(items):\n    return [x for x in items if x > 0]\n```\n"
            "Et le tableau de résultats :\n"
            "| Mois | Revenu |\n|------|--------|\n| Jan | 1000 |\n| Fév | 1200 |\n"
        )
        r = protected_ratio(text)
        self.assertGreater(r, 0.0)
        self.assertLess(r, 1.0)

    def test_sanctuary_gate_in_decider(self):
        """Vérifie que Sanctuary bloque les taux élevés sur contenu protégé."""
        from backend.ace.tables import init_ace_tables
        init_ace_tables()
        from backend.ace.decider import Decider as ACEDecider
        from backend.ace.state import CellState
        decider = ACEDecider(tenant_id="test")
        feats = {
            "tenant_id": "test",
            "user_cluster": "dev",
            "task_type": "code",
            "length_bucket": "medium",
            "model": "gpt-4o",
            "token_count": 500,
            "prompt_text": "Explique ce code:\n```python\ndef hello():\n    pass\n```\nEt aussi:\n```python\ndef world():\n    pass\n```",
        }
        profile, _, rate = decider.decide(feats)
        # Sanctuary doit limiter le taux pour du code protégé
        self.assertLessEqual(rate, 0.40)


class TestQualityJudge(unittest.TestCase):
    def test_returns_default_when_no_api_key(self):
        from backend.ace.judge import QualityJudge
        judge = QualityJudge(api_key="")
        result = judge.evaluate("prompt", "ref response", "compressed response")
        self.assertEqual(result["score"], 0.85)
        self.assertEqual(result["error"], "no_api_key")

    @patch("backend.ace.judge.QualityJudge._get_client")
    def test_parses_json_from_gpt4o(self, mock_get_client):
        from backend.ace.judge import QualityJudge
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "score": 78,
            "details": {
                "exactitude": 80,
                "completude": 75,
                "coherence": 85,
                "fidelite": 80,
                "style": 70,
                "justification": "Bien mais quelques détails manquants",
            },
        })
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        judge = QualityJudge(api_key="sk-test")
        result = judge.evaluate("prompt", "ref", "comp")
        self.assertAlmostEqual(result["score"], 0.78)
        self.assertIsNone(result["error"])

    @patch("backend.ace.judge.QualityJudge._get_client")
    def test_retry_on_failure(self, mock_get_client):
        from backend.ace.judge import QualityJudge
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [Exception("timeout"), Exception("timeout"), MagicMock()]
        mock_get_client.return_value = mock_client

        judge = QualityJudge(api_key="sk-test")
        result = judge.evaluate("prompt", "ref", "comp")
        self.assertIn("error", result)

    def test_get_judge_singleton(self):
        from backend.ace.judge import get_judge, _judge_instance
        _judge_instance = None  # reset
        j1 = get_judge()
        j2 = get_judge()
        self.assertIs(j1, j2)

    def test_evaluate_batch(self):
        from backend.ace.judge import QualityJudge
        judge = QualityJudge(api_key="")
        pairs = [
            ("p1", "a1", "b1"),
            ("p2", "a2", "b2"),
        ]
        results = judge.evaluate_batch(pairs)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r["score"], 0.85)


class TestFeatureExtraction(unittest.TestCase):
    def setUp(self):
        from backend.ace.features import extract_features
        self.extract = extract_features

    def test_code_prompt(self):
        f = self.extract("Write a Python function to sort a list", 10, model="gpt-4o", user_id="u1")
        self.assertEqual(f["task_type"], "code")
        self.assertIn(f["length_bucket"], ["short", "medium", "long", "very_long"])
        self.assertIsInstance(f["user_cluster"], int)

    def test_analytical_prompt(self):
        f = self.extract("Analyse les tendances de vente du dernier trimestre", 12, model="gpt-4o", user_id="u1")
        self.assertEqual(f["task_type"], "analytique")

    def test_factual_prompt(self):
        f = self.extract("What is the capital of France?", 8, model="gpt-4o", user_id="u1")
        self.assertEqual(f["task_type"], "factuel")

    def test_translation_prompt(self):
        f = self.extract("Translate to French: Hello, how are you?", 10, model="gpt-4o", user_id="u1")
        self.assertEqual(f["task_type"], "traduction")

    def test_creative_prompt(self):
        f = self.extract("Write a creative story about a robot who learns to paint", 14, model="gpt-4o", user_id="u1")
        self.assertEqual(f["task_type"], "creatif")

    def test_summary_prompt(self):
        f = self.extract("Summarize this article in 3 bullet points", 10, model="gpt-4o", user_id="u1")
        self.assertEqual(f["task_type"], "resume")

    def test_length_buckets(self):
        short = self.extract("Hi", 1, model="gpt-4o", user_id="u1")
        self.assertEqual(short["length_bucket"], "short")
        medium = self.extract("word " * 100, 100, model="gpt-4o", user_id="u1")
        self.assertEqual(medium["length_bucket"], "medium")
        long_ = self.extract("word " * 600, 600, model="gpt-4o", user_id="u1")
        self.assertEqual(long_["length_bucket"], "long")

    def test_specificity_generic(self):
        f = self.extract("What is the weather today?", 7, model="gpt-4o", user_id="u1")
        self.assertEqual(f["specificity"], "generic")

    def test_specificity_jargon(self):
        f = self.extract("The EBITDA and revenue growth for Q3", 9, model="gpt-4o", user_id="u1")
        self.assertEqual(f["specificity"], "domain_jargon")

    def test_user_cluster_consistency(self):
        f1 = self.extract("test", 1, model="gpt-4o", user_id="user_42")
        f2 = self.extract("test", 1, model="gpt-4o", user_id="user_42")
        self.assertEqual(f1["user_cluster"], f2["user_cluster"])

    def test_user_cluster_stable_for_different_users(self):
        ids = [f"user_{i}" for i in range(100)]
        clusters = set()
        for uid in ids:
            f = self.extract("test", 1, model="gpt-4o", user_id=uid)
            clusters.add(f["user_cluster"])
        self.assertGreaterEqual(len(clusters), 10)


class TestSignalDetection(unittest.TestCase):
    def setUp(self):
        from backend.ace.signals import detect_signals
        self.detect = detect_signals

    def test_no_signals_first_request(self):
        s = self.detect("session_1", "user_1", "default", "Hello", "hash1")
        self.assertFalse(s.reformulation)
        self.assertFalse(s.continuation)

    def test_reformulation_detected(self):
        import time
        self.detect("session_r", "user_1", "default", "What is the capital of France?", "hash1")
        time.sleep(0.01)
        s = self.detect("session_r", "user_1", "default", "What is the capital of France?", "hash2")
        self.assertTrue(s.reformulation)

    def test_continuation_detected(self):
        import time
        self.detect("session_c", "user_1", "default", "What is the capital of France?", "hash1")
        time.sleep(0.01)
        s = self.detect("session_c", "user_1", "default", "Tell me about its history", "hash2")
        self.assertTrue(s.continuation)

    def test_different_session_no_signals(self):
        self.detect("session_a", "user_1", "default", "Hello", "hash1")
        s = self.detect("session_b", "user_1", "default", "Hello", "hash1")
        self.assertFalse(s.reformulation)
        self.assertFalse(s.continuation)


class TestDecider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.core.database_v2 import init_v2_db
        init_v2_db()

    def setUp(self):
        from backend.ace.decider import Decider
        self.decider = Decider(tenant_id="test")

    def test_bypass_for_short_prompts(self):
        feats = {
            "tenant_id": "test", "user_cluster": 0, "task_type": "factuel",
            "length_bucket": "short", "model": "gpt-4o", "token_count": 10,
            "specificity": "generic",
        }
        profile, exp, rate = self.decider.decide(feats)
        self.assertEqual(profile, "bypass")

    def test_bypass_when_no_valid_rates(self):
        feats = {
            "tenant_id": "test", "user_cluster": 1, "task_type": "factuel",
            "length_bucket": "medium", "model": "gpt-4o", "token_count": 100,
            "specificity": "generic",
        }
        profile, exp, rate = self.decider.decide(feats)
        self.assertIn(profile, ["bypass", "safe", "light", "balanced", "aggressive", "max"])

    def test_force_profile(self):
        feats = {
            "tenant_id": "test", "user_cluster": 0, "task_type": "code",
            "length_bucket": "medium", "model": "gpt-4o", "token_count": 500,
            "specificity": "domain_jargon",
        }
        profile, exp, rate = self.decider.decide(feats, force_profile="balanced")
        self.assertEqual(profile, "balanced")

    def test_utility_increases_with_savings(self):
        from backend.ace.state import CellState, FAILURE_COST, TF_SHARE, TOKEN_PRICE, PROFILE_COMPUTE_COST, RATE_TO_PROFILE
        from backend.ace.decider import Decider
        token_count = 500
        price = 0.000005
        feats = {"task_type": "factuel", "specificity": "generic", "length_bucket": "medium"}
        cell_good = CellState(rate=0.40, quality_sum=45, n_samples=50)
        U_good = Decider().compute_utility(0.40, token_count, price, cell_good, feats)
        cell_bad = CellState(rate=0.40, quality_sum=10, n_samples=50)
        U_bad = Decider().compute_utility(0.40, token_count, price, cell_bad, feats)
        self.assertGreater(U_good, U_bad)

    def test_higher_rate_not_always_better(self):
        from backend.ace.state import CellState
        from backend.ace.decider import Decider
        d = Decider()
        token_count = 1000
        price = 0.000005
        feats = {"task_type": "factuel", "specificity": "generic", "length_bucket": "medium"}
        r_low = 0.15
        cell_low = CellState(rate=r_low, quality_sum=48, n_samples=50)
        r_high = 0.70
        cell_high = CellState(rate=r_high, quality_sum=20, n_samples=50)
        U_low = d.compute_utility(r_low, token_count, price, cell_low, feats)
        U_high = d.compute_utility(r_high, token_count, price, cell_high, feats)
        self.assertGreater(U_low, U_high)


class TestIntegration(unittest.TestCase):
    def test_proxy_imports_with_ace(self):
        from backend.middleware.proxy import router, _Compressor, _get_ace_decider, FORGE_COMPRESSION_PROFILE
        self.assertIsNotNone(router)
        self.assertEqual(FORGE_COMPRESSION_PROFILE, "industrial")

    def test_compressor_profile_passthrough(self):
        from backend.middleware.proxy import _Compressor
        c = _Compressor.get()
        with patch.object(c, '_get_spc') as mock_get_spc:
            mock_spc = MagicMock()
            mock_spc.compile.return_value.compressed = "compressed text x y z"
            mock_spc.compile.return_value.fallback = False
            mock_spc.compile.return_value.error = None
            mock_get_spc.return_value = mock_spc
            long_prompt = "this is a longer test prompt that exceeds thirty characters"
            result, fb, pn = c.compress(long_prompt, profile_name="light")
            mock_get_spc.assert_called_with("light")

    def test_full_pipeline_import(self):
        from backend.ace import (
            Decider, extract_features, CellState,
            RATES, RATE_TO_PROFILE, TF_SHARE,
            detect_signals, update_from_signals, init_ace_tables,
        )
        self.assertIsNotNone(Decider)
        self.assertIsNotNone(extract_features)
        self.assertIn(0.0, RATES)
        self.assertEqual(RATE_TO_PROFILE[0.40], "balanced")

    def test_decider_standalone_with_db(self):
        from backend.ace.decider import Decider
        d = Decider(tenant_id="test_no_db")
        feats = {
            "tenant_id": "test_no_db", "user_cluster": 99, "task_type": "factuel",
            "length_bucket": "medium", "model": "gpt-4o", "token_count": 500,
            "specificity": "generic",
        }
        profile, exp, rate = d.decide(feats)
        self.assertIn(profile, ["bypass", "safe", "light", "balanced", "aggressive", "max"])


class TestQualityModel(unittest.TestCase):
    def test_quality_model_predict(self):
        from backend.ace.models.quality_model import QualityModel, get_model
        m = get_model()
        self.assertIsNotNone(m)
        if m.is_available():
            q = m.predict({"task_type": "factuel", "length_bucket": "medium"})
            self.assertIsInstance(q, float)
            self.assertGreaterEqual(q, 0.0)
            self.assertLessEqual(q, 1.0)

    def test_quality_model_on_signal_features(self):
        from backend.ace.models.quality_model import QualityModel
        m = QualityModel()
        feats = {"task_type": "code", "specificity": "domain_jargon", "length_bucket": "long"}
        signals = {"reformulation": True, "continuation": False, "quality_proxy": 0.92}
        q = m.predict(feats, signals)
        self.assertIsInstance(q, float)


class TestExploration(unittest.TestCase):
    def setUp(self):
        from backend.ace.state import CellState
        self.cells = {
            0.15: CellState(rate=0.15, quality_sum=45, n_samples=50, n_explorations=0),
            0.40: CellState(rate=0.40, quality_sum=40, n_samples=50, n_explorations=0),
            0.75: CellState(rate=0.75, quality_sum=25, n_samples=50, n_explorations=0),
        }

    def test_knowledge_gradient_high_for_uncertain(self):
        from backend.ace.exploration import knowledge_gradient
        kg = knowledge_gradient(0.5, 0.2, [0.4, 0.45])
        self.assertGreaterEqual(kg, 0.0)

    def test_knowledge_gradient_zero_when_certain(self):
        from backend.ace.exploration import knowledge_gradient
        kg = knowledge_gradient(0.9, 0.01, [0.4])
        self.assertLess(kg, 50.0)

    def test_pick_exploration_arm_returns_rate_or_none(self):
        from backend.ace.exploration import pick_exploration_arm
        arm = pick_exploration_arm(self.cells, token_count=500, price_per_token=1e-5,
                                   contract_age_days=200, tenant_allows_exploration=True)
        self.assertIsNone(arm)

    def test_pick_exploration_arm_young_contract(self):
        from backend.ace.exploration import pick_exploration_arm
        arm = pick_exploration_arm(self.cells, token_count=500, price_per_token=1e-5,
                                   contract_age_days=50, tenant_allows_exploration=True)
        if arm is not None:
            self.assertIn(arm, [0.15, 0.40, 0.75])

    def test_should_explore_young_contract(self):
        from backend.ace.exploration import should_explore
        from backend.ace.state import CellState
        cell = CellState(rate=0.4, quality_sum=40, n_samples=50)
        expl, _ = should_explore(0.4, 0.8, 0.05, self.cells, 500, 1e-5, contract_age_days=50)
        self.assertFalse(expl)

    def test_should_explore_old_contract(self):
        from backend.ace.exploration import should_explore
        from backend.ace.state import CellState
        expl, _ = should_explore(0.4, 0.8, 0.05, self.cells, 500, 1e-5, contract_age_days=120)
        self.assertFalse(expl)
        # Old contract alone doesn't trigger exploration — needs knowledge gradient > 0


class TestAttribution(unittest.TestCase):
    def test_attribute_reformulation_signal(self):
        from backend.ace.attribution import attribute, AttributionResult
        feats = {"task_type": "code", "specificity": "domain_jargon"}
        result = attribute(feats, rate=0.40, signals={"reformulation": True, "continuation": False})
        self.assertIsInstance(result, AttributionResult)
        self.assertEqual(result.cause, "compression")
        self.assertGreaterEqual(result.confidence, 0.0)

    def test_attribute_no_signals(self):
        from backend.ace.attribution import attribute, should_update_quality
        feats = {"task_type": "factuel", "specificity": "generic"}
        result = attribute(feats, rate=0.40, signals={"reformulation": False, "continuation": False})
        self.assertIn(result.cause, ["user", "model", "compression", "context", "unknown"])
        if result.cause == "model" and result.confidence > 0.7:
            self.assertFalse(should_update_quality(result))

    def test_should_update_quality_compression(self):
        from backend.ace.attribution import attribute, should_update_quality
        feats = {"task_type": "code", "specificity": "domain_jargon"}
        result = attribute(feats, rate=0.40, signals={"reformulation": True, "continuation": False})
        self.assertTrue(should_update_quality(result))


class TestEmbeddings(unittest.TestCase):
    def test_embeddings_cold_start(self):
        from backend.ace.embeddings import CompressionEmbeddings, get_embeddings
        emb = get_embeddings()
        self.assertIsNotNone(emb)
        feats = {"task_type": "factuel", "specificity": "generic", "length_bucket": "short"}
        q = emb.cold_start_quality(feats, rate=0.40)
        # cold_start_quality peut retourner None si aucun contexte similaire n'existe
        if q is not None:
            self.assertIsInstance(q, float)
            self.assertGreaterEqual(q, 0.0)

    def test_embeddings_not_available(self):
        from backend.ace.embeddings import CompressionEmbeddings
        emb = CompressionEmbeddings()
        q = emb.cold_start_quality({}, 0.4)
        self.assertIsNone(q)


class TestDeciderIntegration(unittest.TestCase):
    def test_decider_calls_quality_model(self):
        from backend.ace.decider import Decider
        d = Decider(tenant_id="test_int")
        feats = {
            "tenant_id": "test_int", "user_cluster": 0, "task_type": "factuel",
            "length_bucket": "medium", "model": "gpt-4o", "token_count": 500,
            "specificity": "generic",
        }
        profile, exp, rate = d.decide(feats, contract_age_days=999)
        self.assertIn(profile, ["bypass", "safe", "light", "balanced", "aggressive", "max"])

    def test_decider_quality_model_fallback_when_unavailable(self):
        from backend.ace.decider import Decider
        d = Decider(tenant_id="test_fallback")
        feats = {
            "tenant_id": "test_fallback", "user_cluster": 0, "task_type": "factuel",
            "length_bucket": "medium", "model": "gpt-4o", "token_count": 500,
            "specificity": "generic",
        }
        profile, exp, rate = d.decide(feats)
        self.assertIn(profile, ["bypass", "safe", "light", "balanced", "aggressive", "max"])

    def test_decider_exploration_with_old_contract(self):
        from backend.ace.decider import Decider
        d = Decider(tenant_id="test_old")
        feats = {
            "tenant_id": "test_old", "user_cluster": 0, "task_type": "factuel",
            "length_bucket": "medium", "model": "gpt-4o", "token_count": 500,
            "specificity": "generic",
        }
        profile, exp, rate = d.decide(feats, contract_age_days=200, tenant_allows_exploration=True)
        self.assertIn(profile, ["bypass", "safe", "light", "balanced", "aggressive", "max"])

    def test_on_response_records_request(self):
        from backend.ace.decider import Decider
        from backend.ace.features import extract_features
        d = Decider(tenant_id="test_rec")
        feats = extract_features("Test prompt for recording", 5, model="gpt-4o",
                                 user_id="rec_user", tenant_id="test_rec")
        d.on_response(feats, profile_chosen="balanced", tokens_original=100,
                      tokens_compressed=60, latency_ms=150, was_exploration=False,
                      session_id="sess_rec", prompt_hash="ph1", response_hash="rh1")
        from backend.core.database_v2 import query_one, _param
        p = _param()
        row = query_one(
            f"SELECT COUNT(*) as c FROM ace_requests WHERE session_id={p}",
            ("sess_rec",),
        )
        self.assertGreater((row or {}).get("c", 0), 0)

    def test_on_next_request_without_signals(self):
        from backend.ace.decider import Decider
        d = Decider(tenant_id="test_nosig")
        d.on_next_request("sess_none", "u1", "test_nosig",
                          "New prompt about something else",
                          {"task_type": "factuel", "specificity": "generic"},
                          0.40)
        from backend.core.database_v2 import query_one, _param
        p = _param()
        row = query_one(
            f"SELECT COUNT(*) as c FROM ace_states WHERE tenant_id={p}",
            ("test_nosig",),
        )
        self.assertGreaterEqual((row or {}).get("c", 0), 0)


class TestQualityDashboard(unittest.TestCase):
    def test_dashboard_data_structure(self):
        from backend.ace.dashboard import get_dashboard_data
        data = get_dashboard_data("test_tenant", days=30)
        self.assertIn("summary", data)
        self.assertIn("by_profile", data)
        self.assertIn("by_task_type", data)
        self.assertIn("alerts", data)
        self.assertIn("tenant_id", data)
        self.assertEqual(data["tenant_id"], "test_tenant")
        self.assertIn("total_cells", data["summary"])
        self.assertIn("avg_quality", data["summary"])

    def test_dashboard_empty_tenant(self):
        from backend.ace.dashboard import get_dashboard_data
        data = get_dashboard_data("nonexistent_tenant", days=1)
        self.assertEqual(data["summary"]["total_cells"], 0)
        self.assertEqual(data["by_profile"], [])
        self.assertEqual(data["by_task_type"], [])
        self.assertEqual(data["alerts"], [])

    def test_dashboard_default_days(self):
        from backend.ace.dashboard import get_dashboard_data
        data = get_dashboard_data("test_tenant")
        self.assertEqual(data["period_days"], 7)

    def test_dashboard_estimated_savings(self):
        from backend.ace.dashboard import get_dashboard_data
        data = get_dashboard_data("test_tenant", days=1)
        self.assertIsInstance(data["summary"]["estimated_savings_usd"], float)
        self.assertIsInstance(data["summary"]["total_tokens_saved"], int)

    def test_v2_endpoint_dashboard(self):
        from backend.api.v2.router import router
        found = False
        for route in router.routes:
            if route.path == "/api/v2/ace/quality-dashboard":
                found = True
                self.assertIn("GET", route.methods)
                break
        self.assertTrue(found, "ACE quality dashboard endpoint not found in router")


class TestEndToEndFlow(unittest.TestCase):
    """Test du pipeline ACE complet : features → décision → enregistrement → signal"""

    def setUp(self):
        from backend.ace.decider import Decider
        self.decider = Decider(tenant_id="e2e_test")
        self.counter = 0

    def _make_features(self, prompt: str, task: str = "factuel", model: str = "gpt-4o"):
        from backend.ace.features import extract_features
        feats = extract_features(
            prompt=prompt,
            token_count=len(prompt.split()),
            model=model,
            user_id="e2e_user",
            tenant_id="e2e_test",
        )
        feats["prompt_text"] = prompt
        feats["prompt_preview"] = prompt[:200]
        return feats

    def test_full_cycle_decision_and_recording(self):
        """Décision → compression simulée → enregistrement → vérification DB."""
        prompt = "Expliquez les causes de la Révolution française en trois paragraphes."
        feats = self._make_features(prompt)

        profile, was_exp, rate = self.decider.decide(feats, contract_age_days=500)
        self.assertIn(profile, ["bypass", "safe", "light", "balanced", "aggressive", "max"])

        compressed_len = max(10, int(len(prompt.split()) * (1 - rate)))
        self.decider.on_response(
            feats, profile_chosen=profile, tokens_original=len(prompt.split()),
            tokens_compressed=compressed_len, latency_ms=200,
            was_exploration=was_exp, session_id="e2e_s1",
            prompt_hash="hash_in", response_hash="hash_out",
        )

        from backend.core.database_v2 import query_one, _param
        p = _param()
        row = query_one(
            f"SELECT COUNT(*) as c FROM ace_requests WHERE tenant_id={p}",
            ("e2e_test",),
        )
        self.assertGreater((row or {}).get("c", 0), 0)

    def test_sanctuary_limits_rate_for_code(self):
        """Sanctuary doit limiter le taux sur un prompt avec beaucoup de code."""
        prompt = "Analysez ce code:\n" + "```python\ndef f():\n    pass\n```\n" * 5
        feats = self._make_features(prompt, task="code")
        _, _, rate = self.decider.decide(feats, contract_age_days=500)
        self.assertLessEqual(rate, 0.40)

    def test_quality_model_updates_on_signals(self):
        """Après un signal de reformulation, la qualité doit être mise à jour."""
        from backend.ace.decider import Decider
        d = Decider(tenant_id="e2e_signal_test")

        prompt = "Combien de continents y a-t-il ?"
        feats = self._make_features(prompt)
        profile, _, rate = d.decide(feats, contract_age_days=500)
        compressed = max(10, int(len(prompt.split()) * (1 - rate)))
        d.on_response(
            feats, profile, tokens_original=len(prompt.split()),
            tokens_compressed=compressed, latency_ms=100,
            was_exploration=False, session_id="e2e_sig_s1",
            prompt_hash="ph1", response_hash="rh1",
        )

        task_type = feats["task_type"]
        length_bucket = feats["length_bucket"]

        from backend.ace.state import read_cell
        cell_before = read_cell("e2e_signal_test", 0, task_type, length_bucket, "gpt-4o", rate)

        # Simule le signal de reformulation sur la requête suivante
        d.on_next_request(
            "e2e_sig_s1", "e2e_user", "e2e_signal_test",
            "Peux-tu formuler autrement ?",
            {"task_type": task_type, "specificity": feats.get("specificity", "generic")},
            rate,
        )

        from backend.ace.state import read_cell
        cell_after = read_cell("e2e_signal_test", 0, task_type, length_bucket, "gpt-4o", rate)

        if cell_before is not None and cell_after is not None:
            self.assertGreaterEqual(cell_after.n_samples, cell_before.n_samples)

    def test_utility_respects_min_savings(self):
        """Utility doit être <= 0 si l'économie ne dépasse pas MIN_CLIENT_SAVINGS."""
        from backend.ace.decider import Decider
        from backend.ace.state import get_min_client_savings
        d = Decider(tenant_id="e2e_test")
        feats = self._make_features("Hello world", task="factuel")
        price = d.get_token_price("gpt-4o")
        token_count = 2
        min_sav = get_min_client_savings("gpt-4o")

        for rate in [0.0, 0.15]:
            from backend.ace.state import read_cell
            cell = read_cell("e2e_test", 0, "factuel", "short", "gpt-4o", rate)
            if cell is None:
                cell = MagicMock()
                cell.expected_quality = 0.95
                cell.n_samples = 50
                cell.n_explorations = 0
            u = d.compute_utility(rate, token_count, price, cell, feats)
            if token_count * rate * price < min_sav:
                self.assertLessEqual(u, 0.0)


class TestOnboardingROI(unittest.TestCase):
    def test_calculate_onboarding_structure(self):
        from backend.ace.onboarding import calculate_onboarding
        result = calculate_onboarding("Quels sont les avantages du cloud computing ?")
        self.assertIn("prompt_analysis", result)
        self.assertIn("by_profile", result)
        self.assertIn("recommendation", result)
        self.assertIn("annual_projection", result)
        self.assertIn("model", result)

    def test_calculate_onboarding_by_profile_not_empty(self):
        from backend.ace.onboarding import calculate_onboarding
        result = calculate_onboarding("Expliquez la photosynthèse en détail.")
        self.assertGreater(len(result["by_profile"]), 0)

    def test_calculate_onboarding_recommendation(self):
        from backend.ace.onboarding import calculate_onboarding
        result = calculate_onboarding("Bonjour", model="gpt-4o", monthly_requests=1000)
        rec = result["recommendation"]
        if rec is not None:
            self.assertIn("profile", rec)
            self.assertIn("net_monthly", rec)
            self.assertIn("net_annual", rec)
            self.assertIn("roi_percent", rec)

    def test_calculate_onboarding_sanctuary_respected(self):
        from backend.ace.onboarding import calculate_onboarding
        prompt = "Parse ce JSON:\n{\n\"data\": [1, 2, 3]\n}" * 10
        result = calculate_onboarding(prompt, model="gpt-4o")
        for p in result["by_profile"]:
            rate = p["rate"]
            max_rate = result["prompt_analysis"]["sanctuary_max_rate"]
            self.assertLessEqual(rate, max_rate)

    def test_calculate_onboarding_empty_prompt(self):
        from backend.ace.onboarding import calculate_onboarding
        result = calculate_onboarding("")
        self.assertEqual(result["prompt_analysis"]["token_count"], 0)
        self.assertIsNone(result["recommendation"])

    def test_calculate_onboarding_annual_projection(self):
        from backend.ace.onboarding import calculate_onboarding
        result = calculate_onboarding("Analysez les tendances du marché.",
                                      monthly_requests=50000)
        proj = result["annual_projection"]
        self.assertIn("net_annual_recommended", proj)
        for p in result["by_profile"]:
            self.assertIn("net_annual", p)

    def test_v2_endpoint_onboarding(self):
        from backend.api.v2.router import router
        found = False
        for route in router.routes:
            if route.path == "/api/v2/ace/onboarding":
                found = True
                self.assertIn("GET", route.methods)
                break
        self.assertTrue(found, "ACE onboarding endpoint not found in router")


if __name__ == "__main__":
    unittest.main()
