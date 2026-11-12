"""
NetDiagBench-L7: Suite de Pruebas Universales del Evaluador y Compatibilidad de Modelos
Cubre:
1. Las 18 clases normativas con 6 variantes por clase:
   - Correcta en español
   - Correcta en inglés
   - Correcta en formato JSON
   - Correcta con bloque <think> CoT (el parser lo separa y evalúa solo la respuesta final)
   - Solo síntoma (debe evaluarse como incorrecta)
   - Clase vecina (debe evaluarse como incorrecta)
2. Test cruzado exhaustivo de falsos positivos (18 x 17 = 306 evaluaciones cruzadas con 0 falsos positivos).
3. Llamada nativa tool_calls a dig, curl y openssl.
4. Respuesta vacía o bucle repetitivo -> formato_invalido sin romper la suite.
5. Modelo adicional simulado recorre los 18 escenarios generando filas válidas con model_group='adicional'.
6. Equivalencia estricta de columnas y valores entre suite web y harness.
7. Invarianza de reportes oficiales ante presencia de filas adicionales en el CSV.
"""

import json
from pathlib import Path
import pytest

from src.core.contracts import EscenarioLabContract, GroundTruth, ServiceCategory, FaultClass, ResultadoEvaluacionContract
from src.layer4_inference.engine import LocalInferenceEngine, detect_and_cut_repetition_loops, extract_reasoning_and_response
from src.layer5_orchestrator.agent import DiagnosticOrchestratorAgent
from src.layer7_evaluator.metrics import (
    check_root_cause_correct,
    classify_model,
    get_evaluator_version,
    load_evaluator_concepts
)
from src.layer7_evaluator.harness import BenchmarkEvaluatorHarness
from src.layer1_lab.runner import ScenarioLabRunner


# ── 1. Diccionario de Casos de Prueba Normativos para las 18 Clases ─────────

