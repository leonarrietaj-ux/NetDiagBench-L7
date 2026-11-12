import json
import shutil
import subprocess
import urllib.request
import psutil
from pathlib import Path

def run_pre_validation():
    print("==================================================")
    print("      NETDIAGBENCH-L7: VALIDACION PRE-CAMPANA     ")
    print("==================================================")
    
    # 1. Hardware & System
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage(".")
    cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    
    print("\n--- 1. RECURSOS DEL SISTEMA ANFITRION ---")
    print(f"CPU Logicos: {cpu_count}")
    if cpu_freq:
        print(f"Frecuencia CPU: {cpu_freq.current:.1f} MHz (Max: {cpu_freq.max:.1f} MHz)")
    print(f"RAM Total: {mem.total / (1024**3):.2f} GB")
    print(f"RAM Disponible: {mem.available / (1024**3):.2f} GB ({mem.percent}% en uso)")
    print(f"Espacio en Disco Total: {disk.total / (1024**3):.2f} GB")
    print(f"Espacio en Disco Libre: {disk.free / (1024**3):.2f} GB")
    
    # 2. Ollama & Modelos
    print("\n--- 2. ESTADO DEL SERVIDOR OLLAMA ---")
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            tag_data = json.loads(resp.read().decode("utf-8"))
            models = tag_data.get("models", [])
            print(f"Servidor Ollama ACTIVO (puerto 11434). Total modelos cargados: {len(models)}")
            
            target_models = {
                "qwen3-8b": ["qwen3:8b", "qwen3:8b-q4_K_M"],
                "glm-4-9b-chat": ["glm4:9b-chat-q4_K_M", "glm4:latest"],
                "phi-4-mini-instruct": ["phi4-mini:instruct-q4_K_M", "phi4-mini:latest"]
            }
            
            for canon_id, tags in target_models.items():
                found = False
                for tag in tags:
                    match = next((m for m in models if m["name"] == tag), None)
                    if match:
                        found = True
                        # Consultar /api/show
                        show_req = urllib.request.Request(
                            "http://localhost:11434/api/show",
                            data=json.dumps({"name": tag}).encode("utf-8"),
                            headers={"Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(show_req, timeout=5.0) as show_resp:
                            details = json.loads(show_resp.read().decode("utf-8")).get("details", {})
                        
                        print(f"\n[OK] Modelo Canonico: {canon_id}")
                        print(f"     Tag: {match['name']}")
                        print(f"     Digest: {match['digest']}")
                        print(f"     Tamano: {match['size'] / (1024**3):.2f} GB ({match['size']} bytes)")
                        print(f"     Familia: {details.get('family')} / Cuantizacion: {details.get('quantization_level')}")
                        print(f"     Parametros: {details.get('parameter_size')}")
                        break
                if not found:
                    print(f"\n[ERROR] Modelo {canon_id} NO ENCONTRADO en Ollama!")
    except Exception as e:
        print(f"[FATAL] Error conectando con Ollama: {e}")
        return False

    # 3. Docker & Contenedores Emulados
    print("\n--- 3. ESTADO DE DOCKER & INFRAESTRUCTURA EMULADA ---")
    docker_bin = shutil.which("docker")
    print(f"Binario Docker: {docker_bin}")
    if docker_bin:
        try:
            res = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"], capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0:
                print("Daemon Docker ACTIVO y respondiendo:")
                for line in res.stdout.strip().splitlines():
                    print(f" - {line}")
            else:
                print(f"[WARN] Error en docker ps: {res.stderr}")
        except Exception as e:
            print(f"[WARN] No se pudo consultar daemon de Docker: {e}")
    else:
        print("[WARN] Binario docker no encontrado en PATH.")

    print("\n==================================================")
    print("          FIN DE LA VALIDACION PREVIA             ")
    print("==================================================")
    return True

if __name__ == "__main__":
    run_pre_validation()
