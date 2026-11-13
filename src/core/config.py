EXPERIMENT_SEEDS: list[int] = [42, 1337, 2026]
"""
NetDiagBench-L7 Configuration Loader
Carga y valida los perfiles de hardware, modelos y parámetros del benchmark.
"""

import json
import re
import time
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"


class HardwareConfig(BaseModel):
    name: str = "Reference-Workstation-8GB-GPU"
    vram_gb: float = 8.0
    system_memory_gb: float = 32.0
    cpu_cores: int = 8
    lan_isolation: bool = True


class ModelDefinition(BaseModel):
    id: str
    name: str
    provider: str
    parameters_raw: str
    license: str
    quantization: str = "Q4_K_M"
    format: str = "GGUF"
    context_window_tokens: int = 32768
    function_calling_support: str
    ollama_tag: str
    approx_vram_gb: float
    reason_for_inclusion: str


class BenchmarkSettings(BaseModel):
    name: str = "NetDiagBench-L7-Execution"
    protocol_version: str = "1.0.4"
    seeds: list[int] = Field(default_factory=lambda: [42, 1337, 2026])
    repetitions_per_scenario: int = 1
    temperature: float = 0.0
    max_decoding_tokens: int = 1024
    timeout_per_diagnosis_seconds: int = 900
    rag_max_memory_gb: float = 0.45
    max_vram_gb: float = 8.0
    airgap_mode: bool = False
    min_free_disk_gb: float = 5.0
    execution_modes: dict[str, str] = Field(
        default_factory=lambda: {
            "TLS-EXP-01": "emulado",
            "HTTP-502-01": "emulado",
            "DNS-SRV-01": "emulado",
            "default": "sintetico_determinista"
        }
    )

    def get_execution_mode(self, scenario_id: str) -> str:
        """Devuelve el modo de ejecución configurado ('emulado' o 'sintetico_determinista') para un escenario."""
        return self.execution_modes.get(scenario_id, self.execution_modes.get("default", "sintetico_determinista"))


