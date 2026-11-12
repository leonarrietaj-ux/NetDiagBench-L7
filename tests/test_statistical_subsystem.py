"""
Suite de Pruebas Unitarias del Subsistema Estadístico de NetDiagBench-L7.
Valida:
1. Independencia experimental: unidad de análisis = escenario (18 conglomerados), repeticiones = 3 semillas agregadas.
2. Prueba de Friedman con df = 2 y formateo formal de valores p.
3. Pruebas post-hoc de Wilcoxon pareadas con corrección de Holm-Bonferroni.
4. Prueba de Cochran's Q para consenso binario (df = 2) y post-hoc de McNemar.
5. Bootstrap por conglomerados estratificado (3 emulados + 15 sintéticos, 1000 réplicas, semilla 42, pareado entre modelos).
6. F1 Macro canónico con penalización formal de UNKNOWN y cero fuga de información.
7. Higiene de valores p (nunca 'p = 0.000').
"""

import pytest
import numpy as np
from src.layer7_evaluator.statistical_analysis import (
    compute_paired_friedman_and_wilcoxon,
    compute_model_bootstrap_ci95,
    compute_classification_metrics,
    parse_fault_class_predicted,
    format_p_value,
)


@pytest.fixture
def mock_162_benchmark_rows():
    """Genera 162 corridas sintéticas completas: 18 escenarios x 3 modelos x 3 semillas."""
    emulated_ids = ["TLS-EXP-01", "HTTP-502-01", "DNS-SRV-01"]
    synthetic_ids = [
        "DNS-DEL-01", "DNS-NXD-01", "DNS-REF-01", "DNS-TRUNC-01",
        "HTTP-POOL-01", "HTTP-403-01", "HTTP-429-01", "HTTP-500-01",
        "HTTP-503-01", "HTTP-504-01", "NET-LAT-01", "HTTP-ORIGIN-01",
        "TLS-CHN-01", "TLS-CIPH-01", "TLS-SNI-01"
    ]
    all_scenarios = emulated_ids + synthetic_ids
    assert len(all_scenarios) == 18

    canonical_classes = [
        "TLS_EXPIRED_CERT", "HTTP_502_BAD_GATEWAY", "SERVFAIL",
        "DELEGATION_ERROR", "NXDOMAIN", "DNS_REFUSED", "DNS_TRUNCATED_EDNS",
        "CONNECTION_POOL_EXHAUSTED", "HTTP_403_FORBIDDEN", "HTTP_429_RATE_LIMITED", "HTTP_500_INTERNAL",
        "HTTP_503_SERVICE_UNAVAILABLE", "HTTP_504_GATEWAY_TIMEOUT", "NETWORK_LATENCY_TC", "ORIGIN_DOWN",
        "TLS_CHAIN_INVALID", "TLS_CIPHER_MISMATCH", "TLS_SNI_MISMATCH"
    ]
    sc_to_class = dict(zip(all_scenarios, canonical_classes))

    models = ["glm-4-9b-chat", "qwen3-8b", "phi-4-mini-instruct"]
    seeds = [42, 1337, 2026]

    rows = []
    # Definir capacidades diagnósticas diferenciadas para verificar Friedman y Wilcoxon
    # GLM: 85% acierto, Qwen: 75% acierto, Phi: 50% acierto
    np.random.seed(42)
    for sc in all_scenarios:
        mode = "emulado" if sc in emulated_ids else "sintetico_determinista"
        f_class = sc_to_class[sc]

        for m_idx, m in enumerate(models):
            p_success = 0.85 if m == "glm-4-9b-chat" else (0.75 if m == "qwen3-8b" else 0.50)
            for s in seeds:
                is_correct = bool(np.random.rand() < p_success)
                pred_cls = f_class if is_correct else "UNKNOWN"

                rows.append({
                    "scenario_id": sc,
                    "model_id": m,
                    "seed": s,
                    "execution_mode": mode,
                    "fault_class": f_class,
                    "fault_class_predicted": pred_cls,
                    "is_root_cause_correct": is_correct,
                    "rubric_score": 4.0 if is_correct else 1.5,
                    "tokens_per_sec": 22.0 if m == "phi-4-mini-instruct" else (16.0 if m == "qwen3-8b" else 13.0),
                    "total_time_ms": 2500.0 if m == "phi-4-mini-instruct" else (3500.0 if m == "qwen3-8b" else 4200.0),
                    "model_diagnosis_text": f"Diagnosis text for {f_class}" if is_correct else "Unknown failure",
                })

    assert len(rows) == 162
    return rows


