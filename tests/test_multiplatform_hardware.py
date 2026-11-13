"""
Tests unitarios para la Arquitectura Multiplataforma y Gestión de Hardware (Sección 11):
- Detección NVIDIA.
- Detección AMD.
- GPU integrada.
- CPU-only.
- Memoria compartida.
- VRAM no disponible.
- Errores de instrumentación.
- Ollama no disponible.
- Modelos no instalados.
- Configuraciones incompatibles.

Utiliza mocks exclusivamente para pruebas unitarias de aislamiento.
"""

from unittest.mock import MagicMock, patch
import pytest
import subprocess

from src.core.hardware_detector import (
    HARDWARE_CLASS_CPU_ONLY,
    HARDWARE_CLASS_GPU_DEDICATED,
    HARDWARE_CLASS_GPU_INTEGRATED,
    HARDWARE_CLASS_PARTIAL,
    VRAM_STATUS_MEASURED,
    VRAM_STATUS_NOT_AVAILABLE,
    VRAM_STATUS_SHARED_ONLY,
    BACKEND_CPU,
    BACKEND_GPU,
    HardwareProfile,
    detect_system_hardware,
    detect_ollama_backend_and_vram,
    check_resource_availability,
)
from src.layer4_inference.engine import LocalInferenceEngine
from src.layer7_evaluator.composite_score import (
    calculate_model_composite_scores,
    rank_models_by_composite_score,
)


def test_nvidia_detection():
    """Valida la detección de una GPU dedicada NVIDIA mediante nvidia-smi simulado."""
    mock_smi_out = "NVIDIA GeForce RTX 4090, 24576, 550.54.14\n"
    mock_cuda_out = "NVIDIA-SMI 550.54.14   Driver Version: 550.54.14   CUDA Version: 12.4 |\n"

    def mock_run(cmd, *args, **kwargs):
        res = MagicMock()
        res.returncode = 0
        if "--query-gpu=" in str(cmd):
            res.stdout = mock_smi_out
        else:
            res.stdout = mock_cuda_out
        return res

    with patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
        with patch("subprocess.run", side_effect=mock_run):
            hw = detect_system_hardware(force_refresh=True)
            assert hw.gpu_vendor == "NVIDIA"
            assert "RTX 4090" in hw.gpu_model
            assert hw.hardware_classification == HARDWARE_CLASS_GPU_DEDICATED
            assert hw.vram_total_gb == pytest.approx(24.0, 0.1)
            assert hw.vram_measurement_valid is True
            assert hw.vram_measurement_status == VRAM_STATUS_MEASURED
            assert hw.cuda_version == "12.4"


def test_amd_detection():
    """Valida la detección de una GPU dedicada AMD mediante rocm-smi simulado."""
    with patch("shutil.which", side_effect=lambda x: "/opt/rocm/bin/rocm-smi" if x == "rocm-smi" else None):
        with patch("platform.system", return_value="Linux"):
            def mock_run(cmd, *args, **kwargs):
                res = MagicMock()
                res.returncode = 0
                res.stdout = "AMD Radeon RX 7900 XTX\n"
                return res

            with patch("subprocess.run", side_effect=mock_run):
                hw = detect_system_hardware(force_refresh=True)
                assert hw.gpu_vendor == "AMD"
                assert hw.hardware_classification == HARDWARE_CLASS_GPU_DEDICATED


def test_integrated_gpu_detection():
    """Valida la detección de GPU integrada (ej. AMD Radeon 610M) con memoria compartida y sin sensor VRAM dedicado."""
    with patch("shutil.which", return_value=None):
        with patch("platform.system", return_value="Windows"):
            with patch(
                "src.core.hardware_detector._detect_gpu_windows",
                return_value=(
                    "AMD Radeon(TM) 610M",
                    "AMD",
                    HARDWARE_CLASS_GPU_INTEGRATED,
                    "32.0.21030.13004",
                    2.0,
                    2.0,
                    "winreg_videocontroller",
                    VRAM_STATUS_NOT_AVAILABLE,
                ),
            ):
                hw = detect_system_hardware(force_refresh=True)
                assert hw.hardware_classification == HARDWARE_CLASS_GPU_INTEGRATED
                assert hw.gpu_model == "AMD Radeon(TM) 610M"
                assert hw.vram_shared_gb == 2.0
                assert hw.vram_peak_gb is None
                assert hw.vram_measurement_valid is False
                assert hw.vram_measurement_status == VRAM_STATUS_NOT_AVAILABLE
                assert hw.inference_backend == BACKEND_CPU


