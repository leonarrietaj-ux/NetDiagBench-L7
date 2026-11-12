# RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3
# Fragmentos Operativos para Diagnostico en Entornos de Red L7

## 6. Alert Protocol
Los mensajes de alerta transmiten la gravedad del mensaje (warning o fatal) y una descripcion de la alerta. Las alertas con nivel fatal ocasionan la terminacion inmediata de la conexion TLS.

### 6.2. Error Alerts
- **bad_certificate (42):** Se recibio un certificado que estaba corrupto, contenia firmas que no pudieron verificarse o campos con formato invalido.
- **unsupported_certificate (43):** Se recibio un certificado de un tipo no soportado por la implementacion.
- **certificate_revoked (44):** Se recibio un certificado que fue revocado por su Autoridad de Certificacion (CA) emisora.
- **certificate_expired (45):** Se recibio un certificado cuya validez temporal expiro (notAfter < fecha actual) o que todavia no es valido (notBefore > fecha actual).
- **unknown_ca (48):** Se recibio una cadena de certificados valida pero la Autoridad de Certificacion raiz o intermedia no pudo ser verificada o no se encuentra en el almacen de confianza local (Trust Store).
- **decrypt_error (51):** Fallo la verificacion de la firma del protocolo de enlace o la operacion criptografica de clave publica.
- **handshake_failure (40):** El remitente fue incapaz de negociar un conjunto aceptable de parametros de seguridad dados los ofrecidos por el extremo remoto.
- **unrecognized_name (112):** El servidor no reconoce el nombre de host indicado en la extension Server Name Indication (SNI).

### 6.2.1. Handshake Failure (40) y Discrepancia de Cifrado (TLS_CIPHER_MISMATCH / TLS-CIPH-01)
El emisor envia handshake_failure (codigo 40) cuando no hay interseccion común entre los cipher suites admitidos por el cliente (ClientHello) y los configurados en el servidor (ServerHello). Diagnóstico: `openssl s_client -connect 127.0.0.1:443 -cipher AES128-SHA`.

### 6.2.2. Certificate Expired (45) y Caducidad Temporal (TLS_EXPIRED_CERT / TLS-EXP-01)
Alerta certificate_expired (codigo 45) emitida cuando la fecha actual supera el periodo notAfter del certificado X.509 o verify return code es 10. Diagnóstico: `openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal`.

### 6.2.3. Unknown CA (48) y Cadena Intermedia Invalida (TLS_CHAIN_INVALID / TLS-CHN-01)
Alerta unknown_ca (codigo 48) o verify return code 20 (unable to get local issuer certificate) emitida cuando el bundle no incluye las autoridades de certificacion intermedias firmantes. Diagnóstico: `openssl s_client -connect 127.0.0.1:443 -showcerts`.

### 6.2.4. Hostname Mismatch (62 / 112) y Discrepancia SNI (TLS_SNI_MISMATCH / TLS-SNI-01)
Alerta unrecognized_name (112) o verify return code 62 emitida cuando el FQDN solicitado por el cliente en Server Name Indication (SNI) no coincide con los Subject Alternative Names (SAN) del certificado configurado. Diagnóstico: `openssl s_client -connect 127.0.0.1:443 -servername api-unregistered.corp.internal`.

## B.3. Closure and Verification Diagnostics
Para aislar anomalias en la negociacion TLS:
1. Comprobar la validez temporal del certificado del servidor mediante `openssl s_client -connect <host>:<port> -servername <sni>`.
2. Verificar la completitud de la cadena de confianza (Server Certificate + Intermediate CA Bundle).
3. Evaluar compatibilidad de suites criptograficas (Cipher Suites) y versiones TLS admitidas por el cliente y servidor.