class TestIndependentClusterUnit:
    """Verifica que la unidad de análisis independiente sea el escenario (18 bloques) y no 54."""

    def test_n_blocks_equals_18_not_54(self, mock_162_benchmark_rows):
        res = compute_paired_friedman_and_wilcoxon(mock_162_benchmark_rows, metric="accuracy")
        assert res["n_blocks"] == 18
        assert res["experimental_unit"] == "scenario_id"
        assert res["repetitions_aggregation"] == "mean_across_seeds"

    def test_intra_scenario_repetitions_aggregated(self, mock_162_benchmark_rows):
        # 162 filas = 18 escenarios x 3 modelos x 3 semillas
        res = compute_paired_friedman_and_wilcoxon(mock_162_benchmark_rows, metric="accuracy")
        assert "friedman" in res
        assert res["friedman"]["degrees_of_freedom"] == 2


class TestFriedmanAndWilcoxon:
    """Verifica prueba de Friedman (df=2) y Wilcoxon pareado con Holm-Bonferroni."""

    def test_friedman_degrees_of_freedom_and_formatting(self, mock_162_benchmark_rows):
        res = compute_paired_friedman_and_wilcoxon(mock_162_benchmark_rows, metric="accuracy")
        f = res["friedman"]
        assert f["degrees_of_freedom"] == 2
        assert isinstance(f["statistic_chi2"], float)
        assert isinstance(f["p_value"], float)
        assert f["p_formatted"].startswith("p = ") or f["p_formatted"].startswith("p < ")
        assert "p = 0.000" not in f["p_formatted"]

    def test_post_hoc_wilcoxon_with_holm_bonferroni(self, mock_162_benchmark_rows):
        res = compute_paired_friedman_and_wilcoxon(mock_162_benchmark_rows, metric="accuracy")
        wilc = res["post_hoc_wilcoxon_holm"]
        assert len(wilc) == 3

        # Verificar orden y monotonicidad de p-valores ajustados
        p_raw = [w["p_value_raw"] for w in wilc.values()]
        p_adj = [w["p_value_adjusted"] for w in wilc.values()]
        for r, a in zip(p_raw, p_adj):
            assert a >= r or abs(a - r) < 1e-6
            assert 0.0 <= a <= 1.0


class TestCochranQAndMcNemar:
    """Verifica Cochran's Q para consenso binario y McNemar pareado."""

    def test_cochran_q_consensus(self, mock_162_benchmark_rows):
        res = compute_paired_friedman_and_wilcoxon(mock_162_benchmark_rows, metric="accuracy", consensus_threshold=0.66)
        cq = res["cochran_q_consensus"]
        assert cq["degrees_of_freedom"] == 2
        assert cq["consensus_threshold"] == 0.66
        assert isinstance(cq["statistic_Q"], float)
        assert "p = 0.000" not in cq["p_formatted"]

        mcnemar = cq["post_hoc_mcnemar_holm"]
        assert len(mcnemar) == 3
        for pair_name, m_info in mcnemar.items():
            assert "discordant_b" in m_info
            assert "discordant_c" in m_info
            assert "p_value_adjusted" in m_info
            assert "p = 0.000" not in m_info["p_formatted"]


