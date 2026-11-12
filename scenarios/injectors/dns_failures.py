"""
NetDiagBench-L7: DNS Failure Injector
Scripts de inyección de fallas DNS para escenarios de laboratorio con BIND9.
Opera en modo simulado (sin contenedores reales) para reproducibilidad.
"""

import random
from typing import Any, Dict, List


class DNSFailureInjector:
    """Inyector determinista de anomalías en servicio DNS BIND9."""

    INJECTION_PROFILES = {
        "NXDOMAIN": {
            "action": "remove_zone_record",
            "description": "Elimina registro A/AAAA del archivo de zona para provocar RCODE 3",
            "bind9_config_change": "Comentar línea de registro A en /etc/bind/zones/db.internal.corp",
            "expected_symptom": "Consultas devuelven NXDOMAIN; SOA en Authority Section",
        },
        "SERVFAIL": {
            "action": "block_upstream_port53",
            "description": "Bloquea puerto 53 del servidor autoritativo remoto con iptables",
            "bind9_config_change": "iptables -A OUTPUT -p udp --dport 53 -d 198.51.100.53 -j DROP",
            "expected_symptom": "Timeout en resolución recursiva; SERVFAIL emitido al cliente",
        },
        "DELEGATION_ERROR": {
            "action": "corrupt_ns_records",
            "description": "Apunta registros NS a un servidor que no administra la zona",
            "bind9_config_change": "Modificar NS glue records hacia IP de un servidor lame",
            "expected_symptom": "Lame delegation detectada; SERVFAIL o REFUSED en respuesta",
        },
    }

    def prepare_injection(self, fault_class: str, seed: int = 42) -> Dict[str, Any]:
        """Prepara los parámetros de inyección de falla DNS."""
        rng = random.Random(seed)
        profile = self.INJECTION_PROFILES.get(fault_class, {})
        return {
            "fault_class": fault_class,
            "profile": profile,
            "injection_delay_ms": rng.randint(50, 200),
            "recovery_timeout_s": rng.randint(30, 120),
            "injection_id": f"dns-inj-{fault_class.lower()}-{seed}",
        }

    def generate_affected_logs(
        self, fault_class: str, seed: int = 42, count: int = 10
    ) -> List[Dict[str, str]]:
        """Genera los logs que BIND9 produciría bajo la falla inyectada."""
        rng = random.Random(seed)
        logs = []
        fqdn = "app.internal.corp"

        for i in range(count):
            ts = f"2026-09-25 10:00:{i:02d}"
            if fault_class == "NXDOMAIN":
                msg = f"client 127.0.0.1#{rng.randint(40000, 60000)}: query failed (NXDOMAIN) for {fqdn}/IN/A"
            elif fault_class == "SERVFAIL":
                msg = f"connection timed out resolving '{fqdn}'/A/IN: 198.51.100.53#53"
            else:
                msg = f"lame server resolving '{fqdn}' (in 'corp.internal'?): 192.0.2.10#53"
            logs.append({"timestamp": ts, "source_service": "bind9", "log_level": "ERROR", "raw_message": msg})

        return logs
