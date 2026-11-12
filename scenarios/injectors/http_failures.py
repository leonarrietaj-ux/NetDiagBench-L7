"""
NetDiagBench-L7: HTTP/TLS Failure Injector
Scripts de inyección de fallas HTTP/Web/Gateway/TLS para escenarios con Nginx.
Opera en modo simulado (sin contenedores reales) para reproducibilidad.
"""

import random
from typing import Any, Dict, List


class HTTPFailureInjector:
    """Inyector determinista de anomalías en servicios HTTP/Nginx."""

    INJECTION_PROFILES = {
        "HTTP_502_BAD_GATEWAY": {
            "action": "stop_backend_service",
            "description": "Detiene el proceso de backend (FastAPI/Gunicorn) para provocar 502",
            "nginx_config_change": "Backend upstream en 127.0.0.1:8080 queda inalcanzable",
            "expected_symptom": "connect() failed (111: Connection refused); respuesta 502",
        },
        "HTTP_504_GATEWAY_TIMEOUT": {
            "action": "inject_backend_latency",
            "description": "Inyecta retardo artificial de 65s en el backend con tc netem",
            "nginx_config_change": "proxy_read_timeout permanece en 60s (< retardo inyectado)",
            "expected_symptom": "upstream timed out (110: Connection timed out); respuesta 504",
        },
        "HTTP_500_INTERNAL": {
            "action": "inject_application_exception",
            "description": "Provoca una excepción KeyError no controlada en la ruta del backend",
            "nginx_config_change": "Ningún cambio en Nginx; fallo en código de aplicación",
            "expected_symptom": "500 Internal Server Error; traceback de KeyError en logs",
        },
        "TLS_EXPIRED_CERT": {
            "action": "install_expired_certificate",
            "description": "Reemplaza el certificado X.509 vigente por uno ya expirado",
            "nginx_config_change": "ssl_certificate apunta a cert con notAfter < fecha actual",
            "expected_symptom": "SSL handshake failed; verify error:num=10:certificate has expired",
        },
        "ORIGIN_DOWN": {
            "action": "shutdown_all_upstreams",
            "description": "Apaga todos los servidores del grupo upstream en Nginx",
            "nginx_config_change": "Ningún upstream saludable en el bloque upstream{}",
            "expected_symptom": "no live upstreams while connecting to upstream; respuesta 502",
        },
        "TLS_CHAIN_INVALID": {
            "action": "strip_intermediate_ca",
            "description": "Elimina el certificado intermedio del archivo bundle de certificados",
            "nginx_config_change": "ssl_certificate incluye solo el cert de servidor sin intermediarios",
            "expected_symptom": "SSL verify failed: unable to get local issuer certificate",
        },
        "CONNECTION_POOL_EXHAUSTED": {
            "action": "flood_keepalive_connections",
            "description": "Satura el límite de conexiones worker_connections hacia el backend",
            "nginx_config_change": "max_conns en upstream configurado en valor muy bajo (ej. 2)",
            "expected_symptom": "worker_connections are not enough; respuesta HTTP 503",
        },
        "NETWORK_LATENCY_TC": {
            "action": "inject_tc_netem_delay",
            "description": "Aplica regla de retardo qdisc netem de 2000ms con jitter 500ms en eth0",
            "nginx_config_change": "Sin cambio en Nginx; política de qdisc a nivel kernel Linux",
            "expected_symptom": "upstream timed out (110: Connection timed out); RTT > 2000ms",
        },
    }

    def prepare_injection(self, fault_class: str, seed: int = 42) -> Dict[str, Any]:
        """Prepara los parámetros de inyección de falla HTTP/TLS."""
        rng = random.Random(seed)
        profile = self.INJECTION_PROFILES.get(fault_class, {})
        return {
            "fault_class": fault_class,
            "profile": profile,
            "injection_delay_ms": rng.randint(50, 200),
            "recovery_timeout_s": rng.randint(30, 120),
            "injection_id": f"http-inj-{fault_class.lower()}-{seed}",
        }

    def generate_affected_logs(
        self, fault_class: str, seed: int = 42, count: int = 10
    ) -> List[Dict[str, str]]:
        """Genera los logs que Nginx/Backend produciría bajo la falla inyectada."""
        rng = random.Random(seed)
        logs = []

        for i in range(count):
            ts = f"2026-09-25 10:00:{i:02d}"
            if fault_class == "HTTP_502_BAD_GATEWAY":
                msg = f'[error] connect() failed (111: Connection refused) while connecting to upstream, client: 127.0.0.1, upstream: "http://127.0.0.1:8080/api/v1/users"'
            elif fault_class == "HTTP_504_GATEWAY_TIMEOUT":
                msg = f'[error] upstream timed out (110: Connection timed out) while reading response header from upstream'
            elif fault_class == "HTTP_500_INTERNAL":
                msg = f"[fastapi-backend] Unhandled Exception: KeyError: 'user_id' in /app/routes/checkout.py line 42"
            elif fault_class == "TLS_EXPIRED_CERT":
                msg = f"SSL_do_handshake() failed (SSL: error:0A000086:SSL routines::certificate verify failed:certificate has expired)"
            elif fault_class == "TLS_CHAIN_INVALID":
                msg = f"SSL_do_handshake() failed (SSL: error:0A000086:SSL routines::certificate verify failed:unable to get local issuer certificate)"
            elif fault_class == "CONNECTION_POOL_EXHAUSTED":
                msg = f'[error] 1024 worker_connections are not enough while connecting to upstream: "upstream-backend-api"'
            elif fault_class == "NETWORK_LATENCY_TC":
                msg = f'[warn] slow upstream response detected: connection latency 2450ms exceeding threshold'
            else:
                msg = f'[error] no live upstreams while connecting to upstream: "upstream-cluster"'
            logs.append({"timestamp": ts, "source_service": "nginx", "log_level": "ERROR", "raw_message": msg})

        return logs
