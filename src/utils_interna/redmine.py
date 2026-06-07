"""
utils_interna/redmine.py

Wrapper sobre la API friendly de Redmine (MIEM).
Permite crear tickets usando nombres legibles en lugar de IDs internos.

Variables de entorno (o pasar explícitamente via RedmineConfig):
    REDMINE_API_KEY    - Clave de acceso (requerida para crear tickets)
    REDMINE_API_URL    - URL base de la API (default: https://automatizacion.miem.gub.uy/api/v1)
    REDMINE_VERIFY_SSL - Verificar certificado SSL (default: false, certificados internos)
"""

import base64
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
import urllib3

from .logger import get_logger

logger = get_logger(__name__)

_DEFAULT_API_URL = "https://automatizacion.miem.gub.uy/api/v1"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class IssueResult:
    """Resultado de la creación de un ticket en Redmine."""
    success:    bool
    redmine_id: Optional[int] = None
    url:        Optional[str] = None
    error:      Optional[str] = None


@dataclass
class RedmineConfig:
    """Configuración de conexión a la API wrapper de Redmine."""
    api_url:    str  = field(default_factory=lambda: os.getenv("REDMINE_API_URL", _DEFAULT_API_URL))
    api_key:    str  = field(default_factory=lambda: os.getenv("REDMINE_API_KEY", ""))
    verify_ssl: bool = field(default_factory=lambda: os.getenv("REDMINE_VERIFY_SSL", "false").lower() == "true")
    timeout:    int  = 30   # timeout generoso para adjuntos de hasta 50 MB

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("Configuración de Redmine incompleta. Falta: REDMINE_API_KEY")


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------

def create_issue(
    project:       str,
    tracker:       str,
    priority:      str,
    status:        str,
    subject:       str,
    description:   Optional[str]       = None,
    custom_fields: Optional[list]      = None,
    attachments:   Optional[list]      = None,
    config:        Optional[RedmineConfig] = None,
) -> IssueResult:
    """
    Crea un ticket en Redmine usando nombres legibles.

    Args:
        project:       Nombre exacto del proyecto (ej. "Infraestructura").
        tracker:       Tipo de incidencia (ej. "Tarea", "Error", "Soporte").
        priority:      Prioridad (ej. "Baja", "Normal", "Alta", "Urgente").
        status:        Estado inicial (ej. "Nueva", "En curso").
        subject:       Título breve del ticket.
        description:   Descripción detallada (opcional).
        custom_fields: Lista de dicts {"name": "...", "value": "..."} (opcional).
        attachments:   Lista de dicts {"filename": "...", "content": "<base64>",
                       "content_type": "..."} (opcional). Usar attach_file() como helper.
        config:        Instancia de RedmineConfig. Si es None, usa variables de entorno.

    Returns:
        IssueResult con success=True y redmine_id/url, o success=False con error.

    Example:
        result = create_issue(
            project="Infraestructura",
            tracker="Tarea",
            priority="Alta",
            status="Nueva",
            subject="Falla en backup",
            description="El job de las 03:00 AM falló con timeout.",
        )
        if result.success:
            print(result.url)
    """
    if config is None:
        config = RedmineConfig()

    try:
        config.validate()
    except ValueError as e:
        logger.error("redmine_config_error", error=str(e))
        return IssueResult(success=False, error=str(e))

    if not config.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    payload = {
        "project":  project,
        "tracker":  tracker,
        "priority": priority,
        "status":   status,
        "subject":  subject,
    }
    if description is not None:
        payload["description"] = description
    if custom_fields:
        payload["custom_fields"] = custom_fields
    if attachments:
        payload["attachments"] = attachments

    headers = {
        "X-API-KEY":    config.api_key,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"{config.api_url}/issues",
            json=payload,
            headers=headers,
            verify=config.verify_ssl,
            timeout=config.timeout,
        )

        if response.status_code == 201:
            data = response.json().get("data", {})
            redmine_id = data.get("redmine_id")
            url = data.get("url")
            logger.info("redmine_issue_created", redmine_id=redmine_id, url=url)
            return IssueResult(success=True, redmine_id=redmine_id, url=url)

        error_msg = _extract_error(response)
        logger.error(
            "redmine_issue_error",
            status_code=response.status_code,
            error=error_msg,
        )
        return IssueResult(success=False, error=error_msg)

    except Exception as e:
        logger.error("redmine_connection_error", error=str(e))
        return IssueResult(success=False, error=f"Error de conexión: {e}")


def get_metadata(config: Optional[RedmineConfig] = None) -> Optional[dict]:
    """
    Consulta los nombres válidos de proyectos, trackers, prioridades, estados
    y campos personalizados disponibles en Redmine.

    No requiere autenticación.

    Args:
        config: Instancia de RedmineConfig. Si es None, usa variables de entorno.

    Returns:
        Dict con claves "projects", "trackers", "priorities", "status",
        "custom_fields", o None si hubo error.

    Example:
        meta = get_metadata()
        if meta:
            print(meta["projects"])
    """
    if config is None:
        config = RedmineConfig()

    if not config.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        response = requests.get(
            f"{config.api_url}/metadata",
            verify=config.verify_ssl,
            timeout=config.timeout,
        )

        if response.status_code == 200:
            return response.json()

        logger.error("redmine_metadata_error", status_code=response.status_code)
        return None

    except Exception as e:
        logger.error("redmine_metadata_connection_error", error=str(e))
        return None


def get_field_mappings(config: Optional[RedmineConfig] = None) -> Optional[list]:
    """
    Consulta el mapeo de campos personalizados a proyectos de Redmine.

    No requiere autenticación. Útil para determinar qué campos personalizados
    están disponibles para cada proyecto antes de crear un ticket.

    Args:
        config: Instancia de RedmineConfig. Si es None, usa variables de entorno.

    Returns:
        Lista de dicts con "id", "name" y "asociado_a_proyectos", o None si hubo error.

    Example:
        mappings = get_field_mappings()
        for field in mappings:
            print(field["name"], "->", field["asociado_a_proyectos"])
    """
    if config is None:
        config = RedmineConfig()

    if not config.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        response = requests.post(
            f"{config.api_url}/mapeo-campos",
            verify=config.verify_ssl,
            timeout=config.timeout,
        )

        if response.status_code == 200:
            return response.json()

        logger.error("redmine_mappings_error", status_code=response.status_code)
        return None

    except Exception as e:
        logger.error("redmine_mappings_connection_error", error=str(e))
        return None


def attach_file(filepath: str, content_type: Optional[str] = None) -> dict:
    """
    Helper que lee un archivo local y construye el dict de adjunto para create_issue.

    Args:
        filepath:     Ruta al archivo a adjuntar.
        content_type: Tipo MIME (ej. "application/pdf"). Si es None, la API lo infiere.

    Returns:
        Dict {"filename": "...", "content": "<base64>", "content_type": "..."}
        listo para incluir en el parámetro `attachments` de create_issue.

    Example:
        result = create_issue(
            ...,
            attachments=[attach_file("reporte.pdf", "application/pdf")],
        )
    """
    path = Path(filepath)
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    attachment = {"filename": path.name, "content": encoded}
    if content_type:
        attachment["content_type"] = content_type
    return attachment


# ---------------------------------------------------------------------------
# Privado
# ---------------------------------------------------------------------------

def _extract_error(response: requests.Response) -> str:
    """Extrae el mensaje de error de la respuesta HTTP."""
    try:
        return response.json().get("message", response.text)
    except Exception:
        return response.text
