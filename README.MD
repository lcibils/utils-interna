# utils-interna

Utilidades internas del equipo de desarrollo del MIEM. Actualmente incluye autenticación y autorización contra Active Directory.

---

## Instalación

```bash
pip install git+https://git.miem.gub.uy/infra/utils-interna.git
```

O agregando al `pyproject.toml` / `requirements.txt` del proyecto:

```
utils-interna @ git+https://git.miem.gub.uy/infra/utils-interna.git
```

### Dependencias requeridas

- `ldap3>=2.9`
- `pycryptodome>=3.0` (requerido por ldap3 para autenticación NTLM)
- `python-dotenv>=1.0`
- `structlog>=24.0`

---

## Módulo `auth` — Autenticación contra Active Directory

### Configuración

Las credenciales de conexión al AD se leen desde variables de entorno. La forma recomendada es un archivo `.env` en la raíz del proyecto (git-ignorado):

```ini
# .env
AD_SERVER=ldaps://dcadc.empresa.local
AD_PORT=636
AD_DOMAIN=EMPRESA
AD_BASE_DN=DC=empresa,DC=local
AD_USE_SSL=true
```

Copiar `.env.example` como punto de partida:

```bash
cp .env.example .env
```

En el código de la aplicación, cargar el `.env` antes de usar el módulo:

```python
from dotenv import load_dotenv
load_dotenv()

from utils_interna import login
```

---

### Uso básico

#### Login exitoso

```python
from utils_interna import login

result = login("jdoe", "mi_contrasena")

if result.success:
    user = result.user
    print(f"Bienvenido, {user.display_name}")
    print(f"Email:        {user.email}")
    print(f"Departamento: {user.department}")
    print(f"Cargo:        {user.title}")
    print(f"Grupos:       {user.groups}")
else:
    print(f"Error: {result.error}")
```

#### Credenciales incorrectas

```python
result = login("jdoe", "contrasena_incorrecta")

if not result.success:
    print(result.error)
    # "Credenciales inválidas o usuario deshabilitado."
```

---

### Autorización por grupo

Verificar que el usuario pertenece a un grupo específico **en el mismo llamado** de login.
Si el usuario no es miembro del grupo, `result.success` es `False`.

```python
result = login("jdoe", "mi_contrasena", required_group="GRP_DEVS")

if result.success:
    print("Acceso autorizado")
else:
    print(result.error)
    # "Acceso denegado: el usuario no pertenece al grupo 'GRP_DEVS'."
```

También se puede verificar la pertenencia a grupos **después** del login:

```python
from utils_interna import login, is_member_of

result = login("jdoe", "mi_contrasena")

if result.success:
    if is_member_of(result.user, "GRP_ADMINS"):
        print("Es administrador")
    if is_member_of(result.user, "GRP_DEVS"):
        print("Es desarrollador")
```

> `is_member_of` hace comparación case-insensitive y busca el nombre como subcadena del CN del grupo.

---

### Recuperar campos adicionales de AD

Por defecto se recuperan: `displayName`, `mail`, `memberOf`, `department`, `title`.
Para obtener atributos adicionales, usar el parámetro `extra_fields`:

```python
result = login(
    "jdoe", "mi_contrasena",
    extra_fields=["telephoneNumber", "physicalDeliveryOfficeName", "manager"],
)

if result.success:
    extras = result.user.extra_attributes
    print(extras["telephoneNumber"])             # "+54 11 1234-5678"
    print(extras["physicalDeliveryOfficeName"])  # "Piso 3"
    print(extras["manager"])                     # DN del manager o None
```

---

### Configuración explícita (sin variables de entorno)

Útil para conectar a múltiples dominios o cuando las credenciales de conexión vienen de otra fuente:

```python
from utils_interna import login, ADConfig

config = ADConfig(
    server="dc02.subsidiaria.local",
    domain="SUBSIDIARIA",
    base_dn="DC=subsidiaria,DC=local",
    port=636,
    use_ssl=True,
    timeout=10,
)

result = login("msmith", "contrasena", config=config)
```

`ADConfig` también acepta `ldaps://` en el campo `server`:

```python
config = ADConfig(server="ldaps://dcadc.empresa.local", ...)
```

---

### Logout

En Active Directory no existe sesión de servidor que invalidar. El método `logout` sirve como punto de auditoría y para limpiar estado local (tokens, caché de sesión, etc.):

```python
from utils_interna import logout

logout("jdoe")  # registra el evento en el log
```

---

### Referencia de tipos

#### `AuthResult`

