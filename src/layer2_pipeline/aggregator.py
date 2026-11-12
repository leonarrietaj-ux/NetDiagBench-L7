"""
NetDiagBench-L7: Layer 2 - Data Pipeline & Aggregator
Integra el parsing de Drain3, consolidación de telemetría y renderizado Jinja2
para emitir el contrato VentanaLogContract.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jinja2

from src.core.config import PROJECT_ROOT
from src.core.contracts import (
    EscenarioLabContract,
    TelemetrySummary,
    VentanaLogContract,
)
from src.core.logger import logger
from src.layer2_pipeline.parser import Drain3LogParser


class DataPipelineAgent:
    """Agente de la Capa 2 responsable del preprocesamiento y generación de la ventana temporal."""

    def __init__(self, template_path: Path | None = None):
        self.parser = Drain3LogParser()
        self.template_path = template_path or (PROJECT_ROOT / "data" / "templates" / "context_window.j2")
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_path.parent)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._template = self._jinja_env.get_template(self.template_path.name)

    def process_window(
        self,
        scenario: EscenarioLabContract,
        raw_logs: list[dict[str, Any]],
        raw_telemetry: dict[str, Any] | None = None,
        window_start: datetime | None = None,
        window_end: datetime | None = None
    ) -> VentanaLogContract:
        """
        Procesa registros crudos y telemetría, minando plantillas con Drain3
        y generando el prompt contextual formateado con Jinja2.
        """
        now = datetime.now(UTC)
        start = window_start or now
        end = window_end or now

        parsed_logs = self.parser.parse_batch(raw_logs)

        # Construir resumen de telemetría
        t_data = raw_telemetry or {}
        telemetry = TelemetrySummary(
            error_rate_pct=float(t_data.get("error_rate_pct", 0.0)),
            p50_latency_ms=t_data.get("p50_latency_ms"),
            p95_latency_ms=t_data.get("p95_latency_ms"),
            sample_count=int(t_data.get("sample_count", len(raw_logs))),
        )

        # Renderizar prompt contextual con la plantilla Jinja2
        rendered_prompt = self._template.render(
            scenario_id=scenario.scenario_id,
            service_type=scenario.category.value,
            window_start=start.strftime("%Y-%m-%d %H:%M:%S"),
            window_end=end.strftime("%Y-%m-%d %H:%M:%S"),
            telemetry_summary=telemetry,
            parsed_logs=parsed_logs,
        )

        contract = VentanaLogContract(
            scenario_id=scenario.scenario_id,
            window_start=start,
            window_end=end,
            service_type=scenario.category,
            parsed_logs=parsed_logs,
            telemetry_summary=telemetry,
            rendered_context_prompt=rendered_prompt,
        )

        logger.debug(
            f"Ventana procesada para escenario {scenario.scenario_id}: {len(parsed_logs)} logs parseados."
        )
        return contract
