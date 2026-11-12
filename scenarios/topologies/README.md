# NetDiagBench-L7: Topologías de Red en Containerlab (Capa 1)

Este directorio alberga las especificaciones de topología declarativas de **Containerlab** para la emulación reproducible de servicios de Capa de Aplicación sobre redes IP aisladas.

---

## 1. Topologías Disponibles

### 1.1. Topología DNS (`clab-dns.clab.yml`)
Emula una infraestructura jerárquica de resolución de nombres DNS:
- **`dns-client` (Alpine Linux):** Generador de tráfico sintético mediante `dig` y utilidades de `bind-tools`.
- **`bind9-recursive` (ISC BIND 9.19):** Servidor resolutor recursivo local configurado para reenvío y validación.
- **`bind9-authoritative` (ISC BIND 9.19):** Servidor de nombres autoritativo para la zona `corp.internal`.
- **Fallas soportadas:**
  - `DNS-NXD-01`: Registro inexistente en la zona autoritativa (RCODE 3).
  - `DNS-SRV-01`: Descarte de paquetes o timeout hacia el servidor remoto (RCODE 2 / SERVFAIL).
  - `DNS-DEL-01`: Registros NS desincronizados entre la zona padre y la delegada (*lame delegation*).

**Comando de despliegue:**
```bash
sudo clab deploy -t scenarios/topologies/clab-dns.clab.yml
```

---

### 1.2. Topología Web / HTTP / TLS (`clab-web.clab.yml`)
Emula una arquitectura moderna de microservicios con proxy inverso y balanceador de carga:
- **`http-client` (Alpine Linux):** Emisor de solicitudes HTTP/HTTPS mediante `curl` y `openssl`.
- **`nginx-proxy` (Nginx 1.27-Alpine):** Terminación TLS, enrutamiento por rutas `/api/v1/` y balanceo hacia upstream.
- **`backend-api-1` / `backend-api-2` (Python 3.12 / FastAPI):** Microservicios de aplicación y bases de datos simuladas.
- **Fallas soportadas:**
  - `HTTP-502-01`: Servicio de backend caído (Connection Refused).
  - `HTTP-504-01`: Backend con latencia superior a 60s (Gateway Timeout).
  - `HTTP-500-01`: Excepción no controlada en la aplicación (`KeyError`).
  - `HTTP-ORIGIN-01`: Todos los backends inalcanzables (*no live upstreams*).
  - `HTTP-POOL-01`: Límite de conexiones simultáneas excedido en el pool.
  - `NET-LAT-01`: Retardo artificial extremo y fluctuación con `tc netem`.
  - `TLS-EXP-01`: Certificado digital X.509 expirado.
  - `TLS-CHN-01`: Omisión del certificado intermedio de la CA emisora.

**Comando de despliegue:**
```bash
sudo clab deploy -t scenarios/topologies/clab-web.clab.yml
```

---

## 2. Destrucción y Limpieza de Recursos

Para desmontar las redes virtuales y liberar memoria:
```bash
sudo clab destroy -t scenarios/topologies/clab-dns.clab.yml
sudo clab destroy -t scenarios/topologies/clab-web.clab.yml
```

---

## 3. Modo Simulado Determinista (Sin Docker)

Para entornos donde Docker o Containerlab no estén disponibles o en sistemas Windows convencionales, el framework NetDiagBench-L7 opera mediante su **Simulador de Laboratorio Determinista de Capa 1** (`src/layer1_lab/runner.py`), produciendo logs y telemetría idénticos a los generados en contenedores reales para cada semilla fijada.
