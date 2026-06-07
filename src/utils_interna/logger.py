"""
utils_interna/logger.py

Wrapper sobre structlog para exponer get_logger() y log() de forma consistente.
Las aplicaciones pueden configurar structlog independientemente; este módulo
solo provee un punto de entrada uniforme.
"""

import structlog


def get_logger(name: str = "utils_interna") -> structlog.stdlib.BoundLogger:
    """
    Retorna un logger de structlog.

    Args:
        name: Nombre del logger, tipicamente __name__ del módulo que llama.
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
