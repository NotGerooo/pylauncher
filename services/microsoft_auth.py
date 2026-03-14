"""
microsoft_auth.py
-----------------
Autenticación Microsoft para cuentas premium de Minecraft.

Flujo completo:
  1. Microsoft OAuth 2.0 - Device Code Flow (no requiere redirect URI)
  2. Xbox Live (XBL) authentication
  3. XSTS token
  4. Minecraft access token
  5. Obtener perfil de Minecraft (username, UUID, skin)

El Device Code Flow es el ideal para aplicaciones de escritorio:
  - No requiere servidor web local
  - No requiere browser embebido
  - El usuario visita una URL corta en cualquier browser
  - La app hace polling hasta que el usuario completa el login

Uso:
    auth = MicrosoftAuth()
    
    # Iniciar flujo
    code_info = auth.start_device_flow()
    # Mostrar code_info["user_code"] y code_info["verification_uri"] al usuario
    
    # Hacer polling (bloqueante, llamar en un thread)
    result = auth.poll_for_token(code_info)
    if result:
        account = account_manager.add_microsoft_account(**result)

Dependencias: solo stdlib (urllib, json, time)
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from typing import Optional

from utils.logger import get_logger

log = get_logger()


# ─── Constantes OAuth ────────────────────────────────────────────────────────

# Client ID de la aplicación oficial del launcher de Minecraft (pública, conocida)
# Puedes registrar tu propia app en Azure AD para producción.
_CLIENT_ID = "00000000402b5328"

_DEVICE_CODE_URL   = "https://login.live.com/oauth20_connect.srf"
_TOKEN_URL         = "https://login.live.com/oauth20_token.srf"
_XBL_AUTH_URL      = "https://user.auth.xboxlive.com/user/authenticate"
_XSTS_AUTH_URL     = "https://xsts.auth.xboxlive.com/xsts/authorize"
_MC_AUTH_URL       = "https://api.minecraftservices.com/authentication/login_with_xbox"
_MC_PROFILE_URL    = "https://api.minecraftservices.com/minecraft/profile"

_SCOPE             = "XboxLive.signin offline_access"
_POLL_INTERVAL     = 5   # segundos entre intentos de polling
_MAX_POLL_SECONDS  = 300 # 5 minutos máximo de espera


# ─── Excepciones ─────────────────────────────────────────────────────────────

class MicrosoftAuthError(Exception):
    pass

class AuthCancelledError(MicrosoftAuthError):
    pass

class AuthExpiredError(MicrosoftAuthError):
    pass


# ─── MicrosoftAuth ───────────────────────────────────────────────────────────

class MicrosoftAuth:
    """
    Maneja el flujo completo de autenticación Microsoft → Minecraft.

    Thread-safety: cada instancia es independiente.
    Los callbacks son opcionales y se usan para actualizar la UI.
    """

    def __init__(self, on_status: Optional[callable] = None):
        """
        Args:
            on_status: callback(message: str) llamado durante el flujo
                       para actualizar la UI con el estado actual.
        """
        self._on_status = on_status or (lambda msg: log.info(f"[Auth] {msg}"))

    def start_device_flow(self) -> dict:
        """
        Inicia el Device Code Flow de Microsoft.

        Returns:
            dict con:
                user_code        : Código de 8 letras que el usuario debe ingresar
                verification_uri : URL donde el usuario hace login (microsoft.com/devicelogin)
                device_code      : Código interno para hacer polling
                expires_in       : Segundos hasta que el código expire
                interval         : Segundos recomendados entre polls

        Raises:
            MicrosoftAuthError: Si Microsoft rechaza la solicitud
        """
        self._on_status("Solicitando código de dispositivo...")

        params = urllib.parse.urlencode({
            "client_id": _CLIENT_ID,
            "scope":     _SCOPE,
            "response_type": "device_code",
        }).encode()

        try:
            resp = self._post(_DEVICE_CODE_URL, params)
        except Exception as e:
            raise MicrosoftAuthError(f"No se pudo iniciar el login: {e}")

        log.debug(f"Device flow iniciado. Código: {resp.get('user_code')}")
        return resp

    def poll_for_token(self, code_info: dict, cancel_event=None) -> Optional[dict]:
        """
        Hace polling a Microsoft hasta que el usuario complete el login.

        Este método es BLOQUEANTE. Llamarlo en un thread separado.

        Args:
            code_info    : Resultado de start_device_flow()
            cancel_event : threading.Event — si se activa, cancela el polling

        Returns:
            dict con los datos para crear la cuenta, o None si se canceló

        Raises:
            AuthExpiredError  : Si el código expiró antes de que el usuario hiciera login
            MicrosoftAuthError: En caso de error de autenticación
        """
        device_code = code_info["device_code"]
        interval    = int(code_info.get("interval", _POLL_INTERVAL))
        expires_in  = int(code_info.get("expires_in", _MAX_POLL_SECONDS))
        deadline    = time.time() + expires_in

        self._on_status("Esperando que completes el login en el navegador...")

        while time.time() < deadline:
            if cancel_event and cancel_event.is_set():
                log.info("Login de Microsoft cancelado por el usuario.")
                return None

            time.sleep(interval)

            params = urllib.parse.urlencode({
                "client_id":   _CLIENT_ID,
                "grant_type":  "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
            }).encode()

            try:
                resp = self._post(_TOKEN_URL, params, ignore_http_errors=True)
            except Exception as e:
                log.warning(f"Error en poll: {e}, reintentando...")
                continue

            error = resp.get("error")

            if error == "authorization_pending":
                continue  # Normal — el usuario aún no terminó
            elif error == "slow_down":
                interval += 5
                continue
            elif error == "authorization_declined":
                raise MicrosoftAuthError("El usuario canceló el login.")
            elif error == "expired_token":
                raise AuthExpiredError("El código de dispositivo expiró. Intenta de nuevo.")
            elif error:
                raise MicrosoftAuthError(f"Error de Microsoft: {error}")

            # ¡Login exitoso! Tenemos los tokens de Microsoft
            ms_access_token  = resp["access_token"]
            ms_refresh_token = resp["refresh_token"]
            expires_in_secs  = int(resp.get("expires_in", 86400))

            return self._complete_auth_flow(
                ms_access_token,
                ms_refresh_token,
                expires_in_secs,
            )

        raise AuthExpiredError("Tiempo de espera agotado. Intenta el login de nuevo.")

    def refresh_tokens(self, refresh_token: str) -> dict:
        """
        Refresca los tokens de una cuenta Microsoft existente.

        Llamar cuando account.is_token_expired == True, antes de lanzar el juego.

        Args:
            refresh_token: El refresh_token almacenado en la cuenta

        Returns:
            dict con: access_token, refresh_token, token_expiry

        Raises:
            MicrosoftAuthError: Si el refresh_token es inválido o expiró
        """
        self._on_status("Refrescando sesión de Microsoft...")

        params = urllib.parse.urlencode({
            "client_id":     _CLIENT_ID,
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
            "scope":         _SCOPE,
        }).encode()

        try:
            resp = self._post(_TOKEN_URL, params)
        except Exception as e:
            raise MicrosoftAuthError(f"No se pudo refrescar el token: {e}")

        ms_access_token  = resp["access_token"]
        ms_refresh_token = resp.get("refresh_token", refresh_token)
        expires_in_secs  = int(resp.get("expires_in", 86400))

        # Completar el flujo Xbox/Minecraft
        result = self._complete_auth_flow(
            ms_access_token,
            ms_refresh_token,
            expires_in_secs,
        )
        log.info(f"Tokens refrescados para: {result['username']}")
        return result

    # ─── Flujo interno Xbox → Minecraft

    def _complete_auth_flow(
        self,
        ms_access_token:  str,
        ms_refresh_token: str,
        ms_expires_in:    int,
    ) -> dict:
        """
        Ejecuta los pasos Xbox Live → XSTS → Minecraft con el token de Microsoft.

        Returns:
            dict con todos los datos necesarios para crear/actualizar la cuenta
        """
        token_expiry = (
            datetime.utcnow() + timedelta(seconds=ms_expires_in)
        ).isoformat()

        # Paso 2: Autenticación Xbox Live
        self._on_status("Autenticando con Xbox Live...")
        xbl_token, user_hash = self._authenticate_xbox(ms_access_token)

        # Paso 3: Token XSTS
        self._on_status("Obteniendo token XSTS...")
        xsts_token = self._get_xsts_token(xbl_token)

        # Paso 4: Token de Minecraft
        self._on_status("Obteniendo token de Minecraft...")
        mc_access_token = self._get_minecraft_token(xsts_token, user_hash)

        # Paso 5: Perfil de Minecraft
        self._on_status("Obteniendo perfil de Minecraft...")
        profile = self._get_minecraft_profile(mc_access_token)

        username   = profile["name"]
        mc_uuid    = profile["id"]
        # Formatear UUID con guiones: 8-4-4-4-12
        if len(mc_uuid) == 32 and "-" not in mc_uuid:
            mc_uuid = f"{mc_uuid[0:8]}-{mc_uuid[8:12]}-{mc_uuid[12:16]}-{mc_uuid[16:20]}-{mc_uuid[20:]}"

        # Obtener URL de skin (puede ser None)
        avatar_url = self._extract_skin_url(profile)

        self._on_status(f"¡Login exitoso! Bienvenido, {username}.")
        log.info(f"Autenticación Microsoft completada: {username} ({mc_uuid})")

        return {
            "username":      username,
            "player_uuid":   mc_uuid,
            "access_token":  mc_access_token,
            "refresh_token": ms_refresh_token,
            "token_expiry":  token_expiry,
            "avatar_url":    avatar_url,
        }

    def _authenticate_xbox(self, ms_access_token: str) -> tuple[str, str]:
        """Retorna (xbl_token, user_hash)."""
        body = {
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName":   "user.auth.xboxlive.com",
                "RpsTicket":  f"d={ms_access_token}",
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType":    "JWT",
        }
        resp = self._post_json(_XBL_AUTH_URL, body)
        token     = resp["Token"]
        user_hash = resp["DisplayClaims"]["xui"][0]["uhs"]
        return token, user_hash

    def _get_xsts_token(self, xbl_token: str) -> str:
        body = {
            "Properties": {
                "SandboxId":  "RETAIL",
                "UserTokens": [xbl_token],
            },
            "RelyingParty": "rp://api.minecraftservices.com/",
            "TokenType":    "JWT",
        }
        try:
            resp = self._post_json(_XSTS_AUTH_URL, body)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise MicrosoftAuthError(
                    "Esta cuenta de Microsoft no tiene Xbox Live o no tiene Minecraft."
                )
            raise
        return resp["Token"]

    def _get_minecraft_token(self, xsts_token: str, user_hash: str) -> str:
        body = {
            "identityToken": f"XBL3.0 x={user_hash};{xsts_token}"
        }
        resp = self._post_json(_MC_AUTH_URL, body)
        return resp["access_token"]

    def _get_minecraft_profile(self, mc_access_token: str) -> dict:
        """Retorna el perfil de Minecraft con nombre, UUID y skins."""
        req = urllib.request.Request(
            _MC_PROFILE_URL,
            headers={
                "Authorization": f"Bearer {mc_access_token}",
                "Content-Type":  "application/json",
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise MicrosoftAuthError(
                    "Esta cuenta de Microsoft no tiene Minecraft Java Edition."
                )
            raise MicrosoftAuthError(f"Error al obtener perfil: {e}")

    def _extract_skin_url(self, profile: dict) -> Optional[str]:
        """Extrae la URL de la skin activa del perfil de Minecraft."""
        try:
            for skin in profile.get("skins", []):
                if skin.get("state") == "ACTIVE":
                    return skin.get("url")
        except Exception:
            pass
        return None

    # ─── HTTP helpers

    def _post(
        self,
        url:               str,
        data:              bytes,
        ignore_http_errors: bool = False,
    ) -> dict:
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if ignore_http_errors:
                body = e.read().decode()
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return {"error": str(e.code)}
            raise

    def _post_json(self, url: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        req  = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept",       "application/json")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            log.error(f"Error HTTP {e.code} en {url}: {err_body}")
            raise