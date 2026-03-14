"""
skin_service.py
---------------
Gestiona las skins de los jugadores en el launcher.

Funcionalidades:
  - Descargar y cachear skin oficial de cuentas Microsoft
  - Guardar skin personalizada para cuentas offline
  - Renderizar cabeza del avatar (face crop 8x8 del PNG de skin)
  - Proveer imagen de skin por defecto (Steve / Alex)

La skin de Minecraft es un PNG de 64x64 píxeles.
La cara está en la región (8,8) → (16,16) de la capa base.
El overlay de la cara está en (40,8) → (48,16).

Dependencias: solo stdlib (urllib, os, struct, zlib para PNG)
"""

import os
import struct
import zlib
import urllib.request
import urllib.error
from typing import Optional

from utils.logger import get_logger

log = get_logger()


# ─── Constantes ──────────────────────────────────────────────────────────────

_SKIN_CACHE_DIR = "data/skins"
_DEFAULT_SKIN   = "data/skins/default_steve.png"

# Steve skin por defecto en base64 (PNG 64x64 minimal)
# Se genera programáticamente si no existe el archivo
_STEVE_HEAD_COLOR = (106, 127, 58)   # verde-marrón característico
_ALEX_HEAD_COLOR  = (255, 214, 163)  # tono piel claro


# ─── SkinService ─────────────────────────────────────────────────────────────

