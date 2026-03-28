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
        """
        Lanza Minecraft para un perfil y sesión dados.

        Primero busca si el perfil tiene un loader activo. Si lo tiene,
        carga los datos de la versión del loader en vez de la vanilla y
        construye el classpath con esa versión.

        Args:
            profile      : Perfil con la configuración del juego
            session      : Sesión del jugador (offline u online)
            version_data : JSON de metadatos de la versión base (vanilla)
            on_output    : callback(line: str) para recibir output en tiempo real

        Returns:
            Proceso subprocess.Popen activo

        Raises:
            LaunchError: Si Java no se encuentra, el JAR no existe, o el
                         loader está instalado pero su JSON no se encuentra
        """
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
        """
        Retorna el comando completo como string sin ejecutarlo.
        Útil para debug y para mostrarlo en la UI.
        """
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

        # load_loader_meta devuelve un dict (o {}) con la meta del loader del perfil
        meta = self._loader_manager.load_loader_meta(profile.game_dir)

        loader_type = meta.get("loader", "vanilla")

        if not meta or loader_type == "vanilla":
            log.info("Sin loader activo — lanzando Minecraft vanilla")
            return profile.version_id, base_version_data

        loader_version_id = meta.get("install_id")

        if not loader_version_id:
            log.info("Sin install_id en loader_meta — lanzando vanilla")
            return profile.version_id, base_version_data

        log.info(
            f"Loader detectado: {loader_type} "
            f"({meta.get('loader_version')}) → versión '{loader_version_id}'"
        )

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

        import json
        with open(loader_json_path, "r", encoding="utf-8") as f:
            loader_version_data = json.load(f)

        loader_version_data = self._merge_libraries(base_version_data, loader_version_data)
        return loader_version_id, loader_version_data

    def _merge_libraries(
        self,
        base_data: dict,
        loader_data: dict,
    ) -> dict:
        """
        Fusiona las librerías del JSON vanilla con las del JSON del loader.

        Por qué es necesario:
        Fabric y Quilt exponen su propio JSON de versión pero NO incluyen
        las librerías base de Minecraft, solo las suyas propias. Sin fusionar,
        el classpath quedaría incompleto y el juego no arrancaría.

        Returns:
            Copia del loader_data con la lista de librerías combinada.
        """
        import copy
        merged = copy.deepcopy(loader_data)

        base_libs   = base_data.get("libraries", [])
        loader_libs = loader_data.get("libraries", [])

        # Usamos el "name" de cada librería como clave para deduplicar.
        # Las librerías del loader tienen prioridad si hay conflicto de nombre.
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
        """
        Construye los argumentos de la JVM.

        Incluye:
        - Memoria mínima (512 MB fija) y máxima (configurada en el perfil)
        - Flags de rendimiento G1GC recomendados para Minecraft
        - Ruta de librerías nativas del juego
        - Ruta del JAR del cliente (requerida por algunos loaders)
        """
        ram = profile.ram_mb
        natives_dir = os.path.join(
            self._settings.versions_dir,
            profile.version_id,
            "natives"
        ) # Asume que los natives ya fueron extraídos durante la instalación

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
        # Si el loader no tiene assetIndex, buscar en el JSON vanilla base
        assets_index = version_data.get("assetIndex", {}).get("id", "")
        
        if not assets_index:
            # Intentar leer del JSON vanilla directamente
            import json
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

        # Si el version_data del loader no tiene game args, usar los del vanilla
        if not raw_args:
            import json
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
        """
        Extrae la lista de argumentos del juego del JSON de versión.
        Maneja tanto el formato nuevo (1.13+) como el viejo (pre-1.13).
        """
        # Formato nuevo
        if "arguments" in version_data:
            result = []
            for arg in version_data["arguments"].get("game", []):
                if isinstance(arg, str):
                    result.append(arg)
                # Los dicts son argumentos condicionales — los ignoramos por ahora
            return result

        # Formato viejo
        if "minecraftArguments" in version_data:
            return version_data["minecraftArguments"].split()

        return []
    
    def _build_classpath(self, version_id: str, version_data: dict) -> str:
        separator = ";" if os.name == "nt" else ":"
        paths = []
        seen = set()

        for lib in version_data.get("libraries", []):
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
                        path = os.path.join(
                            group.replace(".", "/"),
                            artifact_id,
                            version,
                            f"{artifact_id}-{version}.jar"
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
        paths.append(client_jar)

        log.debug(f"Classpath con {len(paths)} entradas")
        return separator.join(paths)

    # ── Ejecución del proceso ─────────────────────────────────────────────────

    def _start_process(self, command, working_dir, on_output=None):
        import subprocess
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
            import ctypes
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

    def _start_output_reader(
        self,
        process: subprocess.Popen,
        on_output,
    ):
        """
        Lanza un hilo daemon que lee el output de Minecraft en tiempo real.

        Por qué un hilo separado:
        Si leyéramos el output en el hilo principal, el launcher se congelaría
        esperando que el juego termine. Con un hilo daemon, el launcher sigue
        respondiendo mientras el juego está corriendo.
        """
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
        """
        Decide qué Java usar en este orden de prioridad:
        1. Java específico configurado en el perfil
        2. Java global del launcher (Settings)
        3. Java autodetectado por JavaManager

        Raises:
            LaunchError: Si no se encuentra ningún Java válido
        """
        from managers.java_manager import JavaNotFoundError, JavaVersionError

        if profile.java_path and os.path.isfile(profile.java_path):
            log.debug(f"Java del perfil: {profile.java_path}")
            return profile.java_path

        try:
            return self._java_manager.get_java_path()
        except (JavaNotFoundError, JavaVersionError) as e:
            raise LaunchError(f"Java no disponible: {e}")

    def _resolve_client_jar(self, version_id: str) -> str:
        """
        Retorna la ruta al JAR del cliente de Minecraft para esta versión.

        Raises:
            LaunchError: Si el JAR no está en disco (versión no instalada)
        """
        jar_path = os.path.join(
            self._settings.versions_dir,
            version_id,
            f"{version_id}.jar",
        )

        # Los loaders (Fabric, Quilt) no tienen JAR propio —
        # usan el JAR de la versión vanilla base.
        if not os.path.isfile(jar_path):
            parts        = version_id.split("-")
            base_version = parts[0]  # "1.20.4" de "1.20.4-fabric-0.15.7"
            base_jar     = os.path.join(
                self._settings.versions_dir,
                base_version,
                f"{base_version}.jar",
            )
            if os.path.isfile(base_jar):
                log.debug(
                    f"JAR del loader no existe — usando JAR base: {base_jar}"
                )
                return base_jar

            raise LaunchError(
                f"JAR del cliente no encontrado para '{version_id}'.\n"
                f"Instala la versión de Minecraft antes de lanzar."
            )

        return jar_path
