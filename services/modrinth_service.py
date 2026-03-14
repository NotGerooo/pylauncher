"""
modrinth_service.py
-------------------
Integración completa con la API pública de Modrinth v2.
Solo usa urllib de la stdlib.
"""
import json
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
        self.project_id = data.get("project_id", data.get("id", ""))
        self.slug = data.get("slug", "")
        self.title = data.get("title", "")
        self.description = data.get("description", "")
        self.downloads = data.get("downloads", 0)
        self.game_versions = data.get("game_versions", [])
        self.categories = data.get("categories", [])
        self.icon_url = data.get("icon_url", "")

    def supports_version(self, mc_version: str) -> bool:
        return mc_version in self.game_versions

    def to_dict(self):
        return {"project_id": self.project_id, "slug": self.slug, "title": self.title,
                "description": self.description, "downloads": self.downloads,
                "game_versions": self.game_versions, "categories": self.categories}

    def __repr__(self):
        return f"ModrinthProject({self.title!r}, {self.downloads} descargas)"


class ModrinthVersion:
    def __init__(self, data: dict):
        self.version_id = data.get("id", "")
        self.project_id = data.get("project_id", "")
        self.name = data.get("name", "")
        self.version_number = data.get("version_number", "")
        self.game_versions = data.get("game_versions", [])
        self.loaders = data.get("loaders", [])
        self.files = data.get("files", [])
        self.date_published = data.get("date_published", "")

    def get_primary_file(self):
        for f in self.files:
            if f.get("primary", False):
                return f
        return self.files[0] if self.files else None

    def __repr__(self):
        return f"ModrinthVersion({self.name!r}, MC={self.game_versions})"


class ModrinthService:
    def __init__(self):
        self._base_url = MODRINTH_API_BASE_URL
        self._timeout = HTTP_TIMEOUT_SECONDS

    def search_mods(self, query: str, mc_version: str = None, loader: str = None,
                    limit: int = MODRINTH_DEFAULT_PAGE_SIZE, offset: int = 0) -> list:
        facets = []
        if mc_version:
            facets.append([f"versions:{mc_version}"])
        if loader:
            facets.append([f"categories:{loader}"])
        facets.append(["project_type:mod"])
        params = {"query": query, "limit": limit, "offset": offset,
                  "facets": json.dumps(facets)}
        url = f"{self._base_url}/search?{urllib.parse.urlencode(params)}"
        data = self._get(url)
        return [ModrinthProject(hit) for hit in data.get("hits", [])]
    
    def search_projects(
        self,
        query: str,
        project_type: str,
        mc_version: str = None,
        loader: str = None,
        limit: int = MODRINTH_DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> list[ModrinthProject]:
        facets = [
                [f"project_type:{project_type}"]
        ]
        if mc_version:
            facets.append([f"versions:{mc_version}"])
        if loader:
            facets.append([f"categories:{loader}"])

        params = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "facets": json.dumps(facets),
        }
        url = f"{self._base_url}/search?{urllib.parse.urlencode(params)}"
        data = self._get(url)
        projects = [ModrinthProject(hit) for hit in data.get("hits", [])]
        log.info(f"Modrinth [{project_type}]: {len(projects)} resultados para '{query}'")
        return projects

    def get_project(self, id_or_slug: str) -> ModrinthProject:
        url = f"{self._base_url}/project/{id_or_slug}"
        return ModrinthProject(self._get(url))

    def get_project_versions(self, id_or_slug: str, mc_version: str = None, loader: str = None) -> list:
        params = {}
        if mc_version:
            params["game_versions"] = json.dumps([mc_version])
        if loader:
            params["loaders"] = json.dumps([loader])
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self._base_url}/project/{id_or_slug}/version{query}"
        return [ModrinthVersion(v) for v in self._get(url)]

    def get_latest_version(self, id_or_slug: str, mc_version: str = None, loader: str = None):
        versions = self.get_project_versions(id_or_slug, mc_version, loader)
        return versions[0] if versions else None

    def download_mod_version(self, version: ModrinthVersion, dest_dir: str, progress_callback=None) -> str:
        primary_file = version.get_primary_file()
        if not primary_file:
            raise ModrinthError(f"No se encontro archivo en version {version.version_id}")
        url = primary_file.get("url", "")
        filename = primary_file.get("filename", "mod.jar")
        expected_sha1 = primary_file.get("hashes", {}).get("sha1", "")
        if not url:
            raise ModrinthError(f"URL de descarga vacia para {filename}")
        from core.downloader import Downloader, DownloadError
        from utils.file_utils import ensure_dir
        ensure_dir(dest_dir)
        dest_path = f"{dest_dir}/{filename}"
        downloader = Downloader()
        try:
            downloader.download(url=url, dest_path=dest_path,
                                expected_sha1=expected_sha1 if expected_sha1 else None,
                                progress_callback=progress_callback)
        except DownloadError as e:
            raise ModrinthError(f"Error descargando {filename}: {e}")
        log.info(f"Mod descargado: {filename} -> {dest_dir}")
        return dest_path

    def _get(self, url: str):
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ModrinthError(f"HTTP {e.code} desde Modrinth: {url}")
        except urllib.error.URLError as e:
            raise ModrinthError(f"Error de red con Modrinth: {e.reason}")
        except json.JSONDecodeError as e:
            raise ModrinthError(f"Respuesta invalida de Modrinth: {e}")
