# NetDiagBench-L7: Inyectores de Falla de Capa 7 (Capa 1)

Este directorio contiene los módulos de inyección programática de anomalías de red para reproducir condiciones de falla L7 en entornos reales y simulados.

---

## 1. Inyectores Implementados

### 1.1. Inyector DNS (`dns_failures.py`)
Clase `DNSFailureInjector`:
- `prepare_injection(fault_class, seed)`: Configura retardos aleatorios y perfiles de inyección.
- `generate_affected_logs(fault_class, seed, count)`: Emite trazas de error de BIND9.
- **Perfiles de Inyección:**
  - `NXDOMAIN`: Ausencia intencional del registro de tipo A en la zona autoritativa (`app.internal.corp`).
  - `SERVFAIL`: Regla de descarte de paquetes UDP/53 con `iptables -A INPUT -p udp --dport 53 -j DROP` para forzar timeout recursivo.
  - `DELEGATION_ERROR`: Registros NS configurados hacia servidores de nombres que no reconocen la autoridad de la zona delegada (*lame delegation*).

### 1.2. Inyector HTTP / TLS / Gateway (`http_failures.py`)
Clase `HTTPFailureInjector`:
- **Perfiles de Inyección:**
  - `HTTP_502_BAD_GATEWAY`: Detención del proceso de backend FastAPI (`systemctl stop backend` o `kill -9`).
  - `HTTP_504_GATEWAY_TIMEOUT`: Inyección de retardo de 65s superando el `proxy_read_timeout` de 60s en Nginx.
  - `HTTP_500_INTERNAL`: Inducción de excepción no controlada (`KeyError: 'user_id'`) en la ruta `/api/v1/checkout`.
  - `ORIGIN_DOWN`: Apagado simultáneo de todos los miembros del upstream cluster.
  - `CONNECTION_POOL_EXHAUSTED`: Saturación del pool de conexiones persistentes de Nginx (`worker_connections are not enough`).
  - `NETWORK_LATENCY_TC`: Retardo de red artificial mediante Linux Traffic Control (`tc qdisc add dev eth0 root netem delay 2000ms 500ms`).
  - `TLS_EXPIRED_CERT`: Sustitución del certificado X.509 activo por uno expirado (`notAfter < fecha_actual`).
  - `TLS_CHAIN_INVALID`: Supresión del certificado intermedio de la CA emisora en la directiva `ssl_certificate`.
