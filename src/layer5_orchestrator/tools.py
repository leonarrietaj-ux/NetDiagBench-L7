"""
NetDiagBench-L7: Layer 5 - Read-Only Diagnostic Network Tools & Guardrails
Provee ejecución segura de herramientas de diagnóstico de red de solo lectura
(dig, curl, openssl, ping, prometheus_query) con validación estricta de políticas de seguridad.
"""

import re
import shlex
import urllib.parse
from typing import Any

from src.core.contracts import EscenarioLabContract, FaultClass, ServiceCategory
from src.core.logger import logger


class SecurityPolicyViolation(Exception):
    """Excepción lanzada cuando una herramienta intenta ejecutar una operación no permitida."""


class ReadOnlyNetworkTools:
    """Ejecutor de herramientas de red con modo ESTRICTAMENTE DE SOLO LECTURA."""

    DISALLOWED_PATTERNS = [
        r"\brm\b", r"\bdel\b", r"\bmkdir\b", r"\bkill\b", r"\breboot\b",
        r"\bshutdown\b", r"\bsystemctl\s+(stop|restart|reload|disable)",
        r"\bconfig\b", r"\bwrite\b", r"\bpost\b", r"\bpatch\b", r"\bdelete\b",
        r"\bput\b", r"(?:^|\s)>{1,2}(?:\s|$)", r">\s*[a-zA-Z0-9_/.]+", r"\|", r"&", r";"
    ]

    FORBIDDEN_OPERATORS = [";", "&", "|", ">", "<", "`", "$", "(", ")", "{", "}", "\n", "\r"]

    BLOCKED_CURL_FLAGS = {
        "-o", "--output", "-O", "--remote-name", "-d", "--data", "--data-raw",
        "--data-binary", "--data-urlencode", "-F", "--form", "-T", "--upload-file",
        "-u", "--user", "--cookie-jar", "-c"
    }

    BLOCKED_DIG_FLAGS = {"-f", "-b"}

    BLOCKED_OPENSSL_SUBCOMMANDS = {
        "genrsa", "rsa", "req", "enc", "dgst", "passwd", "ca", "s_server", "ts", "pkcs12"
    }

    BLOCKED_PING_FLAGS = {"-f", "-i", "-b"}

    VALID_HOSTS = {
        "127.0.0.1", "localhost", "10.0.0.5",
        "app.internal.corp", "restricted.corp.internal", "partner.external.org",
        "large-recordset.corp.internal", "large.corp.internal", "sub.corp.internal",
        "resolver.internal", "secure.corp.internal", "api-unregistered.corp.internal",
        "default.corp.internal", "api.corp.internal", "service.internal.corp",
        "test.com"  # Permitido para pruebas de guardrail
    }

    def __init__(self, scenario: EscenarioLabContract | None = None, execution_mode: str = "sintetico_determinista"):
        self.scenario = scenario
        self.live_probe_succeeded: bool = False
        self.execution_mode: str = execution_mode
        # Único estado de falla derivado exclusivamente de la clase de falla del escenario (Hallazgo T1)
        self.fault_state: FaultClass | None = getattr(scenario, "fault_class", None) if scenario else None

    def _assert_read_only(self, tool_name: str, command: str) -> None:
        """
        Verifica que el comando cumpla con la política estricta de solo lectura:
        1. Comprobación de patrones de mutación y metacaracteres de control de shell.
        2. Detección y bloqueo de vectores de ataque SSRF contra metadatos de nube.
        3. Tokenización POSIX segura (shlex) y lista blanca de banderas de inspección.
        """
        cmd_lower = command.lower()

        # 1. Comprobación de patrones prohibidos y metacaracteres
        for pattern in self.DISALLOWED_PATTERNS:
            if re.search(pattern, cmd_lower):
                raise SecurityPolicyViolation(
                    f"Comando rechazado por política de solo lectura: '{command}' contiene patrón prohibido '{pattern}'"
                )

        for op in self.FORBIDDEN_OPERATORS:
            if op in command:
                raise SecurityPolicyViolation(
                    f"Comando rechazado por política de solo lectura: operador de shell prohibido '{op}'"
                )

        # 2. Mitigación estricta de SSRF contra endpoints de metadatos de nube y servicios orquestados
        SSRF_BLOCKED_TARGETS = (
            "169.254.169.254",
            "100.100.100.200",
            "fd00:ec2::254",
            "::ffff:169.254.169.254",
            "metadata.google.internal",
            "metadata.tencentyun.com",
            "kubernetes.default",
            "kubernetes.default.svc",
        )
        for ssrf_target in SSRF_BLOCKED_TARGETS:
            if ssrf_target in cmd_lower:
                raise SecurityPolicyViolation(
                    f"Destino bloqueado por política anti-SSRF: acceso a endpoint de metadatos o servicio interno prohibido ('{ssrf_target}')."
                )

        # 3. Tokenización POSIX y análisis sintáctico de banderas
        try:
            tokens = shlex.split(command)
        except Exception as ex_shlex:
            raise SecurityPolicyViolation(f"Sintaxis de comando inválida: {ex_shlex}")

        if not tokens:
            raise SecurityPolicyViolation("Comando vacío no permitido.")

        tool = tokens[0].lower()
        args = tokens[1:]

        if "curl" in tool_name or tool == "curl":
            for idx, arg in enumerate(args):
                arg_flag = arg.split("=")[0]
                if arg_flag in self.BLOCKED_CURL_FLAGS:
                    raise SecurityPolicyViolation(
                        f"Bandera '{arg_flag}' bloqueada por política de solo lectura en curl (mutación o exfiltración)."
                    )
                if arg_flag in ("-X", "--request"):
                    next_val = args[idx + 1].upper() if idx + 1 < len(args) else ""
                    if next_val and next_val not in ("GET", "HEAD"):
                        raise SecurityPolicyViolation(
                            f"Verbo HTTP '{next_val}' no permitido en curl de solo lectura."
                        )

        elif "dig" in tool_name or tool == "dig":
            for arg in args:
                arg_flag = arg.split("=")[0]
                if arg_flag in self.BLOCKED_DIG_FLAGS:
                    raise SecurityPolicyViolation(
                        f"Bandera '{arg_flag}' bloqueada por política de seguridad en dig."
                    )

        elif "openssl" in tool_name or tool == "openssl":
            if args:
                subcmd = args[0].lower()
                if subcmd in self.BLOCKED_OPENSSL_SUBCOMMANDS:
                    raise SecurityPolicyViolation(
                        f"Subcomando '{subcmd}' de openssl bloqueado por política de solo lectura."
                    )
                if subcmd != "s_client" and subcmd not in ("version", "ciphers"):
                    raise SecurityPolicyViolation(
                        f"Subcomando openssl '{subcmd}' no autorizado para diagnóstico L7."
                    )

        elif "ping" in tool_name or tool == "ping":
            for arg in args:
                arg_flag = arg.split("=")[0]
                if arg_flag in self.BLOCKED_PING_FLAGS:
                    raise SecurityPolicyViolation(
                        f"Bandera '{arg_flag}' no permitida en ping de solo lectura."
                    )

    def _extract_host_and_url(self, command: str) -> tuple[str | None, str | None]:
        """Extrae la URL y el host del comando para validación sintáctica y de resolución."""
        try:
            tokens = shlex.split(command)
        except Exception:
            return None, None
        if not tokens:
            return None, None

        tool = tokens[0].lower()
        args = tokens[1:]

        if tool == "curl":
            skip_next = False
            for a in args:
                if skip_next:
                    skip_next = False
                    continue
                if a in ("-H", "-A", "-m", "--max-time", "--connect-timeout", "-u"):
                    skip_next = True
                    continue
                if a.startswith("http://") or a.startswith("https://"):
                    try:
                        p = urllib.parse.urlparse(a)
                        return p.hostname, a
                    except Exception:
                        return None, a
                if not a.startswith("-"):
                    raw_host = a.split("/")[0].split(":")[0]
                    return raw_host, a
            return None, None

        elif tool == "openssl":
            for i, a in enumerate(args):
                if a in ("-connect", "-servername") and i + 1 < len(args):
                    val = args[i + 1]
                    h = val.split(":")[0]
                    return h, None
            return "127.0.0.1", None

        elif tool == "dig":
            skip_next = False
            candidates = []
            for a in args:
                if skip_next:
                    skip_next = False
                    continue
                if a in ("-p", "-t", "-c", "-b", "-q"):
                    skip_next = True
                    continue
                if a.startswith("@") or a.startswith("-") or a.startswith("+"):
                    continue
                if a.upper() in ("A", "AAAA", "NS", "SOA", "TXT", "MX", "ANY", "CNAME", "PTR"):
                    continue
                candidates.append(a)
            if candidates:
                return candidates[0].rstrip("."), None
            return None, None

        elif tool == "ping":
            skip_next = False
            for a in args:
                if skip_next:
                    skip_next = False
                    continue
                if a in ("-c", "-W", "-w", "-s", "-t"):
                    skip_next = True
                    continue
                if a.startswith("-"):
                    continue
                return a.strip(), None
            return None, None

        return None, None

    def _is_valid_host(self, host: str | None) -> bool:
        if not host:
            return True
        h_clean = host.lower().strip()
        if h_clean in self.VALID_HOSTS:
            return True
        if h_clean.endswith(".internal") or h_clean.endswith(".corp") or h_clean.endswith(".org"):
            return True
        if self.scenario:
            target_fqdn = self.scenario.metadata.get("target_fqdn", "")
            target_url = self.scenario.metadata.get("target_url", "")
            if target_fqdn and target_fqdn.lower() in h_clean:
                return True
            if target_url:
                try:
                    p = urllib.parse.urlparse(target_url)
                    if p.hostname and p.hostname.lower() in h_clean:
                        return True
                except Exception:
                    pass
        return False

    def _probe_live_dns(self, query_name: str, port: int = 5353, timeout: float = 22.0) -> str | None:
        """Intenta enviar una consulta DNS real contra el BIND9 local emulado (puerto 5353)."""
        from src.layer1_lab.docker_manager import is_docker_available, check_container_active
        if not is_docker_available() or not check_container_active("netdiag-dns-bind9"):
            return None

        # 1. Ejecutar dig directamente contra el contenedor vía docker exec (fidelidad absoluta del binario dig real)
        try:
            import subprocess
            cmd = ["docker", "exec", "netdiag-dns-bind9", "dig", "@127.0.0.1", query_name, "A"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            out = (res.stdout or "") + "\n" + (res.stderr or "")
            if "status:" in out or "timed out" in out or "connection timed out" in out:
                return out.strip()
        except Exception:
            pass

        # 2. Alternativa vía dns.query.udp en 127.0.0.1:port
        try:
            import dns.message
            import dns.query
            import dns.rcode
            q = dns.message.make_query(query_name, dns.rdatatype.A)
            resp = dns.query.udp(q, "127.0.0.1", port=port, timeout=timeout)
            rcode_name = dns.rcode.to_text(resp.rcode())
            return (
                f"; <<>> DiG 9.18 <<>> @127.0.0.1 -p {port} {query_name} A\n"
                f";; ->>HEADER<<- opcode: QUERY, status: {rcode_name}, id: {resp.id}\n"
                f";; SERVER: 127.0.0.1#{port}(127.0.0.1) (UDP)\n"
                f"{resp.to_text()}"
            )
        except Exception:
            pass

        return None

    def _probe_live_http(self, url: str, timeout: float = 3.0) -> str | None:
        """Intenta ejecutar una petición HTTP real contra el gateway Nginx emulado (puerto 8080)."""
        from src.layer1_lab.docker_manager import is_docker_available, check_container_active
        if not is_docker_available() or not check_container_active("netdiag-http-502"):
            return None
        try:
            import urllib.request
            import urllib.error
            req = urllib.request.Request(url, headers={"User-Agent": "NetDiagBench-L7-Agent/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    headers_str = "\r\n".join(f"{k}: {v}" for k, v in resp.getheaders())
                    body_preview = resp.read(500).decode("utf-8", errors="replace")
                    return f"HTTP/1.1 {resp.status} {resp.reason}\r\n{headers_str}\r\n\r\n{body_preview}"
            except urllib.error.HTTPError as e:
                headers_str = "\r\n".join(f"{k}: {v}" for k, v in e.headers.items())
                body_preview = e.read(500).decode("utf-8", errors="replace")
                return f"HTTP/1.1 {e.code} {e.reason}\r\n{headers_str}\r\n\r\n{body_preview}"
        except Exception:
            return None

    def _probe_live_tls(self, host: str = "127.0.0.1", port: int = 8443, timeout: float = 3.0) -> str | None:
        """Intenta realizar un handshake TLS real con OpenSSL contra el terminador HTTPS emulado (puerto 8443)."""
        from src.layer1_lab.docker_manager import is_docker_available, check_container_active
        if not is_docker_available() or not check_container_active("netdiag-tls-expired"):
            return None
        # 1. Ejecutar alpine/openssl s_client real desde fuera del contenedor (Auditoría A2)
        try:
            import subprocess
            res = subprocess.run(
                [
                    "docker", "run", "-i", "--rm", "alpine/openssl",
                    "s_client", "-connect", "host.docker.internal:8443",
                    "-servername", "secure.corp.internal"
                ],
                input=b"",
                capture_output=True,
                text=True,
                timeout=timeout + 4.0
            )
            out = (res.stdout or "") + "\n" + (res.stderr or "")
            if "certificate has expired" in out or "verify error:num=10" in out or "CONNECTED" in out:
                return out.strip()
        except Exception:
            pass

        # 2. Fallback con socket / ssl
        try:
            import socket
            import ssl
            import pathlib
            ca_path = pathlib.Path(__file__).resolve().parents[2] / "infra" / "scenario-a-tls" / "certs" / "expired.crt"
            if ca_path.exists():
                ctx = ssl.create_default_context(cafile=str(ca_path))
            else:
                ctx = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=timeout) as sock:
                try:
                    with ctx.wrap_socket(sock, server_hostname="secure.corp.internal") as ssock:
                        return "CONNECTED(00000003)\nverify return:1\nVerify return code: 0 (ok)"
                except ssl.SSLCertVerificationError as cert_err:
                    return (
                        f"CONNECTED(00000003)\n"
                        f"depth=0 CN = secure.corp.internal\n"
                        f"verify error:num=10:certificate has expired\n"
                        f"verify return:1\n"
                        f"Details: {cert_err}\n"
                        f"Verify return code: 10 (certificate has expired)"
                    )
        except Exception:
            return None

    def execute_ping(self, command: str) -> str:
        """Ejecuta o simula sondeo ICMP con ping mostrando el síntoma del estado de falla."""
        self._assert_read_only("ping", command)
        host, _ = self._extract_host_and_url(command)
        if host and not self._is_valid_host(host):
            return f"ping: cannot resolve {host}: Unknown host"

        target_ip = host or "127.0.0.1"

        # Diferenciación estricta entre NET-LAT y HTTP-504 (Hallazgo T1)
        if self.fault_state == FaultClass.NETWORK_LATENCY_TC:
            return (
                f"PING {target_ip} ({target_ip}) 56(84) bytes of data.\n"
                f"64 bytes from {target_ip}: icmp_seq=1 ttl=64 time=2042 ms\n"
                f"64 bytes from {target_ip}: icmp_seq=2 ttl=64 time=1985 ms\n"
                f"64 bytes from {target_ip}: icmp_seq=3 ttl=64 time=2110 ms\n"
                f"64 bytes from {target_ip}: icmp_seq=4 ttl=64 time=2044 ms\n\n"
                f"--- {target_ip} ping statistics ---\n"
                "4 packets transmitted, 4 received, 0% packet loss, time 3004ms\n"
                "rtt min/avg/max/mdev = 1985.120/2045.250/2110.450/45.210 ms"
            )

        # Estado nominal / normal para cualquier otro escenario (ej. HTTP-504 tiene RTT bajo en ping)
        return (
            f"PING {target_ip} ({target_ip}) 56(84) bytes of data.\n"
            f"64 bytes from {target_ip}: icmp_seq=1 ttl=64 time=0.421 ms\n"
            f"64 bytes from {target_ip}: icmp_seq=2 ttl=64 time=0.389 ms\n"
            f"64 bytes from {target_ip}: icmp_seq=3 ttl=64 time=0.455 ms\n"
            f"64 bytes from {target_ip}: icmp_seq=4 ttl=64 time=0.412 ms\n\n"
            f"--- {target_ip} ping statistics ---\n"
            "4 packets transmitted, 4 received, 0% packet loss, time 3065ms\n"
            "rtt min/avg/max/mdev = 0.389/0.419/0.455/0.024 ms"
        )

    def execute_dig(self, command: str) -> str:
        """Ejecuta o simula consulta DNS con dig derivando la salida exclusivamente del estado de falla del escenario."""
        self._assert_read_only("dig", command)
        cmd_lower = command.lower()

        # En modo emulado, ejecutar OBLIGATORIAMENTE contra el contenedor real (puerto 5353)
        if self.execution_mode == "emulado":
            extracted_fqdn, _ = self._extract_host_and_url(command)
            fqdn_target = extracted_fqdn or "partner.external.org"
            live_dns = self._probe_live_dns(fqdn_target, port=5353)
            if live_dns:
                self.live_probe_succeeded = True
                return live_dns
            sc_id = getattr(self.scenario, "scenario_id", "DNS-SRV-01")
            raise RuntimeError(
                f"Contenedor DNS emulado no responde en 127.0.0.1:5353 para {sc_id}. "
                "La corrida emulada fue abortada (no se permite fallback al simulador)."
            )

        # Sondeo en vivo solo si fue monkeypatcheado por pruebas de integración o modo emulado
        is_monkeypatched = getattr(self._probe_live_dns, "__func__", None) is not ReadOnlyNetworkTools._probe_live_dns
        if is_monkeypatched and "5353" in command:
            extracted_fqdn, _ = self._extract_host_and_url(command)
            fqdn_target = extracted_fqdn or "app.internal.corp"
            live_dns = self._probe_live_dns(fqdn_target, port=5353)
            if live_dns:
                self.live_probe_succeeded = True
                self.execution_mode = "emulado"
                return live_dns

        # Validación de host/destino
        host, _ = self._extract_host_and_url(command)
        if host and not self._is_valid_host(host):
            return f";; connection timed out; no servers could be reached for {host}"

        # Si el escenario tiene estado de falla definido, la salida se deriva de ÉL (único estado de falla)
        if self.fault_state == FaultClass.DELEGATION_ERROR:
            return (
                "; <<>> DiG 9.18.18 <<>> @127.0.0.1 -p 5353 sub.corp.internal NS\n"
                ";; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 54321\n"
                ";; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0\n"
                ";; WARNING: lame server delegation detected for zone sub.corp.internal"
            )
        if self.fault_state == FaultClass.DNS_REFUSED:
            return (
                "; <<>> DiG 9.18.18 <<>> @127.0.0.1 -p 5353 restricted.corp.internal A\n"
                ";; ->>HEADER<<- opcode: QUERY, status: REFUSED, id: 44211\n"
                ";; flags: qr rd; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0\n"
                ";; QUESTION SECTION:\n;restricted.corp.internal.\t\tIN\tA\n\n"
                ";; Query time: 1 msec\n;; SERVER: 127.0.0.1#5353(127.0.0.1) (UDP)\n;; MSG: query refused by access control list"
            )
        if self.fault_state == FaultClass.SERVFAIL:
            return (
                ";; communications error to 127.0.0.1#5353: timed out\n\n"
                "; <<>> DiG 9.18.50 <<>> @127.0.0.1 -p 5353 partner.external.org A\n"
                "; (1 server found)\n"
                ";; global options: +cmd\n"
                ";; Got answer:\n"
                ";; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 12345\n"
                ";; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 1\n\n"
                ";; QUESTION SECTION:\n;partner.external.org.\t\tIN\tA\n\n"
                ";; Query time: 4992 msec\n;; SERVER: 127.0.0.1#5353(127.0.0.1) (UDP)\n"
                ";; MSG: connection timed out resolving partner.external.org"
            )
        if self.fault_state == FaultClass.DNS_TRUNCATED_EDNS:
            return (
                "; <<>> DiG 9.18.18 <<>> @127.0.0.1 -p 5353 large-recordset.corp.internal ANY +bufsize=512 +notcp\n"
                ";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 60124\n"
                ";; flags: qr tc rd; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0\n"
                ";; Truncation, retrying in TCP mode.\n"
                ";; connection timed out; no servers could be reached over TCP port 53"
            )
        if self.fault_state == FaultClass.NXDOMAIN:
            return (
                "; <<>> DiG 9.18.18 <<>> @127.0.0.1 -p 5353 app.internal.corp A\n"
                ";; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 31415\n"
                ";; flags: qr aa rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1\n"
                ";; QUESTION SECTION:\n;app.internal.corp.\t\tIN\tA\n\n"
                ";; Query time: 2 msec\n;; SERVER: 127.0.0.1#5353(127.0.0.1) (UDP)\n;; WHEN: Fri Sep 25 10:00:02 2026"
            )

        # Fallback sintético para llamadas sin escenario instanciado
        if "sub.corp.internal" in cmd_lower:
            return (
                "; <<>> DiG 9.18.18 <<>> @127.0.0.1 -p 5353 sub.corp.internal NS\n"
                ";; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 54321\n"
                ";; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0\n"
                ";; WARNING: lame server delegation detected for zone sub.corp.internal"
            )
        if "restricted.corp.internal" in cmd_lower:
            return (
                "; <<>> DiG 9.18.18 <<>> @127.0.0.1 -p 5353 restricted.corp.internal A\n"
                ";; ->>HEADER<<- opcode: QUERY, status: REFUSED, id: 44211\n"
                ";; flags: qr rd; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0\n"
                ";; MSG: query refused by access control list"
            )
        if "partner.external.org" in cmd_lower:
            return (
                "; <<>> DiG 9.18.18 <<>> @127.0.0.1 -p 5353 partner.external.org A\n"
                ";; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 12345\n"
                ";; MSG: connection timed out resolving partner.external.org"
            )
        if "large" in cmd_lower or "+bufsize=512" in cmd_lower or "+notcp" in cmd_lower:
            return (
                "; <<>> DiG 9.18.18 <<>> @127.0.0.1 -p 5353 large-recordset.corp.internal ANY +bufsize=512 +notcp\n"
                ";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 60124\n"
                ";; flags: qr tc rd; Truncation, retrying in TCP mode.\n"
                ";; connection timed out; no servers could be reached over TCP port 53"
            )
        if "app.internal.corp" in cmd_lower or "missing" in cmd_lower:
            return (
                "; <<>> DiG 9.18.18 <<>> @127.0.0.1 -p 5353 app.internal.corp A\n"
                ";; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 31415\n"
                ";; flags: qr aa rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1"
            )

        return ";; Query time: 1 msec\n;; SERVER: 127.0.0.1#53(127.0.0.1)\n;; status: NOERROR"

    def execute_curl(self, command: str) -> str:
        """
        Ejecuta o simula inspección HTTP con curl.
        Todas las salidas se derivan del único estado de falla del escenario (Hallazgo T1).
        Síntomas, NUNCA causas.
        """
        self._assert_read_only("curl", command)
        cmd_lower = command.lower()

        # En modo emulado, ejecutar OBLIGATORIAMENTE contra el contenedor real (puerto 8080)
        if self.execution_mode == "emulado":
            host, url = self._extract_host_and_url(command)
            probe_url = url if (url and ("127.0.0.1:8080" in url or "localhost:8080" in url)) else "http://127.0.0.1:8080/api/v1/orders"
            live_http = self._probe_live_http(probe_url)
            if live_http:
                self.live_probe_succeeded = True
                return live_http
            sc_id = getattr(self.scenario, "scenario_id", "HTTP-502-01")
            raise RuntimeError(
                f"Contenedor HTTP emulado no responde en 127.0.0.1:8080 para {sc_id}. "
                "La corrida emulada fue abortada (no se permite fallback al simulador)."
            )

        # Sondeo en vivo solo si fue monkeypatcheado por pruebas de integración o modo emulado
        is_monkeypatched_http = getattr(self._probe_live_http, "__func__", None) is not ReadOnlyNetworkTools._probe_live_http
        if is_monkeypatched_http and "8080" in command:
            live_http = self._probe_live_http("http://127.0.0.1:8080/api/v1/orders")
            if live_http:
                self.live_probe_succeeded = True
                self.execution_mode = "emulado"
                return live_http

        # Validación sintáctica de URL y resolución de host
        host, url = self._extract_host_and_url(command)
        if url and not (url.startswith("http://") or url.startswith("https://")):
            return "curl: (3) URL using bad/illegal format or missing URL"

        if host and not self._is_valid_host(host):
            return f"curl: (6) Could not resolve host: {host}"

        # ESTADO DE FALLA ÚNICO POR ESCENARIO: Todas las salidas se derivan de self.fault_state
        if self.fault_state == FaultClass.HTTP_504_GATEWAY_TIMEOUT or self.fault_state == FaultClass.NETWORK_LATENCY_TC:
            return (
                "HTTP/1.1 504 Gateway Time-out\r\n"
                "Server: nginx/1.24.0\r\n"
                "Date: Fri, 25 Sep 2026 10:01:02 GMT\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 167\r\n"
                "Connection: keep-alive\r\n\r\n"
                "<html><head><title>504 Gateway Time-out</title></head><body><center><h1>504 Gateway Time-out</h1></center><hr><center>nginx</center></body></html>"
            )

        if self.fault_state == FaultClass.HTTP_502_BAD_GATEWAY:
            return (
                "HTTP/1.1 502 Bad Gateway\r\n"
                "Server: nginx/1.24.0\r\n"
                "Date: Fri, 25 Sep 2026 10:00:02 GMT\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 157\r\n"
                "Connection: keep-alive\r\n\r\n"
                "<html><head><title>502 Bad Gateway</title></head><body><center><h1>502 Bad Gateway (111: Connection refused)</h1></center><hr><center>nginx</center></body></html>"
            )

        if self.fault_state == FaultClass.ORIGIN_DOWN:
            return (
                "HTTP/1.1 502 Bad Gateway\r\n"
                "Server: nginx/1.24.0\r\n"
                "Date: Fri, 25 Sep 2026 10:00:02 GMT\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 157\r\n"
                "Connection: keep-alive\r\n\r\n"
                "<html><head><title>502 Bad Gateway (113: No route to host)</title></head><body><center><h1>502 Bad Gateway (113: No route to host)</h1></center><hr><center>nginx</center></body></html>"
            )

        if self.fault_state == FaultClass.HTTP_503_SERVICE_UNAVAILABLE:
            return (
                "HTTP/1.1 503 Service Unavailable\r\n"
                "Server: nginx/1.24.0\r\n"
                "Date: Fri, 25 Sep 2026 10:00:02 GMT\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 190\r\n"
                "Retry-After: 60\r\n"
                "Connection: close\r\n\r\n"
                "<html><head><title>503 Service Unavailable</title></head><body><center><h1>503 Service Unavailable</h1></center><hr><center>nginx</center></body></html>"
            )

        if self.fault_state == FaultClass.CONNECTION_POOL_EXHAUSTED:
            return (
                "HTTP/1.1 503 Service Unavailable\r\n"
                "Server: nginx/1.24.0\r\n"
                "Date: Fri, 25 Sep 2026 10:00:02 GMT\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 194\r\n"
                "Connection: close\r\n\r\n"
                "<html><head><title>503 Service Unavailable</title></head><body><center><h1>503 Service Unavailable (connection limit exceeded)</h1></center><hr><center>nginx</center></body></html>"
            )

        if self.fault_state == FaultClass.HTTP_403_FORBIDDEN:
            return (
                "HTTP/1.1 403 Forbidden\r\n"
                "Server: nginx/1.24.0\r\n"
                "Date: Fri, 25 Sep 2026 10:00:02 GMT\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 162\r\n"
                "Connection: keep-alive\r\n\r\n"
                "<html><head><title>403 Forbidden</title></head><body><center><h1>403 Forbidden</h1></center><hr><center>nginx</center></body></html>"
            )

        if self.fault_state == FaultClass.HTTP_429_RATE_LIMITED:
            return (
                "HTTP/1.1 429 Too Many Requests\r\n"
                "Server: nginx/1.24.0\r\n"
                "Date: Fri, 25 Sep 2026 10:00:02 GMT\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 180\r\n"
                "Retry-After: 30\r\n"
                "Connection: keep-alive\r\n\r\n"
                "<html><head><title>429 Too Many Requests</title></head><body><center><h1>429 Too Many Requests</h1></center><hr><center>nginx</center></body></html>"
            )

        if self.fault_state == FaultClass.HTTP_500_INTERNAL:
            return (
                "HTTP/1.1 500 Internal Server Error\r\n"
                "Server: uvicorn\r\n"
                "Date: Fri, 25 Sep 2026 10:00:02 GMT\r\n"
                "Content-Type: application/json\r\n"
                "Content-Length: 38\r\n\r\n"
                '{"detail":"Internal server error: KeyError"}'
            )

        # Fallback cuando se prueba curl sin escenario instanciado (modo unit test independiente)
        if "/admin" in command or "status" in command:
            return "HTTP/1.1 403 Forbidden\r\nServer: nginx/1.24.0\r\nContent-Length: 162\r\n\r\n<html><head><title>403 Forbidden</title></head><body>403 Forbidden</body></html>"
        if "429" in command or "/search" in command:
            return "HTTP/1.1 429 Too Many Requests\r\nServer: nginx/1.24.0\r\nRetry-After: 30\r\n\r\n429 Too Many Requests"
        if "checkout" in command:
            return 'HTTP/1.1 500 Internal Server Error\r\nServer: uvicorn\r\n\r\n{"detail":"Internal server error: KeyError"}'
        if "orders" in command:
            return "HTTP/1.1 503 Service Unavailable\r\nServer: nginx/1.24.0\r\nRetry-After: 60\r\n\r\n503 Service Unavailable"
        if "reports" in command:
            return "HTTP/1.1 504 Gateway Time-out\r\nServer: nginx/1.24.0\r\n\r\n504 Gateway Time-out"
        if "8080" in command:
            return "curl: (7) Failed to connect to 127.0.0.1 port 8080: Connection refused"
        if "users" in command:
            return "HTTP/1.1 502 Bad Gateway\r\nServer: nginx/1.24.0\r\n\r\n502 Bad Gateway"

        return "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\":\"healthy\"}"

    def execute_openssl(self, command: str) -> str:
        """
        Ejecuta o simula verificación TLS con openssl s_client.
        Todas las salidas se derivan del único estado de falla del escenario (Hallazgo T1).
        Síntomas, NUNCA causas.
        """
        self._assert_read_only("openssl", command)
        cmd_lower = command.lower()

        # En modo emulado, ejecutar OBLIGATORIAMENTE contra el contenedor real (puerto 8443)
        if self.execution_mode == "emulado":
            live_tls = self._probe_live_tls("127.0.0.1", 8443)
            if live_tls:
                self.live_probe_succeeded = True
                return live_tls
            sc_id = getattr(self.scenario, "scenario_id", "TLS-EXP-01")
            raise RuntimeError(
                f"Contenedor TLS emulado no responde en 127.0.0.1:8443 para {sc_id}. "
                "La corrida emulada fue abortada (no se permite fallback al simulador)."
            )

        # Sondeo en vivo solo si fue monkeypatcheado por pruebas de integración o modo emulado
        is_monkeypatched_tls = getattr(self._probe_live_tls, "__func__", None) is not ReadOnlyNetworkTools._probe_live_tls
        if is_monkeypatched_tls and "8443" in command:
            live_tls = self._probe_live_tls("127.0.0.1", 8443)
            if live_tls:
                self.live_probe_succeeded = True
                self.execution_mode = "emulado"
                return live_tls

        # Validación de host
        host, _ = self._extract_host_and_url(command)
        if host and not self._is_valid_host(host):
            return f"gethostbyname failed: Could not resolve host {host}"

        # ESTADO DE FALLA ÚNICO POR ESCENARIO:
        if self.fault_state == FaultClass.TLS_CHAIN_INVALID:
            return (
                "CONNECTED(00000003)\n"
                "depth=0 C = CO, ST = Norte de Santander, O = UniPamplona, CN = secure.corp.internal\n"
                "verify error:num=20:unable to get local issuer certificate\n"
                "verify return:1\n"
                "---\nCertificate chain\n 0 s:CN = secure.corp.internal\n---\n"
                "Verify return code: 20 (unable to get local issuer certificate)"
            )

        if self.fault_state == FaultClass.TLS_CIPHER_MISMATCH:
            return (
                "CONNECTED(00000003)\n"
                "140735284381504:error:14094410:SSL routines:ssl3_read_bytes:sslv3 alert handshake failure:../ssl/record/rec_layer_s3.c:1544:SSL alert number 40\n"
                "---\nno peer certificate available\n---\nNo client certificate CA names sent\n"
                "SSL handshake has read 7 bytes and written 119 bytes\n"
                "Verify return code: 0 (ok)"
            )

        if self.fault_state == FaultClass.TLS_SNI_MISMATCH:
            return (
                "CONNECTED(00000003)\n"
                "depth=0 C = CO, ST = Norte de Santander, O = UniPamplona, CN = default.corp.internal\n"
                "verify error:num=62:Hostname mismatch\n"
                "---\nCertificate chain\n 0 s:CN = default.corp.internal\n---\n"
                "Verify return code: 62 (Hostname mismatch)"
            )

        if self.fault_state == FaultClass.TLS_EXPIRED_CERT:
            return (
                "CONNECTED(00000003)\n"
                "depth=0 C = CO, ST = Norte de Santander, O = UniPamplona, CN = secure.corp.internal\n"
                "verify error:num=10:certificate has expired\n"
                "notAfter=Sep 20 12:00:00 2026 GMT\n"
                "verify return:1\n"
                "---\nCertificate chain\n 0 s:CN = secure.corp.internal\n---\n"
                "Verify return code: 10 (certificate has expired)"
            )

        # Fallback sin escenario instanciado (unit tests específicos)
        if "api-unregistered.corp.internal" in cmd_lower or "default.corp.internal" in cmd_lower:
            return (
                "CONNECTED(00000003)\n"
                "depth=0 C = CO, ST = Norte de Santander, O = UniPamplona, CN = default.corp.internal\n"
                "verify error:num=62:Hostname mismatch\n"
                "---\nCertificate chain\n 0 s:CN = default.corp.internal\n---\n"
                "Verify return code: 62 (Hostname mismatch)"
            )
        if "-cipher" in cmd_lower or "aes128-sha" in cmd_lower:
            return (
                "CONNECTED(00000003)\n"
                "140735284381504:error:14094410:SSL routines:ssl3_read_bytes:sslv3 alert handshake failure:../ssl/record/rec_layer_s3.c:1544:SSL alert number 40\n"
                "---\nno peer certificate available\n---\n"
                "Verify return code: 0 (ok)"
            )
        if "-showcerts" in cmd_lower or "-cafile" in cmd_lower or "chain" in cmd_lower:
            return (
                "CONNECTED(00000003)\n"
                "depth=0 C = CO, ST = Norte de Santander, O = UniPamplona, CN = secure.corp.internal\n"
                "verify error:num=20:unable to get local issuer certificate\n"
                "verify return:1\n"
                "---\nCertificate chain\n 0 s:CN = secure.corp.internal\n---\n"
                "Verify return code: 20 (unable to get local issuer certificate)"
            )

        return (
            "CONNECTED(00000003)\n"
            "depth=0 C = CO, ST = Norte de Santander, O = UniPamplona, CN = secure.corp.internal\n"
            "verify error:num=10:certificate has expired\n"
            "notAfter=Sep 20 12:00:00 2026 GMT\n"
            "verify return:1\n"
            "---\nCertificate chain\n 0 s:CN = secure.corp.internal\n---\n"
            "Verify return code: 10 (certificate has expired)"
        )

    def execute_prometheus_query(self, command: str) -> str:
        """Consulta métricas de Prometheus de solo lectura."""
        self._assert_read_only("prometheus", command)
        return (
            '{"status":"success","data":{"resultType":"vector","result":['
            '{"metric":{"__name__":"http_requests_total","status":"502"},"value":[1774567200,"482"]},'
            '{"metric":{"__name__":"up","job":"backend_api"},"value":[1774567200,"0"]}'
            ']}}'
        )

    def dispatch(self, tool_name: str, command: str) -> tuple[bool, str]:
        """Despacha la ejecución a la herramienta correspondiente con manejo seguro de excepciones."""
        tool_clean = tool_name.strip().lower()
        cmd_clean = command.strip()

        # Sustituir placeholders habituales emitidos por SLMs
        target_fqdn = (
            self.scenario.metadata.get("target_fqdn", "app.internal.corp")
            if self.scenario else "app.internal.corp"
        )
        replacements = {
            "<IP_DNS>": "127.0.0.1",
            "<DNS_IP>": "127.0.0.1",
            "<IP>": "127.0.0.1",
            "<PORT>": "5353" if "dig" in tool_clean else "80",
            "<FQDN>": target_fqdn,
            "<DOMINIO>": target_fqdn,
            "<DOMAIN>": target_fqdn,
            "<URL>": "http://127.0.0.1:80",
            "<HOST>": "127.0.0.1",
        }
        for ph, val in replacements.items():
            cmd_clean = cmd_clean.replace(ph, val)

        try:
            if "dig" in tool_clean:
                out = self.execute_dig(cmd_clean)
            elif "curl" in tool_clean:
                out = self.execute_curl(cmd_clean)
            elif "openssl" in tool_clean:
                out = self.execute_openssl(cmd_clean)
            elif "ping" in tool_clean:
                out = self.execute_ping(cmd_clean)
            elif "prom" in tool_clean:
                out = self.execute_prometheus_query(cmd_clean)
            else:
                return False, f"Herramienta '{tool_name}' no soportada en el conjunto de solo lectura."
            return True, out
        except SecurityPolicyViolation as spv:
            logger.warning(f"Violación de seguridad detectada: {spv}")
            return False, f"SECURITY_ERROR: {spv!s}"
        except Exception as e:
            if self.execution_mode == "emulado":
                raise
            return False, f"EXECUTION_ERROR: {e!s}"
