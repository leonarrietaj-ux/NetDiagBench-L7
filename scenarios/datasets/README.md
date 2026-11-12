# NetDiagBench-L7: Datasets de Registros y Telemetría de Red

Este directorio almacena las fuentes de registros crudos, trazas sintéticas deterministas y registros del repositorio público Loghub para evaluación y entrenamiento de modelos.

---

## 1. Fuentes de Registros

1. **Generador Sintético Determinista (`src/layer1_lab/runner.py`):**
   - Produce secuencias temporales de registros para BIND9 y Nginx basadas en las plantillas extraídas de incidentes operacionales reales.
   - Controlado mediante semillas deterministas (`seed = 42, 1337, 2026`).
2. **Esquema de Registros de Red:**
   - `timestamp`: Marca temporal con resolución de segundos (`YYYY-MM-DD HH:MM:SS`).
   - `source_service`: Servicio generador (`bind9`, `bind9-authoritative`, `nginx`, `nginx-ssl`).
   - `log_level`: Severidad (`INFO`, `WARNING`, `ERROR`, `CRITICAL`).
   - `raw_message`: Mensaje textual crudo procesado posteriormente por el analizador `Drain3` (Capa 2).
   - `code`: Código de protocolo (`NXDOMAIN`, `SERVFAIL`, `502`, `504`, `500`, `TLS_EXP`).
3. **Métricas de Telemetría Asociadas:**
   - Latencia percentil 50 ($p_{50}$) y percentil 95 ($p_{95}$) en milisegundos.
   - Tasa de error porcentual (`error_rate_pct`).
   - Conteo de muestras de tráfico (`sample_count`).
