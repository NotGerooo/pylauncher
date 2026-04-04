import json
import hashlib
import urllib.request
import urllib.parse
import urllib.error

from config.constants import (
    MODRINTH_API_BASE_URL,
    MODRINTH_DEFAULT_PAGE_SIZE,
    HTTP_TIMEOUT_SECONDS,
    USER_AGENT,
)
from utils.logger import get_logger

log = get_logger()


class ModrinthError(Exception):
    pass


class ModrinthProject:
    def __init__(self, data: dict):
        self.project_id    = data.get("project_id", data.get("id", ""))
        self.slug          = data.get("slug", "")
        self.title         = data.get("title", "")
        self.description   = data.get("description", "")
        self.downloads     = data.get("downloads", 0)
        self.game_versions = data.get("game_versions", [])
        self.categories    = data.get("categories", [])
        self.icon_url      = data.get("icon_url", "")
        self.source_url    = data.get("source_url", "")
        # author viene como "author" en /search, o como "team" en /project
        self.author        = data.get("author", data.get("team", ""))
        self.date_modified = data.get("date_modified", data.get("date_updated", ""))

    def supports_version(self, mc_version: str) -> bool:
        return mc_version in self.game_versions

    def to_dict(self):
        return {
            "project_id":   self.project_id,
            "slug":         self.slug,
            "title":        self.title,
            "description":  self.description,
            "downloads":    self.downloads,
            "game_versions":self.game_versions,
            "categories":   self.categories,
            "icon_url":     self.icon_url,
            "author":       self.author,
        }

    def __repr__(self):
        return f"ModrinthProject({self.title!r}, {self.downloads} descargas)"


class ModrinthVersion:
    def __init__(self, data: dict):
        self.version_id     = data.get("id", "")
        self.project_id     = data.get("project_id", "")
        self.name           = data.get("name", "")
        self.version_number = data.get("version_number", "")
        self.game_versions  = data.get("game_versions", [])
        self.loaders        = data.get("loaders", [])
        self.files          = data.get("files", [])
        self.date_published = data.get("date_published", "")

    def get_primary_file(self) -> dict | None:
        for f in self.files:
            if f.get("primary", False):
                return f
        return self.files[0] if self.files else None

    def to_dict(self):
        return {
            "version_id":    self.version_id,
            "project_id":    self.project_id,
            "name":          self.name,
            "version_number":self.version_number,
            "game_versions": self.game_versions,
            "loaders":       self.loaders,
            "files":         self.files,
        }

    def __repr__(self):
        return f"ModrinthVersion({self.name!r}, MC={self.game_versions})"


