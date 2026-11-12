# Procedimiento Operativo Estándar: Diagnóstico de Fallas en Nginx Reverse Proxy y API Gateway (SOP-NGINX-01)

## 1. Alcance
Procedimiento para aislar e identificar la causa raíz de errores HTTP 5xx, 4xx, latencias y fallas de negociación TLS en arquitecturas con Nginx actuando como API Gateway o proxy inverso.

## 2. Clasificación de Síntomas y Árbol de Decisión

### 2.1. Síntoma: HTTP 502 Bad Gateway (HTTP_502_BAD_GATEWAY / HTTP-502-01)
- **Definición:** Nginx no pudo establecer comunicación con el servidor upstream o recibió una respuesta no válida a nivel de socket.
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `curl -I -s http://127.0.0.1:80/api/v1/users` para capturar encabezados HTTP.
  2. Consultar el archivo `error.log` de Nginx:
     - Si indica `connect() failed (111: Connection refused)`: el servicio backend está apagado o no escucha en el puerto.
  3. Ejecutar sondeo local hacia el socket del backend (`curl -I http://127.0.0.1:8080/health`).
  4. Verificar sockets activos y escucha en el puerto del backend (`ss -tlpn | grep -E '8080|80'`).
- **Causa Raíz Típica:**
  - Proceso de backend (FastAPI, Gunicorn, Node.js) detenido o caído tras fallo crítico en 127.0.0.1:8080.
- **Acción Correctiva:**
  - Reiniciar el servicio backend upstream y comprobar su escucha activa (`systemctl restart backend-app`).

### 2.2. Síntoma: HTTP 504 Gateway Timeout (HTTP_504_GATEWAY_TIMEOUT / HTTP-504-01)
- **Definición:** Nginx estableció conexión pero el backend no devolvió respuesta antes de que expirara el temporizador `proxy_read_timeout`.
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `curl -I -s http://127.0.0.1:80/api/v1/reports` para capturar encabezados HTTP.
  2. Revisar `error.log` buscando `upstream timed out (110: Connection timed out) while reading response header`.
  3. Medir la latencia directa del backend con solicitudes de prueba.
  4. Analizar métricas de CPU y consultas lentas en la base de datos subyacente.
- **Causa Raíz Típica:**
  - Bloqueo por contención en base de datos o cómputo intensivo no asíncrono en backend.
- **Acción Correctiva:**
  - Optimizar la consulta en base de datos o incrementar temporalmente `proxy_read_timeout` en Nginx (`nginx -s reload`).

### 2.3.1. Síntoma: Discrepancia de Cifrado TLS Handshake Failure (TLS_CIPHER_MISMATCH / TLS-CIPH-01)
- **Definición:** Fallo de negociación TLS (handshake_failure 40) debido a falta de coincidencia en los algoritmos criptográficos entre cliente y servidor.
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `openssl s_client -connect 127.0.0.1:443 -cipher AES128-SHA` para forzar la prueba de cifrado.
  2. Revisar `error.log` buscando `SSL_do_handshake() failed (SSL: error:0A000410:SSL routines::sslv3 alert handshake failure)`.
  3. Evaluar compatibilidad de suites de cifrado con `openssl ciphers -v 'HIGH:!aNULL:!MD5'`.
- **Causa Raíz Típica:**
  - Directiva `ssl_ciphers` restrictiva en Nginx o cliente ofreciendo únicamente suites heredadas incompatibles.
- **Acción Correctiva:**
  - Actualizar la directiva `ssl_ciphers` en `/etc/nginx/nginx.conf` y recargar (`nginx -s reload`).

### 2.3.2. Síntoma: Certificado TLS Expirado (TLS_EXPIRED_CERT / TLS-EXP-01)
- **Definición:** El certificado digital X.509 presentado por el servidor superó su fecha límite de validez notAfter (`certificate has expired`).
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal` y verificar `verify return code: 10 (certificate has expired)`.
  2. Ejecutar `curl -Iv https://secure.corp.internal` para comprobar el fallo a nivel de cliente.
  3. Inspeccionar fechas de validez con `openssl x509 -noout -dates`.
