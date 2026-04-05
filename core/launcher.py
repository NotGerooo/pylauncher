"""
launcher.py
-----------
Construye el comando completo de Java y ejecuta Minecraft como subproceso.

Responsabilidades:
- Detectar si el perfil tiene un loader activo (Fabric, Forge, etc.)
- Resolver qué version_id usar al lanzar (vanilla o loader)
- Construir el classpath con todas las librerías de esa versión
- Construir los argumentos JVM (memoria, flags de rendimiento)
- Construir los argumentos del juego (usuario, versión, carpetas)
- Ejecutar Minecraft y capturar su output en tiempo real

Este módulo NO sabe nada de perfiles, mods, ni UI.
Solo recibe datos y lanza el juego.
"""

import os
import json
import subprocess
import threading

from config.settings import Settings
from managers.profile_manager import Profile
from managers.java_manager import JavaManager
from services.auth_service import PlayerSession
from utils.logger import get_logger
import managers.loader_manager as LoaderManager

log = get_logger()


class LaunchError(Exception):
    """Error durante la preparación o ejecución del juego."""
    pass


class LauncherEngine:
    """
    Construye y ejecuta el proceso de Minecraft.

    Detecta automáticamente el loader activo del perfil y usa
    su version_id al construir el classpath y los argumentos.

    Uso:
        engine  = LauncherEngine(settings)
        session = AuthService().create_offline_session("Steve")
        process = engine.launch(profile, session, version_data)
    """

    def __init__(self, settings: Settings):
        self._settings       = settings
        self._java_manager   = JavaManager(settings)
        self._loader_manager = LoaderManager

    # ── API Pública ───────────────────────────────────────────────────────────

    def launch(
        self,
        profile: Profile,
        session: PlayerSession,
        version_data: dict,
        on_output=None,
    ) -> subprocess.Popen:
        log.info(
            f"=== Lanzando Minecraft {profile.version_id} "
            f"para '{session.username}' ==="
        )

        # 1. Resolver qué versión lanzar (vanilla o loader)
        launch_version_id, launch_version_data = self._resolve_launch_version(
            profile, version_data
        )

        log.info(f"Versión efectiva de lanzamiento: {launch_version_id}")

        # 2. Resolver Java
        java_path = self._resolve_java(profile)

        # 3. Construir las partes del comando
        client_jar = self._resolve_client_jar(launch_version_id)
        classpath  = self._build_classpath(launch_version_id, launch_version_data)
        main_class = launch_version_data.get("mainClass", "")

        if not main_class:
            raise LaunchError(
                f"No se encontró mainClass en los datos de '{launch_version_id}'"
            )

        jvm_args  = self._build_jvm_args(profile, client_jar, launch_version_data)
        game_args = self._build_game_args(profile, session, launch_version_data)

        command = (
            [java_path]
            + jvm_args
            + ["-cp", classpath, main_class]
            + game_args
        )

        log.debug(f"Comando construido con {len(command)} partes")

        # 4. Lanzar proceso
        return self._start_process(command, profile.game_dir, on_output)

    def build_command_preview(
        self,
        profile: Profile,
        session: PlayerSession,
        version_data: dict,
    ) -> str:
        launch_version_id, launch_version_data = self._resolve_launch_version(
            profile, version_data
        )

        java_path  = self._resolve_java(profile)
        client_jar = self._resolve_client_jar(launch_version_id)
        classpath  = self._build_classpath(launch_version_id, launch_version_data)
        main_class = launch_version_data.get("mainClass", "")
        jvm_args   = self._build_jvm_args(profile, client_jar, launch_version_data)
        game_args  = self._build_game_args(profile, session, launch_version_data)

        parts = (
            [java_path]
            + jvm_args
            + ["-cp", classpath, main_class]
            + game_args
        )

        return " ".join(f'"{p}"' if " " in p else p for p in parts)

    # ── Resolución de versión con loader ─────────────────────────────────────

    def _resolve_launch_version(
        self,
        profile: Profile,
        base_version_data: dict,
    ) -> tuple[str, dict]:

        meta = self._loader_manager.load_loader_meta(profile.game_dir)
        loader_type = meta.get("loader", "vanilla")

        if not meta or loader_type == "vanilla":
            log.info("Sin loader activo — lanzando Minecraft vanilla")
            return profile.version_id, base_version_data

        log.info(
            f"Loader detectado: {loader_type} "
            f"({meta.get('loader_version')})"
        )

        # ── Fabric / Quilt: usan main_class y extra_libs del loader_meta ──────
        if loader_type in ("fabric", "quilt"):
            return self._resolve_fabric_like(
                profile, base_version_data, meta, loader_type)

        # ── Forge / NeoForge: buscan JSON en versions_dir ─────────────────────
        loader_version_id = meta.get("install_id")
        if not loader_version_id:
            log.info("Sin install_id en loader_meta — lanzando vanilla")
            return profile.version_id, base_version_data

        loader_json_path = os.path.join(
            self._settings.versions_dir,
            loader_version_id,
            f"{loader_version_id}.json",
        )

        if not os.path.isfile(loader_json_path):
            raise LaunchError(
                f"El loader '{loader_version_id}' está registrado pero su JSON "
                f"no se encontró en disco.\nRuta esperada: {loader_json_path}\n"
                f"Solución: reinstala el loader."
            )

        with open(loader_json_path, "r", encoding="utf-8") as f:
            loader_version_data = json.load(f)

        loader_version_data = self._merge_libraries(base_version_data, loader_version_data)
        return loader_version_id, loader_version_data

    def _resolve_fabric_like(
        self,
        profile: Profile,
        base_version_data: dict,
        meta: dict,
        loader_type: str,
    ) -> tuple[str, dict]:
        """
        Resuelve la versión de lanzamiento para Fabric y Quilt.

        Estos loaders guardan main_class y extra_libs directamente en
        loader_meta.json. Si además guardaron un JSON en versions_dir
        (install_id presente), lo usa. Si no, construye los datos
        a partir de base_version_data + meta.
        """
        import copy

        # Intentar usar JSON guardado en disco si existe
        install_id = meta.get("install_id")
        if install_id:
            loader_json_path = os.path.join(
                self._settings.versions_dir,
                install_id,
                f"{install_id}.json",
            )
            if os.path.isfile(loader_json_path):
                log.info(f"Usando JSON de {loader_type}: {loader_json_path}")
                with open(loader_json_path, "r", encoding="utf-8") as f:
                    loader_version_data = json.load(f)
                loader_version_data = self._merge_libraries(
                    base_version_data, loader_version_data)
                return install_id, loader_version_data

        # Fallback: construir version_data desde base + meta
        log.info(
            f"{loader_type.capitalize()} sin JSON en disco — "
            f"usando main_class y extra_libs del loader_meta"
        )

        main_class = meta.get("main_class", "")
        extra_libs = meta.get("extra_libs", [])

        if not main_class:
            raise LaunchError(
                f"El loader {loader_type} no tiene main_class en loader_meta.json.\n"
                f"Solución: reinstala el loader."
            )

        # Clonar base_version_data y sobreescribir mainClass
        merged = copy.deepcopy(base_version_data)
        merged["mainClass"] = main_class

        # Agregar las libs del loader al classpath como entradas "extra"
        # Las convertimos al formato de library dict que espera _build_classpath
        base_libs = list(base_version_data.get("libraries", []))
        extra_lib_dicts = [
            {"name": f"__extra__:{os.path.basename(p)}:0",
             "__path__": p}
            for p in extra_libs
            if os.path.isfile(p)
        ]
        merged["libraries"] = base_libs + extra_lib_dicts
        merged["__extra_classpaths__"] = [
            p for p in extra_libs if os.path.isfile(p)
        ]

        return profile.version_id, merged

    def _merge_libraries(
        self,
        base_data: dict,
        loader_data: dict,
    ) -> dict:
        import copy
        merged = copy.deepcopy(loader_data)

        base_libs   = base_data.get("libraries", [])
        loader_libs = loader_data.get("libraries", [])

        lib_map = {}
        for lib in base_libs:
            lib_map[lib.get("name", "")] = lib
        for lib in loader_libs:
            lib_map[lib.get("name", "")] = lib

        merged["libraries"] = list(lib_map.values())
        log.debug(
            f"Librerías fusionadas: {len(base_libs)} base + "
            f"{len(loader_libs)} loader = {len(merged['libraries'])} total"
        )
        return merged

    # ── Construcción del comando ──────────────────────────────────────────────

    def _build_jvm_args(self, profile: Profile, client_jar: str, version_data: dict) -> list[str]:
        ram = profile.ram_mb
        natives_dir = os.path.join(
            self._settings.versions_dir,
            profile.version_id,
            "natives"
        )

        return [
            "-Xms512m",
            f"-Xmx{ram}m",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+UseG1GC",
            "-XX:G1NewSizePercent=20",
            "-XX:G1ReservePercent=20",
            "-XX:MaxGCPauseMillis=50",
            "-XX:G1HeapRegionSize=32M",
            f"-Djava.library.path={natives_dir}",
            f"-Dminecraft.client.jar={client_jar}",
        ]

    def _build_game_args(
        self,
        profile: Profile,
        session: PlayerSession,
        version_data: dict,
    ) -> list[str]:
        assets_index = version_data.get("assetIndex", {}).get("id", "")

        if not assets_index:
            vanilla_json = os.path.join(
                self._settings.versions_dir,
                profile.version_id,
                f"{profile.version_id}.json",
            )
            if os.path.isfile(vanilla_json):
                with open(vanilla_json, "r", encoding="utf-8") as f:
                    vanilla_data = json.load(f)
                assets_index = vanilla_data.get("assetIndex", {}).get("id", "legacy")
            else:
                assets_index = "legacy"

        log.info(f"Assets index usado: {assets_index}")

        replacements = {
            "${auth_player_name}":  session.username,
            "${version_name}":      profile.version_id,
            "${game_directory}":    profile.game_dir,
            "${assets_root}":       self._settings.assets_dir,
            "${assets_index_name}": assets_index,
            "${auth_uuid}":         session.uuid,
            "${auth_access_token}": session.access_token,
            "${user_type}":         "offline",
            "${version_type}":      "release",
            "${resolution_width}":  "854",
            "${resolution_height}": "480",
        }

        raw_args = self._extract_game_arguments(version_data)

        if not raw_args:
            vanilla_json = os.path.join(
                self._settings.versions_dir,
                profile.version_id,
                f"{profile.version_id}.json",
            )
            if os.path.isfile(vanilla_json):
                with open(vanilla_json, "r", encoding="utf-8") as f:
                    vanilla_data = json.load(f)
                raw_args = self._extract_game_arguments(vanilla_data)

        resolved = []
        for arg in raw_args:
            for placeholder, value in replacements.items():
                arg = arg.replace(placeholder, value)
            resolved.append(arg)

        return resolved

    def _extract_game_arguments(self, version_data: dict) -> list[str]:
        if "arguments" in version_data:
            result = []
            for arg in version_data["arguments"].get("game", []):
                if isinstance(arg, str):
                    result.append(arg)
            return result

        if "minecraftArguments" in version_data:
            return version_data["minecraftArguments"].split()

        return []

    def _build_classpath(self, version_id: str, version_data: dict) -> str:
        separator = ";" if os.name == "nt" else ":"
        paths = []
        seen = set()

        # Extra classpaths de Fabric/Quilt (rutas absolutas directas)
        for extra_path in version_data.get("__extra_classpaths__", []):
            if extra_path not in seen and os.path.isfile(extra_path):
                paths.append(extra_path)
                seen.add(extra_path)

        for lib in version_data.get("libraries", []):
            # Libs extras inyectadas por _resolve_fabric_like (ya en __extra_classpaths__)
            if lib.get("name", "").startswith("__extra__:"):
                continue

            artifact = lib.get("downloads", {}).get("artifact", {})
            path = artifact.get("path", "")

            if not path:
                name = lib.get("name", "")
                if name:
                    parts = name.split(":")
                    if len(parts) >= 3:
                        group       = parts[0].replace(".", "/")
                        artifact_id = parts[1]
                        version     = parts[2]
                        path = (
                            f"{group}/{artifact_id}/{version}"
                            f"/{artifact_id}-{version}.jar"
                        )

            if not path or path in seen:
                continue
            seen.add(path)

            lib_path = os.path.join(
                self._settings.libraries_dir, *path.split("/")
            )
            if os.path.isfile(lib_path):
                paths.append(lib_path)
            else:
                log.debug(f"Librería no encontrada: {lib_path}")

        client_jar = self._resolve_client_jar(version_id)
        if client_jar not in seen:
            paths.append(client_jar)

        log.debug(f"Classpath con {len(paths)} entradas")
        return separator.join(paths)

    # ── Ejecución del proceso ─────────────────────────────────────────────────

    def _start_process(self, command, working_dir, on_output=None):
        os.makedirs(working_dir, exist_ok=True)

        kwargs = dict(
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NO_WINDOW |
                subprocess.DETACHED_PROCESS
            )

        try:
            process = subprocess.Popen(command, **kwargs)
            log.info(f"Minecraft iniciado con PID: {process.pid}")
            if on_output:
                self._start_output_reader(process, on_output)
            return process
        except FileNotFoundError as e:
            raise LaunchError(f"No se encontro el ejecutable: {e}")
        except OSError as e:
            raise LaunchError(f"Error al iniciar el proceso: {e}")

    def _start_output_reader(self, process: subprocess.Popen, on_output):
        def _reader():
            try:
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        log.debug(f"[MC] {line}")
                        on_output(line)
            except Exception as e:
                log.debug(f"Output reader terminado: {e}")

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()

    # ── Helpers de rutas ─────────────────────────────────────────────────────

    def _resolve_java(self, profile: Profile) -> str:
        from managers.java_manager import JavaNotFoundError, JavaVersionError

        if profile.java_path and os.path.isfile(profile.java_path):
            log.debug(f"Java del perfil: {profile.java_path}")
            return profile.java_path

        vanilla_json = os.path.join(
            self._settings.versions_dir,
            profile.version_id,
            f"{profile.version_id}.json",
        )
        java_component = "java-runtime-gamma"
        if os.path.isfile(vanilla_json):
            try:
                with open(vanilla_json, "r", encoding="utf-8") as f:
                    vdata = json.load(f)
                java_component = vdata.get("javaVersion", {}).get(
                    "component", "java-runtime-gamma"
                )
            except Exception:
                pass

        log.debug(f"Componente Java requerido: {java_component}")

        try:
            return self._java_manager.get_java_path_for_component(java_component)
        except (JavaNotFoundError, JavaVersionError) as e:
            raise LaunchError(f"Java no disponible: {e}")

    def _resolve_client_jar(self, version_id: str) -> str:
        jar_path = os.path.join(
            self._settings.versions_dir,
            version_id,
            f"{version_id}.jar",
        )

        if not os.path.isfile(jar_path):
            parts        = version_id.split("-")
            base_version = parts[0]
            base_jar     = os.path.join(
                self._settings.versions_dir,
                base_version,
                f"{base_version}.jar",
            )
            if os.path.isfile(base_jar):
                log.debug(f"JAR del loader no existe — usando JAR base: {base_jar}")
                return base_jar

            raise LaunchError(
                f"JAR del cliente no encontrado para '{version_id}'.\n"
                f"Instala la versión de Minecraft antes de lanzar."
            )

        return jar_path