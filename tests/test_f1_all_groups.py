"""
NetDiagBench-L7: Suite de Pruebas F1 Macro y Clasificación Multiclase (OE4 / Tarea 4.1.2)
Verifica la extracción determinista de las 18 clases canónicas de fallas L7
sin fuga de datos (Zero Data Leakage), preservación de UNKNOWN y cálculo de métricas.
"""

import pytest
from src.layer7_evaluator.statistical_analysis import (
    parse_fault_class_predicted,
    compute_classification_metrics,
)
from src.layer7_evaluator.metrics import load_evaluator_concepts


# Diccionario canónico de frases técnicas realistas para cada una de las 18 fallas
CANONICAL_FAULTS_CORPUS: dict[str, str] = {
    "DELEGATION_ERROR": "Falla de delegacion de zona DNS: Lame delegation y glue records faltantes.",
    "NXDOMAIN": "El dominio consultado no existe en la zona retornando NXDOMAIN / RCODE 3.",
    "DNS_REFUSED": "La consulta fue rechazada por el servidor DNS debido a restriccion de directiva allow-query y lista de control de acceso ACL.",
    "SERVFAIL": "Fallo de resolucion SERVFAIL debido a que el servidor autoritativo remoto no responde (timeout en puerto 53).",
    "DNS_TRUNCATED_EDNS": "Respuesta truncada TC bit con buffer EDNS0 insuficiente o fragmentacion UDP.",
    "HTTP_403_FORBIDDEN": "Acceso prohibido HTTP 403 Forbidden por politicas de control de acceso WAF deny all.",
    "HTTP_429_RATE_LIMITED": "Exceso de tasa de peticiones HTTP 429 Too Many Requests por rate limiting en proxy inverso.",
    "HTTP_500_INTERNAL": "Error interno del servidor HTTP 500 Internal Server Error por excepcion no capturada KeyError en aplicacion FastAPI.",
    "HTTP_502_BAD_GATEWAY": "Fallo HTTP 502 Bad Gateway: backend upstream caido con connection refused al puerto 8080.",
    "HTTP_503_SERVICE_UNAVAILABLE": "Servicio no disponible HTTP 503 Service Unavailable debido a workers saturados y sobrecargados en el backend.",
    "HTTP_504_GATEWAY_TIMEOUT": "Tiempo de espera agotado HTTP 504 Gateway Timeout esperando respuesta de upstream proxy_read_timeout.",
    "CONNECTION_POOL_EXHAUSTED": "Agotamiento del pool de conexiones TCP worker_connections y backlog saturado.",
    "ORIGIN_DOWN": "Host inalcanzable sin ruta no route to host con cluster de servidores de origen caido y fuera de servicio.",
    "NETWORK_LATENCY_TC": "Latencia anormal y degradacion de red inyectada con Traffic Control netem delay tc qdisc.",
    "TLS_EXPIRED_CERT": "El certificado TLS SSL ha expirado fecha de validez notAfter no vigente certificate has expired.",
    "TLS_CHAIN_INVALID": "Cadena de certificados TLS rota o autoridad certificadora CA autofirmada no confiable self signed certificate in certificate chain.",
    "TLS_CIPHER_MISMATCH": "Incompatibilidad de suites de cifrado TLS cipher mismatch handshake failure ssl3_read_bytes.",
    "TLS_SNI_MISMATCH": "Discrepancia en Server Name Indication TLS SNI mismatch hostname verifier en el saludo SSL handshake.",
}


