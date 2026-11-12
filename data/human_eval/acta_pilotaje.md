# Acta de Pilotaje y Calibración Previa de la Rúbrica (Actividad A1.3)

**Proyecto:** NetDiagBench-L7 — Universidad de Pamplona  
**Lugar:** Laboratorio de Redes y Telemática  
**Fecha:** 2 de Noviembre de 2026  
**Participantes:** Evaluador E1, Evaluador E2, Evaluador E3 (Dirimente) y Director de Trabajo de Grado  

---

## 1. Objetivo de la Sesión de Pilotaje

Calibrar el entendimiento inter-evaluador de los seis criterios de la rúbrica aprobada (C1 a C6 y variable S), verificar la inteligibilidad de las fichas ciegas de inspección y ensayar el procedimiento de adjudicación sobre casos de prueba externos que **no forman parte de la muestra de 54 unidades del benchmark principal**.

---

## 2. Casos de Práctica Utilizados

Se utilizaron 3 diagnósticos sintéticos generados en pruebas de desarrollo previas:
1. **Caso Piloto P-01 (DNS):** Escenario de ServFail por timeout remoto. El diagnóstico identificó ServFail como causa raíz en lugar de la inalcanzabilidad del servidor autoritativo upstream.
   - *Acuerdo del panel:* Se aclara que clasificar ServFail como causa raíz y no como síntoma amerita calificación de 1 en C1 (parcial/síntoma), no 2.
2. **Caso Piloto P-02 (TLS):** Escenario de Certificado Caducado (`notAfter` superado). Diagnóstico propuso renovación y contrastó fecha con log de OpenSSL.
   - *Acuerdo del panel:* Calificación unánime de 2 en C1, 2 en C4, 2 en C5 y 2 en C6; variable S = Sí.
3. **Caso Piloto P-03 (HTTP):** Escenario de saturación de workers (503). Diagnóstico sugirió erróneamente renovar certificado SSL.
   - *Acuerdo del panel:* Calificación de 0 en C1 y 0 en C4. Falsa conclusión de protocolo vecino.

---

## 3. Acuerdos Técnicos y Reglas de Calibración

1. **Exactitud Factual (C6):**
   - Una salida de herramienta vacía, truncada con error o un comando no permitido que recibió sanción (`tool_blocked_penalty`) se califica estrictamente con `0`.
   - Si la herramienta confirma de forma incontrovertible la hipótesis planteada en la causa raíz, se califica con `2`.
2. **Variable S (Sustentado):**
   - La mera presencia de un bloque de comando en el diagnóstico no equivale a sustento técnico. Debe verificarse que la herramienta efectivamente respaldó la conclusión emitida.
3. **Congelamiento:**
   - Habiendo alcanzado acuerdo unánime sobre las definiciones operacionales de la rúbrica v3.0.0, se declara formalmente congelado el procedimiento para la aplicación de la prueba ciega sobre las 54 corridas del benchmark.

*Firmas de conformidad archivadas en el expediente del proyecto.*
