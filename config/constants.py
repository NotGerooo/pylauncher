"""
constants.py
------------
Literales inmutables usados en todo el proyecto.
"""

LAUNCHER_NAME = "PyLauncher"
LAUNCHER_VERSION = "0.1.0"
USER_AGENT = f"{LAUNCHER_NAME}/{LAUNCHER_VERSION} (Python)"

MOJANG_VERSION_MANIFEST_URL = (
    "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
)
MOJANG_ASSETS_BASE_URL = "https://resources.download.minecraft.net"
MOJANG_LIBRARIES_BASE_URL = "https://libraries.minecraft.net"

MODRINTH_API_BASE_URL = "https://api.modrinth.com/v2"
MODRINTH_API_SEARCH = f"{MODRINTH_API_BASE_URL}/search"
MODRINTH_API_PROJECT = f"{MODRINTH_API_BASE_URL}/project"
MODRINTH_API_VERSION = f"{MODRINTH_API_BASE_URL}/version"
MODRINTH_DEFAULT_PAGE_SIZE = 20

JAVA_MIN_VERSION = 17
JAVA_RECOMMENDED_VERSION = 21

MC_MIN_RAM_MB = 512
MC_DEFAULT_MAX_RAM_MB = 2048
MC_MIN_SUPPORTED_VERSION = "1.12"

PROFILE_GAME_DIR_NAME = "gamedata"
VERSION_JSON_FILENAME = "version.json"

HTTP_TIMEOUT_SECONDS = 30
DOWNLOAD_MAX_RETRIES = 3
DOWNLOAD_RETRY_DELAY = 2
