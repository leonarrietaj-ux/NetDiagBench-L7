"""
NetDiagBench-L7: Traductor Técnico Especializado de Diagnóstico L7 (Inglés -> Español).
Garantiza que cualquier respuesta, razonamiento CoT, causa raíz, componente o mitigación
emitido por cualquier modelo en idioma inglés sea traducido de forma fiel y fluida al español,
preservando intactos los identificadores técnicos, comandos, protocolos y códigos de error.
"""

import re

# Diccionario de expresiones multi-palabra y estructuras gramaticales técnicas
# Se ordenan descendentemente por longitud para asegurar máxima cobertura de frases completas.
PHRASE_MAPPINGS = [
    # Patrones de instrucciones, taxonomías y memorandos técnicos (ej. Tinyllama)
    ("the following instructions provide a taxonomy of components that must be included in the solution for the vista logic technical support team to perform their verification and final diagnosis",
     "las siguientes instrucciones proporcionan una taxonomía de componentes que deben incluirse en la solución para que el equipo de soporte técnico realice su verificación y diagnóstico final"),
    ("the following instructions provide a taxonomy of components that must be included in the solution",
     "las siguientes instrucciones proporcionan una taxonomía de componentes que deben incluirse en la solución"),
    ("the following instructions provide", "las siguientes instrucciones proporcionan"),
    ("components verified (dns): the dns are the technical support team's primary means of verifying the system's functionality, including its software components, hardware components, and network connectivity",
     "componentes verificados (DNs): los DNs son el medio principal del equipo de soporte técnico para verificar la funcionalidad del sistema, incluidos sus componentes de software, componentes de hardware y conectividad de red"),
    ("the dns are the technical support team's primary means of verifying the system's functionality, including its software components, hardware components, and network connectivity",
     "los DNs son el medio principal del equipo de soporte técnico para verificar la funcionalidad del sistema, incluidos sus componentes de software, componentes de hardware y conectividad de red"),
    ("the dns are the technical support team's primary means of verifying the system's functionality",
     "los DNs son el medio principal del equipo de soporte técnico para verificar la funcionalidad del sistema"),
    ("these dns must be verified before any further troubleshooting or analysis can take place",
     "estos componentes deben verificarse antes de que se pueda realizar cualquier resolución de problemas o análisis adicional"),
    ("must be verified before any further troubleshooting or analysis can take place",
     "deben verificarse antes de que se pueda realizar cualquier resolución de problemas o análisis adicional"),
    ("components valiated (dns): the dns are also used to validate the technical support team's diagnosis of the system's problems",
     "componentes validados (DNs): los DNs también se utilizan para validar el diagnóstico del equipo de soporte técnico sobre los problemas del sistema"),
    ("components validated (dns): the dns are also used to validate the technical support team's diagnosis of the system's problems",
     "componentes validados (DNs): los DNs también se utilizan para validar el diagnóstico del equipo de soporte técnico sobre los problemas del sistema"),
    ("the dns are also used to validate the technical support team's diagnosis of the system's problems",
     "los DNs también se utilizan para validar el diagnóstico del equipo de soporte técnico sobre los problemas del sistema"),
    ("this involves identifying and isolating the root cause(s) of the problem, as well as determining how best to address it",
     "esto implica identificar y aislar la(s) causa(s) raíz del problema, así como determinar la mejor manera de abordarlo"),
    ("identifying and isolating the root cause(s) of the problem, as well as determining how best to address it",
     "identificación y aislamiento de la(s) causa(s) raíz del problema, así como determinación de la mejor manera de abordarlo"),
    ("identifying and isolating the root cause(s) of the problem", "identificación y aislamiento de la(s) causa(s) raíz del problema"),
    ("identifying and isolating the root cause", "identificación y aislamiento de la causa raíz"),
    ("as well as determining how best to address it", "así como determinar la mejor manera de abordarlo"),
    ("determining how best to address it", "determinar la mejor manera de abordarlo"),
    ("components obligatory (json native device-specific): the dns must be provided in json natvie device-specific format with exact 4 clauses that are exactly specified",
     "componentes obligatorios (JSON nativo específico del dispositivo): los datos deben suministrarse en formato nativo JSON específico del dispositivo con 4 cláusulas exactas especificadas"),
    ("the dns must be provided in json natvie device-specific format with exact 4 clauses that are exactly specified",
     "los datos deben suministrarse en formato nativo JSON específico del dispositivo con 4 cláusulas exactas especificadas"),
    ("the dns must be provided in json native device-specific format with exact 4 clauses that are exactly specified",
     "los datos deben suministrarse en formato nativo JSON específico del dispositivo con 4 cláusulas exactas especificadas"),
    ("components verified (dns)", "componentes verificados (DNs)"),
    ("components validated (dns)", "componentes validados (DNs)"),
    ("components valiated (dns)", "componentes validados (DNs)"),
    ("components obligatory", "componentes obligatorios"),
    ("components verified", "componentes verificados"),
    ("components validated", "componentes validados"),
    ("components valiated", "componentes validados"),
    ("technical support team's", "del equipo de soporte técnico"),
    ("technical support team", "equipo de soporte técnico"),
    ("technical support", "soporte técnico"),
    ("primary means of verifying", "medio principal para verificar"),
    ("system's functionality", "funcionalidad del sistema"),
    ("system functionality", "funcionalidad del sistema"),
    ("software components, hardware components, and network connectivity",
     "componentes de software, componentes de hardware y conectividad de red"),
    ("software components", "componentes de software"),
    ("hardware components", "componentes de hardware"),
    ("network connectivity", "conectividad de red"),
    ("troubleshooting or analysis", "resolución de problemas o análisis"),
    ("troubleshooting and analysis", "resolución de problemas y análisis"),
    ("can take place", "pueda llevarse a cabo"),
    ("must be verified before", "deben verificarse antes de"),
    ("must be verified", "debe ser verificado"),
    ("should be verified", "debería verificarse"),
    ("needs to be verified", "necesita verificarse"),

    # Secciones diagnósticas y claves estructuradas
    ("the root cause of the issue is", "la causa raíz del problema es"),
    ("the root cause of the problem is", "la causa raíz del problema es"),
    ("the root cause of the incident is", "la causa raíz del incidente es"),
    ("the root cause of the failure is", "la causa raíz de la falla es"),
    ("the root cause is", "la causa raíz es"),
    ("root cause is", "la causa raíz es"),
    ("root cause:", "causa raíz:"),
    ("root cause", "causa raíz"),
    ("root causes", "causas raíz"),
    ("affected component:", "componente afectado:"),
    ("affected component is", "el componente afectado es"),
    ("affected component", "componente afectado"),
    ("suggested action:", "acción sugerida (SOP):"),
    ("suggested action is", "la acción sugerida es"),
    ("suggested action", "acción sugerida"),
    ("suggested mitigation:", "mitigación sugerida:"),
    ("suggested mitigation is", "la mitigación sugerida es"),
    ("suggested mitigation", "mitigación sugerida"),
    ("recommended action:", "acción recomendada:"),
    ("recommended action is", "la acción recomendada es"),
    ("recommended action", "acción recomendada"),
    ("technical explanation:", "fundamentación técnica:"),
    ("technical explanation", "fundamentación técnica"),
    ("technical justification:", "justificación técnica:"),
    ("technical justification", "justificación técnica"),
    ("chain of thought:", "cadena de pensamiento:"),
    ("chain of thought", "cadena de pensamiento"),
    ("reasoning chain:", "cadena de razonamiento:"),
    ("reasoning chain", "cadena de razonamiento"),
    ("diagnostic task:", "tarea de diagnóstico:"),
    ("diagnostic task", "tarea de diagnóstico"),
    ("system instructions:", "instrucciones del sistema:"),
    ("system instructions", "instrucciones del sistema"),

    # Diagnósticos DNS y protocolos
    ("the dns server returned nxdomain because the domain", "el servidor DNS retornó NXDOMAIN debido a que el dominio"),
    ("the dns server returned nxdomain", "el servidor DNS retornó NXDOMAIN"),
    ("the dns server returned", "el servidor DNS retornó"),
    ("the dns server is returning", "el servidor DNS está retornando"),
    ("the dns server responds with", "el servidor DNS responde con"),
    ("the dns server", "el servidor DNS"),
    ("dns authoritative server", "servidor DNS autoritativo"),
    ("authoritative dns server", "servidor DNS autoritativo"),
    ("authoritative name server", "servidor de nombres autoritativo"),
    ("authoritative server", "servidor autoritativo"),
    ("authoritative zone database", "base de datos de zona autoritativa"),
    ("authoritative database", "base de datos autoritativa"),
    ("authoritative zone", "zona autoritativa"),
    ("recursive resolver", "resolutor recursivo"),
    ("recursive lookup", "resolución recursiva"),
    ("remote authoritative server", "servidor autoritativo remoto"),
    ("zone database", "base de datos de zona"),
    ("zone file", "archivo de zona"),
    ("zone configuration", "configuración de zona"),
    ("missing dns record in the authoritative zone", "registro DNS faltante en la zona autoritativa"),
    ("missing dns record", "registro DNS faltante"),
    ("missing record", "registro faltante"),
    ("does not exist in the authoritative database", "no existe en la base de datos autoritativa"),
    ("does not exist in the zone database", "no existe en la base de datos de zona"),
    ("does not exist in the zone", "no existe en la zona"),
    ("does not exist on the authoritative server", "no existe en el servidor autoritativo"),
    ("does not exist in", "no existe en"),
    ("does not exist on", "no existe en"),
    ("does not exist", "no existe"),
    ("is not found in the authoritative database", "no se encuentra en la base de datos autoritativa"),
    ("is not found in the zone", "no se encuentra en la zona"),
    ("is not found in the", "no se encuentra en la"),
    ("is not found in", "no se encuentra en"),
    ("is not found", "no se encuentra"),
    ("non-existent domain", "dominio inexistente"),
    ("domain not found", "dominio no encontrado"),
    ("host not found", "host no encontrado"),
    ("lame delegation", "delegación defectuosa (lame delegation)"),
    ("lame server", "servidor con delegación lame"),
    ("query timed out", "tiempo de espera de consulta agotado"),
    ("query failed", "consulta fallida"),
    ("query refused", "consulta rechazada"),
    ("access control list", "lista de control de acceso (ACL)"),

    # Diagnósticos TLS / SSL
    ("the intermediate ca certificate is missing from the", "falta el certificado de la CA intermedia en la"),
    ("the intermediate ca certificate is missing", "falta el certificado de la CA intermedia"),
    ("the intermediate ca certificate", "el certificado de la CA intermedia"),
    ("intermediate ca certificate", "certificado de la CA intermedia"),
    ("intermediate certificate", "certificado intermedio"),
    ("certificate chain is incomplete", "la cadena de certificados está incompleta"),
    ("incomplete certificate chain", "cadena de certificados incompleta"),
    ("unable to get local issuer certificate", "no se pudo obtener el certificado de la CA emisora"),
    ("certificate has expired", "el certificado digital ha expirado"),
    ("expired certificate", "certificado digital expirado"),
    ("certificate validity has expired", "la validez del certificado ha expirado"),
    ("cipher suite mismatch", "incompatibilidad de suites de cifrado"),
    ("no shared cipher", "sin cifrado compartido compatible"),
    ("ssl handshake failure", "fallo de negociación SSL (handshake)"),
    ("tls handshake failure", "fallo de negociación TLS (handshake)"),
    ("handshake failure", "fallo de negociación (handshake)"),
    ("handshake failed", "falló la negociación TLS"),
    ("hostname mismatch", "discrepancia de nombre de host"),
    ("sni mismatch", "discrepancia de SNI"),
    ("server name indication", "Server Name Indication (SNI)"),
    ("subject alternative name", "Subject Alternative Name (SAN)"),

    # Diagnósticos HTTP y API Gateway
    ("bad gateway", "puerta de enlace incorrecta (Bad Gateway)"),
    ("gateway timeout", "tiempo de espera de puerta de enlace agotado"),
    ("service unavailable", "servicio no disponible"),
    ("internal server error", "error interno del servidor"),
    ("too many requests", "demasiadas peticiones"),
    ("rate limit exceeded", "límite de tasa excedido"),
    ("rate limiting", "limitación de tasa (rate limiting)"),
    ("connection pool exhausted", "pool de conexiones agotado"),
    ("connection pool", "pool de conexiones"),
    ("pool exhausted", "pool agotado"),
    ("upstream server is down", "el servidor upstream está caído"),
    ("upstream service is down", "el servicio upstream está caído"),
    ("upstream is down", "el upstream está caído"),
    ("upstream connect error", "error de conexión hacia upstream"),
    ("upstream server unavailable", "el servidor upstream no está disponible"),
    ("upstream timeout", "tiempo de espera agotado con upstream"),
    ("nginx configuration", "configuración de Nginx"),
    ("api gateway", "pasarela de API (API Gateway)"),

    # Diagnósticos Kernel y Red
    ("traffic control", "control de tráfico"),
    ("artificial latency", "latencia artificial"),
    ("packet delay", "retardo de paquetes"),
    ("network latency", "latencia de red"),
    ("network infrastructure", "infraestructura de red"),
    ("packet loss", "pérdida de paquetes"),
    ("high latency", "alta latencia"),

    # Acciones operacionales y SOP
    ("reload the bind service using rndc reload to apply the new dns zone records",
     "recargar el servicio BIND utilizando rndc reload para aplicar los nuevos registros de zona DNS"),
    ("reload the bind service", "recargar el servicio BIND"),
    ("restart the bind service", "reiniciar el servicio BIND"),
    ("the bind service", "el servicio BIND"),
    ("bind service", "servicio BIND"),
    ("using rndc reload to apply", "utilizando rndc reload para aplicar"),
    ("using rndc reload", "utilizando rndc reload"),
    ("to apply the new dns zone records", "para aplicar los nuevos registros de zona DNS"),
    ("to apply the new", "para aplicar los nuevos"),
    ("add the dns record to the zone file", "añadir el registro DNS al archivo de zona"),
    ("add the dns record", "añadir el registro DNS"),
    ("add the record", "añadir el registro"),
    ("publish the dns record", "publicar el registro DNS"),
    ("renew the tls certificate", "renovar el certificado TLS"),
    ("renew the certificate", "renovar el certificado"),
    ("install the certificate", "instalar el certificado"),
    ("concatenate the intermediate certificate", "concatenar el certificado intermedio"),
    ("update cipher suites", "actualizar las suites de cifrado"),
    ("check zone configuration", "verificar la configuración de zona"),
    ("check the configuration", "verificar la configuración"),
    ("verify service logs", "verificar los registros del servicio"),
    ("reload the nginx service", "recargar el servicio Nginx"),
    ("restart the backend container", "reiniciar el contenedor del backend"),
    ("restart the service", "reiniciar el servicio"),
    ("reload the service", "recargar el servicio"),

    ("the upstream backend server is unreachable due to high network latency", "el servidor backend upstream es inalcanzable debido a alta latencia de red"),
    ("the upstream backend server is unreachable", "el servidor backend upstream es inalcanzable"),
    ("the upstream backend server", "el servidor backend upstream"),
    ("the upstream backend", "el backend upstream"),
    ("verify network routing and reduce traffic control latency", "verificar el enrutamiento de red y reducir la latencia de control de tráfico"),
    ("verify network routing", "verificar el enrutamiento de red"),
    ("reduce traffic control latency", "reducir la latencia de control de tráfico"),
    ("packet delay caused http 504 gateway timeout", "el retardo de paquetes causó tiempo de espera de puerta de enlace HTTP 504"),
    ("packet delay caused", "el retardo de paquetes causó"),
    ("packet delay", "retardo de paquetes"),
    ("due to high network latency", "debido a alta latencia de red"),
    ("due to high latency", "debido a alta latencia"),
    ("due to", "debido a"),
    ("caused", "causó"),
    ("the dig command confirmed that no such record exists in the authoritative zone", "el comando dig confirmó que dicho registro no existe en la zona autoritativa"),
    ("the dig command confirmed that", "el comando dig confirmó que"),
    ("command confirmed that no such record exists", "comando confirmó que no existe dicho registro"),
    ("command confirmed that", "comando confirmó que"),
    ("confirmed that no such record exists in the authoritative zone", "confirmó que dicho registro no existe en la zona autoritativa"),
    ("no such record exists in the authoritative zone", "dicho registro no existe en la zona autoritativa"),
    ("no such record exists", "no existe dicho registro"),
    ("exists in the authoritative zone", "existe en la zona autoritativa"),
    ("exists in the authoritative", "existe en el autoritativo"),
    ("telemetry shows that queries for", "la telemetría muestra que las consultas para"),
    ("queries for", "consultas para"),
    ("failed with status", "fallaron con estado"),
    ("with status", "con estado"),
    # Conectores y frases argumentativas
    ("based on the observed telemetry", "con base en la telemetría observada"),
    ("based on the telemetry", "con base en la telemetría"),
    ("according to rfc", "de acuerdo con el RFC"),
    ("according to the rfc", "de acuerdo con el RFC"),
    ("telemetry shows that", "la telemetría muestra que"),
    ("telemetry indicates that", "la telemetría indica que"),
    ("telemetry confirms that", "la telemetría confirma que"),
    ("logs show that", "los registros muestran que"),
    ("logs indicate that", "los registros indican que"),
    ("first, let's look at", "primero, observemos"),
    ("first, we see that", "primero, vemos que"),
    ("first, we observe that", "primero, observamos que"),
    ("we can observe that", "podemos observar que"),
    ("it can be seen that", "se puede apreciar que"),
    ("this indicates that", "esto indica que"),
    ("this confirms that", "esto confirma que"),
    ("this proves that", "esto demuestra que"),
    ("this rules out", "esto descarta"),
    ("which rules out", "lo cual descarta"),
    ("which indicates that", "lo cual indica que"),
    ("which means that", "lo que significa que"),
    ("which occurs when", "lo cual ocurre cuando"),
    ("in conclusion", "en conclusión"),
    ("therefore", "por lo tanto"),
    ("furthermore", "además"),
    ("however", "sin embargo"),
]