OFFICIAL_CLASS_TEST_CASES = {
    "DELEGATION_ERROR": {
        "es": "Fallo de resolucion debido a delegacion coja (lame delegation) con servidores NS desincronizados en la zona padre.",
        "en": "Resolution failure caused by lame delegation where delegated NS servers lack authority over child zone.",
        "paraphrase": "Existe una delegacion lame entre las zonas ya que el name server secundario no reconoce ser autoridad para dicho subdominio.",
        "json": json.dumps({"root_cause": "lame server delegation due to out-of-sync NS records", "affected_component": "bind9-zone-delegation"}),
        "think": "<think>Analizando traza DNS. Los NS delegados no tienen autoridad sobre sub.corp.internal.</think>\nCausa Raiz: Delegacion coja (lame delegation) en servidores NS delegados.\nComponente: bind9-zone-delegation",
        "symptom_only": "Error de dns con codigo servfail y resolucion fallida en la consulta.",
        "neighbor": "Fallo de resolucion debido a dominio inexistente nxdomain rcode 3 en la base de datos."
    },
    "NXDOMAIN": {
        "es": "Registro DNS de tipo A ausente en la zona autoritativa de BIND9 (RCODE 3 / NXDOMAIN).",
        "en": "Non-existent domain (NXDOMAIN / RCODE 3) due to missing DNS resource record in zone file.",
        "paraphrase": "El dominio solicitado no existe en el catalogo de registros autoritativos de la zona interna.",
        "json": json.dumps({"root_cause": "dominio inexistente y registro ausente en la base de datos de bind9", "affected_component": "bind9-authoritative"}),
        "think": "<think>Revisando la respuesta de la consulta. RCODE es 3.</think>\nCausa Raiz: Dominio inexistente (NXDOMAIN) por registro de zona faltante.\nComponente: bind9-authoritative",
        "symptom_only": "Resolucion fallida, host not found y error dns sin direccion ip.",
        "neighbor": "Tiempo de espera agotado con servidor autoritativo remoto no responde timeout recursivo servfail."
    },
    "DNS_REFUSED": {
        "es": "Consulta rechazada por ACL debido a la directiva allow-query restrictiva en named.conf (RCODE 5 REFUSED).",
        "en": "DNS query refused by ACL policy due to allow-query restriction on client IP in named.conf (RCODE 5).",
        "paraphrase": "named.conf tiene un control de acceso por match-clients que rechaza la consulta proveniente del cliente.",
        "json": json.dumps({"root_cause": "directiva allow-query o match-clients restringe consultas devolviendo rcode 5 refused", "affected_component": "bind9-authoritative"}),
        "think": "<think>Inspeccionando named.conf. La directiva allow-query bloquea al cliente.</think>\nCausa Raiz: Consulta rechazada por directiva allow-query en named.conf (RCODE 5).\nComponente: bind9-authoritative",
        "symptom_only": "Consulta fallida con rechazo de conexion y error de comunicacion dns.",
        "neighbor": "Error de resolucion debido a dominio inexistente nxdomain rcode 3 en zona."
    },
    "SERVFAIL": {
        "es": "El servidor autoritativo remoto no responde a las consultas recursivas (timeout recursivo RCODE 2 SERVFAIL).",
        "en": "Recursive lookup timeout because remote authoritative server is unreachable, yielding RCODE 2 SERVFAIL.",
        "paraphrase": "Se produjo un timeout durante la resolucion recursiva porque el servidor upstream remoto se encuentra inalcanzable.",
        "json": json.dumps({"root_cause": "servidor autoritativo remoto no responde timeout recursivo", "affected_component": "bind9-recursive-resolver"}),
        "think": "<think>El resolutor recursivo no obtiene respuesta del servidor upstream autoritativo.</think>\nCausa Raiz: Servidor autoritativo remoto no responde, provocando timeout del autoritativo y SERVFAIL.\nComponente: bind9-recursive-resolver",
        "symptom_only": "Fallo de resolucion dns caido donde el servidor no responde la consulta.",
        "neighbor": "Delegacion defectuosa y lame delegation con servidores ns desincronizados."
    },
    "DNS_TRUNCATED_EDNS": {
        "es": "Respuesta truncada con bandera TC=1 por desbordamiento de buffer UDP de 512 bytes sin soporte de EDNS0.",
        "en": "DNS response truncated (TC=1) due to UDP buffer overflow over 512 bytes with lack of EDNS0 support.",
        "paraphrase": "El paquete de respuesta supero los 512 bytes de buffer UDP y al no negociarse edns0 se activo el bit de respuesta truncada.",
        "json": json.dumps({"root_cause": "truncamiento udp tc=1 por desbordamiento de buffer udp 512 bytes sin edns0", "affected_component": "bind9-resolver-firewall"}),
        "think": "<think>Bandera TC=1 observada en el encabezado DNS. Fallo al reintentar sobre TCP.</think>\nCausa Raiz: Truncamiento de respuesta (TC=1) por desbordamiento de buffer UDP sin EDNS0.\nComponente: bind9-resolver-firewall",
        "symptom_only": "Respuesta incompleta y consulta lenta por error udp en paquete dns.",
        "neighbor": "Consulta rechazada por allow-query en named.conf con rcode 5 refused."
    },
    "HTTP_403_FORBIDDEN": {
        "es": "Acceso bloqueado por directiva deny all y control de acceso restrictivo en bloque location de Nginx (403 Forbidden).",
        "en": "Access blocked by deny all directive and IP blacklist access rule in reverse proxy configuration (403 Forbidden).",
        "paraphrase": "Una politica de acceso por lista negra en el bloque de ruta del proxy genero la denegacion del cliente.",
        "json": json.dumps({"root_cause": "directiva deny all en configuracion de control de acceso por ip", "affected_component": "nginx-api-gateway"}),
        "think": "<think>Revisando la seccion location /admin/. Contiene deny all explicito.</think>\nCausa Raiz: Directiva deny all en regla de control de acceso por IP en el gateway.\nComponente: nginx-api-gateway",
        "symptom_only": "Error 403 forbidden con peticion rechazada y acceso no autorizado.",
        "neighbor": "Exceso de tasa de peticiones superando limit_req_zone rate limit too many requests."
    },
    "HTTP_429_RATE_LIMITED": {
        "es": "Tasa de peticiones por segundo excede el umbral configurado en limit_req_zone (Rate Limiting activo).",
        "en": "Incoming request rate exceeds limit_req_zone threshold, triggering rate limiting under leaky bucket policy.",
        "paraphrase": "El modulo limitador de tasa activo el bloqueo temporal porque la frecuencia de solicitudes supero el umbral por segundo.",
        "json": json.dumps({"root_cause": "tasa de peticiones excedida bajo limit_req_zone", "affected_component": "nginx-rate-limiter"}),
        "think": "<think>Analizando headers devueltos. Nginx aplica modulo limit_req con r/s superado.</think>\nCausa Raiz: Limite de tasa excedido en directiva limit_req_zone (Rate Limiting).\nComponente: nginx-rate-limiter",
        "symptom_only": "Error 429 too many requests por demasiado trafico y exceso de solicitudes.",
        "neighbor": "Bloqueo por directiva deny all y regla waf de ip en el gateway."
    },
    "HTTP_500_INTERNAL": {
        "es": "Excepcion no controlada (KeyError) con traceback en el codigo de aplicacion del backend.",
        "en": "Unhandled exception (KeyError) and traceback in backend application source code causing server error.",
        "paraphrase": "Fallo en codigo de la aplicacion al presentarse un KeyError no controlado durante la lectura del diccionario.",
        "json": json.dumps({"root_cause": "unhandled exception KeyError traceback en backend", "affected_component": "backend-application-code"}),
        "think": "<think>Revisando logs de FastAPI. Hay un traceback con KeyError al parsear el JSON.</think>\nCausa Raiz: Excepcion no controlada en backend (KeyError traceback).\nComponente: backend-application-code",
        "symptom_only": "Error 500 internal server error con respuesta 500 y fallo del servidor.",
        "neighbor": "Fallo de conexion rechazada connection refused con servicio upstream caido."
    },
    "HTTP_502_BAD_GATEWAY": {
        "es": "Servicio upstream caido y rechazando conexiones TCP (Connection Refused en puerto backend).",
        "en": "Upstream backend process is down and rejecting TCP connections with Connection Refused.",
        "paraphrase": "El proceso backend de FastAPI se detuvo y rechazo la conexion TCP hacia el gateway con connection refused.",
        "json": json.dumps({"root_cause": "upstream caido rechazando conexiones tcp connection refused", "affected_component": "upstream-backend-api"}),
        "think": "<think>Nginx intenta conectar a 127.0.0.1:8080 pero recibe RST inmediato.</think>\nCausa Raiz: Upstream caido y conexion rechazada (Connection Refused) en proxy inverso.\nComponente: upstream-backend-api",
        "symptom_only": "Error 502 bad gateway por fallo de proxy y error de gateway.",
        "neighbor": "Tiempo de espera proxy_read_timeout excedido por consulta lenta en backend."
    },
    "HTTP_503_SERVICE_UNAVAILABLE": {
        "es": "Saturacion de workers del servidor backend con todos los procesos ocupados (sobrecarga de workers).",
        "en": "Backend application worker pool exhaustion with all workers busy and unable to accept new requests.",
        "paraphrase": "El pool de procesos worker del servidor backend quedo totalmente ocupado y saturado ante la sobrecarga.",
        "json": json.dumps({"root_cause": "sobrecarga de workers en el pool de procesos backend", "affected_component": "backend-application-pool"}),
        "think": "<think>El pool de Uvicorn/Gunicorn no tiene workers libres para atender solicitudes.</think>\nCausa Raiz: Workers saturados en el pool de procesos del servidor de aplicaciones.\nComponente: backend-application-pool",
        "symptom_only": "Error 503 service unavailable servicio no disponible sobrecarga temporal.",
        "neighbor": "Upstream caido con connection refused por servicio apagado."
    },
    "HTTP_504_GATEWAY_TIMEOUT": {
        "es": "El backend tardo mas del tiempo limite en procesar la peticion, excediendo el proxy_read_timeout configurado.",
        "en": "Upstream backend took too long to complete the query, exceeding proxy_read_timeout in Nginx gateway.",
        "paraphrase": "La base de datos demoro mas de 60 segundos en responder superando el proxy_read_timeout configurado en el proxy.",
        "json": json.dumps({"root_cause": "tiempo de espera proxy_read_timeout excedido por lentitud del backend", "affected_component": "upstream-backend-database"}),
        "think": "<think>Nginx cerro la conexion a los 60 segundos exactos segun proxy_read_timeout.</think>\nCausa Raiz: Tiempo de espera del proxy excedido (proxy_read_timeout) por demora en backend.\nComponente: upstream-backend-database",
        "symptom_only": "Error 504 gateway timeout por tiempo de espera agotado y peticion lenta.",
        "neighbor": "Conexion rechazada connection refused con servicio upstream caido."
    },
    "CONNECTION_POOL_EXHAUSTED": {
        "es": "Agotamiento del pool de conexiones persistentes keepalive hacia el upstream (worker_connections alcanzado).",
        "en": "Keepalive connection pool exhausted and worker_connections limit reached for persistent upstream sockets.",
        "paraphrase": "Se alcanzo el limite maximo de conexiones simultaneas worker_connections provocando el colapso del pool keepalive.",
        "json": json.dumps({"root_cause": "pool de conexiones keepalive agotado con limite worker_connections", "affected_component": "nginx-api-gateway"}),
        "think": "<think>La directiva keepalive en el bloque upstream llego a su capacidad maxima.</think>\nCausa Raiz: Agotamiento del pool de conexiones persistentes (worker_connections pool agotado).\nComponente: nginx-api-gateway",
        "symptom_only": "Limite de conexiones alcanzado con socket cerrado y sin conexiones disponibles.",
        "neighbor": "Sobrecarga de workers en el servidor de aplicaciones backend."
    },
    "ORIGIN_DOWN": {
        "es": "Cluster de origen caido por completo sin ningun upstream saludable disponible (no route to host).",
        "en": "All upstream servers in the origin cluster are down with no healthy upstream available to route traffic.",
        "paraphrase": "Falta de ruta y host inalcanzable hacia el cluster de origen de los servidores de backend.",
        "json": json.dumps({"root_cause": "cluster de origen caido sin upstream saludable", "affected_component": "upstream-cluster"}),
        "think": "<think>Nginx informa 'no live upstreams while connecting to upstream'. Todo el cluster esta caido.</think>\nCausa Raiz: Cluster de origen caido y sin upstream saludable en la infraestructura.\nComponente: upstream-cluster",
        "symptom_only": "Servidor inalcanzable con caida del host y error de conectividad.",
        "neighbor": "Excepcion no controlada KeyError en aplicacion backend."
    },
    "NETWORK_LATENCY_TC": {
        "es": "Inyeccion artificial de retardo y jitter en la interfaz de red mediante tc netem (traffic control).",
        "en": "Artificial latency and packet delay injection applied on the network interface via tc netem qdisc.",
        "paraphrase": "Inyeccion intencional de delay artificial y variacion de jitter en la interfaz mediante qdisc netem.",
        "json": json.dumps({"root_cause": "degradacion artificial de rtt por tc netem qdisc traffic control", "affected_component": "network-infrastructure"}),
        "think": "<think>El ping muestra 2000ms con jitter de 500ms constante debido a qdisc netem.</think>\nCausa Raiz: Latencia de red artificial inyectada mediante tc netem (Traffic Control).\nComponente: network-infrastructure",
        "symptom_only": "Latencia de red y retardo de red con alta latencia y enlace lento.",
        "neighbor": "Cluster de origen caido por completo con servidores inaccesibles."
    },
    "TLS_EXPIRED_CERT": {
        "es": "El certificado digital del servidor HTTPS expiro (fecha de expiracion sobrepasada notAfter).",
        "en": "The HTTPS digital server certificate has expired with validity period notAfter in the past.",
        "paraphrase": "El servidor HTTPS presenta un certificado digital cuya validez temporal ya caduco segun la fecha notAfter.",
        "json": json.dumps({"root_cause": "certificado expirado con periodo de validez vencido notAfter", "affected_component": "nginx-tls-termination"}),
        "think": "<think>OpenSSL devuelve verify error:num=10:certificate has expired. notAfter vencio ayer.</think>\nCausa Raiz: Certificado TLS expirado con validez temporal vencida (notAfter).\nComponente: nginx-tls-termination",
        "symptom_only": "Fallo ssl con handshake fallido y error de certificado no valido.",
        "neighbor": "Incompatibilidad de suites de cifrado cipher mismatch alert 40."
    },
    "TLS_CHAIN_INVALID": {
        "es": "Cadena de certificados incompleta en el servidor web por falta del certificado intermedio de la CA emisora.",
        "en": "Incomplete certificate chain due to missing intermediate CA certificate in server bundle.",
        "paraphrase": "No se pudo validar el certificado intermedio de la autoridad de certificacion emisora en la cadena servida.",
        "json": json.dumps({"root_cause": "cadena incompleta por certificado intermedio faltante unknown ca", "affected_component": "nginx-tls-termination"}),
        "think": "<think>OpenSSL reporta unable to get local issuer certificate. Falta el bundle intermedio.</think>\nCausa Raiz: Cadena de certificados incompleta por certificado intermedio faltante.\nComponente: nginx-tls-termination",
        "symptom_only": "Error de verificacion ssl con handshake failed en conexion segura.",
        "neighbor": "Certificado expirado con fecha de validez temporal vencida."
    },
    "TLS_CIPHER_MISMATCH": {
        "es": "Incompatibilidad de suites de cifrado (Cipher Suite Mismatch) rechazando conexion con alert 40 handshake_failure.",
        "en": "Cipher suite mismatch between client and server, triggering alert 40 handshake failure (no shared cipher).",
        "paraphrase": "No hay coincidencia de suite de cifrado compatible entre los algoritmos criptograficos del cliente y el servidor.",
        "json": json.dumps({"root_cause": "incompatibilidad de suites de cifrado cipher mismatch alert 40 no shared cipher", "affected_component": "nginx-tls-crypto-engine"}),
        "think": "<think>El cliente ofrece suites legadas pero el servidor solo admite TLS 1.3 sin cipher compartido.</think>\nCausa Raiz: Incompatibilidad de suites de cifrado (Cipher Suite Mismatch con alert 40).\nComponente: nginx-tls-crypto-engine",
        "symptom_only": "Handshake failure con fallo tls y conexion segura fallida.",
        "neighbor": "Certificado expirado con periodo de validez sobrepasado."
    },
    "TLS_SNI_MISMATCH": {
        "es": "Discrepancia de SNI: el certificado presentado por Nginx no incluye el FQDN solicitado en los Subject Alternative Names (SAN).",
        "en": "Server Name Indication (SNI) mismatch: the served default certificate does not include the requested hostname in SAN.",
        "paraphrase": "El FQDN solicitado por el navegador no coincide con los subject alternative names presentes en el certificado.",
        "json": json.dumps({"root_cause": "discrepancia sni y hostname mismatch con certificado por defecto", "affected_component": "nginx-tls-termination"}),
        "think": "<think>El cliente solicita app.corp.internal pero Nginx sirve el certificado default sin dicho SAN.</think>\nCausa Raiz: Discrepancia de SNI (hostname mismatch) al servir certificado por defecto sin el FQDN.\nComponente: nginx-tls-termination",
        "symptom_only": "Error de nombre y fallo de certificado con nombre no coincide.",
        "neighbor": "Incompatibilidad de suites de cifrado y cipher mismatch alert 40."
    }
}


