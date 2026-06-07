"""
utils_interna/mailer.py

Envío de correos electrónicos vía API MIEM-MailSender con firma HMAC-SHA256.

Variables de entorno (o pasar explícitamente via MailConfig):
    MAIL_API_URL    - URL del endpoint de la API de correo
    MAIL_API_SECRET - Clave secreta para firma HMAC
    MAIL_VERIFY_SSL - Verificar certificado SSL (default: false, para APIs internas)
"""

import hmac
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
import urllib3

from .logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class MailConfig:
    """Configuración de conexión a la API de correo."""
    api_url:    str  = field(default_factory=lambda: os.getenv("MAIL_API_URL", ""))
    secret_key: str  = field(default_factory=lambda: os.getenv("MAIL_API_SECRET", ""))
    verify_ssl: bool = field(default_factory=lambda: (os.getenv("MAIL_VERIFY_SSL", "false")).lower() == "true")
    timeout:    int  = 10

    def validate(self) -> None:
        missing = [k for k, v in {
            "MAIL_API_URL":    self.api_url,
            "MAIL_API_SECRET": self.secret_key,
        }.items() if not v]
        if missing:
            raise ValueError(f"Configuración de correo incompleta. Faltan: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------

def send_notification_email(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    config: Optional[MailConfig] = None,
) -> bool:
    """
    Envía un correo electrónico vía API MIEM-MailSender.

    El cuerpo se envuelve automáticamente en HTML. La petición se firma con
    HMAC-SHA256 usando la clave configurada en MAIL_API_SECRET.

    Args:
        destinatario: Dirección de correo del destinatario.
        asunto:       Asunto del mensaje.
        cuerpo:       Cuerpo del mensaje (texto plano; se envuelve en <html><body>).
        config:       Instancia de MailConfig. Si es None, usa variables de entorno.

    Returns:
        True si el envío fue exitoso, False en caso contrario.

    Example:
        from utils_interna import send_notification_email

        send_notification_email(
            "usuario@empresa.local",
            "Asunto del correo",
            "Cuerpo del mensaje",
        )
    """
    if config is None:
        config = MailConfig()

    try:
        config.validate()
    except ValueError as e:
        logger.error("mail_config_error", error=str(e))
        return False

    if not config.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    payload_data = {
        "destinatario": destinatario,
        "asunto":       asunto,
        "cuerpo":       f"<html><body>{cuerpo}</body></html>",
        "tag":          "html",
    }

    payload_bytes = json.dumps(payload_data, separators=(",", ":")).encode("utf-8")
    request_seq   = int(time.time() * 1000)
    signature     = hmac.new(
        config.secret_key.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "x-signature":   signature,
        "x-request-seq": str(request_seq),
        "Content-Type":  "text/plain; charset=utf-8",
    }

    try:
        response = requests.post(
            config.api_url,
            data=payload_bytes,
            headers=headers,
            verify=config.verify_ssl,
            timeout=config.timeout,
        )

        if response.status_code == 200:
            logger.info("mail_sent", destinatario=destinatario)
            return True

        logger.error(
            "mail_error",
            destinatario=destinatario,
            status_code=response.status_code,
            response=response.text,
        )
        return False

    except Exception as e:
        logger.error("mail_connection_error", destinatario=destinatario, error=str(e))
        return False
