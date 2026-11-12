"""
Pruebas Unitarias para la Capa 4: Inferencia Local y Telemetría (NetDiagBench-L7)
"""

from src.core.contracts import RespuestaInferenciaContract
from src.layer4_inference.engine import LocalInferenceEngine


def test_inference_engine_generation_models():
    engine = LocalInferenceEngine(force_simulation=True)
    models = ["qwen3-8b", "glm-4-9b-chat", "phi-4-mini-instruct"]

    for m in models:
        resp = engine.generate(
            model_id=m,
            prompt="Analizar fallo en servicio DNS NXDOMAIN",
            seed=42
        )
        assert isinstance(resp, RespuestaInferenciaContract)
        assert resp.model_id == m
        assert len(resp.raw_response_text) > 0
        assert resp.telemetry.time_to_first_token_ms > 0
        assert resp.telemetry.decode_tokens_per_second > 0
        assert resp.telemetry.completion_tokens > 0


def test_inference_engine_hardware_profiles():
    engine = LocalInferenceEngine(force_simulation=True)
    resp_phi = engine.generate("phi-4-mini-instruct", "test prompt", seed=42)
    resp_glm = engine.generate("glm-4-9b-chat", "test prompt", seed=42)

    # Phi-4-mini debe tener menor VRAM y menor TTFT que GLM-4-9B
    if resp_phi.telemetry.vram_peak_gb is not None and resp_glm.telemetry.vram_peak_gb is not None:
        assert resp_phi.telemetry.vram_peak_gb < resp_glm.telemetry.vram_peak_gb
    assert resp_phi.telemetry.time_to_first_token_ms < resp_glm.telemetry.time_to_first_token_ms


def test_inference_engine_check_health():
    engine = LocalInferenceEngine(force_simulation=True)
    health = engine.check_health()
    assert isinstance(health, dict)
    assert "ollama_online" in health
    assert "simulator_ready" in health
    assert health["simulator_ready"] is True
    assert health["mode"] == "deterministic_simulator"
    assert "configured_models" in health
    assert len(health["configured_models"]) >= 3


def test_inference_engine_unknown_model_raises_error():
    import pytest
    engine = LocalInferenceEngine(force_simulation=True)
    with pytest.raises(ValueError, match="no reconocido"):
        engine.generate(model_id="non-existent-model-123b", prompt="test")


def test_inference_engine_seed_determinism():
    engine = LocalInferenceEngine(force_simulation=True)
    resp1 = engine.generate("phi-4-mini-instruct", "Diagnóstico DNS", seed=42)
    resp2 = engine.generate("phi-4-mini-instruct", "Diagnóstico DNS", seed=42)

    assert resp1.raw_response_text == resp2.raw_response_text
    assert resp1.telemetry.completion_tokens == resp2.telemetry.completion_tokens
    assert resp1.telemetry.time_to_first_token_ms == resp2.telemetry.time_to_first_token_ms


def test_inference_engine_qwen_thought_generation():
    engine = LocalInferenceEngine(force_simulation=True)
    resp = engine.generate("qwen3-8b", "Escenario DNS-NXD-01 fallo en resolución", seed=42)
    assert resp.model_id == "qwen3-8b"
    assert len(resp.raw_response_text) > 100
    assert "root_cause" in resp.raw_response_text.lower() or "thought" in resp.raw_response_text.lower()


