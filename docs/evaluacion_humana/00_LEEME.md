# Paquete de evaluación humana de NetDiagBench-L7

## Propósito
Este paquete prepara la evaluación humana de los diagnósticos generados por NetDiagBench-L7. No contiene calificaciones inventadas ni resultados de evaluadores. Son plantillas para completar con respuestas reales y con la rúbrica aprobada.

## Diseño recomendado
- Dos evaluadores expertos califican de forma independiente las mismas unidades de evaluación.
- Las respuestas se presentan con identificadores ciegos; se ocultan modelo, proveedor, orden de ranking y puntaje automático.
- Se conserva la identificación del escenario y la evidencia técnica necesaria para juzgar el diagnóstico.
- Un tercer evaluador interviene únicamente después de guardar las calificaciones independientes y calcular la concordancia inicial.
- La adjudicación no reemplaza ni sobrescribe las evaluaciones originales.
- Se recomienda evaluar inicialmente las 54 unidades existentes, si el inventario confirma que son 54 respuestas evaluables distintas. Si el número real difiere, ajustar el marco muestral y documentarlo.

## Archivos
1. `01_Protocolo_evaluacion_humana.docx`: protocolo de aplicación.
2. `02_Rubrica_y_matriz_evaluacion.xlsx`: libro para criterios, calificaciones, asignación y adjudicación.
3. `03_Formulario_individual_evaluador.docx`: ficha para calificar una respuesta.
4. `04_Consentimiento_y_confidencialidad.docx`: modelo de información y compromiso, sujeto a revisión institucional.
5. `05_Registro_evaluaciones.csv`: formato largo para análisis estadístico.
6. `06_Clave_tecnica_escenarios.csv`: plantilla para extraer la verdad de referencia desde los YAML.
7. `07_Plan_analisis_concordancia.md`: métricas y reglas de análisis.
8. `08_analizar_concordancia.py`: script de concordancia y Bootstrap.
9. `09_Guia_anonimizacion_y_adjudicacion.md`: procedimiento de cegamiento y resolución de discrepancias.

## Reglas que no se deben romper
- Transcribir C1-C6, descriptores y pesos exactamente desde la formalización metodológica de la Actividad A1.3 del cronograma de investigación.
- No inferir ni inventar pesos.
- No mostrar a los evaluadores el nombre del modelo ni su puntuación automática.
- No revelar al evaluador la respuesta esperada antes de que realice su calificación independiente, salvo que el protocolo aprobado requiera explícitamente una ficha de referencia.
- Para puntuar exactitud factual, el evaluador sí necesita acceso a los hechos verificables del escenario. Entregar la especificación técnica y las salidas observadas, no la identidad del modelo.
- No considerar `Sustentado = Sí` únicamente porque existe una evidencia. Debe existir respaldo factual de la conclusión y aplicarse la regla exacta aprobada en la rúbrica.
- No sustituir evaluaciones faltantes ni convertirlas en cero.
- No calcular concordancia con las notas adjudicadas.

## Flujo de trabajo
1. Congelar la versión del dataset y generar `case_id` y `blind_response_id`.
2. Extraer la clave técnica de cada escenario desde los archivos YAML y conservar ruta, versión y SHA-256.
3. Aleatorizar el orden de presentación por evaluador usando una semilla registrada.
4. Capacitar a los evaluadores con casos de práctica que no entren en el análisis principal.
5. Recoger las calificaciones de forma independiente.
6. Validar completitud y consistencia sin cambiar puntuaciones.
7. Calcular concordancia entre evaluadores.
8. Adjudicar discrepancias con el tercer experto.
9. Exportar datos originales, adjudicados y reporte estadístico por separado.

## Advertencia
El paquete es una propuesta operativa. Antes de aplicarlo, el equipo de investigación debe confirmar que el protocolo y la rúbrica coinciden con la formalización metodológica aprobada, los lineamientos éticos y los requisitos institucionales.
