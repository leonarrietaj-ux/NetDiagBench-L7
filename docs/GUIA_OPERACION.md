# NetDiagBench-L7 • Guía de Operación del Sistema

**Proyecto:** NetDiagBench-L7: Benchmark Agéntico de Diagnóstico de Redes Layer 7 sobre IP  
**Versión:** 1.0.3 | **Fecha:** Noviembre 2026 | **Entorno:** Local-First Web Dashboard & CLI  

---

## 1. Guía de Inicio Rápido
1. Ejecute el script de inicio rápido:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\launch_demo.ps1
   ```
2. Abra su navegador web en `http://localhost:8000`.

---

## 2. Vistas Principales de la Aplicación
1. **Visor de Diagnóstico (Tecla 1):** Permite configurar escenario, modelo y semilla para ejecutar el diagnóstico interactivo en streaming con observabilidad en tiempo real y traza CoT paso a paso.
2. **Informe Comparativo OE4 (Tecla 2):** Matriz multidimensional con perfiles de modelo (NOC vs Recursos Acotados vs Triaje Rápido), scores compuestos y descomposiciones de latencia y telemetría de hardware.
3. **Análisis Correlacional SciPy (Tecla 3):** Pruebas de hipótesis no paramétricas Kruskal-Wallis, prueba de Friedman pareada en 54 bloques, correlación de Spearman, intervalos de confianza Bootstrap percentil al 95% y tamaños de efecto.
4. **Informe Consolidado HTML (Tecla 4):** Vista documental interactiva para consulta unificada de las especificaciones y reportes del benchmark.
5. **Suite de Observabilidad (Tecla 5):** Ejecución desatendida y secuencial de los 18 escenarios catalogados (100% en memoria RAM vía LangGraph MemorySaver).
6. **Validación Humana y Calibración Inter-Evaluador (Capa 8):** Módulo de auditoría ciega, exportación de kits de evaluación, captura de rúbricas (C1 a C6 y Suficiencia S) y cálculo de concordancia inter-evaluador (Kappa Cohen, ICC 2,1, Alfa Krippendorff).

---

## 3. Atajos de Teclado y Paleta de Comandos
- `Ctrl + K`: Abrir paleta de comandos rápida.
- `Ctrl + Enter`: Ejecutar diagnóstico del escenario activo.
- `1` a `6`: Conmutar instantáneamente entre vistas principales (incluyendo Validación Humana).
- Botón de Luna / Sol: Alternar entre Tema Oscuro y Tema Claro.

---

## 4. Exportación de Resultados
La barra flotante superior derecha permite exportar en:
- **Excel (.xlsx):** Libro multioja con fórmulas, formato condicional y gráficos.
- **PDF Institucional:** Reporte formal para sustentación y archivo académico.
- **JSON / CSV:** Archivos planos de datos para análisis externo en Python o R.

---

## 5. Postura de Seguridad y Buenas Prácticas para el Operador

NetDiagBench-L7 fue concebido bajo el principio de **cero confianza y aislamiento estricto**. El operador puede interactuar con el sistema con total certidumbre gracias a las siguientes salvaguardas:

### 5.1. Aislamiento 100% Local y Privacidad de Datos
- **Sin Conectividad Saliente:** El sistema no contacta APIs externas (OpenAI, Anthropic, etc.) ni emite telemetría hacia la nube.
- **Inferencia en el Host:** Todos los modelos corren localmente en Ollama (`Q4_K_M`) sin enviar consultas fuera del equipo.
- **Protección Anti-SSRF:** Las herramientas de red del agente bloquean accesos a direcciones de metadatos de proveedores cloud (AWS, Alibaba, GCP, Tencent) y servicios internos de Kubernetes.

### 5.2. Herramientas Read-Only No Invasivas
- Las herramientas ejecutadas por los agentes (`dig`, `curl`, `openssl s_client`) operan estrictamente en modo lectura.
- El agente no puede modificar configuraciones del sistema operativo, iptables, DNS ni bases de datos.

### 5.3. Navegación Web Protegida
- El Dashboard Web incorpora cabeceras de seguridad conformes a OWASP:
  - `Content-Security-Policy`: Impide la carga de scripts o recursos desde orígenes no confiables.
  - `X-Frame-Options: DENY`: Evita ataques de Clickjacking.
  - `X-Content-Type-Options: nosniff`: Previene ataques de confusión de tipos MIME.
  - `Cross-Origin-Opener-Policy`: Aísla el contexto de navegación.

### 5.4. Verificación de Seguridad del Sistema
El operador puede verificar en cualquier momento el estado de las protecciones de seguridad ejecutando:
```powershell
.venv\Scripts\pytest.exe tests/test_security_audit.py -v
```
Para mayores detalles técnicos de la auditoría, consulte [`SEGURIDAD_SISTEMA.md`](SEGURIDAD_SISTEMA.md).

---

## 6. Resultados Oficiales Certificados del Benchmark

Al consultar los informes o la vista de resultados, el operador observará las métricas oficiales congeladas de la campaña de 162 corridas (3 réplicas x 18 escenarios x 3 modelos con semillas `42, 1337, 2026`):

- **Aciertos Diagnósticos Completos (`full_text`):** **122 / 162 (75.3%)**
  - Qwen3-8B: 47 / 54 (87.0%)
  - GLM-4-9B-Chat: 40 / 54 (74.1%)
  - Phi-4-mini-instruct: 35 / 54 (64.8%)
- **Aciertos Estrictos (`root_cause`):** **71 / 162 (43.8%)**
  - GLM-4-9B-Chat: 33 / 54 (61.1%)
  - Qwen3-8B: 24 / 54 (44.4%)
  - Phi-4-mini-instruct: 14 / 54 (25.9%)
- **Coincidencia de Clase Canónica (`fault_class`):** **120 / 162 (74.1%)**
  - Qwen3-8B: 47 / 54 (87.0%)
  - GLM-4-9B-Chat: 40 / 54 (74.1%)
  - Phi-4-mini-instruct: 33 / 54 (61.1%)
- **Rúbrica Humana Adjudicada:** GLM-4-9B: 4.13/5.0 | Qwen3-8B: 4.07/5.0 | Phi-4-mini: 3.55/5.0