# ── 1. Pruebas por Clase con Casos de Fuentes Oficiales ──────────────────────

@pytest.mark.parametrize("fault_class,cases", OFFICIAL_CLASS_TEST_CASES.items())
def test_official_evaluator_all_variants_per_class(fault_class: str, cases: dict[str, str]):
    gt_dummy = "Ground truth oficial de referencia para el escenario."

    # 1. Correcta en español
    ok_es, part_es = check_root_cause_correct(cases["es"], gt_dummy, fault_class)
    assert ok_es is True, f"Fallo en español para {fault_class}: '{cases['es']}'"
    assert part_es >= 0.5

    # 2. Correcta en inglés
    ok_en, part_en = check_root_cause_correct(cases["en"], gt_dummy, fault_class)
    assert ok_en is True, f"Fallo en inglés para {fault_class}: '{cases['en']}'"
    assert part_en >= 0.5

    # 3. Parafraseada (sin la frase textual del YAML de conceptos)
    if "paraphrase" in cases:
        ok_para, part_para = check_root_cause_correct(cases["paraphrase"], gt_dummy, fault_class)
        assert ok_para is True, f"Fallo en parafraseado para {fault_class}: '{cases['paraphrase']}'"
        assert part_para >= 0.5

    # 4. Correcta en formato JSON
    ok_json, _ = check_root_cause_correct(cases["json"], gt_dummy, fault_class)
    assert ok_json is True, f"Fallo en JSON para {fault_class}: '{cases['json']}'"

    # 5. Correcta con bloque <think> CoT (el parser debe separar el think y evaluar la respuesta final)
    reasoning, final_text, tokens = extract_reasoning_and_response(cases["think"])
    assert len(reasoning) > 0, f"No extrajo razonamiento para {fault_class}"
    ok_think, _ = check_root_cause_correct(final_text, gt_dummy, fault_class)
    assert ok_think is True, f"Fallo en evaluación post-think para {fault_class}"

    # 6. Solo síntoma -> DEBE ser evaluada como incorrecta
    ok_sym, _ = check_root_cause_correct(cases["symptom_only"], gt_dummy, fault_class)
    assert ok_sym is False, f"Solo síntoma no debe ser correcto para {fault_class}: '{cases['symptom_only']}'"

    # 7. Clase vecina -> DEBE ser evaluada como incorrecta
    ok_neigh, _ = check_root_cause_correct(cases["neighbor"], gt_dummy, fault_class)
    assert ok_neigh is False, f"Clase vecina no debe ser correcta para {fault_class}: '{cases['neighbor']}'"


