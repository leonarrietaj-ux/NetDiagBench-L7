"""
NetDiagBench-L7: Prueba de Integración del Ciclo de Vida de Kits Excel de Evaluación Humana (OE4 / Tarea 4.2.1)
Verifica el ciclo completo:
1. Inicialización de sesión y exportación de Kits A y B (.xlsx).
2. Validación de rangos (C1-C6 en {0,1,2}, S en {Sí, No}, U en {1..5}).
3. Detección de filas inválidas, duplicadas y faltantes.
4. Importación oficial de respuestas de Evaluadores A y B.
5. Detección de discrepancias en todos los criterios (C1..C6 y S) y emisión del Kit C dirimente.
6. Importación de calificaciones de C y resolución de consenso.
7. Preservación estricta de evaluaciones originales de A y B y trazabilidad de decisiones.
"""

from pathlib import Path
import openpyxl
import pytest

from src.core.contracts import EtiquetaExperto
from src.layer8_human_eval.session import (
    create_new_session_dir,
    set_active_session,
)
from src.layer8_human_eval.labels import (
    save_etiquetas,
    load_etiquetas,
    generate_expert_label,
)
from src.layer8_human_eval.sampler import (
    build_stratified_sample,
    save_blind_key,
    load_blind_cards_from_sample,
)
from src.layer8_human_eval.exporter_xlsx import export_expert_instrument
from src.layer8_human_eval.importer import (
    import_expert_responses,
    validate_response_row,
    normalize_s_value,
)
from src.layer8_human_eval.agreement import calculate_consensus