| Campo     | Tipo               | Descripción                                      |
|-----------|--------------------|--------------------------------------------------|
| `success` | `bool`             | `True` si la autenticación (y autorización) fue exitosa |
| `user`    | `UserInfo \| None` | Datos del usuario. `None` si `success=False`     |
| `error`   | `str \| None`      | Mensaje de error. `None` si `success=True`       |

#### `UserInfo`

| Campo              | Tipo        | Atributo AD      | Descripción                              |
|--------------------|-------------|------------------|------------------------------------------|
| `username`         | `str`       | `sAMAccountName` | Nombre de usuario                        |
| `display_name`     | `str`       | `displayName`    | Nombre completo                          |
| `email`            | `str`       | `mail`           | Correo electrónico                       |
| `groups`           | `list[str]` | `memberOf`       | Lista de CNs de grupos                   |
| `department`       | `str`       | `department`     | Departamento                             |
| `title`            | `str`       | `title`          | Cargo                                    |
| `extra_attributes` | `dict`      | —                | Atributos extra solicitados via `extra_fields` |

#### `ADConfig`

| Campo          | Tipo   | Variable de entorno | Default        | Descripción                        |
|----------------|--------|---------------------|----------------|------------------------------------|
| `server`       | `str`  | `AD_SERVER`         | —              | Hostname o `ldaps://hostname`      |
| `domain`       | `str`  | `AD_DOMAIN`         | —              | Dominio NETBIOS (ej: `EMPRESA`)    |
| `base_dn`      | `str`  | `AD_BASE_DN`        | —              | Base DN (ej: `DC=empresa,DC=local`)|
| `port`         | `int`  | `AD_PORT`           | `636`          | Puerto LDAP/LDAPS                  |
| `use_ssl`      | `bool` | `AD_USE_SSL`        | `true`         | Usar SSL/TLS                       |
| `timeout`      | `int`  | —                   | `10`           | Timeout de conexión en segundos    |
| `tls_validate` | `int`  | —                   | `ssl.CERT_NONE`| Validación del certificado TLS     |
| `tls_version`  | `int`  | —                   | `TLSv1_2`      | Versión de TLS                     |

---

### Ejemplo completo (aplicación Flask)

```python
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from utils_interna import login, is_member_of

app = Flask(__name__)

@app.post("/login")
def do_login():
    data = request.json
    result = login(
        data["username"],
        data["password"],
        required_group="GRP_APP_USUARIOS",
    )

    if not result.success:
        return jsonify({"error": result.error}), 401

    user = result.user
    return jsonify({
        "display_name": user.display_name,
        "email": user.email,
        "is_admin": is_member_of(user, "GRP_APP_ADMINS"),
    })
```

---

## Módulo `logger` — Logging con rotación de archivos

### Configuración

```ini
# .env  (no se requieren variables para logging, la configuración es en código)
```

### Inicializar el sistema de logging

Llamar a `setup_logging` una sola vez al arrancar la aplicación:

```python
from utils_interna import setup_logging

setup_logging(
    log_file_path="logs/app.log",   # ruta del archivo (el directorio se crea si no existe)
    log_level="INFO",               # DEBUG | INFO | WARNING | ERROR | CRITICAL
    max_file_size="10MB",           # rotar cuando el archivo supere este tamaño
    console_logging=True,           # también imprimir en consola
    backup_count=10,                # cantidad de archivos de backup
)
```

Después de esto, todos los loggers de stdlib (incluidos los de `auth.py`) y los nuevos helpers escriben al archivo.

### Logger estructurado (`get_logger` / `log`)

```python
from utils_interna import get_logger, log

logger = get_logger(__name__)
logger.info("user_login", user="jdoe", ip="10.0.0.1")

# o en un solo llamado:
log("warning", "acceso_denegado", user="jdoe", grupo="GRP_ADMINS")
```

### Helpers de auditoría

```python
from utils_interna import log_operation, log_api_call, log_system_status

# Auditar una operación CRUD
log_operation("ADD", expediente_id=1234, success=True, details="Creado vía API")
log_operation("DELETE", expediente_id=99, success=False, details="Registro no encontrado")

# Trazar llamadas a APIs externas
log_api_call("POST", "/api/expedientes", success=True, response_time=0.45)
log_api_call("GET",  "/api/usuarios",    success=False, error="Timeout")

# Reportar estado de componentes
log_system_status("DATABASE",   "OK")
log_system_status("WEBSERVICE", "WARNING", details="Latencia alta: 3.2s")
log_system_status("CORREO",     "ERROR",   details="Conexión rechazada")
```