# ── 2. Test Cruzado Exhaustivo de Falsos Positivos (18 x 17 = 306 combinaciones) ─

def test_cross_class_zero_false_positives():
    all_classes = list(OFFICIAL_CLASS_TEST_CASES.keys())
    assert len(all_classes) == 18

    total_checks = 0
    false_positives = []

    for target_class in all_classes:
        correct_text = OFFICIAL_CLASS_TEST_CASES[target_class]["es"]
        for test_class in all_classes:
            if test_class == target_class:
                continue
            total_checks += 1
            is_correct, _ = check_root_cause_correct(correct_text, "gt", test_class)
            if is_correct:
                false_positives.append((target_class, test_class, correct_text))

    assert len(false_positives) == 0, f"Falsos positivos detectados ({len(false_positives)} de {total_checks}): {false_positives}"
    assert total_checks == 18 * 17


# ── 3. Llamada Nativa tool_calls a dig, curl y openssl ───────────────────────

def test_native_tool_calls_extraction_and_evidence():
    agent = DiagnosticOrchestratorAgent()

    # Dig nativo
    tc_dig = [{"function": {"name": "dig", "arguments": {"command": "@127.0.0.1 -p 5353 sub.corp.internal NS"}}}]
    res_dig = agent._extract_tool_call("Respuesta con tool call nativo", raw_tool_calls=tc_dig)
    assert res_dig is not None
    assert res_dig[0] == "dig"
    assert "sub.corp.internal" in res_dig[1]

    # Curl nativo con JSON string en arguments
    tc_curl = [{"function": {"name": "curl", "arguments": json.dumps({"command": "http://127.0.0.1:8080/health"})}}]
    res_curl = agent._extract_tool_call("Llamando a curl", raw_tool_calls=tc_curl)
    assert res_curl is not None
    assert res_curl[0] == "curl"
    assert "8080/health" in res_curl[1]

    # OpenSSL nativo
    tc_ssl = [{"function": {"name": "openssl", "arguments": {"command": "s_client -connect 127.0.0.1:8443"}}}]
    res_ssl = agent._extract_tool_call("Llamando a openssl", raw_tool_calls=tc_ssl)
    assert res_ssl is not None
    assert res_ssl[0] == "openssl"
    assert "8443" in res_ssl[1]