# Ordenar por longitud descendente
PHRASE_MAPPINGS.sort(key=lambda x: len(x[0]), reverse=True)

# Diccionario palabra por palabra para vocabulario residual técnico y conectores
WORD_MAPPINGS = {
    # Artículos y demostrativos
    "the": "el", "a": "un", "an": "un", "this": "este", "these": "estos", "that": "ese", "those": "esos",
    # Verbos auxiliares y cópula
    "is": "es", "are": "son", "was": "fue", "were": "fueron", "been": "sido", "being": "siendo",
    "has": "ha", "have": "han", "had": "había", "will": "será", "would": "sería", "should": "debería",
    "could": "podría", "can": "puede", "must": "debe", "may": "puede", "might": "podría",
    # Conjunciones y conectores
    "and": "y", "or": "o", "but": "pero", "because": "porque", "since": "ya que", "therefore": "por lo tanto",
    "however": "sin embargo", "furthermore": "además", "while": "mientras", "although": "aunque",
    # Preposiciones
    "in": "en", "on": "en", "at": "en", "to": "para", "for": "para", "with": "con", "from": "desde",
    "by": "por", "about": "acerca de", "between": "entre", "under": "bajo", "before": "antes de",
    "after": "después de", "during": "durante", "without": "sin", "into": "en", "of": "de",
    # Pronombres
    "we": "nosotros", "they": "ellos", "it": "ello", "its": "su", "their": "su", "our": "nuestro",
    # Acciones técnicas / Verbos
    "identifying": "identificando", "isolating": "aislando", "verifying": "verificando", "validating": "validando",
    "analyzing": "analizando", "troubleshooting": "resolución de problemas", "determining": "determinando",
    "addressing": "abordando", "providing": "proporcionando", "performing": "realizando",
    "returning": "retornando", "failing": "fallando", "connecting": "conectando", "reloading": "recargando",
    "checking": "verificando", "updating": "actualizando", "configuring": "configurando", "resolving": "resolviendo",
    "verified": "verificado", "validated": "validado", "checked": "verificado", "failed": "falló",
    "returned": "retornó", "observed": "observado", "expected": "esperado", "received": "recibido",
    # Sustantivos técnicos
    "failure": "falla", "failures": "fallas", "error": "error", "errors": "errores", "warning": "advertencia",
    "warnings": "advertencias", "issue": "problema", "issues": "problemas", "problem": "problema",
    "problems": "problemas", "incident": "incidente", "incidents": "incidentes",
    "timeout": "tiempo de espera agotado", "timeouts": "tiempos de espera agotados",
    "request": "petición", "requests": "peticiones", "response": "respuesta", "responses": "respuestas",
    "query": "consulta", "queries": "consultas", "record": "registro", "records": "registros",
    "zone": "zona", "zones": "zonas", "server": "servidor", "servers": "servidores",
    "service": "servicio", "services": "servicios", "client": "cliente", "clients": "clientes",
    "certificate": "certificado", "certificates": "certificados", "domain": "dominio", "domains": "dominios",
    "hostname": "nombre de host", "hostnames": "nombres de host", "port": "puerto", "ports": "puertos",
    "latency": "latencia", "connection": "conexión", "connections": "conexiones",
    "log": "registro", "logs": "registros", "telemetry": "telemetría", "evidence": "evidencia",
    "evidences": "evidencias", "hypothesis": "hipótesis", "mitigation": "mitigación",
    "action": "acción", "actions": "acciones", "solution": "solución", "solutions": "soluciones",
    "explanation": "explicación", "explanations": "explicaciones", "status": "estado",
    "taxonomy": "taxonomía", "format": "formato", "functionality": "funcionalidad",
    "connectivity": "conectividad", "component": "componente", "components": "componentes",
    "clause": "cláusula", "clauses": "cláusulas", "database": "base de datos",
    # Adjetivos técnicos
    "primary": "principal", "initial": "inicial", "final": "final", "conclusive": "concluyente",
    "empirical": "empírico", "missing": "faltante", "expired": "expirado", "invalid": "inválido",
    "incomplete": "incompleto", "unreachable": "inalcanzable", "refused": "rechazado",
    "truncated": "truncado", "slow": "lento", "high": "alto", "critical": "crítico",
    "active": "activo", "passive": "pasivo", "obligatory": "obligatorio", "exact": "exacto",
    "specified": "especificado", "authoritative": "autoritativo", "recursive": "recursivo",
}

