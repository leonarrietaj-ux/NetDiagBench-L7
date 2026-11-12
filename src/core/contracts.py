"""
NetDiagBench-L7: Data Contracts & Artifact Schemas (Capas 1 a 7)
Define los contratos estrictos de datos que intercambian las 7 capas del sistema,
garantizando modularidad e independencia de componentes.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums del Dominio
# ---------------------------------------------------------------------------

class ServiceCategory(str, Enum):
    DNS = "DNS"
    HTTP_WEB = "HTTP_WEB"
    API_GATEWAY = "API_GATEWAY"
    TLS = "TLS"


class FaultClass(str, Enum):
    NXDOMAIN = "NXDOMAIN"
    SERVFAIL = "SERVFAIL"
    DELEGATION_ERROR = "DELEGATION_ERROR"
    DNS_REFUSED = "DNS_REFUSED"
    DNS_TRUNCATED_EDNS = "DNS_TRUNCATED_EDNS"
    HTTP_502_BAD_GATEWAY = "HTTP_502_BAD_GATEWAY"
    HTTP_504_GATEWAY_TIMEOUT = "HTTP_504_GATEWAY_TIMEOUT"
    HTTP_500_INTERNAL = "HTTP_500_INTERNAL"
    HTTP_403_FORBIDDEN = "HTTP_403_FORBIDDEN"
    HTTP_429_RATE_LIMITED = "HTTP_429_RATE_LIMITED"
    HTTP_503_SERVICE_UNAVAILABLE = "HTTP_503_SERVICE_UNAVAILABLE"
    TLS_EXPIRED_CERT = "TLS_EXPIRED_CERT"
    TLS_CHAIN_INVALID = "TLS_CHAIN_INVALID"
    TLS_SNI_MISMATCH = "TLS_SNI_MISMATCH"
    TLS_CIPHER_MISMATCH = "TLS_CIPHER_MISMATCH"
    ORIGIN_DOWN = "ORIGIN_DOWN"
    CONNECTION_POOL_EXHAUSTED = "CONNECTION_POOL_EXHAUSTED"
    NETWORK_LATENCY_TC = "NETWORK_LATENCY_TC"


# ---------------------------------------------------------------------------
# CAPA 1: Escenario de Laboratorio (escenario.yaml)
# ---------------------------------------------------------------------------

class GroundTruth(BaseModel):
    root_cause: str = Field(..., description="Causa raíz exacta esperada según ficha técnica")
    affected_component: str = Field(..., description="Componente de la topología afectado")
    suggested_action: str = Field(..., description="Acción de mitigación/reparación recomendada")
    minimum_required_evidence: list[str] = Field(
        default_factory=list,
        description="Lista de verificaciones o artefactos mínimos que sustentan el diagnóstico (dig, curl, status)"
    )


class EscenarioLabContract(BaseModel):
    """Artefacto emitido por ScenarioLabAgent: escenario.yaml"""
    scenario_id: str = Field(..., description="Identificador único del escenario (ej. DNS-NXD-01)")
    category: ServiceCategory
    fault_class: FaultClass
    description: str
    topology_file: str | None = Field(default=None, description="Ruta al archivo clab o docker-compose")
    injection_script: str | None = None
    ground_truth: GroundTruth
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CAPA 2: Preprocesamiento e Ingesta (ventana.jsonl)
# ---------------------------------------------------------------------------

class ParsedLogEntry(BaseModel):
    timestamp: str
    source_service: str
    log_level: str
    raw_message: str
    template_id: str | None = None
    template_pattern: str | None = None
    extracted_parameters: dict[str, Any] = Field(default_factory=dict)


class TelemetrySummary(BaseModel):
    error_rate_pct: float = Field(0.0, description="Tasa de error observada en la ventana")
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    sample_count: int = 0


class VentanaLogContract(BaseModel):
    """Artefacto emitido por DataPipelineAgent: ventana.jsonl"""
    scenario_id: str
    window_start: datetime
    window_end: datetime
    service_type: ServiceCategory
    parsed_logs: list[ParsedLogEntry] = Field(default_factory=list)
    telemetry_summary: TelemetrySummary = Field(default_factory=TelemetrySummary)
    rendered_context_prompt: str = Field(..., description="Texto final preprocesado con Jinja2")


# ---------------------------------------------------------------------------
# CAPA 3: RAG y Documentación Técnica (contexto.md)
# ---------------------------------------------------------------------------

class RAGDocumentChunk(BaseModel):
    source_document: str = Field(..., description="RFC o SOP de origen (ej: RFC 1035, SOP-DNS-02)")
    section: str | None = None
    content: str
    similarity_score: float = 0.0


class ContextoRAGContract(BaseModel):
    """Artefacto emitido por RAGKnowledgeAgent: contexto.md"""
    query: str
    chunks: list[RAGDocumentChunk] = Field(default_factory=list)
    formatted_markdown: str = Field(..., description="Contenido en formato Markdown para adjuntar al prompt")
    memory_footprint_mb: float = Field(..., description="Uso de memoria del vectorstore al momento de la consulta")


# ---------------------------------------------------------------------------
# CAPA 4: Inferencia Local (respuesta.json)
# ---------------------------------------------------------------------------

class TelemetriaInferencia(BaseModel):
    time_to_first_token_ms: float = Field(..., description="TTFT (fase de prellenado)")
    decode_tokens_per_second: float = Field(..., description="Velocidad de generación autoregresiva")
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_latency_ms: float = 0.0
    vram_peak_gb: float | None = None
    vram_measurement_status: str = Field("not_available", description="measured, estimated, declared, shared_only, not_available")
    inference_backend: str = Field("CPU", description="CPU, GPU, HYBRID, UNKNOWN")
    kv_cache_usage_mb: float | None = None
    ttft_final_ms: float = Field(0.0, description="TTFT para el primer token de respuesta final tras razonamiento CoT")
    reasoning_tokens: int = Field(0, description="Cantidad de tokens emitidos en fases de razonamiento <think>")


class RespuestaInferenciaContract(BaseModel):
    """Artefacto emitido por InferenceEngineAgent: respuesta.json"""
    model_id: str
    prompt_used: str
    raw_response_text: str
    telemetry: TelemetriaInferencia
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reasoning_text: str = Field("", description="Texto de razonamiento extraído de bloques <think>")
    context_truncated: bool = Field(False, description="Indica si el prompt requirió truncamiento determinista por ventana de contexto")
    engine_mode: str = Field("deterministic_simulator", description="live_ollama | deterministic_simulator")


# ---------------------------------------------------------------------------
# CAPA 5: Orquestación Agéntica (traza.jsonl)
# ---------------------------------------------------------------------------

class ToolExecutionStep(BaseModel):
    step_number: int
    tool_name: str = Field(..., description="dig, curl, openssl, prometheus_query")
    command_executed: str
    output_received: str
    reasoning: str
    hypothesis_tested: str


class TrazaOrquestacionContract(BaseModel):
    """Artefacto emitido por DiagnosticOrchestratorAgent: traza.jsonl"""
    session_id: str
    scenario_id: str
    model_id: str
    seed: int
    steps: list[ToolExecutionStep] = Field(default_factory=list)
    final_decision_reached: bool = True
    iterations_count: int = 0
    execution_mode: str = Field("sintetico_determinista", description="Modalidad de ejecución: 'emulado' o 'sintetico_determinista'")
    tool_calls_count: int = Field(0, description="Número de herramientas invocadas (Hallazgo N4)")
    llm_calls_count: int = Field(1, description="Número total de llamadas de inferencia al LLM (Hallazgo N4)")


# ---------------------------------------------------------------------------
# CAPA 6: Interfaz y Diagnóstico Estructurado (diagnostico.json / .md)
# ---------------------------------------------------------------------------

class DiagnosticoFinalContract(BaseModel):
    """Artefacto emitido por InterfaceCLIAgent: diagnostico.json y diagnostico.md"""
    scenario_id: str
    model_id: str
    root_cause: str = Field(..., description="Hipótesis de causa raíz emitida por el asistente")
    affected_component: str = Field(..., description="Componente identificado como causante de la degradación")
    suggested_action: str = Field(..., description="Acción de mitigación propuesta")
    natural_language_explanation: str = Field(..., description="Explicación detallada en lenguaje natural")
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="Evidencias consultadas durante la verificación (outputs de herramientas)"
    )
    is_evidence_backed: bool = Field(False, description="Indica si el diagnóstico se fundamentó con herramientas")
    tool_blocked_penalty: bool = Field(False, description="Penalización de 1.0 punto por comando bloqueado no corregido en reintento")
    confidence_score: float | None = None
    execution_mode: str = Field("sintetico_determinista", description="Modalidad de ejecución: 'emulado' (Docker en vivo) o 'sintetico_determinista'")
    engine_mode: str = Field("deterministic_simulator", description="Motor de inferencia: 'live_ollama' o 'deterministic_simulator'")
    factual_accuracy_c6: int = Field(2, description="Exactitud factual C6 de la evidencia: 2 (plena), 1 (parcial), 0 (alucinación)")
    c6_automated_evidence_check: int = Field(2, description="Verificación automática de evidencia del agente (0=alucinación/bloqueado, 1=parcial, 2=plena)")
    c6_human_score: int | None = Field(None, description="Calificación humana real del criterio C6 (None si no evaluado aún por humanos)")
    evidence_status: str = Field("backed", description="Estado de la evidencia ('backed', 'partial', 'unbacked', 'no_evidence', 'tool_blocked', 'contradictory')")
    sustentation_status: str = Field("sustentado", description="Estado de sustentación ('sustentado', 'no_sustentado', 'pendiente_evaluacion_humana')")
    model_diagnosis_text: str = Field("", description="Texto completo de diagnóstico emitido por el modelo")
    git_commit_hash: str = Field("desconocido", description="Hash commit SHA de git en la corrida o 'desconocido'")
    git_dirty: str | bool = Field("desconocido", description="True si git status tiene cambios sin commitear o 'desconocido'")
    container_image_digest: str = Field("", description="Digest sha256 de la imagen del contenedor en corridas emuladas")
    docker_version: str = Field("", description="Versión del motor Docker empleado en corridas emuladas")
    reasoning_text: str = Field("", description="Texto de razonamiento extraído")
    parse_status: str = Field("ok", description="Estado de parseo de la causa raíz: ok | formato_invalido")
    context_truncated: bool = Field(False, description="Indica si el contexto fue recortado")
    reasoning_tokens: int = Field(0, description="Tokens de razonamiento")
    ttft_final_ms: float = Field(0.0, description="TTFT hasta el primer token de respuesta final")
    rescore_commit: str = Field("", description="Hash commit SHA de git utilizado durante la recalificación normativa")


# ---------------------------------------------------------------------------
# CAPA 7: Evaluación y Medición (resultados.csv)
# ---------------------------------------------------------------------------

class ResultadoEvaluacionContract(BaseModel):
    """Artefacto emitido por BenchmarkEvaluatorAgent: fila de resultados.csv"""
    scenario_id: str
    model_id: str
    seed: int
    repetition_index: int
    category: str
    fault_class: str

    # Métricas de precisión
    is_root_cause_correct: bool = Field(..., description="Acierto estricto en aislamiento de causa raíz (71/162, 43.8%)")
    is_full_diagnosis_correct: bool = Field(False, description="Acierto en diagnóstico completo de la falla (122/162, 75.3%)")
    is_root_cause_correct_strict: bool | None = Field(None, description="Alias de compatibilidad para causa raíz estricta (71/162)")
    is_root_cause_correct_full_text: bool | None = Field(None, description="Alias de compatibilidad para diagnóstico completo (122/162)")
    is_component_correct: bool
    partial_match_score: float = Field(..., ge=0.0, le=1.0)
    evidence_backed: bool

    # Métricas de latencia y velocidad
    ttft_ms: float
    tokens_per_sec: float
    total_time_ms: float
    tool_steps_count: int

    # Métricas de recursos y huella
    cpu_percent_avg: float
    peak_ram_mb: float
    peak_vram_gb: float | None = Field(None, description="VRAM pico física medida en GB (null si no medible dinámicamente)")
    energy_kwh: float
    co2_emissions_kg: float

    # Rúbrica de explicación (0 a 5)
    rubric_score: float | None = None

    # Metadata del entorno y trazabilidad MLOps (Hallazgos 2.1 & 2.2)
    host_hardware_fingerprint: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    modelo_version: str = Field("Q4_K_M-GGUF", description="Versión, cuantización y huella del modelo")
    model_family: str = Field("completo", description="Familia del modelo: ultraligero, razonamiento, intermedio, codigo, completo")
    model_group: str = Field("oficial", description="Grupo del modelo: 'oficial' o 'adicional'")
    evaluator_version: str = Field("", description="Hash SHA256 de evaluator_concepts.yaml")
    ollama_version: str = Field("desconocida", description="Versión del motor Ollama empleado")
    semilla: int = Field(42, description="Semilla pseudoaleatoria (alias canónico de reproducibilidad)")
    timestamp: str = Field("", description="Marca temporal ISO-8601 de la evaluación")
    execution_mode: str = Field("sintetico_determinista", description="Modalidad de ejecución: 'emulado' (Docker en vivo) o 'sintetico_determinista'")
    engine_mode: str = Field("deterministic_simulator", description="Motor de inferencia: 'live_ollama' o 'deterministic_simulator'")
    factual_accuracy_c6: int = Field(2, description="Exactitud factual C6 de la evidencia: 2 (plena), 1 (parcial), 0 (alucinación)")
    c6_automated_evidence_check: int = Field(2, description="Verificación automática de evidencia del agente (0=alucinación/bloqueado, 1=parcial, 2=plena)")
    c6_human_score: int | None = Field(None, description="Calificación humana real del criterio C6 (None si no evaluado aún por humanos)")
    evidence_status: str = Field("backed", description="Estado de la evidencia ('backed', 'partial', 'unbacked', 'no_evidence', 'tool_blocked', 'contradictory')")
    sustentation_status: str = Field("sustentado", description="Estado de sustentación ('sustentado', 'no_sustentado', 'pendiente_evaluacion_humana')")
    model_diagnosis_text: str = Field("", description="Texto completo de diagnóstico emitido por el modelo")
    root_cause: str = Field("", description="Causa raíz predicha emitida por el modelo")
    git_commit_hash: str = Field("desconocido", description="Hash commit SHA de git en la corrida o 'desconocido'")
    git_dirty: str | bool = Field("desconocido", description="True si git status tiene cambios sin commitear o 'desconocido'")
    container_image_digest: str = Field("", description="Digest sha256 de la imagen del contenedor en corridas emuladas")
    docker_version: str = Field("", description="Versión del motor Docker empleado en corridas emuladas")
    reasoning_text: str = Field("", description="Texto de razonamiento extraído")
    parse_status: str = Field("ok", description="Estado de parseo de la causa raíz: ok | formato_invalido")
    context_truncated: bool = Field(False, description="Indica si el contexto fue recortado")
    reasoning_tokens: int = Field(0, description="Tokens de razonamiento")
    ttft_final_ms: float = Field(0.0, description="TTFT hasta el primer token de respuesta final")
    rescore_commit: str = Field("", description="Hash commit SHA de git utilizado durante la recalificación normativa")

    # Unidades normalizadas (Hallazgo 4.5)
    ttft_s: float = Field(0.0, description="TTFT normalizado en segundos")
    tokens_per_kwh: float = Field(0.0, description="Eficiencia energética en tokens/kWh")
    energy_measurement_type: str = Field("estimada", description="Modalidad de medición de energía: 'estimada' o 'medida'")
    ram_gb: float = Field(0.0, description="RAM del proceso normalizada en GB")

    # Detección y persistencia de hardware físico real (Hallazgos 4.2 & 4.3 y Secciones 5 y 6)
    gpu_model_detected: str = Field("AMD Radeon(TM) 610M", description="Modelo real de GPU detectado")
    vram_total_gb: float | None = Field(2.0, description="VRAM física total en GB (null si no existe VRAM dedicada)")
    vram_peak_gb: float | None = Field(None, description="Pico de VRAM física medido en GB (null si no medible dinámicamente)")
    vram_declared_gb: float | None = Field(8.0, description="VRAM declarada en el perfil de configuración")
    vram_estimated_gb: float | None = Field(None, description="VRAM estimada teórica en GB cuando no es medible físicamente")
    vram_shared_gb: float | None = Field(None, description="VRAM/memoria compartida asignada en GB")
    vram_measurement_method: str = Field("static_profile", description="Método de medición: nvidia-smi, nvml, ollama_ps, wmi, static_profile, not_available")
    vram_measurement_valid: bool = Field(False, description="True si la VRAM fue medida dinámicamente en vivo")
    vram_measurement_status: str = Field("not_available", description="measured, estimated, declared, shared_only, not_available")
    ram_total_gb: float = Field(13.8, description="RAM física total del host en GB")
    ram_available_gb: float = Field(0.0, description="RAM física disponible al inicio en GB")
    ram_peak_gb: float = Field(0.0, description="Memoria RAM física pico alcanzada en GB")
    ram_measurement_method: str = Field("psutil", description="Método de medición de RAM: psutil")
    process_max_ram_gb: float = Field(0.0, description="Memoria de trabajo máxima alcanzada por el proceso en GB")
    hardware_classification: str = Field("CPU_ONLY", description="GPU_DEDICATED, GPU_INTEGRATED, CPU_ONLY, GPU_DETECTED_UNSUPPORTED, HARDWARE_DETECTION_PARTIAL")
    inference_backend: str = Field("CPU", description="Backend real de inferencia: CPU, GPU, HYBRID, UNKNOWN")
    cpu_model: str = Field("AMD64 Family 23 Model 160 Stepping 0", description="Modelo de CPU detectado")
    os_version: str = Field("Windows 11", description="Sistema operativo y build")
    driver_version: str = Field("32.0.21030.13004", description="Versión de driver gráfico")
    cuda_version: str = Field("N/A", description="Versión de CUDA o N/A")

    # Puntaje compuesto unificado 40/20/20/20 y elegibilidad (Hallazgo 4.1)
    puntaje_precision: float = Field(0.0, description="Componente de precisión en el puntaje compuesto (40%)")
    puntaje_rubrica: float = Field(0.0, description="Componente de rúbrica en el puntaje compuesto (20%)")
    puntaje_velocidad: float = Field(0.0, description="Componente de velocidad en el puntaje compuesto (20%)")
    puntaje_vram: float | None = Field(None, description="Componente de eficiencia de VRAM en el puntaje compuesto (20%)")
    puntaje_compuesto: float | None = Field(None, description="Puntaje compuesto multicriterio normalizado 40/20/20/20 (null si VRAM no es medible físicamente)")
    elegibilidad: bool | None = Field(None, description="Elegibilidad técnica según umbral mínimo de exactitud (>= 70%) a nivel modelo")
    motivo_exclusion: str = Field("", description="Motivo de exclusión si el modelo no alcanza el umbral de exactitud")


# ---------------------------------------------------------------------------
# CAPA 8: Validación Humana y Calibración Inter-Evaluador
# ---------------------------------------------------------------------------

class EtiquetaExperto(BaseModel):
    """Contrato formal para la etiqueta de autenticación y orden de un evaluador humano."""
    expert_id: str = Field(..., description="Identificador único del experto: 'A', 'B' o 'C'")
    rol: str = Field(..., description="Rol funcional: 'evaluador' o 'dirimente'")
    alias: str = Field(..., description="Alias anónimo del experto (no el nombre real)")
    sesion_id: str = Field(..., description="Identificador de la sesión ciega de validación")
    fecha_emision: str = Field(..., description="Marca temporal de emisión en formato ISO-8601")
    semilla_orden: int = Field(..., description="Semilla pseudoaleatoria usada para barajar el orden de evaluación")
    orden: list[str] = Field(..., description="Lista de los códigos ciegos barajados asignados al evaluador")
    codigo_acceso: str = Field(..., description="Código de acceso seguro de 8 caracteres emitido por secrets")
    huella_sha256: str = Field(..., description="Huella SHA-256 de integridad (sesion_id, expert_id, orden, version_evaluador)")


class ClaveCegamientoEntry(BaseModel):
    """Entrada individual de la clave restringida de cegamiento."""
    codigo: str = Field(..., description="Código ciego asignado (ej. EV-001)")
    model_id: str = Field(..., description="Identificador real del modelo evaluado")
    scenario_id: str = Field(..., description="Identificador del escenario de red evaluado")
    seed: int = Field(..., description="Semilla de la corrida en data/runs")
    ruta_diagnostico: str = Field(..., description="Ruta relativa o absoluta al archivo diagnostico.json")


class FichaCiegaEvaluador(BaseModel):
    """
    Ficha estrictamente ciega entregada a los evaluadores humanos.
    No contiene causa raíz esperada, componente esperado ni evidencia mínima requerida (Ground Truth).
    """
    codigo: str
    scenario_id: str
    sintoma: str
    pasos_herramienta: list[dict[str, Any]] = Field(default_factory=list)
    veredicto: dict[str, Any] = Field(default_factory=dict)


class CorridaAnonimizada(BaseModel):
    """Ficha interna de una corrida anonimizada con referencia técnica para análisis restringido."""
    codigo: str
    scenario_id: str
    sintoma: str
    causa_raiz_esperada: str = ""
    componente_esperado: str = ""
    evidencia_minima: list[str] = Field(default_factory=list)
    pasos_herramienta: list[dict[str, Any]] = Field(default_factory=list)
    veredicto: dict[str, Any] = Field(default_factory=dict)

    def to_blind_card(self) -> FichaCiegaEvaluador:
        """Separa los datos de referencia internos y retorna el objeto estrictamente ciego para el evaluador."""
        return FichaCiegaEvaluador(
            codigo=self.codigo,
            scenario_id=self.scenario_id,
            sintoma=self.sintoma,
            pasos_herramienta=self.pasos_herramienta,
            veredicto=self.veredicto,
        )