- **Causa Raíz Típica:**
  - Certificado SSL/TLS expirado sin renovación automática por Let's Encrypt o Certbot.
- **Acción Correctiva:**
  - Renovar el certificado digital X.509 expirado y recargar Nginx (`certbot renew && nginx -s reload`).

### 2.3.3. Síntoma: Cadena de Certificación Intermedia Inválida (TLS_CHAIN_INVALID / TLS-CHN-01)
- **Definición:** La cadena de confianza no puede validarse porque falta el certificado de la Autoridad de Certificación intermedia en el servidor (`unable to get local issuer certificate`).
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal` y comprobar `verify error:num=20:unable to get local issuer certificate`.
  2. Revisar `error.log` buscando `certificate verify failed`.
  3. Inspeccionar los certificados concatenados con `openssl crl2pkcs7 -nocrl -certfile fullchain.pem`.
- **Causa Raíz Típica:**
  - Paquete de CA intermedias (Intermediate CA Bundle) omitido en la directiva `ssl_certificate`.
- **Acción Correctiva:**
  - Concatenar el certificado intermedio en el archivo `fullchain.pem` y recargar Nginx (`cat intermediate.pem >> fullchain.pem && nginx -s reload`).

### 2.3.4. Síntoma: Discrepancia de Nombre SNI (TLS_SNI_MISMATCH / TLS-SNI-01)
- **Definición:** El FQDN solicitado por el cliente en la extensión SNI no coincide con los Subject Alternative Names (SAN) del certificado servidor servido (`Hostname mismatch`).
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `openssl s_client -connect 127.0.0.1:443 -servername api-unregistered.corp.internal` y verificar `verify error:num=62:Hostname mismatch`.
  2. Revisar `error.log` buscando `no matching SSL certificate for SNI host`.
  3. Inspeccionar los SANs del certificado con `openssl x509 -noout -text`.
- **Causa Raíz Típica:**
  - FQDN no configurado en los bloques `server_name` o ausente del certificado instalado.
- **Acción Correctiva:**
  - Añadir el FQDN en el bloque `server_name` o emitir un certificado multi-dominio con el SAN correspondiente y recargar Nginx (`nginx -s reload`).

### 2.4. Síntoma: HTTP 403 Forbidden y Filtro de Seguridad WAF (HTTP_403_FORBIDDEN / HTTP-403-01)
- **Definición:** El API Gateway o servidor proxy rechaza la petición por restricción de control de acceso IP (`deny all`) o regla WAF en la ruta protegida.
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `curl -I -s http://127.0.0.1:80/admin/system/status` y verificar `HTTP/1.1 403 Forbidden`.
  2. Consultar `error.log` buscando `access forbidden by rule, client: 127.0.0.1, server: api.corp.internal, request: GET /admin/system/status`.
  3. Revisar directivas `allow` y `deny` en `/etc/nginx/conf.d/admin.conf`.
- **Causa Raíz Típica:**
  - IP del cliente bloqueada o no autorizada en el bloque `location /admin/`.
- **Acción Correctiva:**
  - Modificar directiva `allow` en `/etc/nginx/conf.d/admin.conf` para autorizar la IP y recargar Nginx (`nginx -s reload`).

### 2.5. Síntoma: HTTP 429 Too Many Requests y Límite de Tasa (HTTP_429_RATE_LIMITED / HTTP-429-01)
- **Definición:** La frecuencia de peticiones del cliente supera la tasa configurada en el módulo de limitación de tráfico (`limit_req_zone`).
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `curl -I -s http://127.0.0.1:80/api/v1/search?q=telecom` y comprobar retorno de `HTTP/1.1 429 Too Many Requests`.
  2. Consultar `error.log` buscando `limiting requests, excess: ... by zone "req_limit_per_ip"`.
  3. Inspeccionar parámetros `rate` y `burst` de la directiva `limit_req`.