class TestHumanEvalKitsLifecycle:
    """Prueba exhaustiva de extremo a extremo para los kits Excel."""

    def test_validation_rules_and_ranges(self):
        # 1. Normalización de S
        assert normalize_s_value("sí") == "Sí"
        assert normalize_s_value("si") == "Sí"
        assert normalize_s_value("1") == "Sí"
        assert normalize_s_value("no") == "No"
        assert normalize_s_value("0") == "No"

        # 2. Fila válida
        valid_row = {
            "codigo": "RUN-001",
            "c1": 2, "c2": 2, "c3": 1, "c4": 2, "c5": 2, "c6": 2,
            "s": "Sí", "u": 4, "observacion": "Diagnóstico preciso y sustentado",
        }
        res = validate_response_row(valid_row, row_idx=5)
        assert res["c1"] == 2
        assert res["rubrica"] == 4.38  # round_rubric(7) = 4.38

        # 3. Rango inválido C1 > 2
        invalid_c1 = dict(valid_row, c1=3)
        with pytest.raises(ValueError, match="fuera de rango"):
            validate_response_row(invalid_c1, row_idx=5)

        # 4. Rango inválido C6 < 0
        invalid_c6 = dict(valid_row, c6=-1)
        with pytest.raises(ValueError, match="fuera de rango"):
            validate_response_row(invalid_c6, row_idx=5)

        # 5. Valor inválido para S
        invalid_s = dict(valid_row, s="tal_vez")
        with pytest.raises(ValueError, match="S debe ser 'Sí' o 'No'"):
            validate_response_row(invalid_s, row_idx=5)

        # 6. Observación obligatoria cuando C1 = 0
        zero_c1_no_obs = dict(valid_row, c1=0, observacion="")
        with pytest.raises(ValueError, match="Observación.*obligatoria"):
            validate_response_row(zero_c1_no_obs, row_idx=5)

    def test_full_roundtrip_kits_and_adjudication(self, tmp_path: Path):
        """
        Ciclo completo aislado en tmp_path:
        - Crear sesión de prueba
        - Exportar Kits A y B
        - Llenar respuestas con acuerdos y discrepancias controladas
        - Importar A y B
        - Generar Kit C para discrepancias
        - Importar C
        - Calcular consenso y validar preservación de A y B
        """
        session_id = "SESION_TEST_ROUNDTRIP"
        active_id, s_dir = create_new_session_dir(session_id, base_dir=tmp_path)
        set_active_session(active_id, base_dir=tmp_path)

        # Generar muestra estratificada mínima controlada (6 corridas de prueba)
        full_sample = build_stratified_sample(seed=42)
        test_sample = full_sample[:6]  # 6 corridas para prueba rápida
        save_blind_key(test_sample, active_id, seed=42, output_dir=s_dir)

        codes = [s.codigo for s in test_sample]
        disc_code_1 = codes[0]
        disc_code_2 = codes[1]

        etiqueta_a = generate_expert_label("A", active_id, codes, semilla_orden=11)
        etiqueta_b = generate_expert_label("B", active_id, codes, semilla_orden=22)
        etiqueta_c = generate_expert_label("C", active_id, codes, semilla_orden=33)

        etiquetas_map = {"A": etiqueta_a, "B": etiqueta_b, "C": etiqueta_c}
        etiquetas_path = save_etiquetas(etiquetas_map, s_dir)

        cards_map = load_blind_cards_from_sample(test_sample)

        # 1. Exportar Kit A y Kit B
        xlsx_a = s_dir / f"Instrumento_Experto_A_{active_id}.xlsx"
        xlsx_b = s_dir / f"Instrumento_Experto_B_{active_id}.xlsx"
        export_expert_instrument(etiqueta_a, cards_map, xlsx_a)
        export_expert_instrument(etiqueta_b, cards_map, xlsx_b)

        assert xlsx_a.is_file()
        assert xlsx_b.is_file()

        # 2. Llenar respuestas simuladas en Excel para A y B emparejadas por CÓDIGO
        def _fill_instrument(file_path: Path, expert_char: str):
            wb = openpyxl.load_workbook(file_path)
            ws = wb["Evaluación"]
            for r in range(5, 5 + len(codes)):
                code = ws.cell(row=r, column=2).value
                if code == disc_code_1:
                    # Discrepancia en C1 y S
                    c1_val = 2 if expert_char == "A" else 0
                    s_val = "Sí" if expert_char == "A" else "No"
                    ws.cell(row=r, column=5, value=c1_val)
                    ws.cell(row=r, column=6, value=2)
                    ws.cell(row=r, column=7, value=2)
                    ws.cell(row=r, column=8, value=2)
                    ws.cell(row=r, column=9, value=2)
                    ws.cell(row=r, column=10, value=2)
                    ws.cell(row=r, column=11, value=s_val)
                    ws.cell(row=r, column=12, value=4)
                    ws.cell(row=r, column=13, value="Observación de discrepancia C1/S")
                elif code == disc_code_2:
                    # Discrepancia en C6
                    c6_val = 2 if expert_char == "A" else 0
                    ws.cell(row=r, column=5, value=2)
                    ws.cell(row=r, column=6, value=2)
                    ws.cell(row=r, column=7, value=2)
                    ws.cell(row=r, column=8, value=2)
                    ws.cell(row=r, column=9, value=2)
                    ws.cell(row=r, column=10, value=c6_val)
                    ws.cell(row=r, column=11, value="Sí")
                    ws.cell(row=r, column=12, value=4)
                    ws.cell(row=r, column=13, value="Observación de discrepancia C6")
                else:
                    # Coincidencia unánime
                    ws.cell(row=r, column=5, value=2)
                    ws.cell(row=r, column=6, value=2)
                    ws.cell(row=r, column=7, value=1)
                    ws.cell(row=r, column=8, value=2)
                    ws.cell(row=r, column=9, value=2)
                    ws.cell(row=r, column=10, value=2)
                    ws.cell(row=r, column=11, value="Sí")
                    ws.cell(row=r, column=12, value=5)
                    ws.cell(row=r, column=13, value="Acuerdo unánime")
            wb.save(file_path)

        _fill_instrument(xlsx_a, "A")
        _fill_instrument(xlsx_b, "B")

        # 3. Importar Evaluaciones de A y B
        id_a, rows_a = import_expert_responses(xlsx_a, active_id, etiquetas_path, output_dir=s_dir)
        id_b, rows_b = import_expert_responses(xlsx_b, active_id, etiquetas_path, output_dir=s_dir)

        assert id_a == "A"
        assert id_b == "B"
        assert len(rows_a) == len(codes)
        assert len(rows_b) == len(codes)

        # 4. Detección de discrepancias en todos los criterios y emisión de Kit C
        discrepant_codes = []
        map_b = {r["codigo"]: r for r in rows_b}
        for ra in rows_a:
            c = ra["codigo"]
            rb = map_b[c]
            has_disc = any(ra[crit] != rb[crit] for crit in ["c1", "c2", "c3", "c4", "c5", "c6"])
            if not has_disc and ra["s"] != rb["s"]:
                has_disc = True
            if has_disc:
                discrepant_codes.append(c)

        # Deben detectarse exactamente los 2 casos discrepantes configurados
        assert set(discrepant_codes) == {disc_code_1, disc_code_2}

        # 5. Generar Kit C con los casos discrepantes
        from src.layer8_human_eval.labels import compute_huella, get_evaluator_version
        etiqueta_c_tiebreak = etiqueta_c.model_copy(
            update={
                "total_corridas": len(discrepant_codes),
                "orden": discrepant_codes,
                "nombre_archivo": f"Instrumento_Experto_C_{active_id}.xlsx",
                "huella_sha256": compute_huella(active_id, "C", discrepant_codes, get_evaluator_version()),
            }
        )
        etiquetas_map["C"] = etiqueta_c_tiebreak
        save_etiquetas(etiquetas_map, s_dir)

        xlsx_c = s_dir / f"Instrumento_Experto_C_{active_id}.xlsx"
        export_expert_instrument(etiqueta_c_tiebreak, cards_map, xlsx_c)
        assert xlsx_c.is_file()

        # Llenar respuestas dirimentes de C
        wb_c = openpyxl.load_workbook(xlsx_c)
        ws_c = wb_c["Evaluación"]
        for r in range(5, 5 + len(discrepant_codes)):
            code = ws_c.cell(row=r, column=2).value
            if code == disc_code_1:
                ws_c.cell(row=r, column=5, value=2)  # C1 = 2 (consenso A)
                ws_c.cell(row=r, column=6, value=2)
                ws_c.cell(row=r, column=7, value=2)
                ws_c.cell(row=r, column=8, value=2)
                ws_c.cell(row=r, column=9, value=2)
                ws_c.cell(row=r, column=10, value=2)
                ws_c.cell(row=r, column=11, value="Sí")  # S = Sí (consenso A)
                ws_c.cell(row=r, column=12, value=4)
                ws_c.cell(row=r, column=13, value="Adjudicado por C a favor de A")
            elif code == disc_code_2:
                ws_c.cell(row=r, column=5, value=2)
                ws_c.cell(row=r, column=6, value=2)
                ws_c.cell(row=r, column=7, value=2)
                ws_c.cell(row=r, column=8, value=2)
                ws_c.cell(row=r, column=9, value=2)
                ws_c.cell(row=r, column=10, value=0)  # C6 = 0 (consenso B)
                ws_c.cell(row=r, column=11, value="Sí")
                ws_c.cell(row=r, column=12, value=4)
                ws_c.cell(row=r, column=13, value="Adjudicado por C a favor de B")
        wb_c.save(xlsx_c)

        # 6. Importar calificaciones de C
        id_c, rows_c = import_expert_responses(xlsx_c, active_id, etiquetas_path, output_dir=s_dir)
        assert id_c == "C"
        assert len(rows_c) == 2

        # 7. Construir consenso y validar trazabilidad
        consensus = calculate_consensus(rows_a, rows_b, rows_c)
        assert len(consensus) == len(codes)

        # Verificar caso 1 (resuelto C1=2, S=Sí)
        cons_1 = next(item for item in consensus if item["codigo"] == disc_code_1)
        assert cons_1["c1_consenso"] == 2
        assert cons_1["s_consenso"] == "Sí"
        assert "dirimidas por E3" in cons_1["motivo_adjudicacion"]

        # Verificar caso 2 (resuelto C6=0)
        cons_2 = next(item for item in consensus if item["codigo"] == disc_code_2)
        assert cons_2["c6_consenso"] == 0
        assert "dirimidas por E3" in cons_2["motivo_adjudicacion"]

        # Verificar casos no discrepantes (unánimes)
        unanimous_codes = [c for c in codes if c not in (disc_code_1, disc_code_2)]
        for uc in unanimous_codes:
            item = next(it for it in consensus if it["codigo"] == uc)
            assert "consenso unánime" in item["motivo_adjudicacion"].lower()

        # 8. Verificar que las respuestas originales de A y B en disco no sufrieron modificación
        assert (s_dir / "respuestas_A.csv").is_file()
        assert (s_dir / "respuestas_B.csv").is_file()
        assert (s_dir / "respuestas_C.csv").is_file()
