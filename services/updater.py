"""Auto-actualización — consulta GitHub Releases."""
import threading, requests
from config.constants import APP_VERSION
from utils.helpers import get_logger

RELEASES_API = "https://api.github.com/repos/NotGerooo/zen-launcher/releases/latest"
log = get_logger("updater")


def _ver(v: str) -> tuple:
    return tuple(int(x) for x in v.lstrip("v").split("."))


def check_async(callback):
    """Fire-and-forget: llama callback(info) si hay versión nueva."""
    def _work():
        try:
            r = requests.get(RELEASES_API, timeout=8)
            d = r.json()
            tag = d.get("tag_name", "0.0.0")
            if _ver(tag) > _ver(APP_VERSION):
                asset = next((a for a in d.get("assets", [])
                              if a["name"].endswith(".exe")), None)
                callback({
                    "version": tag,
                    "url": asset["browser_download_url"] if asset else "",
                })
        except Exception as e:
            log.debug("update check: %s", e)
    threading.Thread(target=_work, daemon=True, name="updater").start()


def download(url: str, on_progress=None) -> str:
    import tempfile
    r = requests.get(url, stream=True, timeout=60)
    size = int(r.headers.get("content-length", 0))
    tmp = tempfile.mktemp(suffix=".exe")
    done = 0
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(65536):
            f.write(chunk)
            done += len(chunk)
            if on_progress and size:
                on_progress(done / size * 100)
    return tmp


def apply(exe_path: str):
    import subprocess, sys
    subprocess.Popen([exe_path])
    sys.exit(0)