class SkinService:
    """
    Gestiona la obtención, caché y extracción de skins.

    Uso:
        skin_svc = SkinService()

        # Obtener ruta de skin (descarga si es necesario)
        skin_path = skin_svc.get_skin_path(account)

        # Obtener los datos de la cara (PNG 8x8) para mostrar en la UI
        face_png = skin_svc.get_face_bytes(account)

        # Guardar skin personalizada para cuenta offline
        skin_svc.save_offline_skin(account_id, source_path)
    """

    def __init__(self, cache_dir: str = _SKIN_CACHE_DIR):
        self._cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    # ─── API pública

    def get_skin_path(self, account) -> Optional[str]:
        """
        Retorna la ruta al PNG de skin del jugador.

        Para cuentas Microsoft: descarga desde avatar_url si no está en caché.
        Para cuentas offline:   retorna la ruta guardada en account.skin_path.

        Returns:
            Ruta al archivo PNG, o None si no hay skin disponible
        """
        if account.is_microsoft and account.avatar_url:
            return self._get_cached_skin(account.uuid, account.avatar_url)
        elif not account.is_microsoft and account.skin_path:
            if os.path.isfile(account.skin_path):
                return account.skin_path
        return None

    def get_face_bytes(self, account) -> bytes:
        """
        Retorna el PNG de la cara del jugador (32x32 px, listo para Tkinter).

        Extrae la región de la cara del PNG de skin completo.
        Si no hay skin disponible, retorna la cara de Steve por defecto.

        Returns:
            Bytes del PNG de la cara
        """
        skin_path = self.get_skin_path(account)
        if skin_path and os.path.isfile(skin_path):
            try:
                return self._extract_face_png(skin_path)
            except Exception as e:
                log.warning(f"No se pudo extraer la cara de {skin_path}: {e}")

        return self._default_face_png()

    def save_offline_skin(self, account_id: str, source_path: str) -> str:
        """
        Copia una skin personalizada al directorio de caché del launcher.

        Args:
            account_id  : ID de la cuenta offline
            source_path : Ruta al PNG de skin elegido por el usuario

        Returns:
            Ruta destino donde se guardó la skin

        Raises:
            ValueError: Si el archivo no es un PNG válido de Minecraft
        """
        if not os.path.isfile(source_path):
            raise ValueError(f"Archivo no encontrado: {source_path}")

        self._validate_skin_png(source_path)

        dest_path = os.path.join(self._cache_dir, f"offline_{account_id}.png")

        # Copiar manualmente (sin shutil para mantener stdlib puro)
        with open(source_path, "rb") as src, open(dest_path, "wb") as dst:
            dst.write(src.read())

        log.info(f"Skin offline guardada: {dest_path}")
        return dest_path

    def clear_cache(self, account_id: str):
        """Elimina la skin cacheada de una cuenta Microsoft."""
        cached = os.path.join(self._cache_dir, f"{account_id}.png")
        if os.path.isfile(cached):
            os.remove(cached)
            log.debug(f"Caché de skin eliminada para: {account_id}")

    # ─── Descarga y caché

    def _get_cached_skin(self, account_uuid: str, url: str) -> Optional[str]:
        """Retorna la skin desde caché o la descarga."""
        cached = os.path.join(self._cache_dir, f"{account_uuid}.png")

        if os.path.isfile(cached):
            return cached

        return self._download_skin(url, cached)

    def _download_skin(self, url: str, dest_path: str) -> Optional[str]:
        """Descarga la skin desde la URL oficial de Mojang."""
        try:
            log.debug(f"Descargando skin desde: {url}")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "PyLauncher/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()

            with open(dest_path, "wb") as f:
                f.write(data)

            log.debug(f"Skin descargada: {dest_path}")
            return dest_path

        except (urllib.error.URLError, OSError) as e:
            log.warning(f"No se pudo descargar skin: {e}")
            return None

    # ─── Procesamiento PNG puro (sin Pillow)

    def _extract_face_png(self, skin_path: str, size: int = 32) -> bytes:
        """
        Extrae la región de la cara de un PNG de skin de Minecraft.

        La cara está en (8,8)→(16,16) en la imagen de 64x64.
        El overlay está en (40,8)→(48,16).
        Combina ambas capas y escala al tamaño deseado.

        Returns:
            Bytes del PNG de la cara escalado a `size`x`size`
        """
        pixels = self._read_png(skin_path)
        if pixels is None:
            return self._default_face_png()

        width, height, img_data = pixels
        if width < 16 or height < 16:
            return self._default_face_png()

        # Extraer cara base (8,8)→(16,16) — 8x8 píxeles
        face_pixels = []
        for row in range(8, 16):
            for col in range(8, 16):
                idx = (row * width + col) * 4
                if idx + 4 <= len(img_data):
                    r, g, b, a = img_data[idx:idx+4]
                    face_pixels.append((r, g, b, a))
                else:
                    face_pixels.append((0, 0, 0, 255))

        # Extraer overlay (40,8)→(48,16) si existe
        if width >= 48:
            for i, row in enumerate(range(8, 16)):
                for j, col in enumerate(range(40, 48)):
                    idx = (row * width + col) * 4
                    if idx + 4 <= len(img_data):
                        r, g, b, a = img_data[idx:idx+4]
                        if a > 0:  # Solo aplicar si el overlay no es transparente
                            face_pixels[i * 8 + j] = (r, g, b, a)

        # Escalar 8x8 → size x size (nearest neighbor)
        scale  = size // 8
        scaled = []
        for fy in range(8):
            for _ in range(scale):
                for fx in range(8):
                    pixel = face_pixels[fy * 8 + fx]
                    for _ in range(scale):
                        scaled.append(pixel)

        return self._encode_png(size, size, scaled)

    def _read_png(self, path: str) -> Optional[tuple]:
        """
        Lee un PNG y retorna (width, height, raw_rgba_bytes).
        Implementación mínima que soporta PNG de 8-bit RGBA/RGB.
        """
        try:
            with open(path, "rb") as f:
                data = f.read()

            # Verificar firma PNG
            if data[:8] != b'\x89PNG\r\n\x1a\n':
                return None

            # Leer IHDR
            ihdr_len = struct.unpack(">I", data[8:12])[0]
            if data[12:16] != b'IHDR':
                return None

            width, height = struct.unpack(">II", data[16:24])
            bit_depth     = data[24]
            color_type    = data[25]  # 2=RGB, 6=RGBA

            if bit_depth != 8:
                return None

            # Recolectar chunks IDAT
            idat_data = bytearray()
            pos = 8
            while pos < len(data) - 12:
                chunk_len  = struct.unpack(">I", data[pos:pos+4])[0]
                chunk_type = data[pos+4:pos+8]
                chunk_data = data[pos+8:pos+8+chunk_len]
                if chunk_type == b'IDAT':
                    idat_data.extend(chunk_data)
                elif chunk_type == b'IEND':
                    break
                pos += 12 + chunk_len

            raw = zlib.decompress(bytes(idat_data))

            # Desfiltrar líneas
            bpp        = 4 if color_type == 6 else 3
            stride     = width * bpp
            pixels_raw = bytearray()
            prev_row   = bytearray(stride)

            raw_pos = 0
            for _ in range(height):
                filter_byte = raw[raw_pos]
                raw_pos += 1
                scanline = bytearray(raw[raw_pos:raw_pos + stride])
                raw_pos += stride

                if filter_byte == 0:
                    pass
                elif filter_byte == 1:
                    for i in range(bpp, stride):
                        scanline[i] = (scanline[i] + scanline[i - bpp]) & 0xFF
                elif filter_byte == 2:
                    for i in range(stride):
                        scanline[i] = (scanline[i] + prev_row[i]) & 0xFF
                elif filter_byte == 3:
                    for i in range(stride):
                        a = scanline[i - bpp] if i >= bpp else 0
                        scanline[i] = (scanline[i] + (a + prev_row[i]) // 2) & 0xFF
                elif filter_byte == 4:
                    for i in range(stride):
                        a = scanline[i - bpp] if i >= bpp else 0
                        b = prev_row[i]
                        c = prev_row[i - bpp] if i >= bpp else 0
                        p = a + b - c
                        pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
                        pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                        scanline[i] = (scanline[i] + pr) & 0xFF

                # Convertir RGB→RGBA si necesario
                if color_type == 2:
                    for i in range(width):
                        pixels_raw.extend(scanline[i*3:i*3+3])
                        pixels_raw.append(255)
                else:
                    pixels_raw.extend(scanline)

                prev_row = scanline

            return (width, height, bytes(pixels_raw))

        except Exception as e:
            log.debug(f"Error leyendo PNG {path}: {e}")
            return None

    def _encode_png(self, width: int, height: int, pixels: list) -> bytes:
        """
        Codifica una lista de (r,g,b,a) a PNG RGBA sin compresión.
        Solo para imágenes pequeñas (caras 32x32).
        """
        raw = bytearray()
        for y in range(height):
            raw.append(0)  # filter byte: None
            for x in range(width):
                r, g, b, a = pixels[y * width + x]
                raw.extend([r, g, b, a])

        compressed = zlib.compress(bytes(raw), 9)

        def chunk(name: bytes, data: bytes) -> bytes:
            c = name + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        png  = b'\x89PNG\r\n\x1a\n'
        png += chunk(b'IHDR', ihdr_data)
        png += chunk(b'IDAT', compressed)
        png += chunk(b'IEND', b'')
        return png

    def _default_face_png(self, size: int = 32) -> bytes:
        """Genera una cara de Steve por defecto (verde-marrón sólido)."""
        r, g, b = 106, 127, 58
        pixels  = [(r, g, b, 255)] * (size * size)
        return self._encode_png(size, size, pixels)

    def _validate_skin_png(self, path: str):
        """Valida que el archivo sea un PNG de Minecraft (64x32 o 64x64)."""
        result = self._read_png(path)
        if result is None:
            raise ValueError("El archivo no es un PNG válido.")
        width, height, _ = result
        if width not in (64,) or height not in (32, 64):
            raise ValueError(
                f"La skin debe ser un PNG de 64x32 o 64x64 píxeles. "
                f"Este archivo es {width}x{height}."
            )