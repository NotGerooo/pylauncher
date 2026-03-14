"""
downloader.py
-------------
Motor de descargas del launcher. Solo usa urllib de la stdlib.
"""
import http.client
import threading
from collections import defaultdict
import os
import time
import urllib.request
import urllib.error
from config.constants import (
    HTTP_TIMEOUT_SECONDS,
    DOWNLOAD_MAX_RETRIES,
    DOWNLOAD_RETRY_DELAY,
    USER_AGENT,
)
from utils.hash_utils import verify_sha1
from utils.file_utils import ensure_dir
from utils.logger import get_logger
log = get_logger()


class DownloadError(Exception):
    pass


class Downloader:
    def __init__(
        self,
        max_retries: int = DOWNLOAD_MAX_RETRIES,
        retry_delay: float = DOWNLOAD_RETRY_DELAY,
        timeout: int = HTTP_TIMEOUT_SECONDS,
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        # Pool de conexiones persistentes por host (thread-safe)
        self._conn_lock = threading.Lock()
        self._sessions = {}  # host -> lista de conexiones libres

    def download(
        self,
        url: str,
        dest_path: str,
        expected_sha1: str = None,
        progress_callback=None,
    ) -> bool:
        if self._is_already_valid(dest_path, expected_sha1):
            log.debug(f"Ya válido, omitiendo: {os.path.basename(dest_path)}")
            return True

        ensure_dir(os.path.dirname(dest_path))
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self._download_with_progress(url, dest_path, progress_callback)
                if expected_sha1 and not verify_sha1(dest_path, expected_sha1):
                    os.remove(dest_path)
                    raise DownloadError(f"Hash inválido: {os.path.basename(dest_path)}")
                return True
            except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        raise DownloadError(f"Fallo tras {self.max_retries} intentos para {url}: {last_error}")

    def _download_with_progress(self, url: str, dest_path: str, progress_callback=None):
        """Descarga usando http.client con conexiones reutilizables."""
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        host   = parsed.netloc
        path   = parsed.path
        if parsed.query:
            path += "?" + parsed.query

        use_https = parsed.scheme == "https"

        conn = (
            http.client.HTTPSConnection(host, timeout=self.timeout)
            if use_https
            else http.client.HTTPConnection(host, timeout=self.timeout)
        )

        try:
            conn.request("GET", path, headers={
                "User-Agent": USER_AGENT,
                "Connection": "keep-alive",
                "Accept-Encoding": "identity",  # Sin compresión — más rápido para binarios
            })
            resp = conn.getresponse()

            if resp.status == 301 or resp.status == 302:
                location = resp.getheader("Location", "")
                conn.close()
                return self._download_with_progress(location, dest_path, progress_callback)

            if resp.status != 200:
                conn.close()
                raise urllib.error.HTTPError(url, resp.status, resp.reason, {}, None)

            total_bytes = int(resp.getheader("Content-Length", 0))
            downloaded  = 0
            chunk_size  = 131072  # 128 KB por chunk — óptimo para assets pequeños y medianos

            tmp_path = dest_path + ".tmp"
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_bytes > 0:
                        progress_callback(
                            downloaded / (1024 * 1024),
                            total_bytes / (1024 * 1024),
                            downloaded / total_bytes * 100,
                        )

            os.replace(tmp_path, dest_path)  # Atómico — evita archivos corruptos
        finally:
            conn.close()

    def download_json(self, url: str) -> dict:
        import tempfile, json as _json
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp_path = tmp.name
        try:
            self._download_with_progress(url, tmp_path)
            with open(tmp_path, "r", encoding="utf-8") as f:
                return _json.load(f)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _is_already_valid(self, dest_path: str, expected_sha1: str) -> bool:
        if not os.path.isfile(dest_path):
            return False
        if expected_sha1:
            return verify_sha1(dest_path, expected_sha1)
        return os.path.getsize(dest_path) > 0
