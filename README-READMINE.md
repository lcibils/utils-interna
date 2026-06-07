# API Friendly-Wrapper para Redmine (MIEM)

Esta API actúa como un middleware amigable sobre la API de Redmine, permitiendo a los sistemas internos crear tickets (issues) utilizando nombres legibles (ej. "Infraestructura", "Tarea") en lugar de IDs numéricos internos de Redmine.

## 🚀 Información General

- **URL Base:** `https://automatizacion.miem.gub.uy/api/v1`
- **Endpoints:**
  - `GET /metadata`: Consulta los nombres válidos (Proyectos, Trackers, etc).
  - `POST /issues`: Creación de tickets.
  - `POST /mapeo-campos`: Consulta el mapeo de campos personalizados a proyectos.
- **Autenticación:** Requiere cabecera `X-API-KEY` (solo para `POST /issues`).
- **Límites de Payload:** Soporta adjuntos de hasta **50MB**.

## 🔐 Autenticación

Todas las peticiones deben incluir la siguiente cabecera HTTP:

```http
X-API-KEY: su_clave_de_aplicacion
```

> [!IMPORTANT]
> La `X-API-KEY` es una clave de acceso específica para esta API. Si no dispone de una, debe solicitarla al equipo de **Infraestructura**.

## 📝 Formato de Petición (JSON)

La API acepta un objeto JSON donde los campos principales utilizan los nombres tal cual aparecen en la interfaz de Redmine.

### Ejemplo de Payload

```json
{
  "project": "Infraestructura",
  "tracker": "Tarea",
  "priority": "Alta",
  "status": "Nueva",
  "subject": "Falla detectada en backup de base de datos",
  "description": "El job de las 03:00 AM falló con error de timeout. Se requiere revisión del volumen de red.",
  "custom_fields": [
    {
      "name": "Sistema Afectado",
      "value": "Core Bancario"
    },
    {
      "name": "Nivel de Impacto",
      "value": "Crítico"
    }
  ]
}
```

### Descripción de Campos

| Campo | Obligatorio | Descripción |
| :--- | :---: | :--- |
| `project` | Sí | Nombre exacto del proyecto en Redmine. |
| `tracker` | Sí | Tipo de incidencia (ej. Tarea, Error, Soporte). |
| `priority` | Sí | Prioridad (ej. Baja, Normal, Alta, Urgente). |
| `status` | Sí | Estado inicial (ej. Nueva, En curso). |
| `subject` | Sí | Asunto o título breve del ticket. |
| `description` | No | Descripción detallada del problema. |
| `custom_fields` | No | Array de objetos `{ "name": "...", "value": "..." }` para campos personalizados. |
| `attachments` | No | Array de objetos para archivos adjuntos con `filename`, `content` (Base64) y `content_type` opcional. |

## 📥 Formato de Respuesta

### Consulta de Metadatos (GET /api/v1/metadata)

Este endpoint es fundamental para los desarrolladores, ya que devuelve las listas de nombres permitidos actualmente en Redmine.

**Respuesta (200 OK):**
```json
{
  "status": "success",
  "projects": ["Infraestructura", "Desarrollo", "Soporte Técnico"],
  "trackers": ["Tarea", "Error", "Mejora"],
  "priorities": ["Baja", "Normal", "Alta", "Urgente"],
  "status": ["Nueva", "En curso", "Cerrada"],
  "custom_fields": [
    { "name": "Sistema Afectado", "id": 12 },
    { "name": "Nivel de Impacto", "id": 15 }
  ]
}
```

### Consulta de Mapeo de Campos Personalizados (POST /api/v1/mapeo-campos)

Este endpoint devuelve el mapeo de campos personalizados de Redmine a los proyectos asociados, facilitando la determinación de qué campos están disponibles para cada proyecto.

**Respuesta (200 OK):**
```json
[
  {
    "id": 12,
    "name": "Sistema Afectado",
    "asociado_a_proyectos": ["Infraestructura", "Desarrollo"]
  },
  {
    "id": 15,
    "name": "Nivel de Impacto",
    "asociado_a_proyectos": "TODOS (Global)"
  }
]
```

**Notas:**
- No requiere autenticación con `X-API-KEY`.
- Los campos marcados como "TODOS (Global)" están disponibles en todos los proyectos.
- Útil para determinar qué campos personalizados están disponibles para cada proyecto antes de crear un ticket.

### Creación de Ticket (POST /api/v1/issues)

#### Éxito (201 Created)

```json
{
  "status": "success",
  "data": {
    "redmine_id": 12345,
    "url": "https://redmine.miem.gub.uy/issues/12345",
    "resolved_params": {
      "project_id": 15,
      "tracker_id": 1,
      "priority_id": 4,
      "status_id": 1
    }
  }
}
```

### Errores Comunes

- **401 Unauthorized:** La `X-API-KEY` es incorrecta o no fue enviada.
- **400 Bad Request:** Alguno de los nombres proporcionados (Proyecto, Tracker, etc.) no coincide con los existentes en Redmine. El mensaje de error indicará cuál es el campo problemático.
- **500 Internal Error:** Problemas de conexión con Redmine o el caché de metadatos no ha sido inicializado.