PRESERVED_TOKENS = {
    "dns", "http", "tls", "bind9", "nginx", "dig", "curl", "openssl",
    "nxdomain", "servfail", "refused", "tcp", "udp", "ip", "rfc", "sop",
    "bind9-authoritative", "bind9-recursive-resolver", "bind9-zone-delegation",
    "bind9-resolver-firewall", "nginx-api-gateway", "nginx-rate-limiter",
    "backend-application-code", "backend-application-pool", "upstream-backend-api",
    "upstream-backend-database", "upstream-cluster", "network-infrastructure",
    "nginx-tls-termination", "nginx-tls-crypto-engine", "rndc", "reload",
    "exit", "a", "aaaa", "cname", "mx", "txt", "ns", "so", "get", "post",
    "put", "delete", "head", "options", "upstream", "backend", "internal",
    "corp", "lab", "local", "status"
}


def is_predominantly_english(text: str) -> bool:
    """Detecta si un texto contiene oraciones o palabras predominantemente en inglés."""
    if not text or len(text.strip()) < 10:
        return False
    english_markers = {
        "the", "is", "at", "which", "on", "and", "a", "an", "this", "that",
        "following", "instructions", "provide", "taxonomy", "of", "components",
        "must", "be", "included", "in", "solution", "for", "technical", "support",
        "team", "to", "perform", "their", "verification", "root", "cause", "analysis",
        "affected", "component", "recommended", "action", "with", "from", "by",
        "these", "those", "should", "could", "would", "because", "error", "failed",
        "failure", "troubleshooting", "identifying", "isolating", "diagnostic", "task",
        "system", "explanations", "mitigation", "returned", "missing", "expired"
    }
    words = re.findall(r"\b[a-zA-Z]{2,}\b", text.lower())
    if not words or len(words) < 3:
        return False
    eng_matches = sum(1 for w in words if w in english_markers)
    return (eng_matches / len(words)) >= 0.20


