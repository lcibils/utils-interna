"""
utils_interna/dnic.py

Consulta de datos de persona a partir de cédula de identidad, vía API interna DNIC (MIEM).
Autenticación mediante HMAC-SHA256 + número de secuencia incremental.

Variables de entorno (o pasar explícitamente via DnicConfig):
    DNIC_API_SECRET  - Clave secreta HMAC (requerida). Solicitar a Infraestructura.
    DNIC_API_URL     - URL base de la API (default: https://automatizacion.miem.gub.uy/api/dnic)
    DNIC_VERIFY_SSL  - Verificar certificado SSL (default: false, certificados internos)

ADVERTENCIA: Esta API impacta contra el WebService de DNIC de Producción.
             Usar con criterio. No apta para aplicaciones expuestas a la ciudadanía.
"""

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
import urllib3

from .logger import get_logger

logger = get_logger(__name__)

_DEFAULT_API_URL = "https://automatizacion.miem.gub.uy/api/dnic"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class DnicConfig:
    """Configuración de conexión a la API interna DNIC."""
    api_url:    str  = field(default_factory=lambda: os.getenv("DNIC_API_URL", _DEFAULT_API_URL))
    secret_key: str  = field(default_factory=lambda: os.getenv("DNIC_API_SECRET", ""))
    verify_ssl: bool = field(default_factory=lambda: os.getenv("DNIC_VERIFY_SSL", "false").lower() == "true")
    timeout:    int  = 10

    def validate(self) -> None:
        if not self.secret_key:
            raise ValueError("Configuración DNIC incompleta. Falta: DNIC_API_SECRET")


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------

def query_person(
    nrodocumento: str,
    config: Optional[DnicConfig] = None,
) -> Optional[dict]:
    """
    Consulta datos de una persona a partir de su número de documento (cédula).

    Obtiene automáticamente el último número de secuencia del servidor antes de
    enviar la petición, incrementándolo en 1. Si el endpoint de secuencia no está
    disponible, usa un timestamp en milisegundos como fallback.

    Args:
        nrodocumento: Número de cédula de identidad (ej. "43146984").
        config:       Instancia de DnicConfig. Si es None, usa variables de entorno.

    Returns:
        Dict con los datos de la persona (nombre, apellidos, sexo, fecha de
        nacimiento, etc.), o None si hubo error o el documento no fue encontrado.

    Example:
        from utils_interna import query_person

        datos = query_person("43146984")
        if datos:
            print(datos["nombre1"], datos["primerApellido"])
    """
    if config is None:
        config = DnicConfig()

    try:
        config.validate()
    except ValueError as e:
        logger.error("dnic_config_error", error=str(e))
        return None

    if not config.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    seq = _next_sequence(config)
    payload = {"Nrodocumento": nrodocumento}
    body    = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(
        config.secret_key.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "Content-Type":  "application/json",
        "X-Signature":   signature,
        "X-Request-Seq": str(seq),
    }

    try:
        response = requests.post(
            config.api_url,
            data=body,
            headers=headers,
            verify=config.verify_ssl,
            timeout=config.timeout,
        )

        if response.status_code == 200:
            logger.info("dnic_query_ok", nrodocumento=nrodocumento)
            return response.json()

        if response.status_code == 404:
            logger.warning("dnic_not_found", nrodocumento=nrodocumento)
            return None

        logger.error(
            "dnic_query_error",
            nrodocumento=nrodocumento,
            status_code=response.status_code,
            response=response.text,
        )
        return None

    except Exception as e:
        logger.error("dnic_connection_error", nrodocumento=nrodocumento, error=str(e))
        return None


def get_sequence(config: Optional[DnicConfig] = None) -> Optional[int]:
    """
    Obtiene el último número de secuencia procesado por la API DNIC.

    Útil para sincronizar el contador de secuencia antes de enviar peticiones
    desde una nueva instancia o cliente.

    Args:
        config: Instancia de DnicConfig. Si es None, usa variables de entorno.

    Returns:
        Último número de secuencia (int), o None si hubo error.

    Example:
        seq = get_sequence()
        print(f"Próxima secuencia a usar: {seq + 1}")
    """
    if config is None:
        config = DnicConfig()

    if not config.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        response = requests.get(
            f"{config.api_url}/sequence",
            verify=config.verify_ssl,
            timeout=config.timeout,
        )

        if response.status_code == 200:
            return response.json().get("ultima_secuencia")

        logger.error("dnic_sequence_error", status_code=response.status_code)
        return None

    except Exception as e:
        logger.error("dnic_sequence_connection_error", error=str(e))
        return None


# ---------------------------------------------------------------------------
# Privado
# ---------------------------------------------------------------------------

def _next_sequence(config: DnicConfig) -> int:
    """Retorna el próximo número de secuencia a usar (último conocido + 1)."""
    last = get_sequence(config)
    if last is not None:
        return last + 1
    # Fallback: timestamp en milisegundos (siempre creciente)
    return int(time.time() * 1000)