---

## Módulo `mailer` — Envío de correos vía API MIEM-MailSender

### Configuración

```ini
# .env
MAIL_API_URL=https://mailsender.empresa.local/api/send
MAIL_API_SECRET=tu_clave_secreta
MAIL_VERIFY_SSL=false   # false para APIs internas con certificado self-signed
```

### Uso básico

```python
from dotenv import load_dotenv
load_dotenv()

from utils_interna import send_notification_email

enviado = send_notification_email(
    "usuario@empresa.local",
    "Asunto del correo",
    "El expediente Nro. 1234 fue aprobado.",
)

if not enviado:
    print("Error al enviar el correo — revisar logs")
```

### Configuración explícita (sin variables de entorno)

```python
from utils_interna import send_notification_email, MailConfig

config = MailConfig(
    api_url="https://mailsender.subsidiaria.local/api/send",
    secret_key="clave_subsidiaria",
    verify_ssl=False,
    timeout=15,
)

send_notification_email("dest@subsidiaria.local", "Asunto", "Cuerpo", config=config)
```

### Referencia de tipos

#### `MailConfig`

| Campo        | Tipo   | Variable de entorno | Default | Descripción                                      |
|--------------|--------|---------------------|---------|--------------------------------------------------|
| `api_url`    | `str`  | `MAIL_API_URL`      | —       | URL del endpoint de la API de correo             |
| `secret_key` | `str`  | `MAIL_API_SECRET`   | —       | Clave secreta para firma HMAC-SHA256             |
| `verify_ssl` | `bool` | `MAIL_VERIFY_SSL`   | `false` | Verificar certificado SSL (false para APIs internas) |
| `timeout`    | `int`  | —                   | `10`    | Timeout de conexión en segundos                  |

---

## Módulo `teams` — Notificaciones a Microsoft Teams

Envía mensajes a un canal de Teams vía el servicio centralizado MIEM. El servicio gestiona la autenticación contra Azure automáticamente; el cliente no necesita credenciales de Azure.

> **Uso interno exclusivamente.** El servicio no debe estar expuesto a internet.

### Configuración

```ini
# .env
TEAMS_API_URL=https://automatizacion.miem.gub.uy/enviar-a-teams  # valor por defecto
TEAMS_VERIFY_SSL=true
```

`TEAMS_API_URL` ya tiene el valor por defecto incorporado, por lo que solo es necesario definirlo en `.env` si la URL cambia.

### Uso básico

```python
from dotenv import load_dotenv
load_dotenv()

from utils_interna import send_notification_teams

ok = send_notification_teams(
    "usuario@miem.gub.uy",
    "El expediente Nro. 1234 fue aprobado.",
)

if not ok:
    print("Error al enviar la notificación — revisar logs")
```

### Configuración explícita (sin variables de entorno)

```python
from utils_interna import send_notification_teams, TeamsConfig

config = TeamsConfig(
    api_url="https://automatizacion.miem.gub.uy/enviar-a-teams",
    verify_ssl=True,
    timeout=15,
)

send_notification_teams("usuario@miem.gub.uy", "Mensaje de prueba", config=config)
```

### Referencia de tipos

#### `TeamsConfig`

| Campo        | Tipo   | Variable de entorno | Default                                              | Descripción                          |
|--------------|--------|---------------------|------------------------------------------------------|--------------------------------------|
| `api_url`    | `str`  | `TEAMS_API_URL`     | `https://automatizacion.miem.gub.uy/enviar-a-teams` | URL del endpoint del servicio        |
| `verify_ssl` | `bool` | `TEAMS_VERIFY_SSL`  | `true`                                               | Verificar certificado SSL            |
| `timeout`    | `int`  | —                   | `10`                                                 | Timeout de conexión en segundos      |

### Códigos de respuesta del servicio

| Código | Significado                                                                 |
|--------|-----------------------------------------------------------------------------|
| `202`  | Notificación aceptada y en proceso (`send_notification_teams` retorna `True`) |
| `400`  | Payload inválido o parámetros faltantes                                     |
| `503`  | Servicio temporalmente no disponible — reintentar en unos segundos          |

---

## Desarrollo local

```bash
# Clonar y crear entorno
git clone https://git.miem.gub.uy/infra/utils-interna.git
cd utils-interna
python -m venv .venv
.venv/Scripts/activate      # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt

# Configurar conexión AD
cp .env.example .env
# editar .env con los valores reales

# Ejecutar demo interactivo
python prueba.py
```
