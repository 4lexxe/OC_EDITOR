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

- `editor_web/data/allowed_users.json` → usuarios con acceso, admin y bloqueados.
- `editor_web/data/authenticated_users.json` → historial de cuentas autenticadas (primer/último login y cantidad).
- `editor_web/data/security_settings.json` → bandera `login_required` para exigir o no login en el editor web.

## Notas

- Mantiene paneles equivalentes al editor de escritorio: registros, RAM editable, editor, traza y resultados.
- La calculadora web existente no se modifica.
