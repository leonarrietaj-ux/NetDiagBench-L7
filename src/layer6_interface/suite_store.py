"""
NetDiagBench-L7: SuiteRunStore
Almacena y gestiona las sesiones de ejecución en vivo de la Suite de Observabilidad (LangGraph).
Mantiene en memoria y en disco (JSON) el historial completo de cada corrida para exportaciones PDF, Excel y JSON.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import PROJECT_ROOT
from src.core.logger import logger

SUITE_RUNS_DIR = PROJECT_ROOT / "data" / "runs" / "suite"
SUITE_RUNS_DIR.mkdir(parents=True, exist_ok=True)
LATEST_POINTER_FILE = SUITE_RUNS_DIR / "latest_suite_run.json"


@dataclass
class SuiteRunSession:
    run_id: str
    model_id: str
    model_name: str
    seed: int
    status: str = "running"  # "running" | "paused" | "completed" | "failed"
    total_cases: int = 18
    completed_cases: int = 0
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None
    cases: list[dict[str, Any]] = field(default_factory=list)
    summary_metrics: dict[str, Any] = field(default_factory=dict)

    def update_metrics(self) -> None:
        """Recalcula las métricas agregadas de la suite en base a los casos registrados."""
        if not self.cases:
            self.summary_metrics = {}
            return

        n = len(self.cases)
        rc_correct = sum(1 for c in self.cases if c.get("evaluation", {}).get("root_cause_correct"))
        comp_correct = sum(1 for c in self.cases if c.get("evaluation", {}).get("component_correct"))
        tools_called = sum(1 for c in self.cases if c.get("evaluation", {}).get("tool_called"))

        ttft_list = [c.get("telemetry", {}).get("ttft_ms", 0.0) for c in self.cases]
        tok_s_list = [c.get("telemetry", {}).get("tok_per_sec", 0.0) for c in self.cases]
        latency_list = [c.get("telemetry", {}).get("total_latency_ms", 0.0) for c in self.cases]
        vram_list = [c.get("telemetry", {}).get("vram_peak_gb", 0.0) for c in self.cases]
        tokens_list = [c.get("telemetry", {}).get("completion_tokens", 0) for c in self.cases]

        self.summary_metrics = {
            "completed_cases": n,
            "total_cases": self.total_cases,
            "root_cause_accuracy": round(rc_correct / n, 4) if n > 0 else 0.0,
            "component_accuracy": round(comp_correct / n, 4) if n > 0 else 0.0,
            "tool_call_rate": round(tools_called / n, 4) if n > 0 else 0.0,
            "avg_ttft_ms": round(sum(ttft_list) / n, 2) if n > 0 else 0.0,
            "avg_tok_per_sec": round(sum(tok_s_list) / n, 2) if n > 0 else 0.0,
            "total_latency_ms": round(sum(latency_list), 2),
            "avg_latency_ms": round(sum(latency_list) / n, 2) if n > 0 else 0.0,
            "vram_peak_gb": round(max(vram_list), 2) if vram_list else 4.0,
            "total_tokens_generated": sum(tokens_list),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convierte la sesión a un diccionario serializable."""
        return asdict(self)

    def to_dataframe(self):
        """Convierte los 18 casos de la ejecución real a un DataFrame de pandas."""
        import pandas as pd

        rows = []
        for c in self.cases:
            gt = c.get("ground_truth", {})
            pred = c.get("prediction", {})
            tel = c.get("telemetry", {})
            ev = c.get("evaluation", {})
            tool = c.get("tool_execution", {})

            rows.append({
                "Caso (#)": c.get("index"),
                "Escenario_ID": c.get("scenario_id"),
                "Categoria": c.get("category"),
                "Clase_Falla": c.get("fault_class"),
                "Modelo": self.model_name or self.model_id,
                "Semilla": self.seed,
                "Causa_Raiz_Predicha": pred.get("root_cause", ""),
                "Causa_Raiz_Esperada": gt.get("root_cause", ""),
                "Acierto_Causa_Raiz": 1 if ev.get("root_cause_correct") else 0,
                "Componente_Predicho": pred.get("affected_component", ""),
                "Componente_Esperado": gt.get("affected_component", ""),
                "Acierto_Componente": 1 if ev.get("component_correct") else 0,
                "Accion_Sugerida_Predicha": pred.get("suggested_action", ""),
                "Mitigacion_Esperada": gt.get("suggested_action", ""),
                "Herramienta_Ejecutada": tool.get("command") or tool.get("tool_name") or "Ninguna",
                "TTFT_ms": tel.get("ttft_ms", 0.0),
                "Velocidad_tok_s": tel.get("tok_per_sec", 0.0),
                "Latencia_Total_ms": tel.get("total_latency_ms", 0.0),
                "Pico_VRAM_GB": tel.get("vram_peak_gb", 0.0),
                "Tokens_Generados": tel.get("completion_tokens", 0),
                "Cadena_Razonamiento_CoT_Real": pred.get("natural_language_explanation", ""),
            })

        return pd.DataFrame(rows)


