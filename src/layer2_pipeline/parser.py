"""
NetDiagBench-L7: Layer 2 - Drain3 Log Parser
Realiza minería de plantillas y normalización semántica de logs crudos
mediante el algoritmo Drain3.
"""

from typing import Any

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from src.core.contracts import ParsedLogEntry


class Drain3LogParser:
    """Parser y extractor de patrones basado en Drain3."""

    def __init__(self, depth: int = 4, similarity_threshold: float = 0.5):
        config = TemplateMinerConfig()
        config.drain_depth = depth
        config.drain_sim_th = similarity_threshold
        # Desactivamos persistencia a disco durante corridas en memoria para mayor velocidad
        self.miner = TemplateMiner(config=config)

    def parse_log_line(
        self,
        raw_message: str,
        timestamp: str,
        source_service: str,
        log_level: str = "INFO",
        extra_meta: dict[str, Any] | None = None
    ) -> ParsedLogEntry:
        """Procesa una única línea de log con Drain3 y devuelve ParsedLogEntry."""
        result = self.miner.add_log_message(raw_message)
        cluster_id = str(result["cluster_id"]) if "cluster_id" in result else None
        template = result.get("template_mined", raw_message)
        params = result.get("parameter_list", [])

        extracted = {"drain_params": params}
        if extra_meta:
            extracted.update(extra_meta)

        return ParsedLogEntry(
            timestamp=timestamp,
            source_service=source_service,
            log_level=log_level,
            raw_message=raw_message,
            template_id=cluster_id,
            template_pattern=template,
            extracted_parameters=extracted
        )

    def parse_batch(self, raw_logs: list[dict[str, Any]]) -> list[ParsedLogEntry]:
        """Procesa un lote de registros crudos."""
        parsed_list: list[ParsedLogEntry] = []
        for entry in raw_logs:
            raw_msg = entry.get("raw_message", "")
            ts = entry.get("timestamp", "")
            srv = entry.get("source_service", "unknown")
            lvl = entry.get("log_level", "INFO")
            meta = {k: v for k, v in entry.items() if k not in ("raw_message", "timestamp", "source_service", "log_level")}

            parsed = self.parse_log_line(
                raw_message=raw_msg,
                timestamp=ts,
                source_service=srv,
                log_level=lvl,
                extra_meta=meta
            )
            parsed_list.append(parsed)
        return parsed_list
