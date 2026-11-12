"""
Generador del Manifiesto Criptográfico de Publicación SHA-256
Proyecto: NetDiagBench-L7 v1.0.0
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    root = Path(__file__).resolve().parent.parent
    manifest_path = root / "data" / "benchmark_results" / "MANIFEST_PUBLICACION_SHA256.json"

    print(f"Generando manifiesto de publicación para: {root}")

    # Archivos protegidos y clave de la versión pública
    tracked_categories = {
        "dataset_canonico": [
            "data/benchmark_results/resultados.csv",
            "data/benchmark_results/traza.jsonl",
            "data/benchmark_results/dataset_bundle.json",
        ],
        "campana_congelada_162": [
            "data/campaign_162/resultados.csv",
            "data/campaign_162/recalificacion_auditada.csv",
            "data/campaign_162/traza.jsonl",
            "data/campaign_162/manifest.json",
        ],
        "evaluacion_humana_publica": [
            "data/human_eval/evaluaciones_adjudicadas.csv",
        ],
        "configuraciones_oficiales": [
            "configs/models.yaml",
            "configs/benchmark_config.yaml",
            "configs/evaluator_concepts.yaml",
            "configs/hardware_reference.yaml",
        ],
        "documentacion_academica_y_tecnica": [
            "README.md",
            "docs/DOCUMENTO_FINAL_TESIS_GRADO.md",
            "docs/GUIA_REPRODUCIBILIDAD.md",
            "docs/MANUAL_TECNICO_SISTEMA.md",
            "docs/MANUAL_USUARIO_SISTEMA.md",
            "docs/MATRIZ_CIFRAS_OFICIALES_TESIS.md",
            "docs/E1_matriz_caracterizacion_y_acta_seleccion.md",
            "docs/E4_conjunto_datos_y_tabla_comparativa.md",
            "docs/E5_informe_tecnico_evaluacion_comparativa_tradeoff.md",
            "docs/E6_articulo_manuscrito_academico.md",
            "docs/E7_documento_final_trabajo_de_grado.md",
            "docs/INFORME_SEGURIDAD.md",
            "docs/INFORME_ESTADISTICO_FINAL.md",
            "docs/INTEGRIDAD_TRAZABILIDAD_FINAL.md",
            "docs/DICTAMEN_FINAL_NETDIAGBENCH_L7.md",
        ],
        "metadatos_del_proyecto": [
            "pyproject.toml",
            "requirements.txt",
            ".gitignore",
            "LICENSE",
        ],
    }

    manifest_data = {
        "project": "NetDiagBench-L7",
        "version": "1.0.0",
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

    for category, rel_paths in tracked_categories.items():
        manifest_data["integrity_hashes"][category] = {}
        for rel in rel_paths:
            fp = root / rel
            if fp.exists():
                h = compute_sha256(fp)
                manifest_data["integrity_hashes"][category][rel] = {
                    "sha256": h,
                    "size_bytes": fp.stat().st_size,
                }
                print(f"  [{category}] {rel} -> {h}")
            else:
                print(f"  [ALERTA] Archivo no encontrado: {rel}")

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print(f"\nManifiesto generado exitosamente en: {manifest_path}")


if __name__ == "__main__":
    main()