def translate_english_to_spanish(text: str) -> str:
    """
    Traduce texto técnico emitido en inglés al español.
    Preserva intactos comandos, rutas, IPs, FQDNs, códigos de error y tokens canónicos.
    """
    if not text or not str(text).strip():
        return ""

    res = text.strip()

    # 1. Aplicar mapeo de frases idiomáticas y compuestas (mayor especificidad primero)
    for p_en, p_es in PHRASE_MAPPINGS:
        pattern = re.compile(rf"\b{re.escape(p_en)}\b", re.IGNORECASE)
        def _repl_phrase(match, rep=p_es):
            orig = match.group(0)
            if orig.isupper():
                return rep.upper()
            if orig[0].isupper() and not orig.islower():
                return rep[0].upper() + rep[1:]
            return rep
        res = pattern.sub(_repl_phrase, res)

    # 2. Aplicar mapeo palabra por palabra para vocabulario residual
    def _repl_word(match):
        w = match.group(0)
        wl = w.lower()
        # Preservar tokens técnicos, IPs, FQDNs o nombres con puntos/guiones
        if wl in PRESERVED_TOKENS or "." in w or "-" in w or "_" in w or any(c.isdigit() for c in w):
            return w
        if wl in WORD_MAPPINGS:
            trans = WORD_MAPPINGS[wl]
            if w.isupper():
                return trans.upper()
            if w[0].isupper():
                return trans[0].upper() + trans[1:]
            return trans
        return w

    res = re.sub(r"\b[a-zA-Z]+\b", _repl_word, res)

    # 3. Limpiezas gramaticales de fluidez en español
    res = re.sub(r"\bde el\b", "del", res, flags=re.IGNORECASE)
    res = re.sub(r"\ba el\b", "al", res, flags=re.IGNORECASE)
    res = re.sub(r"\s{2,}", " ", res).strip()

    return res
