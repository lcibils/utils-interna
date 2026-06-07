"""
utils_interna/auth.py

Autenticación y autorización contra Active Directory usando ldap3.

Variables de entorno (o pasar explícitamente via ADConfig):
    AD_SERVER   - hostname o IP del Domain Controller
    AD_DOMAIN   - dominio NETBIOS  (ej: "EMPRESA")
    AD_BASE_DN  - base DN          (ej: "DC=empresa,DC=local")
    AD_PORT     - puerto LDAP/LDAPS (default: 636)
    AD_USE_SSL  - usar SSL/TLS     (default: true)
"""

import os
import ssl
import logging
from dataclasses import dataclass, field
from typing import Optional

from ldap3 import Server, Connection, Tls, ALL, NTLM, SUBTREE
from ldap3.core.exceptions import LDAPException, LDAPBindError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class UserInfo:
    """Información del usuario autenticado obtenida desde AD."""
    username:         str
    display_name:     str       = ""
    email:            str       = ""
    groups:           list[str] = field(default_factory=list)
    department:       str       = ""
    title:            str       = ""
    extra_attributes: dict      = field(default_factory=dict)


@dataclass
class AuthResult:
    """Resultado de una operación de autenticación."""
    success: bool
    user:    Optional[UserInfo] = None
    error:   Optional[str]     = None


