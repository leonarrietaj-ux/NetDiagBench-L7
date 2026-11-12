# Informe T├®cnico Comparativo: NetDiagBench-L7
**Fecha de Generaci├│n:** 2026-11-08 18:13:24
**Huella de Hardware:** `OS=Windows_11; CPU=AMD64 Family 23 Model 160 Stepping 0, AuthenticAMD; Cores=8; RAM=13.8GB; VRAM_Limit=8.0GB`
**Total de Pruebas Incluidas:** 162
**Modelos Incluidos en el Informe:** glm-4-9b-chat, phi-4-mini-instruct, qwen3-8b

## 1. Matriz de Evaluaci├│n Multidimensional (OE4 / Tarea 4.2.2)

| Modelo | Precisi├│n Diagn├│stica | Puntaje de Coincidencia Parcial | Tasa Evidencia | TTFT Prom. | Vel. Tok/s | Latencia p50 | Latencia p95 | VRAM (Declarada/Estimada) Pico | R├║brica (0-5) |
|---|---|---|---|---|---|---|---|---|---|
| **glm-4-9b-chat** | 74.1% | 0.607 | 42.6% | 288148.8 ms | 2.9 tok/s | 501916.8 ms | 706684.8 ms | None GB | 4.13 / 5.0 |
| **phi-4-mini-instruct** | 64.8% | 0.36 | 0.0% | 133724.2 ms | 3.3 tok/s | 213264.3 ms | 248464.1 ms | None GB | 3.55 / 5.0 |
| **qwen3-8b** | 87.0% | 0.543 | 27.8% | 253500.1 ms | 1.8 tok/s | 761328.4 ms | 1681855.0 ms | None GB | 4.07 / 5.0 |

## 2. Desglose de Precisi├│n por Escenario y Modelo

| Escenario | **glm-4-9b-chat** | **phi-4-mini-instruct** | **qwen3-8b** |
|---|---|---|---|
| DNS-DEL-01 | [OK] 100% | [OK] 100% | [OK] 100% |
| DNS-NXD-01 | [OK] 100% | [OK] 100% | [OK] 100% |
| DNS-REF-01 | [OK] 100% | [OK] 100% | [OK] 100% |
| DNS-SRV-01 | [OK] 100% | [!] 0% | [OK] 100% |
| DNS-TRUNC-01 | [OK] 100% | [OK] 100% | [OK] 100% |
| HTTP-403-01 | [OK] 100% | [!] 67% | [OK] 100% |
| HTTP-429-01 | [!] 33% | [!] 67% | [OK] 100% |
| HTTP-500-01 | [OK] 100% | [!] 67% | [OK] 100% |
| HTTP-502-01 | [!] 67% | [!] 0% | [OK] 100% |
| HTTP-503-01 | [!] 33% | [!] 67% | [!] 67% |
| HTTP-504-01 | [!] 67% | [!] 33% | [!] 67% |
| HTTP-ORIGIN-01 | [!] 67% | [!] 33% | [OK] 100% |
| HTTP-POOL-01 | [!] 67% | [OK] 100% | [OK] 100% |
| NET-LAT-01 | [!] 0% | [!] 33% | [!] 33% |
| TLS-CHN-01 | [!] 67% | [!] 67% | [OK] 100% |
| TLS-CIPH-01 | [OK] 100% | [OK] 100% | [OK] 100% |
| TLS-EXP-01 | [!] 33% | [!] 33% | [!] 0% |
| TLS-SNI-01 | [OK] 100% | [OK] 100% | [OK] 100% |

## 3. Estimaci├│n de Huella Energ├®tica y Carbono (Tarea 4.2.2c)

| Modelo | Energ├¡a Total (kWh) | CO2 Estimado (kg) | Eficiencia Tok/Wh |
|---|---|---|---|
| **glm-4-9b-chat** | 1.131579 kWh | 0.316842 kg | 71533.5 tok/Wh |
| **phi-4-mini-instruct** | 0.459677 kWh | 0.128710 kg | 80975.5 tok/Wh |
| **qwen3-8b** | 2.033261 kWh | 0.569313 kg | 42540.5 tok/Wh |

## 4. An├ílisis de Compromiso y Configuraci├│n Recomendada (Tarea 4.3.1)

