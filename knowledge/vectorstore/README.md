# NetDiagBench-L7: Vectorstore y Recuperador Semántico Bounded (Capa 3)

Este directorio documenta el almacenamiento y estado del motor de Recuperación Aumentada por Generación (RAG) de Capa 3 (`src/layer3_rag/retriever.py`).

---

## 1. Principio de Diseño: Recuperador Acotado (Bounded RAG)

Conforme a lo estipulado en la metodología del proyecto de grado:
- **Presupuesto Máximo de Memoria RAM:** ≤ 0.45 GB (450 MB).
- **Consumo Real Medido:** **0.02 MB** (Índice BM25 estructurado de 17 fragmentos normativos).
- **Congelamiento de Índice:** El índice se construye una sola vez al inicializar el sistema a partir de los documentos normativos ubicados en `knowledge/docs/` y se congela permanentemente, garantizando que todos los modelos evaluados reciban idéntico contexto sin deriva temporal.

---

## 2. Documentos Normativos Indexados

1. **`rfc1035_dns_excerpts.md`:** Especificación estándar de códigos de retorno DNS (`RCODE 0`, `RCODE 2 / SERVFAIL`, `RCODE 3 / NXDOMAIN`) y tipos de registros (`A`, `NS`, `SOA`, `CNAME`).
2. **`rfc9110_http_excerpts.md`:** Semántica de respuestas de error de servidor (`500 Internal Server Error`, `502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`).
3. **`rfc8446_tls_excerpts.md`:** Protocolo de alertas y negociación de seguridad TLS 1.3 (`bad_certificate`, `certificate_expired`, `unknown_ca`, `handshake_failure`).
4. **`sop_dns_troubleshooting.md`:** Procedimiento operativo estándar (SOP) para diagnóstico de servidores BIND9, resolución recursiva y delegación de zonas.
5. **`sop_nginx_gateway_troubleshooting.md`:** Procedimiento operativo estándar (SOP) para resolución de incidentes en pasarelas Nginx, agotamiento de sockets de backend y clusters upstream.