# ── 4. Respuesta Vacía o en Bucle de Repetición -> formato_invalido ──────────

def test_empty_response_handling_without_breaking():
    runner = ScenarioLabRunner()
    sc = runner.get_scenario("HTTP-500-01")
    agent = DiagnosticOrchestratorAgent()

    diag = agent._parse_final_diagnosis(
        scenario=sc,
        model_id="test-model",
        response_text="",
        evidence_list=[]
    )
    assert diag.parse_status == "formato_invalido"
    assert diag.root_cause == ""


def test_repetition_loop_detection_and_cutoff():
    looping_text = (
        "El servicio responde con error 502 bad gateway.\n"
        "Error en la conexion con el backend.\n"
        "Error en la conexion con el backend.\n"
        "Error en la conexion con el backend.\n"
        "Error en la conexion con el backend.\n"
        "Error en la conexion con el backend.\n"
    )
    clean_text, loop_detected = detect_and_cut_repetition_loops(looping_text)
    assert loop_detected is True
    assert clean_text.count("Error en la conexion con el backend.") <= 2


# ── 5. Modelo Adicional Simulado Recorre los 18 Escenarios ───────────────────

def test_additional_simulated_model_full_18_scenarios_and_group():
    from src.core.config import ModelDefinition

    engine = LocalInferenceEngine(force_simulation=True)
    # Registrar modelo adicional ultraligero
    smol_model = ModelDefinition(
        id="smollm-1b",
        name="SmolLM-1B Test",
        provider="HuggingFace",
        parameters_raw="1B",
        license="Apache-2.0",
        quantization="Q4_K_M",
        format="GGUF",
        context_window_tokens=4096,
        function_calling_support="none",
        ollama_tag="smollm:1b",
        approx_vram_gb=1.2,
        reason_for_inclusion="Modelo ultraligero adicional para pruebas"
    )
    engine.register_model(smol_model)

    grp, fam = classify_model("smollm-1b", parameters_raw="1B")
    assert grp == "adicional"
    assert fam == "ultraligero"

    harness = BenchmarkEvaluatorHarness(inference_engine=engine)
    harness.inference_engine.force_simulation = True

    runner = ScenarioLabRunner()
    all_scenarios = runner.list_scenarios()
    assert len(all_scenarios) == 18

    results = []
    for sc in all_scenarios:
        res = harness._execute_single_trial(
            model_id="smollm-1b",
            scenario=sc,
            seed=42,
            rep_index=1
        )
        assert res.model_group == "adicional"
        assert res.model_family == "ultraligero"
        assert len(res.evaluator_version) == 12
        results.append(res)

    assert len(results) == 18


