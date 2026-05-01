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

La web del editor ahora requiere login con Google y solo acepta cuentas `@fi.unju.edu.ar`.

Variables de entorno obligatorias:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `FLASK_SECRET_KEY` (recomendado en producción)

Variables opcionales:

- `ALLOWED_DOMAIN` (por defecto `fi.unju.edu.ar`)
- `EDITOR_WEB_ADMIN_PATH` (por defecto `/_internal/access-control`)
- `EDITOR_WEB_DEFAULT_ADMINS` (lista separada por comas de correos admin iniciales)
- `GOOGLE_REDIRECT_URI` (si quieres fijar explícitamente el callback OAuth)

Ejemplo rápido en PowerShell:

```powershell
$env:GOOGLE_CLIENT_ID="tu-client-id"
$env:GOOGLE_CLIENT_SECRET="tu-client-secret"
$env:FLASK_SECRET_KEY="cambia-esto"
$env:EDITOR_WEB_DEFAULT_ADMINS="admin1@fi.unju.edu.ar,admin2@fi.unju.edu.ar"
python app.py
```

La interfaz de administración de usuarios no aparece enlazada en la UI principal: se accede directamente por `EDITOR_WEB_ADMIN_PATH`.

Persistencia en JSON (sin base de datos):

- `allowed_users.json` → usuarios con acceso, admin y bloqueados.
- `authenticated_users.json` → historial de cuentas autenticadas (primer/último login y cantidad).
- `security_settings.json` → bandera `login_required` para exigir o no login en el editor web.

Por defecto se guardan en `editor_web/data/` junto al código. En **Render** (y similares) el sistema de archivos del contenedor suele ser **efímero**: al reiniciar el servicio esos archivos vuelven al estado del despliegue.

### Persistencia en producción (Render u otro PaaS)

1. Crea un **Persistent Disk** en tu servicio web y móntalo, por ejemplo en `/var/oc-data`.
2. Define la variable de entorno:
   - `EDITOR_WEB_DATA_DIR=/var/oc-data`
3. Al arrancar, si el volumen está vacío, la app **copia** desde `editor_web/data/` del repo los JSON que falten (plantilla inicial).
4. Opcional: `EDITOR_WEB_REQUEST_LOG_MAX=200` (tamaño máximo del anillo de la consola de peticiones en el panel admin).

El panel `/_internal/access-control` muestra la ruta de datos activa y un aviso si sigues en modo efímero.

## Notas

- Mantiene paneles equivalentes al editor de escritorio: registros, RAM editable, editor, traza y resultados.
- La calculadora web existente no se modifica.