class ModrinthService:
    def __init__(self):
        self._base_url = MODRINTH_API_BASE_URL
        self._timeout  = HTTP_TIMEOUT_SECONDS

    # ── Búsqueda ──────────────────────────────────────────────────────────────
    def search_mods(
        self,
        query: str,
        mc_version: str = None,
        loader: str = None,
        limit: int = MODRINTH_DEFAULT_PAGE_SIZE,
        offset: int = 0,
        sort_by: str = "relevance",
        project_type: str = "mod",
        categories: list = None,
        excluded_cats: list = None,   
    ) -> list[ModrinthProject]:
        facets = [[f"project_type:{project_type}"]]

        if mc_version:
            facets.append([f"versions:{mc_version}"])
        if loader:
            facets.append([f"categories:{loader}"])
        # Categorías: cada una va como facet OR dentro del mismo sub-array
        # Ej: ["categories:optimization", "categories:utility"] = OR entre ellas
        if categories:
            facets.append([f"categories:{c.lower()}" for c in categories])

        params = {
            "limit":   limit,
            "offset":  offset,
            "index":   sort_by,
            "facets":  json.dumps(facets),
        }
        if query:
            params["query"] = query

        url  = f"{self._base_url}/search?{urllib.parse.urlencode(params)}"
        data = self._get(url)

        self._last_total_hits = data.get("total_hits", 0)

        projects = [ModrinthProject(hit) for hit in data.get("hits", [])]
        log.info(f"Modrinth: {len(projects)} resultados (type={project_type},"
                f" sort={sort_by}, offset={offset})")
        return projects

    # ── Proyecto individual ───────────────────────────────────────────────────
    def get_project(self, id_or_slug: str) -> ModrinthProject:
        url  = f"{self._base_url}/project/{id_or_slug}"
        data = self._get(url)
        return ModrinthProject(data)

    # ── Lookup por hash SHA1 del archivo ─────────────────────────────────────
    def get_project_by_file_hash(self, file_path: str) -> ModrinthProject | None:
        """
        Dado el path de un archivo local (.jar / .zip), calcula su SHA1
        y consulta GET /version_file/{hash} para obtener el proyecto exacto.

        Devuelve ModrinthProject con icon_url, o None si no está en Modrinth.
        Este método es 100% preciso: no hay ambigüedad de nombre de archivo.
        """
        try:
            sha1 = self._sha1(file_path)
        except OSError:
            return None

        url = f"{self._base_url}/version_file/{sha1}"
        try:
            version_data = self._get(url)
        except ModrinthError:
            # 404 = archivo no registrado en Modrinth (mod manual, fork, etc.)
            return None

        # /version_file devuelve un objeto Version; necesitamos el proyecto
        project_id = version_data.get("project_id", "")
        if not project_id:
            return None

        try:
            return self.get_project(project_id)
        except ModrinthError:
            return None

    # ── Versiones de un proyecto ──────────────────────────────────────────────
    def get_project_versions(
        self,
        id_or_slug: str,
        mc_version: str = None,
        loader: str = None,
    ) -> list[ModrinthVersion]:
        params = {}
        if mc_version:
            params["game_versions"] = json.dumps([mc_version])
        if loader:
            params["loaders"] = json.dumps([loader])

        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url   = f"{self._base_url}/project/{id_or_slug}/version{query}"
        data  = self._get(url)
        versions = [ModrinthVersion(v) for v in data]
        log.info(f"Modrinth: {len(versions)} versiones para '{id_or_slug}'")
        return versions

    def get_latest_version(
        self,
        id_or_slug: str,
        mc_version: str = None,
        loader: str = None,
    ) -> ModrinthVersion | None:
        versions = self.get_project_versions(id_or_slug, mc_version, loader)
        return versions[0] if versions else None

    # ── Descarga ──────────────────────────────────────────────────────────────
    def download_mod_version(
        self,
        version: ModrinthVersion,
        dest_dir: str,
        progress_callback=None,
    ) -> str:
        primary_file = version.get_primary_file()
        if not primary_file:
            raise ModrinthError(
                f"No se encontro archivo en version {version.version_id}")

        url           = primary_file.get("url", "")
        filename      = primary_file.get("filename", "mod.jar")
        expected_sha1 = primary_file.get("hashes", {}).get("sha1", "")

        if not url:
            raise ModrinthError(f"URL de descarga vacia para {filename}")

        from core.downloader import Downloader, DownloadError
        from utils.file_utils import ensure_dir

        ensure_dir(dest_dir)
        dest_path  = f"{dest_dir}/{filename}"
        downloader = Downloader()

        try:
            downloader.download(
                url=url,
                dest_path=dest_path,
                expected_sha1=expected_sha1 if expected_sha1 else None,
                progress_callback=progress_callback,
            )
        except DownloadError as e:
            raise ModrinthError(f"Error descargando {filename}: {e}")

        log.info(f"Mod descargado: {filename} → {dest_dir}")
        return dest_path

    # ── HTTP helper ───────────────────────────────────────────────────────────
    def _get(self, url: str) -> dict | list:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept":     "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            raise ModrinthError(f"HTTP {e.code} desde Modrinth: {url}")
        except urllib.error.URLError as e:
            raise ModrinthError(f"Error de red con Modrinth: {e.reason}")
        except json.JSONDecodeError as e:
            raise ModrinthError(f"Respuesta invalida de Modrinth: {e}")

    # ── SHA1 helper ───────────────────────────────────────────────────────────
    @staticmethod
    def _sha1(file_path: str) -> str:
        h = hashlib.sha1()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()