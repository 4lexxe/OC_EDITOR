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

## Fórmulas y seguimiento de F

La web y el escritorio comparten `modelo/formato_apuntes.py` y
`modelo/seguimiento_f.py`. Las divisiones enteras se muestran como `ACC/4`.
`F_inicial` identifica el bit al comenzar y `F_extraido1`, `F_extraido2`, etc.
identifican bits distintos que salen de las rotaciones. Las notas explican su
origen. No se vuelve a interpretar el texto mostrado para verificar equivalencias.

Ejemplo: dos ROR con F en cero, negación, guardado en GPR, dos ROL sobre
ACC en cero, suma de GPR e incremento producen
`ACC <- -ACC/4 + 2F_extraido1 + 1`.
Aquí `F_extraido1` es el segundo bit del ACC inicial, contando desde la derecha.
El F original se perdió en el primer `0 -> F`.

El seguimiento distingue el contenido actual de F de la información inicial
copiada a otros registros. Es un análisis de dependencias de bits: puede conservar
dependencias que una simplificación algebraica mayor eliminaría. Las lecturas de
memoria posteriores a una escritura dependiente de F se tratan conservadoramente.
`palabra12(...)` se usa cuando una rotación requiere expresar el ajuste a 12 bits.

## Trazas según la cátedra

Una línea es un ciclo. Las microoperaciones simultáneas leen el estado anterior
y se aplican juntas. La búsqueda ocupa tres ciclos, incluido `M -> GPR, PC+1 -> PC`.
PC/MAR tienen 8 bits; OPR 4; ACC/GPR/M 12; F 1. SUM conserva F y `GPR -> M`
escribe en RAM[MAR]. Una línea inválida detiene la traza sin ejecutar fragmentos.

En **Traza**, elegí un ejemplo del material y pulsá **Cargar ejemplo**. Se cargan
código, registros y RAM. La tabla permite mostrar solo cambios, ver el estado
inicial, seleccionar ciclos, revisar F y copiar TSV. Los valores iniciales son
editables en el panel desplegable. La tabla web conserva el punto de partida
mientras avanzás con Play; una edición manual o carga nueva inicia otra traza.

Referencias de `VON_NEUMAN_EDITOR_MATERIAL`:

- Taub, *Circuitos Digitales y Microprocesadores*, cap. 9, tabla 9.1-1: registros y microoperaciones.
- *OC26. Clase Práctica TP5_Arquitectura*, pp. 15–16: M ← M − ACC + F; termina en M[83] = 00C.
- *OC26_2C. TP5 - Arquitectura de Computadoras*, p. 4, ejercicios 8 y 9: resultados M[48] = 024 y M[37] = 065.

## Ejercicios de parciales

El catálogo incluye las cuatro fórmulas aportadas por el usuario, el ejercicio h
de TP5 p. 2 y una variante expresamente identificada como propuesta. Cada uno
tiene consigna, condiciones, pistas, solución explicada y 26 casos visibles.
El dominio anunciado para esos seis desafíos es 0 ≤ ACC ≤ 400 y F ∈ {0,1};
las soluciones se comprueban exhaustivamente para las 4.812 combinaciones.
Las fracciones se redondean hacia abajo y los negativos se representan en C2.

**Verificar mi solución** muestra F inicial/final y su procedencia. **Ver en Traza**
carga el código actual y el estado sugerido, limpia la RAM anterior y respeta
si la consigna incluye búsqueda. Aprobar casos de prueba no constituye una
prueba universal de cualquier programa escrito por el alumno.

Pruebas desde la raíz del proyecto:

```bash
python -B -m unittest discover -s tests -v
```
