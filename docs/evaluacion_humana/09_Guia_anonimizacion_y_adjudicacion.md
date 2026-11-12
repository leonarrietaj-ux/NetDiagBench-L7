# Guía de anonimización, aleatorización y adjudicación

1. Mantener una tabla maestra reservada que vincule `blind_response_id` con `run_id`, modelo y demás metadatos. Solo el coordinador conserva esta llave.
2. Eliminar de los paquetes de evaluación nombre del modelo, proveedor, tamaño, cuantización, ranking, score compuesto y etiquetas de simulador/live que puedan revelar el sistema.
3. Mantener visible el escenario y sus hechos técnicos necesarios para valorar exactitud. La verdad de referencia debe derivarse del YAML y de los resultados observados, no de una suposición.
4. No editar la respuesta del modelo. Si se necesita ocultar metadatos, hacerlo en una copia de presentación y conservar el original íntegro.
5. Aleatorizar el orden por evaluador y guardar semilla y algoritmo.
6. E1 y E2 califican sin comunicarse ni ver la hoja del otro.
7. Congelar las evaluaciones antes de calcular concordancia.
8. Enviar a E3 únicamente discrepancias o casos que el protocolo defina como no evaluables.
9. E3 registra criterio, decisión, razonamiento y evidencia. Nunca sobrescribe las columnas de E1/E2.
10. Publicar resultados agregados sin identificar a los expertos, salvo autorización explícita.
