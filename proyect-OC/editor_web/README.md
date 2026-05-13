# Editor Web (OC Help)

Interfaz web del **editor de microoperaciones** (no de la calculadora), reutilizando la lógica de:

- `modelo/Von_Neumann.py`
- `modelo/Inferidor.py`
- `modelo/Generador.py`
- `modelo/traza.py`
- `compilador/AnalizadorSintactico.py`

## Ejecutar

Desde `proyect-OC/editor_web`:

```bash
python app.py
```

Luego abrir:

- `http://localhost:5050`

## Acceso con Google y control de usuarios

Login con **Google** (correo verificado). Por defecto se acepta **cualquier dominio** salvo que definas `ALLOWED_DOMAIN` en el entorno.

Variables de entorno obligatorias:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `FLASK_SECRET_KEY` (recomendado en producción)

Variables opcionales:

- `ALLOWED_DOMAIN` — vacío, `*` o `ALLOW_ALL_EMAIL_DOMAINS=1` → cualquier dominio.
- `ALLOW_ALL_EMAIL_DOMAINS=1` — fuerza aceptar cualquier host de correo (útil si `ALLOWED_DOMAIN` quedó fija en un PaaS).
- `EDITOR_WEB_ADMIN_PATH` (por defecto `/_internal/access-control`)
- `EDITOR_WEB_DEFAULT_ADMINS` (lista separada por comas de correos admin iniciales)
- `GOOGLE_REDIRECT_URI` (callback OAuth explícito)
- `EDITOR_WEB_ACTIVITY_LOG_MAX` — tope de entradas en `activity_logs.json` (por defecto 4000).

`security_settings.json`:

- `login_required` — si el editor exige sesión.
- `open_google_registration` — si **true**, la primera vez que entra un Google válido se **crea solo** en `allowed_users.json` (sin admin). Si **false**, hace falta dar de alta el correo a mano en el panel admin.

Los usuarios pueden guardar un **nombre para mostrar** (Configuración en el editor); se guarda en `authenticated_users.json` junto al nombre de perfil de Google.

Persistencia en JSON:

- `allowed_users.json` — acceso, admin y bloqueados.
- `authenticated_users.json` — logins, nombre Google, `display_name` opcional.
- `execution_logs.json` — pasos de ejecución del simulador por sesión de navegador.
- `activity_logs.json` — inferencias y generaciones de microops (para auditoría en el panel admin).

Ejemplo en PowerShell:

```powershell
$env:GOOGLE_CLIENT_ID="tu-client-id"
$env:GOOGLE_CLIENT_SECRET="tu-client-secret"
$env:FLASK_SECRET_KEY="cambia-esto"
$env:EDITOR_WEB_DEFAULT_ADMINS="admin1@gmail.com,admin2@fi.unju.edu.ar"
python app.py
```

La interfaz de administración no está enlazada en la barra principal: entrá por `EDITOR_WEB_ADMIN_PATH` (tras login). En **Render** (y similares) el sistema de archivos del contenedor suele ser **efímero**: al reiniciar el servicio esos archivos vuelven al estado del despliegue.

### Persistencia en producción (Render u otro PaaS)

1. Crea un **Persistent Disk** en tu servicio web y móntalo, por ejemplo en `/var/oc-data`.
2. Define la variable de entorno:
   - `EDITOR_WEB_DATA_DIR=/var/oc-data`
3. Al arrancar, si el volumen está vacío, la app **copia** desde `editor_web/data/` del repo los JSON que falten (plantilla inicial).
4. Opcional: `EDITOR_WEB_REQUEST_LOG_MAX=200` (tamaño máximo del anillo de la consola de peticiones en el panel admin).

### Mantener el servicio despierto (plan gratis / spin-down)

- Con la página del editor abierta, el front hace **`GET /api/keepalive` cada 8 minutos** (tráfico HTTP hacia tu instancia).
- Si **nadie** tiene el sitio abierto, podés configurar en Render:
  - `EDITOR_WEB_SELF_KEEPALIVE_URL` = `https://TU-SERVICIO.onrender.com/api/keepalive`
  - opcional `EDITOR_WEB_SELF_KEEPALIVE_INTERVAL_SEC` = `480` (8 min; mínimo efectivo 120 s)

Eso hace que el proceso pida su propia URL por HTTP y suela contar como visita para el proxy de Render (un worker: un hilo).

El panel `/_internal/access-control` muestra la ruta de datos activa y un aviso si sigues en modo efímero.

## Notas

- Mantiene paneles equivalentes al editor de escritorio: registros, RAM editable, editor, traza y resultados.
- La calculadora web existente no se modifica.
