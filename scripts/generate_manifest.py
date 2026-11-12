import json
from datetime import datetime, timezone
from pathlib import Path
from src.core.config import PROJECT_ROOT, EXPERIMENT_SEEDS
from src.core.hardware_detector import detect_system_hardware

def create_manifest():
    hw = detect_system_hardware()
    hw_dict = {
        "timestamp_detection": datetime.now(timezone.utc).isoformat(),
        "cpu_model": hw.cpu_model,
        "cpu_cores_physical": hw.cpu_cores_physical,
        "cpu_cores_logical": hw.cpu_cores_logical,
        "os_version": hw.os_version,
        "ram_total_gb": hw.ram_total_gb,
        "ram_available_gb": hw.ram_available_gb,
        "ram_measurement_method": hw.ram_measurement_method,
        "gpu_model": hw.gpu_model,
        "gpu_vendor": hw.gpu_vendor,
        "hardware_classification": hw.hardware_classification,
        "driver_version": hw.driver_version,
        "vram_total_gb": hw.vram_total_gb,
        "vram_shared_gb": hw.vram_shared_gb,
        "vram_measurement_method": hw.vram_measurement_method,
        "vram_measurement_valid": hw.vram_measurement_valid,
        "vram_measurement_status": hw.vram_measurement_status,
        "inference_backend": hw.inference_backend,
        "hardware_fingerprint": hw.fingerprint
    }
    
    # Guardar hardware_detectado.json
    hw_file = PROJECT_ROOT / "hardware_detectado.json"
    hw_file.write_text(json.dumps(hw_dict, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Hardware detectado guardado en {hw_file}")

    manifest_dict = {
        "benchmark_name": "NetDiagBench-L7",
        "version": "Parte 3/4 - Campaña Oficial 162 Corridas",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_design": {
            "total_runs": 162,
            "total_scenarios": 18,
            "models_count": 3,
            "seeds_count": 3,
            "repetitions_per_seed": 1,
            "distribution": {
                "emulated_docker_scenarios": ["TLS-EXP-01", "HTTP-502-01", "DNS-SRV-01"],
                "synthetic_lab_scenarios": [
                    "DNS-NXD-01", "DNS-DEL-01", "DNS-PTR-01", "DNS-CHA-01",
                    "HTTP-403-01", "HTTP-404-01", "HTTP-408-01", "HTTP-500-01", "HTTP-504-01",
                    "TLS-CIP-01", "TLS-CNM-01", "TLS-PRT-01",
                    "ROUT-BGP-01", "ROUT-OSPF-01", "ROUT-BLA-01"
                ]
            },
            "cluster_units": 18,
            "seeds_authorized": EXPERIMENT_SEEDS,
            "temperature": 0.0,
            "top_p": 0.9,
            "max_tokens": 1024,
            "context_window": 8192
        },
        "models": {
            "qwen3-8b": {
                "ollama_tag": "qwen3:8b",
                "parameters_raw": "8.2B",
                "architecture": "qwen3",
                "quantization": "Q4_K_M",
                "digest": "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
            },
            "glm-4-9b-chat": {
                "ollama_tag": "glm4:9b-chat-q4_K_M",
                "parameters_raw": "9.4B",
                "architecture": "chatglm",
                "quantization": "Q4_0",
                "digest": "5b699761eca535dc55047ad9d2dbf54e3b8697709419ef78a70503ed4bfbcf44"
            },
            "phi-4-mini-instruct": {
                "ollama_tag": "phi4-mini:instruct-q4_K_M",
                "parameters_raw": "3.8B",
                "architecture": "phi3",
                "quantization": "Q4_K_M",
                "digest": "78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753"
            }
        },
        "infrastructure": {
            "ollama_host": "http://localhost:11434",
            "docker_engine": "Docker Desktop 28.4.0",
            "execution_backend": hw.inference_backend,
            "hardware_summary": f"{hw.cpu_model} | {hw.ram_total_gb:.1f} GB RAM | GPU: {hw.gpu_model}"
        }
    }
    
    # Guardar manifest.json
    manifest_file = PROJECT_ROOT / "manifest.json"
    manifest_file.write_text(json.dumps(manifest_dict, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Manifiesto guardado en {manifest_file}")

if __name__ == "__main__":
    create_manifest()
