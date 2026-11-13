# Resumen de concordancia de la evaluación humana

## 1. Diseño y muestra

La validación humana comprendió 54 casos, 18 por modelo, con dos evaluadores independientes (E1 y E2) y un tercer evaluador (E3) para resolver discrepancias. El archivo público data/human_eval/evaluaciones_adjudicadas.csv contiene 54 registros consolidados de adjudicación.

## 2. Resultados de la rúbrica humana

La puntuación humana v3.0.0 se calcula con C2, C3, C4 y C5:

\[
R_{\mathrm{humana}}=\operatorname{round}\left(\frac{C2+C3+C4+C5}{8}\times 5,\ 2\right)
\]

| Modelo | Rúbrica técnica, media (d. e.), n=54 | Rúbrica humana v3.0.0, media (d. e.), n=18 | S humano = Sí | C6 humano, media (0-2) | S automático = Sí |
|---|---:|---:|---:|---:|---:|
| GLM-4-9B-Chat | 4,13 (0,81) | 3,82 (0,83) | 14/18 | 1,33 | 23/54 (42,6 %) |
| Qwen3-8B | 4,07 (0,71) | 3,65 (1,10) | 13/18 | 1,22 | 15/54 (27,8 %) |
| Phi-4-mini-instruct | 3,55 (0,90) | 3,64 (0,84) | 15/18 | 1,39 | 0/54 (0,0 %) |

La rúbrica técnica se conserva en rubric_score. No debe rotularse como rúbrica humana. S humano y S automático tienen reglas operativas distintas: la primera refleja la valoración del panel sobre el diagnóstico y su soporte en los registros; la segunda requiere verificación activa con herramientas de solo lectura.

## 3. Coeficientes de concordancia comunicados

| Indicador | Valor | Muestra informada |
|---|---:|---:|
| Kappa de Cohen sobre S, casos de consenso | 0,932 | n=41 |
| Kappa de Cohen sobre S, con dirimente | 0,955 | n=54 |
| ICC(2,1), rúbrica continua | 0,786 | Evaluación global |
| Alfa de Krippendorff ordinal | 0,787 | Evaluación global |
| Kappa ponderado del puntaje total | 0,783 | Evaluación global |

El resumen de la evaluación registra 32 casos de consenso espontáneo entre E1 y E2 y 22 casos dirimidos por E3. Se conserva una discrepancia documental: el kappa de S para el subconjunto de consenso se comunica con n=41, mientras que el recuento de consenso espontáneo es 32. No se modifica ninguno de estos valores sin los formularios originales.

## 4. Alcance de la publicación

El repositorio contiene las 54 decisiones adjudicadas, pero no publica los 108 formularios originales independientes de E1 y E2 ni la matriz de asignación ciega. El archivo docs/evaluacion_humana/05_Registro_evaluaciones.csv es una plantilla vacía, no un registro de calificaciones.

Por esta razón, los coeficientes de la sección anterior se conservan como valores comunicados en el resumen de resultados. No se afirma que puedan recalcularse a partir de los archivos actualmente publicados. Para una reproducción independiente se requieren los registros originales anonimizados E1/E2 y la especificación de las decisiones E3.
