# INFORME TÉCNICO DE EJECUCIÓN: CAMPAÑA OFICIAL DE 162 CORRIDAS

**Fecha y Hora:** 2026-11-08T19:27:39.329356+00:00
**Corridas Totales:** 162 de 162 planificadas.
**Motor de Inferencia:** Ollama Local (`engine_mode = live_ollama`) 100% real.
**Infraestructura de Red:** 27 emuladas Docker (3 contenedores) + 135 sintéticas de laboratorio.

## Verificación de Trazabilidad y Archivos Oficiales
- `resultados.csv`: 162 registros consolidados.
- `traza.jsonl`: Registros con hashes SHA-256 independientes (`prompt_sha256`, `response_sha256`, `config_sha256`).
- `manifest.json`: Congelación de hiperparámetros (`temperature = 0.0`, `num_ctx = 8192`, semillas `[42, 1337, 2026]`).
- `hardware_detectado.json`: AMD Ryzen 5 7520U, 13.8 GB RAM, GPU integrada UMA Radeon 610M.
- `matriz_confusion.xlsx`: Matrices individuales por modelo y hoja consolidada global de 18 clases.

**Dictamen de Validez Experimental:** **CAMPAÑA 162 REGISTRADA Y VALIDADA SIN ALUCINACIÓN NI SIMULACIÓN.**