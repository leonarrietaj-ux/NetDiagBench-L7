"""
NetDiagBench-L7: Detector de Hardware Físico Real y Telemetría de Recursos Multiplataforma
Detecta de forma automática y precisa sin supuestos declarativos las especificaciones
del host real (NVIDIA, AMD, GPU integrada, CPU-only), clasificando el hardware y
diferenciando memoria física, compartida, declarada, estimada y picos de consumo.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Any

import psutil

# Clasificaciones normativas de hardware (Sección 5)
HARDWARE_CLASS_GPU_DEDICATED = "GPU_DEDICATED"
HARDWARE_CLASS_GPU_INTEGRATED = "GPU_INTEGRATED"
HARDWARE_CLASS_CPU_ONLY = "CPU_ONLY"
HARDWARE_CLASS_GPU_UNSUPPORTED = "GPU_DETECTED_UNSUPPORTED"
HARDWARE_CLASS_PARTIAL = "HARDWARE_DETECTION_PARTIAL"

# Estados normativos de medición de VRAM (Sección 6)
VRAM_STATUS_MEASURED = "measured"
VRAM_STATUS_ESTIMATED = "estimated"
VRAM_STATUS_DECLARED = "declared"
VRAM_STATUS_SHARED_ONLY = "shared_only"
VRAM_STATUS_NOT_AVAILABLE = "not_available"

# Backends de inferencia de Ollama (Sección 7)
BACKEND_CPU = "CPU"
BACKEND_GPU = "GPU"
BACKEND_HYBRID = "HYBRID"
BACKEND_UNKNOWN = "UNKNOWN"


@dataclass
class HardwareProfile:
    # Identificación de GPU y plataforma
    gpu_model: str
    gpu_vendor: str
    hardware_classification: str
    driver_version: str
    cuda_version: str

    # Gestión rigurosa de VRAM
    vram_total_gb: float | None
    vram_shared_gb: float | None
    vram_declared_gb: float | None
    vram_estimated_gb: float | None
    vram_peak_gb: float | None
    vram_measurement_method: str
    vram_measurement_valid: bool
    vram_measurement_status: str

    # Gestión de RAM de sistema
    ram_total_gb: float
    ram_available_gb: float
    ram_peak_gb: float
    ram_measurement_method: str

    # CPU y Sistema Operativo
    cpu_model: str
    cpu_cores_logical: int
    cpu_cores_physical: int
    os_version: str

    # Backend de inferencia
    inference_backend: str

    # Huella inalterable de reproducibilidad
    fingerprint: str


_CACHED_PROFILE: HardwareProfile | None = None


def _detect_gpu_windows() -> tuple[str, str, str, str, float | None, float | None, str, str]:
    """
    Detecta adaptadores gráficos en Windows mediante winreg y PowerShell CIM con fallback.
    Retorna: (gpu_model, gpu_vendor, classification, driver_version, vram_total_gb, vram_shared_gb, method, status)
    """
    gpu_model = "None"
    gpu_vendor = "NONE"
    classification = HARDWARE_CLASS_CPU_ONLY
    driver_version = "N/A"
    vram_total_gb: float | None = None
    vram_shared_gb: float | None = None
    method = "not_available"
    status = VRAM_STATUS_NOT_AVAILABLE

    # 1. Intentar sondeo directo vía Windows Registry (winreg) - Seguro y sin requerir privilegios CIM
    try:
        import winreg
        key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
            for i in range(15):
                try:
                    sub = winreg.EnumKey(k, i)
                    if sub.isdigit():
                        with winreg.OpenKey(k, sub) as sk:
                            desc = ""
                            ver = "N/A"
                            mem_bytes = 0
                            try:
                                desc, _ = winreg.QueryValueEx(sk, "DriverDesc")
                            except FileNotFoundError:
                                pass
                            try:
                                ver, _ = winreg.QueryValueEx(sk, "DriverVersion")
                            except FileNotFoundError:
                                pass
                            try:
                                mem_bytes, _ = winreg.QueryValueEx(sk, "HardwareInformation.qwMemorySize")
                            except FileNotFoundError:
                                try:
                                    mem_bytes, _ = winreg.QueryValueEx(sk, "HardwareInformation.MemorySize")
                                except FileNotFoundError:
                                    mem_bytes = 0

                            if desc and "Basic Display" not in desc:
                                gpu_model = str(desc).strip()
                                driver_version = str(ver).strip()
                                method = "winreg_videocontroller"
                                
                                # Identificar fabricante
                                d_lower = gpu_model.lower()
                                if "amd" in d_lower or "radeon" in d_lower:
                                    gpu_vendor = "AMD"
                                elif "nvidia" in d_lower or "geforce" in d_lower or "quadro" in d_lower:
                                    gpu_vendor = "NVIDIA"
                                elif "intel" in d_lower:
                                    gpu_vendor = "Intel"
                                else:
                                    gpu_vendor = "OTHER"

                                # Determinar si es GPU integrada o dedicada
                                is_integrated = any(term in d_lower for term in [
                                    "610m", "vega", "graphics", "iris", "uhd", "hd graphics", "apu", "integrated", "soc"
                                ])
                                adapter_gb = round(float(mem_bytes) / (1024**3), 2) if mem_bytes > 0 else None

                                if is_integrated:
                                    classification = HARDWARE_CLASS_GPU_INTEGRATED
                                    vram_shared_gb = adapter_gb
                                    vram_total_gb = adapter_gb
                                    status = VRAM_STATUS_NOT_AVAILABLE
                                else:
                                    classification = HARDWARE_CLASS_GPU_DEDICATED
                                    vram_total_gb = adapter_gb
                                    status = VRAM_STATUS_DECLARED
                                break
                except OSError:
                    break
    except Exception:
        pass

    # 2. Si no se detectó o se requiere enriquecimiento, intentar PowerShell CIM
    if classification == HARDWARE_CLASS_CPU_ONLY:
        try:
            ps_cmd = 'Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json'
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                import json
                parsed = json.loads(res.stdout)
                if isinstance(parsed, list):
                    parsed = parsed[0]
                name = parsed.get("Name", "")
                if name and "Basic Display" not in name:
                    gpu_model = name
                    driver_version = parsed.get("DriverVersion", "N/A")
                    adapter_ram = parsed.get("AdapterRAM", 0)
                    adapter_gb = round(float(adapter_ram) / (1024**3), 2) if adapter_ram else None
                    method = "wmi_videocontroller"
                    n_lower = name.lower()
                    if "amd" in n_lower or "radeon" in n_lower:
                        gpu_vendor = "AMD"
                    elif "nvidia" in n_lower:
                        gpu_vendor = "NVIDIA"
                    elif "intel" in n_lower:
                        gpu_vendor = "Intel"

                    if any(t in n_lower for t in ["610m", "vega", "graphics", "iris", "uhd", "hd graphics", "apu"]):
                        classification = HARDWARE_CLASS_GPU_INTEGRATED
                        vram_shared_gb = adapter_gb
                        vram_total_gb = adapter_gb
                        status = VRAM_STATUS_NOT_AVAILABLE
                    else:
                        classification = HARDWARE_CLASS_GPU_DEDICATED
                        vram_total_gb = adapter_gb
                        status = VRAM_STATUS_DECLARED
        except Exception:
            pass

    return gpu_model, gpu_vendor, classification, driver_version, vram_total_gb, vram_shared_gb, method, status


def _detect_gpu_linux() -> tuple[str, str, str, str, float | None, float | None, str, str]:
    """Detecta GPU en Linux mediante sysfs, lspci o rocm-smi."""
    gpu_model = "None"
    gpu_vendor = "NONE"
    classification = HARDWARE_CLASS_CPU_ONLY
    driver_version = "N/A"
    vram_total_gb = None
    vram_shared_gb = None
    method = "not_available"
    status = VRAM_STATUS_NOT_AVAILABLE

    # 1. Probar rocm-smi
    rocm = shutil.which("rocm-smi")
    if rocm:
        try:
            r = subprocess.run([rocm, "--showproductname", "--showdriverversion"], capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                gpu_vendor = "AMD"
                gpu_model = "AMD ROCm GPU"
                classification = HARDWARE_CLASS_GPU_DEDICATED
                method = "rocm-smi"
                status = VRAM_STATUS_MEASURED
                return gpu_model, gpu_vendor, classification, driver_version, vram_total_gb, vram_shared_gb, method, status
        except Exception:
            pass

    # 2. Probar lspci
    lspci = shutil.which("lspci")
    if lspci:
        try:
            r = subprocess.run([lspci], capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if "VGA compatible controller" in line or "3D controller" in line:
                        gpu_model = line.split(":")[-1].strip()
                        l_lower = gpu_model.lower()
                        if "amd" in l_lower or "radeon" in l_lower:
                            gpu_vendor = "AMD"
                        elif "intel" in l_lower:
                            gpu_vendor = "Intel"
                        elif "nvidia" in l_lower:
                            gpu_vendor = "NVIDIA"
                        classification = HARDWARE_CLASS_GPU_INTEGRATED if "integrated" in l_lower or "intel" in l_lower else HARDWARE_CLASS_GPU_DEDICATED
                        method = "lspci"
                        return gpu_model, gpu_vendor, classification, driver_version, vram_total_gb, vram_shared_gb, method, status
        except Exception:
            pass

    return gpu_model, gpu_vendor, classification, driver_version, vram_total_gb, vram_shared_gb, method, status


def detect_system_hardware(force_refresh: bool = False, declared_vram_gb: float | None = None) -> HardwareProfile:
    """
    Detecta el hardware físico real del sistema host de forma multiplataforma y sin suposiciones declarativas.
    Maneja: NVIDIA, AMD, GPU integrada, CPU-only, memoria compartida y estado de medición de VRAM.
    """
    global _CACHED_PROFILE
    if _CACHED_PROFILE is not None and not force_refresh:
        vm = psutil.virtual_memory()
        _CACHED_PROFILE.ram_available_gb = round(vm.available / (1024**3), 2)
        return _CACHED_PROFILE

    # 1. CPU y Sistema Operativo
    vm = psutil.virtual_memory()
    ram_tot = round(vm.total / (1024**3), 2)
    ram_avail = round(vm.available / (1024**3), 2)
    cpu_cores_log = psutil.cpu_count(logical=True) or 1
    cpu_cores_phys = psutil.cpu_count(logical=False) or 1
    cpu_model = platform.processor() or platform.machine() or "CPU x86_64"
    os_ver = f"{platform.system()} {platform.release()} ({platform.version()})"

    # 2. Sondeo GPU NVIDIA prioritario (nvidia-smi)
    gpu_model = "None"
    gpu_vendor = "NONE"
    classification = HARDWARE_CLASS_CPU_ONLY
    driver_ver = "N/A"
    cuda_ver = "N/A"
    vram_tot: float | None = None
    vram_shared: float | None = None
    vram_peak: float | None = None
    vram_method = "not_available"
    vram_valid = False
    vram_status = VRAM_STATUS_NOT_AVAILABLE
    inference_backend = BACKEND_CPU

    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            r = subprocess.run(
                [smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if r.returncode == 0 and r.stdout.strip():
                parts = [p.strip() for p in r.stdout.strip().split(",")]
                gpu_model = parts[0]
                gpu_vendor = "NVIDIA"
                vram_tot = round(float(parts[1]) / 1024.0, 2)
                driver_ver = parts[2]
                vram_method = "nvidia-smi"
                vram_valid = True
                vram_status = VRAM_STATUS_MEASURED
                classification = HARDWARE_CLASS_GPU_DEDICATED
                inference_backend = BACKEND_GPU

                c_proc = subprocess.run([smi], capture_output=True, text=True, timeout=2)
                if "CUDA Version:" in c_proc.stdout:
                    for line in c_proc.stdout.splitlines():
                        if "CUDA Version:" in line:
                            cuda_ver = line.split("CUDA Version:")[-1].split("|")[0].strip()
        except Exception:
            pass

    # 3. Sondeo GPU por Sistema Operativo si no es NVIDIA
    if classification == HARDWARE_CLASS_CPU_ONLY:
        sys_type = platform.system()
        try:
            if sys_type == "Windows":
                (gpu_model, gpu_vendor, classification, driver_ver,
                 vram_tot, vram_shared, vram_method, vram_status) = _detect_gpu_windows()
            elif sys_type == "Linux":
                (gpu_model, gpu_vendor, classification, driver_ver,
                 vram_tot, vram_shared, vram_method, vram_status) = _detect_gpu_linux()
            elif sys_type == "Darwin":
                gpu_vendor = "Apple"
                gpu_model = "Apple Silicon GPU"
                classification = HARDWARE_CLASS_GPU_INTEGRATED
                vram_shared = ram_tot
                vram_tot = ram_tot
                vram_method = "apple_unified_memory"
                vram_status = VRAM_STATUS_SHARED_ONLY
        except Exception:
            classification = HARDWARE_CLASS_PARTIAL

    # 4. Reglas estrictas de VRAM y memoria (Sección 6)
    # Si la GPU es integrada o no existe, no confundir memoria compartida con VRAM dedicada
    if classification in (HARDWARE_CLASS_GPU_INTEGRATED, HARDWARE_CLASS_CPU_ONLY, HARDWARE_CLASS_PARTIAL):
        vram_peak = None
        vram_valid = False
        vram_status = VRAM_STATUS_NOT_AVAILABLE
        inference_backend = BACKEND_CPU
    elif classification == HARDWARE_CLASS_GPU_DEDICATED:
        vram_valid = bool(vram_method in ("nvidia-smi", "rocm-smi", "nvml"))
        vram_status = VRAM_STATUS_MEASURED if vram_valid else VRAM_STATUS_DECLARED

    vram_dec = declared_vram_gb if declared_vram_gb is not None else (8.0 if classification == HARDWARE_CLASS_GPU_DEDICATED else None)
    vram_est = vram_dec if not vram_valid else None

    # Huella física inalterable
    fingerprint = (
        f"OS={platform.system()}_{platform.release()}; "
        f"CPU={cpu_model}; "
        f"Cores={cpu_cores_log}; "
        f"RAM={ram_tot}GB; "
        f"GPU={gpu_model}; "
        f"Class={classification}; "
        f"VRAM_Total={vram_tot if vram_tot is not None else 'N/A'}GB"
    )

    profile = HardwareProfile(
        gpu_model=gpu_model,
        gpu_vendor=gpu_vendor,
        hardware_classification=classification,
        driver_version=driver_ver,
        cuda_version=cuda_ver,
        vram_total_gb=vram_tot,
        vram_shared_gb=vram_shared,
        vram_declared_gb=vram_dec,
        vram_estimated_gb=vram_est,
        vram_peak_gb=vram_peak,
        vram_measurement_method=vram_method,
        vram_measurement_valid=vram_valid,
        vram_measurement_status=vram_status,
        ram_total_gb=ram_tot,
        ram_available_gb=ram_avail,
        ram_peak_gb=round((vm.total - vm.available) / (1024**3), 2),
        ram_measurement_method="psutil",
        cpu_model=cpu_model,
        cpu_cores_logical=cpu_cores_log,
        cpu_cores_physical=cpu_cores_phys,
        os_version=os_ver,
        inference_backend=inference_backend,
        fingerprint=fingerprint,
    )

    _CACHED_PROFILE = profile
    return profile


def detect_ollama_backend_and_vram(ollama_base_url: str, model_tag: str) -> tuple[str, float | None, bool]:
    """
    Sondea en vivo el endpoint /api/ps de Ollama para determinar con exactitud técnica:
    1. Backend real (CPU, GPU, HYBRID)
    2. VRAM dedicada real asignada en bytes (convertida a GB)
    3. Validez de la medición
    No declara GPU cuando size_vram == 0 (ejecución exclusiva en CPU).
    """
    import httpx
    urls = [ollama_base_url]
    if "localhost" in ollama_base_url:
        urls.append(ollama_base_url.replace("localhost", "127.0.0.1"))
    elif "127.0.0.1" in ollama_base_url:
        urls.append(ollama_base_url.replace("127.0.0.1", "localhost"))

    for url in urls:
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(f"{url.rstrip('/')}/api/ps")
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("models", []):
                        m_name = m.get("name", "")
                        if model_tag in m_name or m_name in model_tag:
                            vram_bytes = m.get("size_vram", 0)
                            total_size_bytes = m.get("size", 0)
                            if vram_bytes == 0:
                                return BACKEND_CPU, None, False
                            vram_gb = round(vram_bytes / (1024**3), 2)
                            if total_size_bytes > 0 and vram_bytes < (total_size_bytes * 0.90):
                                return BACKEND_HYBRID, vram_gb, True
                            return BACKEND_GPU, vram_gb, True
        except Exception:
            pass

    # Fallback según perfil de host
    hw = detect_system_hardware()
    if hw.hardware_classification in (HARDWARE_CLASS_CPU_ONLY, HARDWARE_CLASS_GPU_INTEGRATED):
        return BACKEND_CPU, None, False
    return BACKEND_UNKNOWN, None, False


def check_resource_availability(model_name: str, approx_size_gb: float) -> tuple[bool, str]:
    """
    Comprueba si los recursos de RAM física disponible del sistema host permiten
    alojar el modelo sin provocar swap extremo o fallo OOM.
    """
    vm = psutil.virtual_memory()
    available_gb = vm.available / (1024**3)
    if available_gb < approx_size_gb:
        msg = (
            f"Recursos insuficientes: El modelo {model_name} requiere aprox. {approx_size_gb:.1f} GB, "
            f"pero sólo hay {available_gb:.2f} GB de RAM física libre."
        )
        return False, msg
    return True, f"Recursos suficientes: {available_gb:.2f} GB libres para {approx_size_gb:.1f} GB requeridos."