@dataclass
class ADConfig:
    """Configuración de conexión al Active Directory."""
    server:       str  = field(default_factory=lambda: os.getenv("AD_SERVER", ""))
    domain:       str  = field(default_factory=lambda: os.getenv("AD_DOMAIN", ""))
    base_dn:      str  = field(default_factory=lambda: os.getenv("AD_BASE_DN", ""))
    port:         int  = field(default_factory=lambda: int(os.getenv("AD_PORT") or "636"))
    use_ssl:      bool = field(default_factory=lambda: (os.getenv("AD_USE_SSL") or "true").lower() == "true")
    timeout:      int  = 10
    tls_validate: int  = field(default_factory=lambda: ssl.CERT_NONE)
    tls_version:  int  = field(default_factory=lambda: ssl.PROTOCOL_TLSv1_2)

    def validate(self) -> None:
        missing = [k for k, v in {
            "AD_SERVER":  self.server,
            "AD_DOMAIN":  self.domain,
            "AD_BASE_DN": self.base_dn,
        }.items() if not v]
        if missing:
            raise ValueError(f"Configuración AD incompleta. Faltan: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------

def login(
    username: str,
    password: str,
    config: Optional[ADConfig] = None,
    fetch_user_info: bool = True,
    required_group: Optional[str] = None,
    extra_fields: Optional[list[str]] = None,
) -> AuthResult:
    """
    Autentica un usuario contra Active Directory.

    Args:
        username:        Nombre de usuario (sin dominio).
        password:        Contraseña en texto plano.
        config:          Instancia de ADConfig. Si es None, usa variables de entorno.
        fetch_user_info: Si True, recupera atributos del usuario tras el bind.
        required_group:  CN del grupo requerido para autorizar al usuario.
                         Si se especifica, el login falla si el usuario no es miembro.
        extra_fields:    Atributos AD adicionales a recuperar (ej. ["telephoneNumber"]).
                         Se devuelven en UserInfo.extra_attributes.

    Returns:
        AuthResult con success=True y datos del usuario, o success=False con error.

    Example:
        result = login("jdoe", "s3cr3t", required_group="GRP_DEVS")
        if result.success:
            print(result.user.display_name)
    """
    if config is None:
        config = ADConfig()

    try:
        config.validate()
    except ValueError as e:
        logger.error("Configuración inválida: %s", e)
        return AuthResult(success=False, error=str(e))

    upn = f"{config.domain}\\{username}"

    try:
        host, use_ssl = _parse_server_address(config.server, config.use_ssl)

        tls_config = Tls(
            validate=config.tls_validate,
            version=config.tls_version,
        )
        server = Server(
            host,
            port=config.port,
            use_ssl=use_ssl,
            tls=tls_config,
            get_info=ALL,
            connect_timeout=config.timeout,
        )

        conn = Connection(
            server,
            user=upn,
            password=password,
            authentication=NTLM,
            auto_bind=True,
        )

        logger.info("Login exitoso: %s", username)

        user_info = UserInfo(username=username)
        # required_group necesita los atributos para verificar grupos
        should_fetch = fetch_user_info or (required_group is not None)

        if should_fetch:
            user_info = _fetch_user_attributes(conn, username, config, extra_fields=extra_fields)

        if required_group is not None and not is_member_of(user_info, required_group):
            logger.warning(
                "Login rechazado: '%s' no es miembro del grupo '%s'", username, required_group
            )
            conn.unbind()
            return AuthResult(
                success=False,
                error=f"Acceso denegado: el usuario no pertenece al grupo '{required_group}'.",
            )

        conn.unbind()
        return AuthResult(success=True, user=user_info)

    except LDAPBindError as e:
        logger.warning("Login fallido para '%s': %s", username, e)
        return AuthResult(success=False, error="Credenciales inválidas o usuario deshabilitado.")

    except LDAPException as e:
        logger.error("Error LDAP al autenticar '%s': %s", username, e)
        return AuthResult(success=False, error=f"Error de conexión LDAP: {e}")

    except Exception as e:
        logger.exception("Error inesperado en login para '%s'", username)
        return AuthResult(success=False, error=f"Error inesperado: {e}")


def logout(username: str) -> None:
    """
    Hook de logout para auditoría y limpieza de sesión local.

    Args:
        username: Nombre de usuario que cierra sesión.
    """
    logger.info("Logout: %s", username)


def is_member_of(user: UserInfo, group_name: str) -> bool:
    """
    Verifica si el usuario pertenece a un grupo de AD (case-insensitive).

    Args:
        user:       UserInfo obtenido del login.
        group_name: Nombre del grupo.

    Returns:
        True si el usuario es miembro del grupo.

    Example:
        if is_member_of(result.user, "GRP_DEVS"):
            ...
    """
    return any(group_name.lower() in g.lower() for g in user.groups)


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _fetch_user_attributes(
    conn: Connection,
    username: str,
    config: ADConfig,
    extra_fields: Optional[list[str]] = None,
) -> UserInfo:
    """Recupera atributos del usuario en el directorio tras autenticarse."""
    base_attributes = ["displayName", "mail", "memberOf", "department", "title"]
    requested_extra = [f for f in (extra_fields or []) if f not in base_attributes]
    attributes = base_attributes + requested_extra

    conn.search(
        search_base=config.base_dn,
        search_filter=f"(sAMAccountName={username})",
        search_scope=SUBTREE,
        attributes=attributes,
    )

    if not conn.entries:
        logger.warning("Usuario '%s' autenticado pero no encontrado en búsqueda LDAP.", username)
        return UserInfo(username=username)

    entry = conn.entries[0]

    raw_groups = entry.memberOf.values if entry.memberOf else []
    groups = [_extract_cn(dn) for dn in raw_groups]

    extra_data = {}
    for field_name in requested_extra:
        attr = getattr(entry, field_name, None)
        if attr and attr.values:
            vals = attr.values
            extra_data[field_name] = vals[0] if len(vals) == 1 else list(vals)
        else:
            extra_data[field_name] = None

    return UserInfo(
        username=username,
        display_name=str(entry.displayName) if entry.displayName else "",
        email=str(entry.mail) if entry.mail else "",
        groups=groups,
        department=str(entry.department) if entry.department else "",
        title=str(entry.title) if entry.title else "",
        extra_attributes=extra_data,
    )


def _extract_cn(dn: str) -> str:
    """Extrae el valor del primer CN de un Distinguished Name."""
    for part in dn.split(","):
        if part.strip().upper().startswith("CN="):
            return part.strip()[3:]
    return dn


def _parse_server_address(server: str, use_ssl: bool) -> tuple[str, bool]:
    """Strips ldap:// or ldaps:// scheme from server address."""
    lowered = server.lower()
    if lowered.startswith("ldaps://"):
        return server[8:], True
    if lowered.startswith("ldap://"):
        return server[7:], use_ssl
    return server, use_ssl