class SuiteRunStoreManager:
    """Gestor singleton en memoria y disco de sesiones de ejecución de la Suite."""

    def __init__(self) -> None:
        self._sessions: dict[str, SuiteRunSession] = {}
        self._latest_run_id: str | None = None
        self._latest_completed_run_id: str | None = None
        self._load_latest_pointer()

    def _load_latest_pointer(self) -> None:
        if LATEST_POINTER_FILE.exists():
            try:
                data = json.loads(LATEST_POINTER_FILE.read_text(encoding="utf-8"))
                self._latest_run_id = data.get("latest_run_id")
                self._latest_completed_run_id = data.get("latest_completed_run_id")
            except Exception:
                pass

    def _save_latest_pointer(self) -> None:
        try:
            LATEST_POINTER_FILE.write_text(
                json.dumps({
                    "latest_run_id": self._latest_run_id,
                    "latest_completed_run_id": self._latest_completed_run_id,
                    "updated_at": datetime.now().isoformat()
                }, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    def create_or_get_session(
        self,
        model_id: str,
        seed: int,
        run_id: str | None = None,
        model_name: str | None = None
    ) -> SuiteRunSession:
        if not run_id:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_model = model_id.replace(":", "-").replace(".", "-")
            run_id = f"suite_{clean_model}_s{seed}_{ts}"

        if run_id in self._sessions:
            session = self._sessions[run_id]
            session.updated_at = datetime.now().isoformat()
            return session

        # Intentar cargar de disco si existe
        disk_session = self.load_from_disk(run_id)
        if disk_session:
            self._sessions[run_id] = disk_session
            self._latest_run_id = run_id
            return disk_session

        # Crear nueva sesión
        session = SuiteRunSession(
            run_id=run_id,
            model_id=model_id,
            model_name=model_name or model_id,
            seed=seed,
            status="running",
            total_cases=18,
            completed_cases=0,
            cases=[]
        )
        self._sessions[run_id] = session
        self._latest_run_id = run_id
        self._save_latest_pointer()
        self.save_to_disk(session)
        return session

    def record_case(self, run_id: str, case_data: dict[str, Any]) -> SuiteRunSession:
        session = self._sessions.get(run_id)
        if not session:
            session = self.load_from_disk(run_id)
            if session:
                self._sessions[run_id] = session
            else:
                model_id = case_data.get("model_id", "unknown")
                seed = case_data.get("seed", 42)
                session = self.create_or_get_session(model_id=model_id, seed=seed, run_id=run_id)

        # Evitar duplicados por scenario_id reemplazando si ya existe
        sc_id = case_data.get("scenario_id")
        existing_idx = next((i for i, c in enumerate(session.cases) if c.get("scenario_id") == sc_id), None)
        if existing_idx is not None:
            session.cases[existing_idx] = case_data
        else:
            session.cases.append(case_data)

        session.completed_cases = len(session.cases)
        session.updated_at = datetime.now().isoformat()
        session.update_metrics()
        self._latest_run_id = run_id

        if session.completed_cases >= session.total_cases:
            session.status = "completed"
            session.completed_at = datetime.now().isoformat()
            self._latest_completed_run_id = run_id
            self._save_latest_pointer()

        self.save_to_disk(session)
        return session

    def mark_paused(self, run_id: str) -> SuiteRunSession | None:
        session = self._sessions.get(run_id) or self.load_from_disk(run_id)
        if session:
            session.status = "paused"
            session.updated_at = datetime.now().isoformat()
            self.save_to_disk(session)
        return session

    def mark_completed(self, run_id: str) -> SuiteRunSession | None:
        session = self._sessions.get(run_id) or self.load_from_disk(run_id)
        if session:
            session.status = "completed"
            session.completed_cases = len(session.cases)
            session.completed_at = datetime.now().isoformat()
            session.updated_at = datetime.now().isoformat()
            session.update_metrics()
            self._latest_completed_run_id = run_id
            self._save_latest_pointer()
            self.save_to_disk(session)
        return session

    def get_session(self, run_id: str | None = None) -> SuiteRunSession | None:
        if not run_id or run_id.lower() == "latest":
            run_id = self._latest_completed_run_id or self._latest_run_id
        if not run_id:
            # Buscar el archivo más reciente en disco
            files = sorted(SUITE_RUNS_DIR.glob("suite_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if files:
                run_id = files[0].stem

        if not run_id:
            return None

        if run_id in self._sessions:
            return self._sessions[run_id]

        disk_session = self.load_from_disk(run_id)
        if disk_session:
            self._sessions[run_id] = disk_session
            return disk_session

        return None

    def get_latest_completed_session(self) -> SuiteRunSession | None:
        if self._latest_completed_run_id:
            return self.get_session(self._latest_completed_run_id)
        # Buscar en disco alguna sesión completada
        files = sorted(SUITE_RUNS_DIR.glob("suite_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files:
            sess = self.load_from_disk(f.stem)
            if sess and sess.status == "completed" and sess.completed_cases >= sess.total_cases:
                self._latest_completed_run_id = sess.run_id
                return sess
        return None

    def save_to_disk(self, session: SuiteRunSession) -> Path:
        out_file = SUITE_RUNS_DIR / f"{session.run_id}.json"
        try:
            out_file.write_text(json.dumps(session.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Error guardando sesión suite {session.run_id} en disco: {e}")
        return out_file

    def load_from_disk(self, run_id: str) -> SuiteRunSession | None:
        file_path = SUITE_RUNS_DIR / f"{run_id}.json"
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return SuiteRunSession(**data)
        except Exception as e:
            logger.warning(f"Error cargando sesión suite {run_id} desde disco: {e}")
            return None


suite_store = SuiteRunStoreManager()