- **Causa Raíz Típica:**
  - Algoritmo leaky bucket activado por ráfagas intensas que superan la cuota asignada en la zona de limitación.
- **Acción Correctiva:**
  - Incrementar el parámetro `burst` o ajustar la tasa en `nginx.conf` y recargar (`nginx -s reload`).

### 2.6. Síntoma: HTTP 500 Internal Server Error (HTTP_500_INTERNAL / HTTP-500-01)
- **Definición:** El backend de aplicaciones falló debido a una excepción no controlada en tiempo de ejecución (`KeyError: user_id`).
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `curl -I -s http://127.0.0.1:80/api/v1/checkout` para validar `HTTP/1.1 500 Internal Server Error`.
  2. Consultar los logs del backend buscando traceback de error (`journalctl -u backend-app -n 50`).
- **Causa Raíz Típica:**
  - Error de código o clave de usuario inexistente en el payload procesado por el backend.
- **Acción Correctiva:**
  - Inspeccionar los logs con journalctl, identificar la excepción no controlada y corregir el código del microservicio (`journalctl -u backend-app -n 50`).

### 2.7. Síntoma: HTTP 503 Service Unavailable y Agotamiento de Pool (HTTP_503_SERVICE_UNAVAILABLE / HTTP-503-01 / CONNECTION_POOL_EXHAUSTED / HTTP-POOL-01)
- **Definición:** El servicio backend no puede atender peticiones por sobrecarga de workers o agotamiento de conexiones persistentes (`keepalive pool` / `worker_connections`).
- **Verificación Técnica Obligatoria:**
  1. Validar código 503 con `curl -I -s http://127.0.0.1:80/api/v1/orders` o `/api/v1/users`.
  2. Revisar logs de Nginx buscando `upstream temporarily unavailable` o `connection pool exhausted`.
  3. Inspeccionar sockets activos con `ss -s`.
- **Causa Raíz Típica:**
  - Concurrencia superior a la capacidad del pool de workers o conexiones keepalive insuficientes.
- **Acción Correctiva:**
  - Aumentar `worker_connections` y `keepalive` en Nginx o reiniciar el pool de la aplicación (`systemctl restart backend-application-pool` o `nginx -s reload`).

### 2.8. Síntoma: Servidor de Origen Inalcanzable (ORIGIN_DOWN / HTTP-ORIGIN-01)
- **Definición:** Todos los servidores upstream configurados en el clúster de origen están fuera de servicio o inalcanzables (`no live upstreams`).
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `curl -I -s http://127.0.0.1:80/api/v1/health` y validar respuesta 502 Bad Gateway.
  2. Consultar logs de Nginx buscando `no live upstreams while connecting to upstream`.
  3. Comprobar el estado del clúster de origen con `systemctl status upstream-cluster`.
- **Causa Raíz Típica:**
  - Caída total del clúster de servidores de origen o desconexión del socket de balanceo.
- **Acción Correctiva:**
  - Reiniciar el clúster upstream completo y verificar la conectividad de los nodos (`systemctl restart upstream-cluster`).

### 2.9. Síntoma: Latencia de Red Severa e Inyección de Retardo (NETWORK_LATENCY_TC / NET-LAT-01)
- **Definición:** Retardo artificial introducido mediante Traffic Control (`tc netem`) que provoca degradación extrema y timeouts en las peticiones HTTP.
- **Verificación Técnica Obligatoria:**
  1. Ejecutar `ping -c 4 127.0.0.1` y verificar que el RTT promedio supera los 2000 ms.
  2. Consultar reglas activas de control de tráfico con `tc qdisc show dev eth0`.
  3. Revisar logs de error de Nginx buscando timeouts asociados a la lentitud de red.
- **Causa Raíz Típica:**
  - Disciplina de cola `netem` configurada con retardo excesivo en la interfaz de red `eth0`.
- **Acción Correctiva:**
  - Eliminar la disciplina de cola tc netem en la interfaz eth0 para restaurar la latencia nominal (`tc qdisc del dev eth0 root`).
