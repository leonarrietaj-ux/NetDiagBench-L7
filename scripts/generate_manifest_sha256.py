"""
Generador y Verificador del Manifiesto Criptográfico de Publicación SHA-256
Proyecto: NetDiagBench-L7 v1.0.4
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def get_tracked_categories() -> dict[str, list[str]]:
    raw = {
        "campana_congelada_162": [
            "data/campaign_162/manifest.json",
            "data/campaign_162/recalificacion_auditada.csv",
            "data/campaign_162/resultados.csv",
            "data/campaign_162/traza.jsonl",
        ],
        "configuraciones_oficiales": [
            "configs/benchmark_config.yaml",
            "configs/evaluator_concepts.yaml",
            "configs/hardware_reference.yaml",
            "configs/models.yaml",
        ],
        "dataset_canonico": [
            "data/benchmark_results/dataset_bundle.json",
            "data/benchmark_results/resultados.csv",
            "data/benchmark_results/traza.jsonl",
        ],
        "documentacion_tecnica": [
            "README.md",
            "docs/ANALISIS_ESTADISTICO.md",
            "docs/CONFIGURACION_MODELOS.md",
            "docs/EVALUACION_TRADEOFF.md",
            "docs/GUIA_OPERACION.md",
            "docs/GUIA_REPRODUCIBILIDAD.md",
            "docs/MANUAL_TECNICO.md",
            "docs/RESULTADOS_BENCHMARK.md",
            "docs/SEGURIDAD_SISTEMA.md",
        ],
        "evaluacion_humana_publica": [
            "data/human_eval/acta_pilotaje.md",
            "data/human_eval/clave_tecnica_escenarios.csv",
            "data/human_eval/concordancia_resultados.csv",
            "data/human_eval/evaluaciones_adjudicadas.csv",
            "data/human_eval/informe_concordancia.md",
            "data/human_eval/registro_evaluadores.md",
            "data/human_eval/version_rubrica.json",
        ],
        "instrumentos_evaluacion_humana": [
            "docs/evaluacion_humana/00_LEEME.md",
            "docs/evaluacion_humana/01_Protocolo_evaluacion_humana.docx",
            "docs/evaluacion_humana/02_Rubrica_y_matriz_evaluacion.xlsx",
            "docs/evaluacion_humana/03_Formulario_individual_evaluador.docx",
            "docs/evaluacion_humana/04_Consentimiento_y_confidencialidad.docx",
            "docs/evaluacion_humana/05_Registro_evaluaciones.csv",
            "docs/evaluacion_humana/06_Clave_tecnica_escenarios.csv",
            "docs/evaluacion_humana/07_Plan_analisis_concordancia.md",
            "docs/evaluacion_humana/08_analizar_concordancia.py",
            "docs/evaluacion_humana/09_Guia_anonimizacion_y_adjudicacion.md",
        ],
        "metadatos_del_proyecto": [
            ".gitignore",
            "CITATION.cff",
            "LICENSE",
            "pyproject.toml",
            "requirements.txt",
        ],
    }
    # Deterministic sort for categories and file lists
    return {cat: sorted(paths) for cat, paths in sorted(raw.items())}


def build_manifest(root: Path) -> dict:
    tracked = get_tracked_categories()
    manifest_data = {
        "project": "NetDiagBench-L7",
        "version": "1.0.4",
        "release_type": "scientific_public_release",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": "https://github.com/leonarrietaj-ux/NetDiagBench-L7.git",
        "experimental_summary": {
            "total_runs": 162,
            "scenarios": 18,
            "models": ["glm-4-9b-chat", "qwen3-8b", "phi-4-mini-instruct"],
            "seeds": [42, 1337, 2026],
            "full_diagnosis_correct": 122,
            "strict_root_cause_correct": 71,
            "fault_class_correct": 120,
            "evidence_backed_correct": 38,
            "rubric_scores": {
                "glm-4-9b-chat": 4.13,
                "qwen3-8b": 4.07,
                "phi-4-mini-instruct": 3.55,
                "global_mean": 3.92,
            },
        },
        "integrity_hashes": {},
    }

    for category, rel_paths in tracked.items():
        manifest_data["integrity_hashes"][category] = {}
        for rel in sorted(rel_paths):
            fp = root / rel
            if fp.exists():
                h = compute_sha256(fp)
                manifest_data["integrity_hashes"][category][rel] = {
                    "sha256": h,
                    "size_bytes": fp.stat().st_size,
                }
            else:
                print(f"  [ALERTA] Archivo no encontrado: {rel}")

    return manifest_data


def check_manifest(root: Path, manifest_path: Path) -> bool:
    if not manifest_path.exists():
        print(f"ERROR: Manifiesto no encontrado en {manifest_path}")
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    hashes_block = data.get("integrity_hashes", {})
    all_ok = True
    checked = 0
    mismatches = []

    for cat, file_dict in hashes_block.items():
        for rel_str, meta in sorted(file_dict.items()):
            fp = root / rel_str
            if not fp.exists():
                print(f"  [MISSING] {rel_str}")
                all_ok = False
                mismatches.append(f"Inexistente: {rel_str}")
                continue
            real_hash = compute_sha256(fp)
            exp_hash = meta.get("sha256", "").upper()
            if real_hash != exp_hash:
                print(f"  [MISMATCH] {rel_str}: real={real_hash[:8]} vs exp={exp_hash[:8]}")
                all_ok = False
                mismatches.append(f"{rel_str} (real={real_hash[:8]} vs exp={exp_hash[:8]})")
            else:
                checked += 1

    if all_ok:
        print(f"Verificación exitosa: {checked} archivos coinciden con sus digests SHA-256.")
        return True
    else:
        print(f"FALLO DE INTEGRIDAD: {len(mismatches)} desajustes detectados.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generador y Verificador SHA-256 para NetDiagBench-L7")
    parser.add_argument("--check", action="store_true", help="Verifica la integridad de los archivos contra el manifiesto existente")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    manifest_path = root / "data" / "benchmark_results" / "MANIFEST_PUBLICACION_SHA256.json"

    if args.check:
        print(f"Verificando manifiesto criptográfico en: {manifest_path}")
        ok = check_manifest(root, manifest_path)
        sys.exit(0 if ok else 1)
    else:
        print(f"Generando manifiesto de publicación para: {root}")
        manifest_data = build_manifest(root)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        total_files = sum(len(v) for v in manifest_data["integrity_hashes"].values())
        print(f"\nManifiesto generado exitosamente ({total_files} archivos) en: {manifest_path}")


if __name__ == "__main__":
    main()
