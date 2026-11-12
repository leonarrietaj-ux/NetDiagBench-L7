# RFC 9110: HTTP Semantics (Fragmentos Operativos para Diagnóstico)

## 15.5. Client Error 4xx
Los códigos de estado 4xx indican que el cliente parece haber cometido un error en la solicitud.

### 15.5.4. 403 Forbidden - Control de Acceso y Reglas WAF (HTTP_403_FORBIDDEN / HTTP-403-01)
El código 403 indica que el servidor comprendió la solicitud pero se niega a autorizarla. En proxies inversos y API Gateways Nginx, este código se genera cuando una lista de control de acceso IP (`deny all` / `allow`), filtro de red o directiva de autenticación bloquea la dirección del cliente para la ruta solicitada (ej. `/admin/system/status`). Diagnóstico: `curl -I -s http://127.0.0.1:80/admin/system/status`.

### 15.5.28. 429 Too Many Requests - Limitación de Tasa (HTTP_429_RATE_LIMITED / HTTP-429-01)
El código 429 indica que el cliente ha enviado demasiadas solicitudes en un intervalo de tiempo dado (rate limiting). Implementado típicamente en módulos como `ngx_http_limit_req_module` mediante algoritmo leaky bucket. Diagnóstico: `curl -I -s http://127.0.0.1:80/api/v1/search?q=telecom`.

## 15.6. Server Error 5xx
Los códigos de estado de la clase 5xx indican que el servidor es consciente de que ha fallado o es incapaz de ejecutar la solicitud.

### 15.6.1. 500 Internal Server Error (HTTP_500_INTERNAL / HTTP-500-01)
El código 500 indica que el servidor encontró una condición inesperada que le impidió cumplir la solicitud. Comúnmente causado por excepciones no capturadas en aplicaciones web o scripts CGI (ej. `KeyError: user_id`). Diagnóstico: `curl -I -s http://127.0.0.1:80/api/v1/checkout`.

### 15.6.3. 502 Bad Gateway (HTTP_502_BAD_GATEWAY / HTTP-502-01 / ORIGIN_DOWN / HTTP-ORIGIN-01)
El código 502 indica que el servidor, al actuar como una puerta de enlace (gateway) o intermediario (proxy inverso), recibió una respuesta no válida o ninguna respuesta del servidor entrante (upstream) al que intentó acceder para completar la solicitud.
Causas típicas:
- El servicio upstream está apagado o no escucha en la dirección IP/puerto configurados (`connect() failed 111: Connection refused`).
- Todos los nodos del backend fallaron los health checks (`no live upstreams while connecting to upstream`).
- El upstream cerró abruptamente la conexión TCP antes de enviar encabezados HTTP completos.
- Diagnóstico: `curl -I -s http://127.0.0.1:80/api/v1/users` o `curl -I -s http://127.0.0.1:80/api/v1/health`.

### 15.6.4. 503 Service Unavailable (HTTP_503_SERVICE_UNAVAILABLE / HTTP-503-01 / CONNECTION_POOL_EXHAUSTED / HTTP-POOL-01)
El código 503 indica que el servidor no puede atender la solicitud debido a una sobrecarga temporal de peticiones o a que el pool de conexiones upstream (`worker_connections` o `keepalive pool`) se encuentra completamente agotado. Diagnóstico: `curl -I -s http://127.0.0.1:80/api/v1/orders`.

### 15.6.5. 504 Gateway Timeout (HTTP_504_GATEWAY_TIMEOUT / HTTP-504-01 / NETWORK_LATENCY_TC / NET-LAT-01)
El código 504 indica que el servidor intermediario no recibió una respuesta a tiempo del servidor ascendente (upstream) antes de vencer el temporizador `proxy_read_timeout` (110: Connection timed out). También se produce cuando existe degradación severa de latencia inducida en el canal de red. Diagnóstico: `curl -I -s http://127.0.0.1:80/api/v1/reports` o `ping -c 4 127.0.0.1`.
