"""
NetDiagBench-L7: Layer 1 - Scenario Lab Runner
Gestiona el catálogo de escenarios de falla y la generación/ejecución
de trazas de red y registros de telemetría para DNS y HTTP/Web.
"""

import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from src.core.config import PROJECT_ROOT
from src.core.contracts import EscenarioLabContract, FaultClass, ServiceCategory
from src.core.logger import logger
from src.layer1_lab.docker_manager import (
    EMULATED_SCENARIOS,
    calculate_container_telemetry,
    check_container_active,
    fetch_container_logs,
    is_docker_available,
    restart_container,
    isolate_emulated_scenario,
    restore_emulated_containers,
    generate_scenario_traffic,
    wait_for_service_ready,
)


class ScenarioLabRunner:
    """Administra y ejecuta escenarios del catálogo de laboratorio."""

    def __init__(self, catalog_dir: Path | None = None):
        self.catalog_dir = catalog_dir or (PROJECT_ROOT / "scenarios" / "catalog")
        self._cache: dict[str, EscenarioLabContract] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Carga y valida todos los escenarios YAML en el catálogo."""
        if not self.catalog_dir.exists():
            logger.warning(f"Directorio de catálogo no encontrado: {self.catalog_dir}")
            return

        for yaml_path in self.catalog_dir.glob("**/*.yaml"):
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and "scenario_id" in data:
                    scenario = EscenarioLabContract(**data)
                    self._cache[scenario.scenario_id] = scenario
                    logger.debug(f"Escenario cargado: {scenario.scenario_id} ({scenario.category})")
            except Exception as e:
                logger.error(f"Error cargando escenario {yaml_path}: {e}")

    def list_scenarios(self) -> list[EscenarioLabContract]:
        """Devuelve la lista de todos los escenarios disponibles."""
        return list(self._cache.values())

    def get_scenario(self, scenario_id: str) -> EscenarioLabContract | None:
        """Busca un escenario por su identificador único."""
        return self._cache.get(scenario_id)

    def generate_synthetic_logs(
        self, scenario: EscenarioLabContract, seed: int = 42, count: int = 15
    ) -> list[dict[str, Any]]:
        """
        Genera una secuencia temporal determinista y realista de registros de log
        que refleja el comportamiento del servicio bajo la falla estipulada.
        """
        rng = random.Random(seed)
        base_time = datetime(2026, 9, 25, 10, 0, 0)
        logs: list[dict[str, Any]] = []

        target_fqdn = scenario.metadata.get("target_fqdn", "service.internal.corp")

        if scenario.category == ServiceCategory.DNS:
            service_name = "bind9"
            if scenario.fault_class == FaultClass.NXDOMAIN:
                patterns = [
                    ("INFO", "client 127.0.0.1#49152: query: resolver.internal IN A + (127.0.0.1)", "NOERROR"),
                    ("INFO", f"client 127.0.0.1#49153: query: {target_fqdn} IN A -E(0)K (127.0.0.1)", "NXDOMAIN"),
                    ("WARNING", f"client 127.0.0.1#49153: query failed (NXDOMAIN) for {target_fqdn}/IN/A: not found in zone", "NXDOMAIN"),
                    ("INFO", f"client 127.0.0.1#49154: query: {target_fqdn} IN AAAA -E(0)K (127.0.0.1)", "NXDOMAIN"),
                ]
            elif scenario.fault_class == FaultClass.SERVFAIL:
                patterns = [
                    ("INFO", f"client 127.0.0.1#51000: query: {target_fqdn} IN A + (127.0.0.1)", "QUERY"),
                    ("ERROR", f"connection timed out resolving {target_fqdn}/A/IN: 198.51.100.53#53", "TIMEOUT"),
                    ("ERROR", f"client 127.0.0.1#51000: query failed (SERVFAIL) for {target_fqdn}/IN/A: server failure", "SERVFAIL"),
                    ("WARNING", f"resolver: broken trust chain or authoritative server unreachable for {target_fqdn}", "SERVFAIL"),
                ]
            elif scenario.fault_class == FaultClass.DNS_REFUSED:
                patterns = [
                    ("INFO", f"client 127.0.0.1#53000: query: {target_fqdn} IN A + (127.0.0.1)", "QUERY"),
                    ("WARNING", f"client 127.0.0.1#53000: query failed (REFUSED) for {target_fqdn}/IN/A: query refused by ACL", "REFUSED"),
                    ("ERROR", f"client 127.0.0.1#53001: view internal: query '{target_fqdn}/A/IN' denied by access control list", "DENIED"),
                ]
            elif scenario.fault_class == FaultClass.DNS_TRUNCATED_EDNS:
                patterns = [
                    ("INFO", f"client 127.0.0.1#54000: query: {target_fqdn} IN ANY -E(0)K (127.0.0.1)", "QUERY"),
                    ("WARNING", "client 127.0.0.1#54000: response size 1480 exceeds UDP buffer limit 512, setting TC flag", "TRUNC"),
                    ("ERROR", "client 127.0.0.1#54000: client TCP retry connection timed out on port 53 (Connection timed out)", "TCP_FAIL"),
                ]
            else:  # DELEGATION_ERROR
                patterns = [
                    ("INFO", f"client 127.0.0.1#52000: query: {target_fqdn} IN NS + (127.0.0.1)", "QUERY"),
                    ("ERROR", f"lame server resolving '{target_fqdn}' (in 'corp.internal'?): 192.0.2.10#53", "LAME"),
                    ("ERROR", f"client 127.0.0.1#52000: query failed (SERVFAIL) for {target_fqdn}/IN/NS: lame server", "SERVFAIL"),
                ]

        elif scenario.category in (ServiceCategory.HTTP_WEB, ServiceCategory.API_GATEWAY):
            service_name = "nginx"
            if scenario.fault_class == FaultClass.HTTP_502_BAD_GATEWAY:
                patterns = [
                    ("INFO", '127.0.0.1 - - [GET /static/style.css HTTP/1.1] 200 4521 "-" "curl/8.4.0"', "200"),
                    ("ERROR", '[error] connect() failed (111: Connection refused) while connecting to upstream, client: 127.0.0.1, upstream: "http://127.0.0.1:8080/api/v1/users"', "502"),
                    ("WARNING", '127.0.0.1 - - [GET /api/v1/users HTTP/1.1] 502 157 "-" "curl/8.4.0"', "502"),
                    ("ERROR", '[error] connect() failed (111: Connection refused) while connecting to upstream, request: "GET /api/v1/users HTTP/1.1"', "502"),
                ]
            elif scenario.fault_class == FaultClass.HTTP_504_GATEWAY_TIMEOUT:
                patterns = [
                    ("INFO", '127.0.0.1 - - [GET /health HTTP/1.1] 200 15 "-" "curl/8.4.0"', "200"),
                    ("ERROR", '[error] upstream timed out (110: Connection timed out) while reading response header from upstream, client: 127.0.0.1, upstream: "http://127.0.0.1:8080/api/v1/reports"', "504"),
                    ("WARNING", '127.0.0.1 - - [GET /api/v1/reports HTTP/1.1] 504 167 "-" "curl/8.4.0"', "504"),
                ]
            elif scenario.fault_class == FaultClass.ORIGIN_DOWN:
                patterns = [
                    ("ERROR", '[error] connect() to 10.0.0.5:8080 failed (113: No route to host) while connecting to upstream', "502"),
                    ("ERROR", '[error] connect() to 10.0.0.5:8080 failed (113: No route to host) while connecting to upstream', "502"),
                    ("WARNING", '127.0.0.1 - - [GET /api/v1/health HTTP/1.1] 502 584 "-" "Mozilla/5.0"', "502"),
                ]
            elif scenario.fault_class == FaultClass.CONNECTION_POOL_EXHAUSTED:
                patterns = [
                    ("ERROR", '[error] 1024 worker_connections are not enough while connecting to upstream, client: 127.0.0.1, upstream: "http://127.0.0.1:8080/api/v1/users"', "503"),
                    ("WARNING", '127.0.0.1 - - [GET /api/v1/users HTTP/1.1] 503 194 "-" "curl/8.4.0"', "503"),
                    ("ERROR", '[alert] upstream connection limit exceeded, rejecting client request', "503"),
                ]
            elif scenario.fault_class == FaultClass.NETWORK_LATENCY_TC:
                patterns = [
                    ("WARNING", '[warn] slow network response detected: RTT exceeded 2000ms threshold for 127.0.0.1', "SLOW"),
                    ("ERROR", '[error] upstream timed out (110: Connection timed out) while reading response header from upstream, client: 127.0.0.1, upstream: "http://127.0.0.1:8080/api/v1/reports"', "504"),
                    ("INFO", '[warn] network RTT anomaly: observed latency 2150ms on upstream transport interface', "NETEM"),
                ]
            elif scenario.fault_class == FaultClass.HTTP_403_FORBIDDEN:
                patterns = [
                    ("WARNING", '127.0.0.1 - - [GET /admin/system/status HTTP/1.1] 403 162 "-" "curl/8.4.0"', "403"),
                    ("ERROR", '[error] access forbidden by rule, client: 127.0.0.1, server: api.corp.internal, request: "GET /admin/system/status HTTP/1.1"', "403"),
                    ("INFO", '[error] access forbidden by rule, client: 127.0.0.1, request: "GET /admin/system/status HTTP/1.1"', "WAF"),
                ]
            elif scenario.fault_class == FaultClass.HTTP_429_RATE_LIMITED:
                patterns = [
                    ("WARNING", '127.0.0.1 - - [GET /api/v1/search?q=telecom HTTP/1.1] 429 180 "-" "curl/8.4.0"', "429"),
                    ("ERROR", '[error] limiting requests, excess: 5.230 by zone "req_limit_per_ip", client: 127.0.0.1, server: api.corp.internal', "429"),
                    ("INFO", '127.0.0.1 - - [GET /api/v1/search?q=telecom HTTP/1.1] 429 180 "-" "curl/8.4.0"', "LIMIT"),
                ]
            elif scenario.fault_class == FaultClass.HTTP_503_SERVICE_UNAVAILABLE:
                patterns = [
                    ("WARNING", '127.0.0.1 - - [GET /api/v1/orders HTTP/1.1] 503 190 "-" "curl/8.4.0"', "503"),
                    ("ERROR", '[error] upstream temporarily unavailable: all 4 worker threads busy, queue full', "503"),
                    ("ERROR", '[alert] service upstream rejected request: server overloaded or in maintenance', "503"),
                ]
            else:  # HTTP_500_INTERNAL
                patterns = [
                    ("INFO", '127.0.0.1 - - [POST /api/v1/checkout HTTP/1.1] 500 240 "-" "curl/8.4.0"', "500"),
                    ("ERROR", '[fastapi-backend] Unhandled Exception: KeyError: \'user_id\' in /app/routes/checkout.py line 42', "500"),
                    ("ERROR", '[error] upstream sent 500 Internal Server Error, client: 127.0.0.1', "500"),
                ]
        else:  # TLS
            service_name = "nginx-ssl"
            if scenario.fault_class == FaultClass.TLS_CHAIN_INVALID:
                patterns = [
                    ("INFO", '127.0.0.1 TLSv1.3 / TLS_AES_256_GCM_SHA384 handshake started', "TLS"),
                    ("ERROR", 'SSL_do_handshake() failed (SSL: error:0A000086:SSL routines::certificate verify failed:unable to get local issuer certificate) while SSL handshaking', "TLS_CHAIN"),
                    ("ERROR", 'client 127.0.0.1 disconnected during TLS negotiation: certificate verification failed', "TLS_CHAIN"),
                ]
            elif scenario.fault_class == FaultClass.TLS_SNI_MISMATCH:
                patterns = [
                    ("INFO", '127.0.0.1 TLSv1.3 / TLS_AES_256_GCM_SHA384 handshake started for SNI: api-unregistered.corp.internal', "TLS"),
                    ("WARNING", '[warn] no matching SSL certificate for SNI host: api-unregistered.corp.internal, serving default certificate CN=default.corp.internal', "SNI_WARN"),
                    ("ERROR", 'client 127.0.0.1 disconnected during TLS handshake: certificate hostname mismatch (verify error:num=62)', "SNI_ERR"),
                ]
            elif scenario.fault_class == FaultClass.TLS_CIPHER_MISMATCH:
                patterns = [
                    ("INFO", '127.0.0.1 TLS client hello offered suites: [TLS_RSA_WITH_AES_128_CBC_SHA]', "TLS"),
                    ("ERROR", 'SSL_do_handshake() failed (SSL: error:0A000410:SSL routines::sslv3 alert handshake failure) while SSL handshaking', "CIPHER_ERR"),
                    ("ERROR", 'client 127.0.0.1 disconnected: no shared cipher supported between client and server', "CIPHER_ERR"),
                ]
            else:  # TLS_EXPIRED_CERT
                patterns = [
                    ("INFO", '127.0.0.1 TLSv1.3 / TLS_AES_256_GCM_SHA384 handshake started', "TLS"),
                    ("ERROR", 'SSL_do_handshake() failed (SSL: error:0A000086:SSL routines::certificate verify failed:certificate has expired) while SSL handshaking', "TLS_EXP"),
                    ("ERROR", 'client 127.0.0.1 disconnected during TLS negotiation: certificate expired', "TLS_EXP"),
                ]

        for i in range(count):
            delta_seconds = rng.randint(i * 2, (i + 1) * 3)
            current_time = base_time + timedelta(seconds=delta_seconds)
            time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

            lvl, msg, code = rng.choice(patterns)
            logs.append({
                "timestamp": time_str,
                "source_service": service_name,
                "log_level": lvl,
                "raw_message": msg,
                "code": code
            })

        return logs

    def generate_synthetic_telemetry(
        self, scenario: EscenarioLabContract, seed: int = 42
    ) -> dict[str, Any]:
        """Genera métricas de resumen de telemetría de red deterministas."""
        rng = random.Random(seed)
        if scenario.fault_class in (FaultClass.HTTP_504_GATEWAY_TIMEOUT, FaultClass.NETWORK_LATENCY_TC, FaultClass.DNS_TRUNCATED_EDNS):
            p50 = rng.uniform(1500.0, 3000.0)
            p95 = rng.uniform(45000.0, 62000.0)
            error_rate = rng.uniform(85.0, 100.0)
        elif scenario.fault_class in (FaultClass.CONNECTION_POOL_EXHAUSTED, FaultClass.HTTP_503_SERVICE_UNAVAILABLE):
            p50 = rng.uniform(150.0, 800.0)
            p95 = rng.uniform(3000.0, 8000.0)
            error_rate = rng.uniform(75.0, 95.0)
        elif scenario.fault_class in (FaultClass.NXDOMAIN, FaultClass.SERVFAIL, FaultClass.HTTP_502_BAD_GATEWAY, FaultClass.DNS_REFUSED, FaultClass.HTTP_403_FORBIDDEN, FaultClass.HTTP_429_RATE_LIMITED):
            p50 = rng.uniform(2.5, 15.0)
            p95 = rng.uniform(25.0, 65.0)
            error_rate = rng.uniform(90.0, 100.0)
        else:
            p50 = rng.uniform(5.0, 30.0)
            p95 = rng.uniform(40.0, 120.0)
            error_rate = rng.uniform(70.0, 95.0)

        return {
            "error_rate_pct": round(error_rate, 2),
            "p50_latency_ms": round(p50, 2),
            "p95_latency_ms": round(p95, 2),
            "sample_count": rng.randint(40, 120)
        }

    def execute_scenario(
        self, scenario_id: str, seed: int = 42, execution_mode: str = "sintetico_determinista"
    ) -> tuple[EscenarioLabContract, list[dict[str, Any]], dict[str, Any]]:
        """
        Ejecuta el escenario de laboratorio devolviendo el contrato, los logs crudos
        y la telemetría asociada. En modo 'emulado', los logs provienen directamente del
        contenedor Docker real y la corrida se aborta explícitamente si el contenedor no está activo.
        """
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Escenario {scenario_id} no encontrado en catálogo")

        if execution_mode == "emulado":
            container_meta = EMULATED_SCENARIOS.get(scenario_id)
            if not container_meta:
                raise ValueError(
                    f"Escenario '{scenario_id}' está configurado como 'emulado' pero no tiene contenedor asignado."
                )

            c_name = container_meta["container_name"]
            if not is_docker_available():
                raise RuntimeError(
                    f"Abortando corrida emulada de '{scenario_id}': El motor Docker no está disponible en el host."
                )

            if not check_container_active(c_name):
                raise RuntimeError(
                    f"Abortando corrida emulada de '{scenario_id}': El contenedor '{c_name}' no está activo o no responde."
                )

            # Aislar escenario emulado (detener los otros dos para evitar crosstalk)
            isolate_emulated_scenario(scenario_id)
            try:
                # 1. Reiniciar contenedor antes de cada corrida para asegurar estado basal limpio
                restart_container(c_name, wait_seconds=1.0)

                # 2. Esperar deterministamente a que el servicio responda
                if not wait_for_service_ready(scenario_id, timeout=10.0):
                    logger.warning(f"Servicio '{scenario_id}' no respondió al sondeo de preparación post-reinicio.")

                # Pausa para asegurar que los logs de las sondas de preparación queden asentados antes de t0
                time.sleep(0.5)

                # 3. Registrar t0 exacto post-reinicio y servicio listo (estrictamente después de sondeo)
                t0 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                # 4. Generar tráfico de la falla (8 solicitudes desde cliente fuera del contenedor)
                generate_scenario_traffic(scenario_id)

                # 5. Esperar 2 s para vaciado de buffers de logs del daemon
                time.sleep(2.0)

                # 6. Extraer logs reales posteriores a t0 (filtrando líneas de arranque)
                logs = fetch_container_logs(c_name, since_ts=t0)

                # 7. Validar presencia del síntoma en la ventana filtrada
                raw_all = " ".join(e.get("raw_message", "") for e in logs).lower()
                if scenario_id == "DNS-SRV-01" and not any(k in raw_all for k in ("timed out", "servfail", "partner")):
                    logger.warning(f"Ventana de logs de {scenario_id} no contiene trazas de SERVFAIL/timed out.")
                elif scenario_id == "HTTP-502-01" and "111: connection refused" not in raw_all and "502" not in raw_all:
                    logger.warning(f"Ventana de logs de {scenario_id} no contiene trazas de conexión rechazada.")
                elif scenario_id == "TLS-EXP-01" and not any(k in raw_all for k in ("closed", "client", "200")):
                    logger.warning(f"Ventana de logs de {scenario_id} no contiene trazas de conexión de handshake.")

                telemetry = calculate_container_telemetry(logs, scenario_id)
                return scenario, logs, telemetry
            finally:
                # Reanudar contenedores emulados para mantener el cluster disponible
                restore_emulated_containers()

        # Modo 'sintetico_determinista' (simulador calibrado)
        logs = self.generate_synthetic_logs(scenario, seed=seed)
        telemetry = self.generate_synthetic_telemetry(scenario, seed=seed)
        return scenario, logs, telemetry