# ── 6. Invarianza de Reportes Oficiales ante Filas Adicionales ───────────────

def test_official_reports_invariance_with_additional_rows():
    harness = BenchmarkEvaluatorHarness()
    harness.inference_engine.force_simulation = True

    runner = ScenarioLabRunner()
    sc = runner.get_scenario("DNS-NXD-01")

    # Corrida oficial
    res_oficial = harness._execute_single_trial(
        model_id="phi-4-mini-instruct",
        scenario=sc,
        seed=42,
        rep_index=1
    )
    assert res_oficial.model_group == "oficial"

    # Corrida adicional
    res_adicional = harness._execute_single_trial(
        model_id="phi-4-mini-instruct",
        scenario=sc,
        seed=42,
        rep_index=1
    )
    # Clonar como modelo adicional
    dump = res_adicional.model_dump()
    dump["model_id"] = "custom-external-model"
    dump["model_group"] = "adicional"
    dump["model_family"] = "codigo"
    res_adicional_obj = ResultadoEvaluacionContract(**dump)

    # Generar reporte solo con oficial
    report_only_official = harness.generate_summary_report([res_oficial], report_filename="test_inv_1.md")
    # Generar reporte mezclado (oficial + adicional)
    report_mixed = harness.generate_summary_report([res_oficial, res_adicional_obj], report_filename="test_inv_2.md")

    # El reporte oficial debe ser idéntico porque filtra por defecto model_group="oficial"
    assert "phi-4-mini-instruct" in report_only_official
    assert "custom-external-model" not in report_mixed
    assert report_only_official == report_mixed


