# API para Enviar Notificaciones a Teams

Esta API proporciona un endpoint centralizado para enviar notificaciones a un canal de Microsoft Teams, gestionando automáticamente la autenticación y el formateo de diversos orígenes de datos.

---

> **⚠️ Advertencia: Uso Interno Exclusivamente**
>
> Esta API ha sido diseñada únicamente para uso dentro de la red interna del MIEM. **No debe ser expuesta a internet ni utilizada en sistemas de cara al público.** Su implementación utiliza un sistema de tokens automáticos optimizado para la red interna.

---

## Información General

* **URL del Servicio:** `https://automatizacion.miem.gub.uy/enviar-a-teams`
* **Método:** `POST`
* **Autenticación:** El sistema renueva automáticamente un Token de Microsoft cada 50 minutos. No es necesario que el cliente gestione credenciales de Azure.

---

## Formatos de Uso Soportados

El servicio detecta automáticamente el tipo de payload recibido y lo procesa según las siguientes reglas:

### 1. API Simple (Formato Estándar)
Ideal para integraciones directas desde aplicaciones o scripts.

**Ejemplo de cuerpo (JSON):**
```json
{
  "email": "destinatario@miem.gub.uy",
  "asunto": "Este es un mensaje de prueba"
}
```



#### Formato 2: Compatible con Grafana

Diseñado para recibir webhooks de Grafana. El cuerpo de la petición debe contener una clave `message` cuyo valor sea un **JSON stringificado**. Este JSON interno puede ser un array de objetos o un único objeto con las claves `email` y `asunto`.

**Ejemplo de cuerpo (JSON stringificado dentro de `message`):**

```json
{
  "message": "[{\"email\":\"jorge.gonzalez@miem.gub.uy\",\"asunto\":\"Alerta de Grafana: latencia elevada\"}]"
}
```

**Ejemplo con `cURL`:**

```bash
curl -X POST \
  http://<URL_DEL_SERVIDOR>/enviar-a-teams \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "[{\"email\":\"jorge.gonzalez@miem.gub.uy\",\"asunto\":\"Alerta de Grafana: latencia elevada\"}]"
  }'
```

---

## Respuestas del API

-   `202 Accepted`: La petición fue recibida y aceptada para su procesamiento. Esta es la respuesta estándar de éxito.
-   `400 Bad Request`: El cuerpo de la petición es inválido, le faltan parámetros o el JSON está mal formado.
-   `503 Service Unavailable`: El servicio no está disponible temporalmente. Esto puede ocurrir durante un reinicio o si hay un problema interno. Se recomienda reintentar la petición pasados unos segundos.

---
