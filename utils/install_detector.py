"""
utils/install_detector.py
Detección robusta de contenido instalado en carpetas de perfil.

Funciona con archivos instalados por cualquier medio (Modrinth, manual,
antes de que existiera esta función) comparando nombres normalizados.
"""

import os
import re


# Extensiones válidas por tipo de contenido
CONTENT_EXTENSIONS = {
    "mod":         (".jar", ".jar.disabled"),
    "modpack":     (".jar", ".jar.disabled", ".mrpack", ".zip", ".zip.disabled"),
    "resourcepack": (".zip", ".zip.disabled"),
    "shader":      (".zip", ".zip.disabled"),
}


def normalize(text: str) -> str:
    """
    Limpia un nombre de archivo o slug para comparación robusta.

    Ejemplos:
        "sodium-0.5.8+mc1.20.1-fabric.jar"  →  "sodium"
        "Sodium Fabric"                       →  "sodiumfabric"
        "iris-1.7.0+1.21.jar"                →  "iris"
        "complementary-reimagined"            →  "complementaryreimagined"
    """
    # Quitar extensiones conocidas
    text = re.sub(
        r"\.(jar|zip|mrpack|disabled)$", "", text, flags=re.IGNORECASE
    )
    # Quitar sufijos de versión y todo lo que sigue:
    #   -1.2.3 | +mc1.20 | _v2 | -mc1.21 | +1.21
    text = re.sub(r"[-+_](mc)?[\d].*$", "", text, flags=re.IGNORECASE)
    # Quitar separadores y pasar a minúsculas
    text = re.sub(r"[-_. ]", "", text).lower()
    return text


def build_installed_set(directory: str) -> set:
    """
    Escanea un directorio y devuelve un set de nombres normalizados.
    Incluye archivos .disabled (deshabilitados pero presentes).
    Funciona con archivos instalados antes o después de esta función.
    """
    if not directory or not os.path.isdir(directory):
        return set()
    result = set()
    for fn in os.listdir(directory):
        if not os.path.isfile(os.path.join(directory, fn)):
            continue
        normalized = normalize(fn)
        if normalized:
            result.add(normalized)
    return result


def is_installed_in(project_slug: str, project_title: str,
                    installed_set: set) -> bool:
    """
    Comprueba si un proyecto está instalado comparando su slug y título
    normalizados contra el set de archivos del directorio.

    Usa tres niveles de comparación:
      1. Igualdad exacta (slug == nombre_archivo)
      2. Prefijo: el nombre del archivo empieza por el slug
         Ej: slug "sodium" matchea archivo normalizado "sodiumfabric0581"
      3. Prefijo inverso: el slug es más largo que el nombre (poco común)
    """
    slug_key  = normalize(project_slug)
    title_key = normalize(project_title)

    for key in (slug_key, title_key):
        if not key:
            continue
        # Igualdad exacta
        if key in installed_set:
            return True
        # Comparación por prefijo
        for installed_name in installed_set:
            if installed_name.startswith(key):
                return True
            # Prefijo inverso (mínimo 4 chars para evitar falsos positivos)
            if key.startswith(installed_name) and len(installed_name) >= 4:
                return True

    return False