## 🛠️ Ejemplo de Invocación (cURL)

```bash
curl -X POST https://automatizacion.miem.gub.uy/api/v1/issues \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: su_clave_aqui" \
  -d '{
    "project": "Infraestructura",
    "tracker": "Tarea",
    "priority": "Normal",
    "status": "Nueva",
    "subject": "Ticket de prueba desde API",
    "description": "Prueba de integración exitosa."
  }'
```

### Python (Requests)

```python
import requests
import urllib3

# Deshabilitar advertencias SSL si se usa verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://automatizacion.miem.gub.uy/api/v1/issues"
headers = {
    "X-API-KEY": "su_clave_aqui",
    "Content-Type": "application/json"
}

payload = {
    "project": "Infraestructura",
    "tracker": "Tareas",
    "priority": "Alta",
    "status": "Nueva",
    "subject": "Falla en Backup (Python)",
    "description": "Creado desde script automatizado.",
    "attachments": [
        {
            "filename": "logs.txt",
            "content": "SGVsbG8gV29ybGQ=", # Base64 del contenido
            "content_type": "text/plain"
        }
    ]
}

# Importante: verify=False para entornos con certificados auto-firmados
response = requests.post(url, json=payload, headers=headers, verify=False)

if response.status_code == 201:
    print("Ticket creado:", response.json()["data"]["url"])
else:
    print("Error:", response.text)
```

### Next.js / Node.js (Fetch)

```typescript
// Ejemplo usando fetch en el servidor
async function createRedmineIssue(data: any) {
  // Para certificados auto-firmados en Node.js, puede ser necesario:
  // process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

  const response = await fetch("https://automatizacion.miem.gub.uy/api/v1/issues", {
    method: "POST",
    headers: {
      "X-API-KEY": process.env.REDMINE_WRAPPER_KEY as string,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      project: data.proyecto,
      tracker: "Tarea",
      priority: "Normal",
      status: "Nueva",
      subject: data.asunto,
      description: data.mensaje,
      // Ejemplo con adjuntos múltiples:
      attachments: [
        {
          filename: "documento.pdf",
          content: "base64_string_here",
          content_type: "application/pdf"
        }
      ]
    }),
  });

  const result = await response.json();
  return result;
}
```

## 📎 Envío de Adjuntos

La API soporta el envío de múltiples archivos adjuntos en una sola petición. Los archivos deben enviarse dentro de un array llamado `attachments`, con el contenido codificado en **Base64**.

### Formato de Adjunto
Cada objeto del array `attachments` debe tener:
- `filename`: Nombre del archivo (ej. "error.log").
- `content`: Contenido del archivo en Base64.
- `content_type`: (Opcional) Tipo MIME del archivo.

### Ejemplo Python con Adjunto Real

```python
import requests
import base64

# Leer un archivo local y convertirlo a Base64
file_path = "reporte.pdf"
with open(file_path, "rb") as f:
    encoded_content = base64.b64encode(f.read()).decode("utf-8")

payload = {
    "project": "Infraestructura",
    "subject": "Envío de Reporte Semanal",
    "attachments": [
        {
            "filename": "reporte.pdf",
            "content": encoded_content,
            "content_type": "application/pdf"
        }
    ]
}
# ... resto de la petición ...
```

## 🔍 Notas Adicionales

- **Seguridad SSL:** Dado que el servidor utiliza certificados internos, los clientes deben desactivar la verificación SSL (ej. `verify=False` en Python) para conectar exitosamente.
- **Nombres Exactos:** Se recomienda encarecidamente consultar primero el endpoint `GET /metadata` para obtener la lista de nombres válidos antes de realizar integraciones automáticas.
- **Sensibilidad a Mayúsculas:** La búsqueda de nombres es **insensible** a mayúsculas/minúsculas (ej. "Alta" es lo mismo que "alta").
- **Campos Personalizados:** Asegúrese de que el nombre del campo personalizado (`name`) coincida exactamente con el definido en Redmine.
- **Sincronización:** La API sincroniza automáticamente los nombres y IDs de Redmine cada 24 horas.

## 🧪 Pruebas de Adjuntos Grandes

Se incluye un script de prueba en `scripts/test_redmine_api.py` diseñado para validar la capacidad de envío de archivos grandes (~20MB+).

### Requisitos del Script
1. Python 3.x
2. `pip install -r requirements.txt`

### Ejecución
```bash
# Crear entorno virtual
python -m venv venv
# Activar (Windows)
venv\Scripts\activate
# Ejecutar prueba
python scripts/test_redmine_api.py
```

El script generará automáticamente un archivo de prueba de 20MB y lo enviará al proyecto **"Apia Trámite - Desarrollos MIEM"**.

> [!CAUTION]
> Para archivos mayores a **25MB**, se debe aumentar el límite en la administración de Redmine (*Configuración -> Ficheros -> Tamaño máximo del fichero*).