class SystemConfig:
    def __init__(self, configs_dir: Path = CONFIGS_DIR):
        self.configs_dir = configs_dir
        self.hardware = self._load_hardware()
        self.models = self._load_models()
        self.dynamic_models = self._load_dynamic_models()
        self.benchmark = self._load_benchmark()
        self._last_sync_time: float = time.time()
        self._sync_ttl_seconds: float = 30.0

    def get_all_models(self, force_sync: bool = False) -> list[ModelDefinition]:
        """Devuelve tanto la terna de modelos de referencia como los modelos integrados dinámicamente sincronizados con Ollama."""
        now = time.time()
        if not force_sync and (now - self._last_sync_time < self._sync_ttl_seconds) and (self.models or self.dynamic_models):
            return self.models + self.dynamic_models
        try:
            res = self.sync_with_ollama()
            self._last_sync_time = now
            return res
        except Exception:
            self.dynamic_models = self._load_dynamic_models()
            self.models = self._load_models()
            self._last_sync_time = now
            return self.models + self.dynamic_models

    def sync_with_ollama(self, ollama_url: str = "http://localhost:11434") -> list[ModelDefinition]:
        """
        Descubre automáticamente todos los modelos descargados en Ollama y los registra
        en dynamic_models si aún no están registrados, eliminando modelos que no existan.
        """
        urls_to_try = [ollama_url]
        if "localhost" in ollama_url:
            urls_to_try.append(ollama_url.replace("localhost", "127.0.0.1"))
        elif "127.0.0.1" in ollama_url:
            urls_to_try.append(ollama_url.replace("127.0.0.1", "localhost"))

        ollama_models = []
        try:
            import httpx
            for u in urls_to_try:
                try:
                    with httpx.Client(timeout=httpx.Timeout(1.5, connect=0.5)) as client:
                        resp = client.get(f"{u.rstrip('/')}/api/tags")
                        if resp.status_code == 200:
                            data = resp.json()
                            ollama_models = data.get("models", [])
                            ollama_url = u
                            break
                except Exception:
                    continue
        except Exception:
            pass

        if not ollama_models:
            self.dynamic_models = self._load_dynamic_models()
            self.models = self._load_models()
            return self.models + self.dynamic_models

        installed_tags = {m.get("name", "") for m in ollama_models if m.get("name")}
        base_models = self._load_models()
        base_ids = {bm.id.lower() for bm in base_models}
        dyn_models = self._load_dynamic_models()
        dyn_by_tag = {m.ollama_tag: m for m in dyn_models}

        updated_dyn: list[ModelDefinition] = []
        for tag in installed_tags:
            clean_slug = re.sub(r'[^a-zA-Z0-9_\-]', '-', tag).lower().strip('-')
            is_base = False
            for bm in base_models:
                bm_slug = re.sub(r'[^a-zA-Z0-9_\-]', '-', bm.ollama_tag).lower().strip('-')
                tag_prefix = tag.split(":")[0].lower() if ":" in tag else tag.lower()
                bm_prefix = bm.ollama_tag.split(":")[0].lower() if ":" in bm.ollama_tag else bm.ollama_tag.lower()
                if (
                    tag.lower() == bm.ollama_tag.lower()
                    or clean_slug == bm.id.lower()
                    or clean_slug == bm_slug
                    or clean_slug in base_ids
                    or (tag_prefix == bm_prefix and any(k in tag_prefix for k in ("qwen", "glm", "phi")))
                    or (tag_prefix in bm.id.lower() and any(k in tag_prefix for k in ("qwen", "glm", "phi")))
                ):
                    is_base = True
                    break
            if is_base:
                continue

            if tag in dyn_by_tag:
                updated_dyn.append(dyn_by_tag[tag])
            else:
                clean_slug = re.sub(r'[^a-zA-Z0-9_\-]', '-', tag).lower().strip('-')
                clean_name = tag.split(":")[0].replace("-", " ").title()
                param_m = re.search(r'(\d+(?:\.\d+)?)[bB]', tag)
                param_sz = f"{param_m.group(1)}B" if param_m else "Auto"
                quant = "Q4_K_M"
                family = "Ollama"
                try:
                    import httpx
                    with httpx.Client(timeout=httpx.Timeout(1.5, connect=0.5)) as client:
                        show_r = client.post(f"{ollama_url.rstrip('/')}/api/show", json={"name": tag})
                        if show_r.status_code == 200:
                            det = show_r.json().get("details", {})
                            quant = det.get("quantization_level", quant)
                            family = det.get("family", family)
                            if det.get("parameter_size"):
                                param_sz = det.get("parameter_size")
                except Exception:
                    pass

                new_m = ModelDefinition(
                    id=clean_slug,
                    name=f"{clean_name} ({tag})",
                    provider="Ollama Local",
                    parameters_raw=param_sz,
                    license=f"Open ({family.capitalize()})",
                    quantization=quant,
                    format="GGUF",
                    context_window_tokens=32768,
                    function_calling_support="native",
                    ollama_tag=tag,
                    approx_vram_gb=4.5,
                    reason_for_inclusion=f"Modelo {tag} detectado dinámicamente en Ollama local."
                )
                updated_dyn.append(new_m)

        removed = self._load_removed_model_ids()
        for dm in dyn_models:
            if dm.id.lower() in base_ids:
                continue
            if dm.ollama_tag not in installed_tags and dm.id not in {m.id for m in updated_dyn}:
                if dm.id not in removed and dm.ollama_tag not in removed:
                    updated_dyn.append(dm)

        self.dynamic_models = updated_dyn
        self._persist_dynamic_models()
        self.models = base_models
        return self.models + self.dynamic_models

    def _load_dynamic_models(self) -> list[ModelDefinition]:
        path = self.configs_dir / "dynamic_models.json"
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or []
                base_ids = {m.id.lower() for m in self._load_models()}
                return [ModelDefinition(**m) for m in data if m.get("id", "").lower() not in base_ids]
        except Exception:
            return []

    def save_dynamic_model(self, model: ModelDefinition) -> None:
        """Registra un modelo dinámico y lo persiste en dynamic_models.json."""
        for idx, m in enumerate(self.dynamic_models):
            if m.id == model.id or m.ollama_tag == model.ollama_tag:
                self.dynamic_models[idx] = model
                break
        else:
            self.dynamic_models.append(model)

        # Si el modelo había sido retirado previamente, se reactiva al volver a integrarlo
        removed = self._load_removed_model_ids()
        if model.id in removed or model.ollama_tag in removed:
            removed.discard(model.id)
            removed.discard(model.ollama_tag)
            self._save_removed_model_ids(removed)

        self._last_sync_time = 0.0
        self._persist_dynamic_models()

    def remove_model(self, model_id: str) -> ModelDefinition | None:
        """
        Retira un modelo del sistema.
        - Modelos dinámicos: se eliminan de dynamic_models.json.
        - Modelos de la terna base (models.yaml): se registran en removed_models.json
          (lista de exclusión) para no alterar el archivo de configuración original.
        Devuelve la definición del modelo retirado o None si no existía.
        """
        removed_def: ModelDefinition | None = None

        remaining = []
        for m in self.dynamic_models:
            if m.id == model_id or m.ollama_tag == model_id:
                removed_def = m
            else:
                remaining.append(m)
        if removed_def is not None:
            self._last_sync_time = 0.0
            self.dynamic_models = remaining
            self._persist_dynamic_models()

        for m in self.models:
            if m.id == model_id or m.ollama_tag == model_id:
                removed_def = removed_def or m
                removed = self._load_removed_model_ids()
                removed.add(m.id)
                self._save_removed_model_ids(removed)
                self.models = [x for x in self.models if x.id != m.id]
                break

        return removed_def

    def _persist_dynamic_models(self) -> None:
        path = self.configs_dir / "dynamic_models.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump([m.model_dump() for m in self.dynamic_models], f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_removed_model_ids(self) -> set[str]:
        path = self.configs_dir / "removed_models.json"
        if not path.exists():
            return set()
        try:
            with open(path, "r", encoding="utf-8") as f:
                return set(json.load(f) or [])
        except Exception:
            return set()

    def _save_removed_model_ids(self, ids: set[str]) -> None:
        path = self.configs_dir / "removed_models.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sorted(ids), f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_hardware(self) -> HardwareConfig:
        path = self.configs_dir / "hardware_reference.yaml"
        if not path.exists():
            return HardwareConfig()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            plat = data.get("platform", {})
            return HardwareConfig(
                name=plat.get("name", "Reference-Workstation-8GB-GPU"),
                vram_gb=plat.get("gpu", {}).get("vram_gb", 8.0),
                system_memory_gb=plat.get("system_memory", {}).get("ram_gb", 32.0),
                cpu_cores=plat.get("cpu", {}).get("cores", 8),
                lan_isolation=plat.get("network", {}).get("lan_isolation", True)
            )

    def _load_models(self) -> list[ModelDefinition]:
        path = self.configs_dir / "models.yaml"
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            raw_models = data.get("models", [])
            removed = self._load_removed_model_ids()
            return [
                ModelDefinition(**m) for m in raw_models
                if m.get("id") not in removed and m.get("ollama_tag") not in removed
            ]

    def _load_benchmark(self) -> BenchmarkSettings:
        path = self.configs_dir / "benchmark_config.yaml"
        if not path.exists():
            return BenchmarkSettings()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            bench_data = data.get("benchmark", {})
            limits = data.get("memory_limits", {})
            modes = data.get("execution_modes", {})
            sec_data = data.get("security", {})
            return BenchmarkSettings(
                name=bench_data.get("name", "NetDiagBench-L7-Execution"),
                protocol_version=bench_data.get("protocol_version", "1.0.0"),
                seeds=bench_data.get("seeds", [42, 1337, 2026]),
                repetitions_per_scenario=bench_data.get("repetitions_per_scenario", 1),
                temperature=bench_data.get("temperature", 0.0),
                max_decoding_tokens=bench_data.get("max_decoding_tokens", 1024),
                timeout_per_diagnosis_seconds=bench_data.get("timeout_per_diagnosis_seconds", 900),
                rag_max_memory_gb=limits.get("rag_max_memory_gb", 0.45),
                max_vram_gb=limits.get("max_vram_gb", 8.0),
                airgap_mode=bool(sec_data.get("airgap_mode", False)),
                min_free_disk_gb=float(sec_data.get("min_free_disk_gb", 5.0)),
                execution_modes=modes if modes else {
                    "TLS-EXP-01": "emulado",
                    "HTTP-502-01": "emulado",
                    "DNS-SRV-01": "emulado",
                    "default": "sintetico_determinista"
                }
            )
