# Paquete de validación humana

## Propósito
Este directorio contiene instrumentos genéricos para documentar la evaluación humana de diagnósticos técnicos. Los resultados públicos consolidados se encuentran en data/human_eval/evaluaciones_adjudicadas.csv y el resumen metodológico en data/human_eval/informe_concordancia.md.

## Reglas de aplicación
- Dos evaluadores califican de forma independiente las mismas unidades.
- Las respuestas se identifican con códigos ciegos.
- Se conserva cada evaluación original sin sobrescribirla.
- El tercer evaluador interviene después de congelar las calificaciones independientes y calcular la concordancia inicial.
- La adjudicación se almacena por separado.
- No se inventan ni imputan calificaciones faltantes.
- No se calculan coeficientes con los datos adjudicados como si fueran evaluaciones independientes.

## Estado de los materiales
La publicación actual contiene 54 registros adjudicados. Los formularios originales independientes de E1 y E2 no forman parte del conjunto público. Los coeficientes de concordancia comunicados se documentan como tales y no se presentan como recálculos reproducidos desde esos formularios.

## Fórmula de puntuación humana
La puntuación v3.0.0 utiliza C2, C3, C4 y C5:

    round((C2 + C3 + C4 + C5) / 8 * 5, 2)

C1 y C6 se informan como criterios ordinales independientes; S es una variable dicotómica. La variable S humana no debe confundirse con la regla automática de evidencia.