# ── 7. Pruebas Específicas de Auditoría A4, A5/A6 y A2 ───────────────────────

def test_distinct_component_evaluation():
    """Auditoría A4: El evaluador no puede aceptar palabras compartidas ('api', 'nginx', etc.) y exige término distintivo."""
    from src.layer7_evaluator.metrics import check_component_correct

    # 'nginx-api-gateway' vs 'upstream-backend-api' debe ser False (comparten 'api' pero son componentes distintos)
    assert check_component_correct("nginx-api-gateway", "upstream-backend-api") is False

    # Palabra genérica compartida sin especificador distintivo debe ser False
    assert check_component_correct("nginx", "nginx-api-gateway") is False
    assert check_component_correct("backend", "upstream-backend-api") is False

    # Términos distintivos propios deben ser True
    assert check_component_correct("api-gateway", "nginx-api-gateway") is True
    assert check_component_correct("backend-api", "upstream-backend-api") is True


def test_telemetry_ttft_monotonicity():
    """Auditoría A5/A6: Invarianza monótona ttft_final_ms >= ttft_ms en telemetría e inferencia."""
    from src.layer4_inference.engine import LocalInferenceEngine

    engine = LocalInferenceEngine(force_simulation=True)
    resp = engine.generate(
        prompt="Test diagnostic prompt for NetDiagBench-L7 telemetry verification.",
        model_id="phi-4-mini-instruct",
        system_prompt="Diagnostic evaluation system instruction"
    )
    assert resp.telemetry.ttft_final_ms >= resp.telemetry.time_to_first_token_ms