class TestStratifiedClusterBootstrap:
    """Verifica el remuestreo por conglomerados estratificado (3 emulados + 15 sintéticos)."""

    def test_stratified_cluster_sampling_and_pairing(self, mock_162_benchmark_rows):
        boot_res = compute_model_bootstrap_ci95(mock_162_benchmark_rows, n_bootstrap=100, seed=42)

        for m in ["glm-4-9b-chat", "qwen3-8b", "phi-4-mini-instruct"]:
            assert m in boot_res
            m_info = boot_res[m]
            assert m_info["method"] == "cluster_bootstrap_percentile"
            assert m_info["stratification"] == "emulated_vs_synthetic"
            assert m_info["cluster_unit"] == "scenario_id"
            assert m_info["n_clusters"] == 18
            assert m_info["n_strata_emulated"] == 3
            assert m_info["n_strata_synthetic"] == 15
            assert m_info["n_bootstrap"] == 100
            assert m_info["confidence_level"] == 0.95

            # Validar intervalos de confianza al 95%
            for metric in ["accuracy", "f1_macro", "rubric", "speed_tok_s", "latency_ms"]:
                assert metric in m_info
                lo, hi = m_info[metric]["ci95"]
                assert lo <= hi

        # Validar diferencias pareadas entre modelos
        assert "pairwise_differences" in boot_res
        diffs = boot_res["pairwise_differences"]
        assert len(diffs) == 3
        for pair_key in ["glm-4-9b-chat_vs_phi-4-mini-instruct", "qwen3-8b_vs_phi-4-mini-instruct", "glm-4-9b-chat_vs_qwen3-8b"]:
            assert pair_key in diffs
            p_data = diffs[pair_key]
            assert "delta_accuracy" in p_data
            assert "delta_f1_macro" in p_data
            assert "delta_speed_tok_s" in p_data
            d_lo, d_hi = p_data["delta_accuracy"]["ci95"]
            assert d_lo <= d_hi


class TestF1MacroCanonicalAndUnknownPenalty:
    """Verifica que F1 Macro penalice formalmente a UNKNOWN y use las 18 clases canónicas."""

    def test_unknown_causes_strict_penalty(self):
        # 18 clases canónicas exactas
        from src.layer7_evaluator.metrics import load_evaluator_concepts
        catalog = load_evaluator_concepts().get("classes", {})
        canonical_labels = sorted(list(catalog.keys()))
        assert len(canonical_labels) == 18

        # Caso perfecto: acierta todas las 18 clases
        perfect_rows = [
            {"scenario_id": f"SC-{i}", "fault_class": cls, "fault_class_predicted": cls}
            for i, cls in enumerate(canonical_labels)
        ]
        m_perf = compute_classification_metrics(perfect_rows, n_bootstrap=50, seed=42)
        assert m_perf["f1_macro"] == 1.0

        # Caso degradado: falla la mitad prediciendo UNKNOWN
        degraded_rows = []
        for i, cls in enumerate(canonical_labels):
            pred = cls if i < 9 else "UNKNOWN"
            degraded_rows.append({
                "scenario_id": f"SC-{i}",
                "fault_class": cls,
                "fault_class_predicted": pred,
            })
        m_deg = compute_classification_metrics(degraded_rows, n_bootstrap=50, seed=42)
        # 9 aciertos de 18 => F1 Macro debe ser exactamente 0.50
        assert m_deg["f1_macro"] == 0.50
        assert m_deg["f1_macro_ci95"][0] <= m_deg["f1_macro_ci95"][1]


