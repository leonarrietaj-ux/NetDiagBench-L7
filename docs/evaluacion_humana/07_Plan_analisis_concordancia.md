# Plan de análisis de concordancia humana

## 1. Congelamiento
Antes del análisis, congelar la versión del archivo de calificaciones, la rúbrica validada en la Actividad A1.3 del cronograma de investigación y el inventario de casos. Registrar hashes SHA-256 y fecha.

## 2. Análisis primario
Para dos evaluadores:
- C1-C6: porcentaje de acuerdo exacto y kappa de Cohen ponderado. Definir antes del análisis si los pesos serán lineales o cuadráticos y mantener esa elección.
- S: porcentaje de acuerdo y kappa de Cohen no ponderado.
- Reportar número de pares completos por criterio.
- Informar distribución marginal de categorías, porque kappa puede verse afectado por prevalencia y desequilibrio de categorías.

No existe un umbral universal que convierta automáticamente un kappa en evaluación aceptable. Interpretarlo junto con intervalo de confianza, acuerdo observado, prevalencia, tamaño de muestra y consecuencias de desacuerdo.

## 3. Intervalos
Cuando el número de unidades y la distribución lo permitan, obtener intervalos de confianza percentiles mediante Bootstrap pareado por unidad de evaluación (1000 remuestreos, semilla registrada). No remuestrear las calificaciones de cada evaluador de manera independiente: el par de cada caso debe mantenerse unido.

## 4. Adjudicación
Solo después del análisis primario, enviar discrepancias al evaluador E3. Conservar E1 y E2 inalterados. Crear una tabla de decisiones adjudicadas y motivos.

## 5. Datos faltantes
No imputar automáticamente. Informar cuántos pares se excluyeron en cada criterio y por qué. El script utiliza únicamente pares completos.

## 6. Interpretación
Kappa no sustituye el análisis cualitativo. Revisar los desacuerdos por tipo: causa raíz, evidencia, componente, explicación o recomendación. La adjudicación puede identificar ambigüedades de la rúbrica que deban corregirse en una versión posterior.

## 7. Escala
El script de ejemplo asume que C1-C6 son ordinales codificados como enteros comparables. Antes de ejecutarlo, comprobar que la escala formalizada en la Actividad A1.3 realmente es ordinal y adaptar el script si no lo es. No convertir texto libre a números sin un diccionario aprobado.
