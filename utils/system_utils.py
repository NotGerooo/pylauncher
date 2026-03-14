"""
system_utils.py
---------------
Detección de información del sistema operativo.
FIX APLICADO: find_java_executables usa shutil.which primero.
"""
import os
import subprocess
import platform
from utils.logger import get_logger
log = get_logger()

_JAVA_SEARCH_PATHS_WINDOWS = [
    r"C:\Program Files\Java",
    r"C:\Program Files\Eclipse Adoptium",
    r"C:\Program Files\Microsoft",
    r"C:\Program Files\Eclipse Foundation",
    r"C:\Program Files (x86)\Java",
]


def get_os() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    return "linux"


def get_architecture() -> str:
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return "x64"
    return "x86"


def get_total_ram_mb() -> int:
    try:
        if get_os() == "windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulong = ctypes.c_ulong
            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", c_ulong),
                    ("dwMemoryLoad", c_ulong),
                    ("dwTotalPhys", ctypes.c_ulonglong),
                    ("dwAvailPhys", ctypes.c_ulonglong),
                    ("dwTotalPageFile", ctypes.c_ulonglong),
                    ("dwAvailPageFile", ctypes.c_ulonglong),
                    ("dwTotalVirtual", ctypes.c_ulonglong),
                    ("dwAvailVirtual", ctypes.c_ulonglong),
                ]
            mem_status = MemoryStatus()
            mem_status.dwLength = ctypes.sizeof(MemoryStatus)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))
            return int(mem_status.dwTotalPhys // (1024 * 1024))
    except Exception as e:
        log.warning(f"No se pudo detectar RAM: {e}. Usando fallback 4096 MB")
    return 4096


def get_recommended_ram_mb() -> int:
    total = get_total_ram_mb()
    if total >= 16384:
        return 4096
    elif total >= 8192:
        return 3072
    elif total >= 4096:
        return 2048
    return 1024


def find_java_executables() -> list:
    """
    Busca instalaciones de Java.
    FIX: Busca primero en el PATH del sistema con shutil.which.
    """
    import shutil
    found = []
    seen_paths = set()

    # 1. Buscar en PATH primero (donde Windows registra Java al instalarlo)
    java_in_path = shutil.which("java")
    if java_in_path:
        version = _get_java_version(java_in_path)
        if version and java_in_path not in seen_paths:
            seen_paths.add(java_in_path)
            found.append({"path": java_in_path, "version_string": version})
            log.info(f"Java encontrado en PATH: {java_in_path} v{version}")

    if get_os() != "windows":
        return found

    # 2. Buscar en rutas estándar de Windows
    for base_path in _JAVA_SEARCH_PATHS_WINDOWS:
        if not os.path.isdir(base_path):
            continue
        for entry in os.listdir(base_path):
            for subfolder in ["bin", os.path.join("jre", "bin")]:
                java_exe = os.path.join(base_path, entry, subfolder, "java.exe")
                if os.path.isfile(java_exe) and java_exe not in seen_paths:
                    version = _get_java_version(java_exe)
                    if version:
                        seen_paths.add(java_exe)
                        found.append({"path": java_exe, "version_string": version})

    log.info(f"Total instalaciones de Java encontradas: {len(found)}")
    return found


def _get_java_version(java_path: str):
    try:
        result = subprocess.run(
            [java_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stderr or result.stdout
        for line in output.splitlines():
            if "version" in line.lower():
                parts = line.split('"')
                if len(parts) >= 2:
                    return parts[1]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        log.debug(f"Error obteniendo version de Java en {java_path}: {e}")
    return None


def get_system_info() -> dict:
    return {
        "os": get_os(),
        "architecture": get_architecture(),
        "ram_mb": get_total_ram_mb(),
        "python_version": platform.python_version(),
        "platform_detail": platform.platform()
    }