class TestPValueHygiene:
    """Verifica que ningún valor p imprima '0.000', use 'p = NA' para indeterminados y respete norma APA / IEEE."""

    def test_format_p_value_hygiene(self):
        assert format_p_value(0.000001) == "p < 0.001"
        assert format_p_value(0.0009) == "p < 0.001"
        assert format_p_value(0.001) == "p = 0.001"
        assert format_p_value(0.0498) == "p = 0.050"
        assert format_p_value(0.500) == "p = 0.500"
        assert format_p_value(1.0) == "p = 1.000"
        assert format_p_value(None) == "p = NA"
        assert format_p_value(float("nan")) == "p = NA"

    def test_indeterminate_tests_produce_na_and_record_reason(self, mock_162_benchmark_rows):
        # Crear filas donde todos los modelos tienen rendimiento 100% idéntico (sin varianza)
        identical_rows = []
        for r in mock_162_benchmark_rows:
            r_copy = dict(r)
            r_copy["is_root_cause_correct"] = True
            r_copy["rubric_score"] = 5.0
            identical_rows.append(r_copy)

        res = compute_paired_friedman_and_wilcoxon(identical_rows, metric="accuracy")
        f = res["friedman"]
        assert f["p_value"] is None
        assert f["p_formatted"] == "p = NA"
        assert f["indeterminacy_reason"] is not None
        assert "Sin variabilidad" in f["indeterminacy_reason"] or "Varianza nula" in f["indeterminacy_reason"]

        for pair_k, w_data in res["post_hoc_wilcoxon_holm"].items():
            assert w_data["p_value_adjusted"] is None
            assert w_data["p_formatted"] == "p = NA"
            assert "Todas las diferencias pareadas son cero" in w_data["indeterminacy_reason"]

        cq = res["cochran_q_consensus"]
        assert cq["p_value"] is None
        assert cq["p_formatted"] == "p = NA"
        assert "Sin discordancia" in cq["indeterminacy_reason"]

    def test_diagnostic_confusion_matrix_with_unknown(self):
        # Probar que compute_classification_metrics genere matriz diagnóstica con categoría UNKNOWN
        from src.layer7_evaluator.metrics import load_evaluator_concepts
        catalog = load_evaluator_concepts().get("classes", {})
        canonical_labels = sorted(list(catalog.keys()))

        rows_with_unknown = [
            {"scenario_id": f"SC-{i}", "fault_class": cls, "fault_class_predicted": cls if i % 2 == 0 else "UNKNOWN"}
            for i, cls in enumerate(canonical_labels)
        ]
        res = compute_classification_metrics(rows_with_unknown, n_bootstrap=20, seed=42)
        assert "confusion_matrix_diagnostic" in res
        assert "confusion_matrix_diagnostic_labels" in res
        assert "UNKNOWN" in res["confusion_matrix_diagnostic_labels"]
        assert res["unknown_predictions_count"] == 9
        assert res["error_report"]["unknown_predictions_count"] == 9

    def test_holm_bonferroni_family_preservation_and_indeterminate_handling(self):
        """
        Verifica que la corrección de Holm-Bonferroni:
        1. Mantenga la familia completa de 3 comparaciones (m = 3).
        2. Los contrastes indeterminados conserven p = NA.
        3. NO reduzca el número de comparaciones (el multiplicador debe basarse en m = 3, no en n_valid).
        4. Verifique las semillas autorizadas EXPERIMENT_SEEDS = [42, 1337, 2026].
        """
        from src.core.config import EXPERIMENT_SEEDS
        from src.layer7_evaluator.statistical_analysis import compute_paired_friedman_and_wilcoxon
        assert EXPERIMENT_SEEDS == [42, 1337, 2026]

        # Crear 18 escenarios donde:
        # GLM y Qwen tienen diferencias sistemáticas (W significativo)
        # Phi es idéntico a Qwen en todos los 18 escenarios (diferencias = 0, p = NA)
        rows = []
        for i in range(1, 19):
            sc_id = f"SC-{i:02d}"
            # Para cada semilla de las autorizadas
            for s in EXPERIMENT_SEEDS:
                # GLM obtiene velocidad alta diferenciada
                rows.append({"scenario_id": sc_id, "model_id": "glm-4-9b-chat", "seed": s, "total_time_ms": 100.0 + i, "is_root_cause_correct": True, "rubric_score": 5.0})
                # Qwen obtiene velocidad media
                rows.append({"scenario_id": sc_id, "model_id": "qwen3-8b", "seed": s, "total_time_ms": 300.0 + i * 2, "is_root_cause_correct": False, "rubric_score": 3.0})
                # Phi es IDÉNTICO a Qwen
                rows.append({"scenario_id": sc_id, "model_id": "phi-4-mini-instruct", "seed": s, "total_time_ms": 300.0 + i * 2, "is_root_cause_correct": False, "rubric_score": 3.0})

        res = compute_paired_friedman_and_wilcoxon(rows, metric="latency")
        wilc = res["post_hoc_wilcoxon_holm"]
        assert len(wilc) == 3, "Deben existir exactamente 3 comparaciones en la familia"

        # qwen vs phi debe ser indeterminado (diferencias = 0)
        qwen_phi = wilc["qwen3-8b_vs_phi-4-mini-instruct"]
        assert qwen_phi["p_value_adjusted"] is None
        assert qwen_phi["p_formatted"] == "p = NA"
        assert "Todas las diferencias pareadas son cero" in qwen_phi["indeterminacy_reason"]

        # glm vs qwen y glm vs phi deben ser válidos y tener ajuste con m = 3
        glm_qwen = wilc["glm-4-9b-chat_vs_qwen3-8b"]
        assert glm_qwen["p_value_raw"] is not None
        # Con m = 3, el menor p-value se multiplica por m = 3 (NO por n_valid = 2)
        expected_adj_first = min(glm_qwen["p_value_raw"] * 3, 1.0)
        assert abs(glm_qwen["p_value_adjusted"] - expected_adj_first) < 1e-4
