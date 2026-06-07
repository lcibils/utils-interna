"""
utils_interna/teams.py

Envío de notificaciones a Microsoft Teams vía API interna MIEM.

El servicio gestiona la autenticación contra Azure automáticamente;
el cliente solo necesita la URL del endpoint.

Variables de entorno (o pasar explícitamente via TeamsConfig):
    TEAMS_API_URL    - URL del endpoint (default: https://automatizacion.miem.gub.uy/enviar-a-teams)
    TEAMS_VERIFY_SSL - Verificar certificado SSL (default: true)
"""

import os
from dataclasses import dataclass, field
from typing import Optional

import requests

from .logger import get_logger

logger = get_logger(__name__)

_DEFAULT_API_URL = "https://automatizacion.miem.gub.uy/enviar-a-teams"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class TeamsConfig:
    """Configuración de conexión a la API de notificaciones Teams."""
    api_url:    str  = field(default_factory=lambda: os.getenv("TEAMS_API_URL", _DEFAULT_API_URL))
    verify_ssl: bool = field(default_factory=lambda: os.getenv("TEAMS_VERIFY_SSL", "true").lower() == "true")
    timeout:    int  = 10

    def validate(self) -> None:
        if not self.api_url:
            raise ValueError("Configuración de Teams incompleta. Falta: TEAMS_API_URL")


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------

def send_notification_teams(
    email: str,
    asunto: str,
    config: Optional[TeamsConfig] = None,
) -> bool:
    """
    Envía una notificación a un canal de Microsoft Teams vía API interna MIEM.

    El servicio determina el canal de destino a partir del email del destinatario
    y gestiona la autenticación contra Azure de forma transparente.

    Args:
        email:  Dirección de correo del destinatario (ej. "usuario@miem.gub.uy").
        asunto: Mensaje o asunto de la notificación.
        config: Instancia de TeamsConfig. Si es None, usa variables de entorno.

    Returns:
        True si la notificación fue aceptada (HTTP 202), False en caso contrario.

    Example:
        from utils_interna import send_notification_teams

        send_notification_teams(
            "usuario@miem.gub.uy",
            "El expediente Nro. 1234 fue aprobado.",
        )
    """
    if config is None:
        config = TeamsConfig()

    try:
        config.validate()
    except ValueError as e:
        logger.error("teams_config_error", error=str(e))
        return False

    payload = {"email": email, "asunto": asunto}

    try:
        response = requests.post(
            config.api_url,
            json=payload,
            verify=config.verify_ssl,
            timeout=config.timeout,
        )

        if response.status_code == 202:
            logger.info("teams_notification_sent", email=email)
            return True

        if response.status_code == 503:
            logger.warning(
                "teams_service_unavailable",
                email=email,
                detail="El servicio no está disponible temporalmente. Reintentar en unos segundos.",
            )
        else:
            logger.error(
                "teams_notification_error",
                email=email,
                status_code=response.status_code,
                response=response.text,
            )
        return False

    except Exception as e:
        logger.error("teams_connection_error", email=email, error=str(e))
        return False