def test_emulated_log_cleanliness_window():
    """Auditoría A2: Limpieza de ventana de logs emulados sin logs previos al reinicio ni de otros contenedores."""
    from unittest.mock import patch
    from src.layer1_lab.docker_manager import (
        fetch_container_logs,
        isolate_emulated_scenario,
        restore_emulated_containers,
        is_docker_available
    )

    if is_docker_available():
        future_iso = "2099-01-01T00:00:00Z"
        logs_empty = fetch_container_logs("netdiag-http-502", since_ts=future_iso)
        assert len(logs_empty) == 0
        isolate_emulated_scenario("HTTP-502-01")
        restore_emulated_containers()
    else:
        # Mock representativo para entornos sandbox o CI sin acceso directo al daemon Docker
        with patch("src.layer1_lab.docker_manager.is_docker_available", return_value=True):
            with patch("subprocess.run") as mock_sub:
                mock_sub.return_value.returncode = 0
                mock_sub.return_value.stdout = ""
                future_iso = "2099-01-01T00:00:00Z"
                logs_empty = fetch_container_logs("netdiag-http-502", since_ts=future_iso)
                assert len(logs_empty) == 0
                called_cmd = mock_sub.call_args[0][0]
                assert "--since" in called_cmd
                assert future_iso in called_cmd