def test_cpu_only_detection():
    """Valida el inicio y comportamiento del sistema en equipos sin GPU (CPU-only)."""
    with patch("shutil.which", return_value=None):
        with patch("platform.system", return_value="Linux"):
            with patch(
                "src.core.hardware_detector._detect_gpu_linux",
                return_value=("None", "NONE", HARDWARE_CLASS_CPU_ONLY, "N/A", None, None, "not_available", VRAM_STATUS_NOT_AVAILABLE),
            ):
                hw = detect_system_hardware(force_refresh=True)
                assert hw.hardware_classification == HARDWARE_CLASS_CPU_ONLY
                assert hw.vram_total_gb is None
                assert hw.vram_peak_gb is None
                assert hw.vram_measurement_valid is False
                assert hw.vram_measurement_status == VRAM_STATUS_NOT_AVAILABLE
                assert hw.inference_backend == BACKEND_CPU


def test_shared_memory_differentiation():
    """Verifica que la memoria RAM compartida nunca se confunda con VRAM física dedicada."""
    hw = detect_system_hardware(force_refresh=True)
    assert hw.ram_total_gb > 0.0
    assert hw.ram_available_gb > 0.0
    assert hw.ram_measurement_method == "psutil"
    if hw.hardware_classification == HARDWARE_CLASS_GPU_INTEGRATED:
        # En GPU integrada, vram_shared_gb puede existir, pero el pico dedicado es null
        assert hw.vram_peak_gb is None
        assert hw.vram_measurement_valid is False


def test_vram_unavailable_composite_score():
    """Verifica que la ausencia de VRAM no bloquee el cálculo ni redistribuya el peso del 20%."""
    sample_models = {
        "qwen3-8b": {
            "accuracy_pct": 85.0,
            "rubric": 4.2,
            "tokens_per_sec": 28.0,
            "vram_gb": None,
            "vram_measurement_valid": False,
        },
        "glm-4-9b-chat": {
            "accuracy_pct": 78.0,
            "rubric": 4.0,
            "tokens_per_sec": 22.0,
            "vram_gb": None,
            "vram_measurement_valid": False,
        },
    }

    scored = calculate_model_composite_scores(sample_models, threshold_pct=70.0)
    assert scored["qwen3-8b"]["elegibilidad"] is True
    assert scored["qwen3-8b"]["puntaje_vram"] is None
    assert scored["qwen3-8b"]["puntaje_compuesto"] is None
    assert scored["qwen3-8b"]["estado_mediciones"]["vram"] in ("no_disponible", "declared")

    ranked_eligible, ranked_excluded = rank_models_by_composite_score(scored)
    assert "qwen3-8b" in ranked_eligible
    assert "glm-4-9b-chat" in ranked_eligible
    assert ranked_eligible[0] == "qwen3-8b"


def test_instrumentation_errors_handling():
    """Valida la resiliencia ante errores de ejecución de comandos de instrumentación del SO."""
    with patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=2)):
            with patch("platform.system", return_value="Linux"):
                with patch("src.core.hardware_detector._detect_gpu_linux", side_effect=Exception("Permiso denegado")):
                    hw = detect_system_hardware(force_refresh=True)
                    assert hw.hardware_classification in (HARDWARE_CLASS_CPU_ONLY, HARDWARE_CLASS_PARTIAL)
                    assert hw.vram_measurement_valid is False


def test_ollama_unavailable_handling():
    """Verifica que el motor detecte de forma determinista la ausencia de Ollama."""
    engine = LocalInferenceEngine(ollama_base_url="http://127.0.0.1:9999")
    with patch("httpx.Client.get", side_effect=Exception("Connection refused")):
        health = engine.check_health()
        assert health["ollama_online"] is False
        assert health["installed_models"] == []


def test_model_not_installed_handling():
    """Verifica la detección de modelos requeridos faltantes en el servidor Ollama."""
    engine = LocalInferenceEngine()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [{"name": "qwen3:8b-q4_K_M"}]  # Faltan glm4 y phi4
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        health = engine.check_health()
        assert health["ollama_online"] is True
        assert "qwen3:8b-q4_K_M" in health["installed_models"]
        assert "glm4:9b-chat-q4_K_M" not in health["installed_models"]


def test_incompatible_configurations_handling():
    """Valida la detección de memoria insuficiente antes de ejecutar un modelo de gran escala."""
    # Simular solo 2.0 GB de RAM disponible
    mock_vm = MagicMock()
    mock_vm.available = 2 * (1024**3)
    mock_vm.total = 16 * (1024**3)

    with patch("psutil.virtual_memory", return_value=mock_vm):
        # Qwen3-8B requiere ~5.5 GB
        feasible, msg = check_resource_availability("qwen3-8b", 5.5)
        assert feasible is False
        assert "Recursos insuficientes" in msg

        # Un modelo ultraligero de 1.5 GB sí cabría
        feasible_small, msg_small = check_resource_availability("phi-mini", 1.5)
        assert feasible_small is True
