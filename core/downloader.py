"""Descargador genérico con callback de progreso."""
import requests
from pathlib import Path
from utils.helpers import get_logger

log = get_logger("downloader")


def download(url: str, dest: Path, on_progress=None):
    """Descarga url → dest; llama on_progress(pct) si se provee."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    size = int(r.headers.get("content-length", 0))
    done = 0
    with open(dest, "wb") as f:
        for chunk in r.iter_content(65536):
            f.write(chunk)
            done += len(chunk)
            if on_progress and size:
                on_progress(done / size * 100)
    log.debug("descargado %s → %s", url, dest)