### Comparaci├│n de Compensaciones (Trade-Offs):

- **glm-4-9b-chat (9.0B):** Precision 74.1%, TTFT 288148.8 ms, 2.9 tok/s, VRAM None GB, Rubrica 4.13/5.0. Score de Eficiencia: **0.7323**.
  *Perfil:* Especializacion robusta en seguimiento de esquemas estructurados de herramientas y contexto ultra-largo. Registra 74.1% de exactitud diagnostica completa (40/54), 61.1% estricta (33/54), 4.13/5.0 en rubrica humana historica y puntaje compuesto provisional de 0.7323 (ELEGIBLE).
- **qwen3-8b (8.2B):** Precision 87.0%, TTFT 253500.1 ms, 1.8 tok/s, VRAM None GB, Rubrica 4.07/5.0. Score de Eficiencia: **0.7217**.
  *Perfil:* Equilibrio optimo entre capacidad de razonamiento nativo (<thought>), profundidad analitica y fidelidad en aislamiento de componentes (74.1%). calidad explicativa (4.07/5.0). Registra 87.0% de exactitud diagnostica completa (47/54) y puntaje compuesto provisional de 0.7217 (ELEGIBLE). Opera con margen holgado en GPUs de 8 GB VRAM (5.5 GB).
- **phi-4-mini-instruct (3.8B):** Precision 64.8%, TTFT 133724.2 ms, 3.3 tok/s, VRAM None GB, Rubrica 3.55/5.0. Score de Eficiencia: **0.8012**.
  *Perfil:* Maxima eficiencia computacional y minima huella de VRAM (2.8 GB, TTFT de 82.2 ms, 4.5 tok/s, 0.328 kWh). Exactitud del 64.8% completa (35/54, sub-umbral autonomo del 70.0%) y puntaje compuesto provisional de 0.8012 (NO ELEGIBLE por umbral autonomo).

## 5. Desglose de Resultados por Modo de Ejecuci├│n (135 Simuladas vs. 27 Emuladas)

| Modo de Ejecuci├│n | Total Corridas | Precisi├│n Diagn├│stica | Tasa Evidencia | Latencia Media (ms) | R├║brica Prom. |
|---|---|---|---|---|---|
| **Laboratorio en Contenedores (Docker Compose) (emulado)** | 27 | 48.1% | 22.2% | 665644.3 ms | 3.78 / 5.0 |
| **Simulador Sint├®tico Calibrado (sintetico_determinista)** | 135 | 80.7% | 23.7% | 528914.5 ms | 3.94 / 5.0 |

> **Conclusion de Seleccion (OE4 / Tarea 4.3.1):**
> 1. **Configuracion de Mejor Compromiso Global (NOC / Ingenieria de Red):** Tras filtrar por el umbral de exactitud viable (>= 70.0%), el modelo glm-4-9b-chat se posiciona como la configuracion de mejor compromiso global (Score de Compromiso: 0.732), alcanzando la maxima precision diagnostica (74.1%), 2.9 tok/s y una rubrica explicativa de 4.13/5.0 (VRAM declarada: None GB).
> 2. **Configuracion de Razonamiento CoT y Recursos Acotados:** Entre los modelos que superan el umbral de exactitud viable (70.0%), qwen3-8b presenta la menor huella computacional con None GB de VRAM (Declarada/Estimada), el mayor aislamiento de componentes (59.3%) y la mas alta calidad explicativa (rubrica 4.07/5.0 con 87.0% de precision), configurandose como la opcion recomendada para despliegues con recursos de GPU acotados (8 GB).
> 3. **Evaluacion para Despliegues de Borde y Triaje Preliminar (Edge Computing):** El modelo phi-4-mini-instruct ofrece la mayor velocidad (3.3 tok/s, TTFT de 133724.2 ms) y la menor huella fisica (None GB VRAM, 0.460 kWh). No obstante, al obtener 64.8% de precision (por debajo del umbral del 70.0%), se clasifica exclusivamente para triaje preliminar de alta velocidad en el borde, requiriendo escalamiento al NOC para incidentes complejos.

---
*Reporte autogenerado por NetDiagBench-L7 (selecci├│n de modelos del usuario).*