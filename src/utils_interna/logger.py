"""
utils_interna/logger.py

Logging estructurado (structlog) + configuración de stdlib con rotación de archivos.

Uso típico en una aplicación:

    from dotenv import load_dotenv
    load_dotenv()

    from utils_interna import setup_logging, get_logger

    setup_logging(log_file_path="logs/app.log", log_level="INFO")
    logger = get_logger(__name__)
    logger.info("app_start")
"""

import logging
import logging.handlers
import os

import structlog


# ---------------------------------------------------------------------------
# API pública — structlog
# ---------------------------------------------------------------------------

def get_logger(name: str = "utils_interna") -> structlog.stdlib.BoundLogger:
    """
    Retorna un logger de structlog.

    Args:
        name: Nombre del logger, típicamente __name__ del módulo que llama.
    """
    return structlog.get_logger(name)


def log(level: str, event: str, **kwargs) -> None:
    """
    Registra un evento en un solo llamado.

    Args:
        level:    Nivel de log: "debug", "info", "warning", "error", "critical".
        event:    Nombre/mensaje del evento.
        **kwargs: Contexto clave-valor adjunto al log.

    Example:
        log("info", "user_login", user="jdoe", ip="10.0.0.1")
    """
    _logger = structlog.get_logger("utils_interna")
    log_fn = getattr(_logger, level.lower(), _logger.info)
    log_fn(event, **kwargs)


# ---------------------------------------------------------------------------
# API pública — configuración stdlib
# ---------------------------------------------------------------------------

_LOG_FORMAT  = "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_file_path: str = "logs/app.log",
    log_level: str = "INFO",
    max_file_size: str = "10MB",
    console_logging: bool = True,
    backup_count: int = 10,
) -> None:
    """
    Configura el sistema de logging de stdlib con rotación por tamaño.

    Crea el directorio de logs si no existe. Los loggers de utils_interna
    (que usan logging.getLogger internamente) heredan esta configuración
    automáticamente.

    Args:
        log_file_path:   Ruta del archivo de logs.
        log_level:       Nivel de logging: DEBUG, INFO, WARNING, ERROR, CRITICAL.
        max_file_size:   Tamaño máximo antes de rotar (ej. "10MB", "500KB", "1GB").
        console_logging: Si True, también imprime logs en consola.
        backup_count:    Cantidad de archivos de backup a conservar.
    """
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    if console_logging:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=_parse_size(max_file_size) * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root.info(
        "Logging configurado: nivel=%s, archivo=%s, tamaño_max=%s",
        log_level, log_file_path, max_file_size,
    )


# ---------------------------------------------------------------------------
# API pública — helpers de auditoría
# ---------------------------------------------------------------------------

def log_operation(
    operation: str,
    expediente_id: int | None = None,
    success: bool = True,
    details: str | None = None,
) -> None:
    """
    Registra una operación de negocio (ADD, EDIT, DELETE, CONSULTA, etc.).

    Args:
        operation:     Tipo de operación.
        expediente_id: ID del registro afectado (opcional).
        success:       True si la operación fue exitosa.
        details:       Información adicional (opcional).
    """
    _logger = logging.getLogger("operations")
    status        = "EXITOSA" if success else "FALLIDA"
    exp_info      = f" (expediente_id: {expediente_id})" if expediente_id is not None else ""
    details_info  = f" - {details}" if details else ""
    msg = f"Operación {operation}{exp_info}: {status}{details_info}"
    _logger.info(msg) if success else _logger.error(msg)


def log_api_call(
    endpoint: str,
    method: str,
    success: bool = True,
    response_time: float | None = None,
    error: str | None = None,
) -> None:
    """
    Registra una llamada a una API externa.

    Args:
        endpoint:      Endpoint de la API.
        method:        Método HTTP (GET, POST, etc.).
        success:       True si la llamada fue exitosa.
        response_time: Tiempo de respuesta en segundos (opcional).
        error:         Mensaje de error si hubo fallo (opcional).
    """
    _logger = logging.getLogger("api")
    time_info  = f" - Tiempo: {response_time:.2f}s" if response_time is not None else ""
    error_info = f" - Error: {error}" if error else ""
    msg = f"Llamada API {method} {endpoint}: {'EXITOSA' if success else 'FALLIDA'}{time_info}{error_info}"
    _logger.info(msg) if success else _logger.error(msg)


def log_system_status(
    component: str,
    status: str,
    details: str | None = None,
) -> None:
    """
    Registra el estado de un componente del sistema.

    Args:
        component: Nombre del componente (DATABASE, WEBSERVICE, etc.).
        status:    Estado: "OK", "WARNING" o "ERROR".
        details:   Detalles adicionales (opcional).
    """
    _logger = logging.getLogger("system")
    details_info = f" - {details}" if details else ""
    msg = f"Componente {component}: {status}{details_info}"
    if status == "OK":
        _logger.info(msg)
    elif status == "WARNING":
        _logger.warning(msg)
    else:
        _logger.error(msg)


# ---------------------------------------------------------------------------
# Privado
# ---------------------------------------------------------------------------

def _parse_size(size_str: str) -> int:
    """Convierte un string de tamaño (ej. '10MB') a número de megabytes (int)."""
    s = size_str.upper()
    if s.endswith("GB"):
        return int(s[:-2]) * 1024
    if s.endswith("MB"):
        return int(s[:-2])
    if s.endswith("KB"):
        return max(1, int(s[:-2]) // 1024)
    return int(s)