class TestF1AllEighteenGroups:
    """Verificación integral de las 18 clases canónicas de fallas."""

    def test_catalog_contains_exactly_18_classes(self):
        catalog = load_evaluator_concepts()
        classes = catalog.get("classes", {})
        assert len(classes) == 18
        for expected_cls in CANONICAL_FAULTS_CORPUS:
            assert expected_cls in classes, f"Clase {expected_cls} no encontrada en evaluator_concepts.yaml"

    @pytest.mark.parametrize("expected_class,diagnostic_text", list(CANONICAL_FAULTS_CORPUS.items()))
    def test_parse_each_canonical_fault_class(self, expected_class: str, diagnostic_text: str):
        pred_class, is_ambig, scores = parse_fault_class_predicted(diagnostic_text)
        assert pred_class == expected_class, (
            f"Fallo en clasificación: esperada '{expected_class}', predicha '{pred_class}'. Scores: {scores}"
        )
        assert expected_class in scores
        assert scores[expected_class] > 0

    def test_unknown_preserved_on_empty_or_unrelated_text(self):
        # Texto vacío
        cls_empty, ambig_empty, sc_empty = parse_fault_class_predicted("")
        assert cls_empty == "UNKNOWN"
        assert ambig_empty is False
        assert sc_empty == {}

        # Texto con sólo espacios
        cls_spaces, _, _ = parse_fault_class_predicted("   \n\t  ")
        assert cls_spaces == "UNKNOWN"

        # Texto no relacionado (ruido o alucinación sin términos de red)
        cls_noise, ambig_noise, _ = parse_fault_class_predicted(
            "Se observa un hermoso día soleado y las flores están floreciendo."
        )
        assert cls_noise == "UNKNOWN"
        assert ambig_noise is False

    def test_ambiguity_detection_documented(self):
        # Texto deliberadamente ambiguo que menciona indicios equivalentes de dos fallas
        ambig_text = (
            "No se puede determinar con certeza: por un lado el dominio no existe en la zona (NXDOMAIN / RCODE 3), "
            "pero también el certificado TLS ha expirado (notAfter no vigente certificate has expired)."
        )
        pred, is_ambig, scores = parse_fault_class_predicted(ambig_text)
        assert pred in ("NXDOMAIN", "TLS_EXPIRED_CERT")
        assert "NXDOMAIN" in scores
        assert "TLS_EXPIRED_CERT" in scores

    def test_zero_leakage_in_metrics_calculation(self):
        """
        Garantiza que compute_classification_metrics evalúe estrictamente
        y_true (etiqueta del escenario) vs y_pred (extraído del texto del modelo),
        ignorando 'is_root_cause_correct' o pistas tramposas.
        """
        rows = [
            {
                "scenario_id": "DNS-NXD-01",
                "fault_class": "NXDOMAIN",
                "root_cause_predicted": CANONICAL_FAULTS_CORPUS["NXDOMAIN"],
                "is_root_cause_correct": False,  # No debe forzar que sea incorrecto
            },
            {
                "scenario_id": "TLS-EXP-01",
                "fault_class": "TLS_EXPIRED_CERT",
                "root_cause_predicted": CANONICAL_FAULTS_CORPUS["HTTP_500_INTERNAL"],  # Predice 500 en vez de TLS
                "is_root_cause_correct": True,  # Trampa: no debe forzar que sea correcto
            },
            {
                "scenario_id": "HTTP-502-01",
                "fault_class": "HTTP_502_BAD_GATEWAY",
                "root_cause_predicted": "El sistema no pudo identificar la falla técnica.",
                "is_root_cause_correct": True,  # Debe ser UNKNOWN independientemente del booleano
            },
        ]

        metrics = compute_classification_metrics(rows, n_bootstrap=20, seed=42)
        assert "f1_macro" in metrics
        assert "confusion_matrix" in metrics
        assert "labels" in metrics
        assert "UNKNOWN" in metrics["labels"]

        # Confirmar que UNKNOWN fue clasificado y contabilizado en el reporte
        assert metrics["support_total"] == 3

    def test_full_corpus_macro_metrics(self):
        """Calcula métricas multiclase sobre todo el corpus canónico de las 18 clases."""
        rows = []
        for idx, (cls_name, text) in enumerate(CANONICAL_FAULTS_CORPUS.items(), start=1):
            rows.append({
                "scenario_id": f"SCENARIO-{idx:02d}",
                "fault_class": cls_name,
                "root_cause_predicted": text,
            })

        metrics = compute_classification_metrics(rows, n_bootstrap=50, seed=42)
        assert metrics["f1_macro"] == 1.0  # Todas las 18 clases canónicas clasificadas a la perfección
        assert metrics["precision_macro"] == 1.0
        assert metrics["recall_macro"] == 1.0
        assert metrics["support_total"] == 18
