from __future__ import annotations

import os
import sys
import json
import time
import shutil
import threading
from collections import deque
from functools import wraps
from pathlib import Path
from datetime import datetime, timezone

from bitstring import BitArray
from authlib.integrations.flask_client import OAuth
from flask import Flask, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from compilador.AnalizadorSintactico import parser, preprocesar_linea_microop  # noqa: E402
from modelo import Inferidor  # noqa: E402
from modelo.Generador import ErrorGeneracion, generar  # noqa: E402
from modelo.Von_Neumann import VonNeuman  # noqa: E402
from modelo.explicacion_microops import texto_explicacion_codigo  # noqa: E402
from modelo.traza import simular_traza  # noqa: E402

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret")

oauth = OAuth(app)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    client_kwargs={"scope": "openid email profile"},
)

ALLOWED_DOMAIN = os.environ.get("ALLOWED_DOMAIN", "fi.unju.edu.ar").lower()
ADMIN_PATH = os.environ.get("EDITOR_WEB_ADMIN_PATH", "/_internal/access-control")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()

_EDITOR_WEB_ROOT = Path(__file__).resolve().parent
_BUNDLED_DATA_DIR = _EDITOR_WEB_ROOT / "data"


def _resolve_data_dir() -> Path:
    custom = os.environ.get("EDITOR_WEB_DATA_DIR", "").strip()
    if custom:
        return Path(custom).expanduser().resolve()
    return _BUNDLED_DATA_DIR


DATA_DIR = _resolve_data_dir()
USERS_FILE = DATA_DIR / "allowed_users.json"
AUTH_USERS_FILE = DATA_DIR / "authenticated_users.json"
SECURITY_FILE = DATA_DIR / "security_settings.json"

REQUEST_LOG_MAX = max(20, min(500, int(os.environ.get("EDITOR_WEB_REQUEST_LOG_MAX", "120"))))
_request_audit_log: deque[dict] = deque(maxlen=REQUEST_LOG_MAX)

DEFAULT_ADMIN_EMAILS = [
    email.strip().lower()
    for email in os.environ.get("EDITOR_WEB_DEFAULT_ADMINS", "").split(",")
    if email.strip()
]


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _is_domain_allowed(email: str) -> bool:
    return email.endswith(f"@{ALLOWED_DOMAIN}")


def _load_access_data() -> dict:
    if USERS_FILE.exists():
        try:
            data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
            users = data.get("users", {})
            if isinstance(users, dict):
                normalized = {}
                for email, info in users.items():
                    clean = _normalize_email(email)
                    if not clean:
                        continue
                    normalized[clean] = {
                        "is_admin": bool((info or {}).get("is_admin", False)),
                        "is_banned": bool((info or {}).get("is_banned", False)),
                    }
                return {"users": normalized}
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": {}}


def _save_access_data(data: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_authenticated_data() -> dict:
    if AUTH_USERS_FILE.exists():
        try:
            data = json.loads(AUTH_USERS_FILE.read_text(encoding="utf-8"))
            users = data.get("users", {})
            if isinstance(users, dict):
                return {"users": users}
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": {}}


def _save_authenticated_data(data: dict) -> None:
    AUTH_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_USERS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _record_authenticated_user(email: str, name: str, picture: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    data = _load_authenticated_data()
    users = data["users"]
    current = users.get(email, {})
    users[email] = {
        "name": str(name or ""),
        "picture": str(picture or ""),
        "first_login_at": current.get("first_login_at", now),
        "last_login_at": now,
        "login_count": int(current.get("login_count", 0)) + 1,
    }
    _save_authenticated_data(data)


def _load_security_settings() -> dict:
    if SECURITY_FILE.exists():
        try:
            data = json.loads(SECURITY_FILE.read_text(encoding="utf-8"))
            return {"login_required": bool(data.get("login_required", True))}
        except (json.JSONDecodeError, OSError):
            pass
    return {"login_required": True}


def _save_security_settings(settings: dict) -> None:
    SECURITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECURITY_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def _bootstrap_data_from_bundled_if_needed() -> None:
    if DATA_DIR.resolve() == _BUNDLED_DATA_DIR.resolve():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("allowed_users.json", "security_settings.json", "authenticated_users.json"):
        src = _BUNDLED_DATA_DIR / name
        dst = DATA_DIR / name
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass


def _is_login_required() -> bool:
    return bool(_load_security_settings().get("login_required", True))


def _ensure_default_admins() -> None:
    if not DEFAULT_ADMIN_EMAILS:
        return
    data = _load_access_data()
    changed = False
    for email in DEFAULT_ADMIN_EMAILS:
        if not _is_domain_allowed(email):
            continue
        user = data["users"].get(email, {"is_admin": False, "is_banned": False})
        if not user.get("is_admin"):
            user["is_admin"] = True
            data["users"][email] = user
            changed = True
    if changed:
        _save_access_data(data)


def _get_user_access(email: str) -> dict | None:
    data = _load_access_data()
    return data["users"].get(_normalize_email(email))


def _is_logged_in() -> bool:
    return bool(session.get("user_email"))


def _is_admin() -> bool:
    return bool(session.get("is_admin"))


def _refresh_session_access() -> None:
    email = _normalize_email(session.get("user_email", ""))
    if not email:
        return
    access = _get_user_access(email)
    if not access or bool(access.get("is_banned")):
        session.clear()
        return
    session["is_admin"] = bool(access.get("is_admin"))


def login_required(fn):
    @wraps(fn)
    def _wrapped(*args, **kwargs):
        if not _is_login_required():
            return fn(*args, **kwargs)
        _refresh_session_access()
        if not _is_logged_in():
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "No autenticado."}), 401
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return _wrapped


def admin_required(fn):
    @wraps(fn)
    def _wrapped(*args, **kwargs):
        _refresh_session_access()
        if not _is_logged_in():
            return redirect(url_for("login", next=request.path))
        if not _is_admin():
            return "No autorizado.", 403
        return fn(*args, **kwargs)

    return _wrapped


def _bin_a_hex_ui(s: str, bits: int) -> str:
    raw = "".join(c for c in (s or "") if c in "01")
    if bits == 1:
        if not raw:
            return "0"
        return raw[-1]
    if not raw:
        return "000"
    raw = raw.zfill(bits)[-bits:]
    return f"{int(raw, 2) & ((1 << bits) - 1):03X}"


def _sanitize_bin(s: str, bits: int) -> str:
    raw = "".join(c for c in str(s or "") if c in "01")
    if bits == 1:
        return (raw[-1:] or "0")
    return raw.zfill(bits)[-bits:] if raw else ("0" * bits)


def _to_bitarray(s: str, bits: int) -> BitArray:
    return BitArray(bin=_sanitize_bin(s, bits))


class EditorWebState:
    def __init__(self) -> None:
        self.cpu = VonNeuman()
        self.pc = 0
        self.code = ""
        self.registers = {
            "PC": "000000000000",
            "ACC": "000000000000",
            "GPR": "000000000000",
            "F": "0",
            "M": "000000000000",
        }
        self.mem_edit = ["000000000000" for _ in range(256)]
        self.last_status = "Listo."
        self.last_error = False
        self._sync_cpu_from_ui()

    def _sync_cpu_from_ui(self) -> None:
        self.cpu.PC = _to_bitarray(self.registers["PC"], 12)
        self.cpu.ACC = _to_bitarray(self.registers["ACC"], 12)
        self.cpu.GPR = _to_bitarray(self.registers["GPR"], 12)
        self.cpu.F = _to_bitarray(self.registers["F"], 1)
        self.cpu.M = _to_bitarray(self.registers["M"], 12)
        for i, cell in enumerate(self.mem_edit):
            try:
                self.cpu.RAM.escribir(i, int(_sanitize_bin(cell, 12), 2))
            except (ValueError, IndexError):
                self.cpu.RAM.escribir(i, 0)

    def _sync_ui_from_cpu(self) -> None:
        self.registers["PC"] = self.cpu.PC.bin
        self.registers["ACC"] = self.cpu.ACC.bin
        self.registers["GPR"] = self.cpu.GPR.bin
        self.registers["F"] = self.cpu.F.bin
        self.registers["M"] = self.cpu.M.bin
        dump = self.cpu.RAM.dump()
        for i in range(min(256, len(dump))):
            self.mem_edit[i] = dump[i]

    def load_payload(self, payload: dict) -> None:
        self.code = str(payload.get("code", self.code))
        regs = payload.get("registers", {})
        for key in ("PC", "ACC", "GPR", "F", "M"):
            if key in regs:
                self.registers[key] = _sanitize_bin(regs[key], 1 if key == "F" else 12)
        memory = payload.get("memory", None)
        if isinstance(memory, list):
            for i in range(min(256, len(memory))):
                self.mem_edit[i] = _sanitize_bin(memory[i], 12)
        if "pc_counter" in payload:
            try:
                self.pc = max(0, int(payload["pc_counter"]))
            except (TypeError, ValueError):
                self.pc = 0
        self._sync_cpu_from_ui()

    def serialize(self) -> dict:
        self._sync_ui_from_cpu()
        reg_hex = {
            "PC": _bin_a_hex_ui(self.registers["PC"], 12),
            "ACC": _bin_a_hex_ui(self.registers["ACC"], 12),
            "GPR": _bin_a_hex_ui(self.registers["GPR"], 12),
            "F": _bin_a_hex_ui(self.registers["F"], 1),
            "M": _bin_a_hex_ui(self.registers["M"], 12),
        }
        memory_hex = [_bin_a_hex_ui(v, 12) for v in self.mem_edit]
        return {
            "code": self.code,
            "pc_counter": self.pc,
            "registers": self.registers,
            "registers_hex": reg_hex,
            "memory": self.mem_edit,
            "memory_hex": memory_hex,
            "status": self.last_status,
            "is_error": self.last_error,
        }

    def ejecutar_una(self) -> dict:
        self._sync_cpu_from_ui()
        lineas = self.code.strip().split("\n") if self.code.strip() else []
        if self.pc >= len(lineas):
            self.last_status = f"Fin del programa — ACC={self.cpu.ACC.bin}"
            self.last_error = False
            return self.serialize()

        linea = preprocesar_linea_microop(lineas[self.pc])
        if not linea:
            self.pc += 1
            self.last_status = f"Línea {self.pc}: vacía/comentario, se omitió."
            self.last_error = False
            return self.serialize()

        try:
            instr = parser.parse(linea)
        except Exception as exc:
            self.last_status = f"Línea {self.pc + 1}: error de sintaxis ({exc})"
            self.last_error = True
            self.pc += 1
            return self.serialize()

        ops_linea = [t[0] for t in (instr or []) if t is not None and t[0] is not None]
        if not ops_linea:
            self.last_status = f"Línea {self.pc + 1}: error de sintaxis en '{linea}'"
            self.last_error = True
            self.pc += 1
            return self.serialize()

        dispatch = {
            "INC_ACC": self.cpu.INC_ACC,
            "INC_GPR": self.cpu.INC_GPR,
            "NOT_ACC": self.cpu.NOT_ACC,
            "NOT_F": self.cpu.NOT_F,
            "ROL_F_ACC": self.cpu.ROL_F_ACC,
            "ROR_F_ACC": self.cpu.ROR_F_ACC,
            "SUM_ACC_GPR": self.cpu.SUM_ACC_GPR,
            "ACC_TO_GPR": self.cpu.ACC_TO_GPR,
            "GPR_TO_ACC": self.cpu.GPR_TO_ACC,
            "ZERO_ACC": self.cpu.ZERO_TO_ACC,
            "ZERO_F": self.cpu.ZERO_TO_F,
            "GPR_AD_TO_MAR": self.cpu.GPR_AD_TO_MAR,
            "GPR_TO_M": self.cpu.GPR_TO_M,
            "M_TO_GPR": self.cpu.M_TO_GPR,
            "M_TO_ACC": self.cpu.M_TO_ACC,
            "PC_TO_MAR": self.cpu.PC_TO_MAR,
            "INC_PC": self.cpu.INC_PC,
            "GPR_OP_TO_OPR": self.cpu.GPR_OP_TO_OPR,
        }

        for op in ops_linea:
            fn = dispatch.get(op)
            if fn is None:
                self.last_status = f"Línea {self.pc + 1}: instrucción no soportada '{op}'"
                self.last_error = True
                self.pc += 1
                return self.serialize()
            fn()

        self.pc += 1
        self.last_status = f"Línea {self.pc}: {linea}  →  {' · '.join(ops_linea)}"
        self.last_error = False
        self._sync_ui_from_cpu()
        return self.serialize()

    def reiniciar(self) -> dict:
        self.cpu = VonNeuman()
        self.pc = 0
        self.registers = {
            "PC": "000000000000",
            "ACC": "000000000000",
            "GPR": "000000000000",
            "F": "0",
            "M": "000000000000",
        }
        self.mem_edit = ["000000000000" for _ in range(256)]
        self.last_status = "Reiniciado."
        self.last_error = False
        self._sync_cpu_from_ui()
        return self.serialize()


STATE = EditorWebState()
_bootstrap_data_from_bundled_if_needed()
_ensure_default_admins()


@app.before_request
def _protect_editor_web():
    if request.path == "/api/keepalive":
        return None
    public_paths = {
        "/login",
        "/auth/google",
        "/auth/google/callback",
    }
    if (
        request.path.startswith("/static/")
        or request.path.startswith("/assets/")
        or request.path.startswith("/editor-images/")
    ):
        return None
    if request.path in public_paths:
        return None
    if request.path == ADMIN_PATH:
        return None
    if request.path.startswith("/api/admin/"):
        return None
    if not _is_login_required():
        return None
    if not _is_logged_in():
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "No autenticado."}), 401
        return redirect(url_for("login"))
    return None


@app.before_request
def _request_start_timer():
    g._t0 = time.perf_counter()


def _safe_json_preview(obj: object, limit: int = 600) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = str(obj)
    return s if len(s) <= limit else s[: limit - 3] + "..."


@app.after_request
def _admin_request_audit_log(response):
    try:
        if request.path == "/api/keepalive":
            return response
        if (
            request.path.startswith("/static/")
            or request.path.startswith("/editor-images/")
            or request.path.startswith("/assets/")
        ):
            return response
        duration_ms = None
        if getattr(g, "_t0", None) is not None:
            duration_ms = round((time.perf_counter() - g._t0) * 1000, 2)

        req_preview = ""
        if request.method in ("POST", "PUT", "PATCH") and request.path.startswith("/api/"):
            cl = request.content_length
            if cl is not None and cl < 12000:
                if request.is_json:
                    req_preview = _safe_json_preview(request.get_json(silent=True) or {}, 800)

        resp_preview = ""
        ct = (response.headers.get("Content-Type") or "").lower()
        if "application/json" in ct and not response.direct_passthrough:
            try:
                raw = response.get_data()
                if len(raw) <= 20000:
                    resp_preview = raw.decode("utf-8", errors="replace")[:1200]
                response.set_data(raw)
            except OSError:
                pass

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.path,
            "query": request.query_string.decode("utf-8", errors="replace")[:500],
            "status": response.status_code,
            "duration_ms": duration_ms,
            "request_json": req_preview or None,
            "response_preview": resp_preview or None,
        }
        _request_audit_log.appendleft(entry)
    except Exception:
        pass
    return response


@app.route("/login")
def login():
    next_path = str(request.args.get("next", "") or "").strip()
    wants_internal_login = next_path.startswith(ADMIN_PATH)
    if wants_internal_login:
        session["post_login_next"] = next_path
    if not _is_login_required() and not wants_internal_login:
        return redirect(url_for("index"))
    return render_template("login.html", domain=ALLOWED_DOMAIN)


@app.route("/auth/google")
def auth_google():
    if not os.environ.get("GOOGLE_CLIENT_ID") or not os.environ.get("GOOGLE_CLIENT_SECRET"):
        return "Falta configurar GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET.", 500
    redirect_uri = GOOGLE_REDIRECT_URI or url_for("auth_google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def auth_google_callback():
    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        return "No se pudo autenticar con Google.", 401
    userinfo = token.get("userinfo") or {}
    email = _normalize_email(userinfo.get("email", ""))
    name = str(userinfo.get("name", "") or "")
    picture = str(userinfo.get("picture", "") or "")
    verified = bool(userinfo.get("email_verified"))
    if not email or not verified or not _is_domain_allowed(email):
        session.clear()
        return "Solo se permite acceso con cuentas @fi.unju.edu.ar verificadas.", 403
    access = _get_user_access(email)
    if not access or bool(access.get("is_banned")):
        session.clear()
        return "Tu cuenta no está habilitada para usar este sitio.", 403

    _record_authenticated_user(email, name, picture)
    session["user_email"] = email
    session["is_admin"] = bool(access.get("is_admin"))
    next_path = str(session.pop("post_login_next", "") or "").strip()
    if next_path.startswith(ADMIN_PATH):
        return redirect(next_path)
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html", user_email=session.get("user_email"), is_admin=_is_admin(), admin_path=ADMIN_PATH)


@app.get(ADMIN_PATH)
@admin_required
def admin_users():
    data = _load_access_data()
    users = [
        {"email": email, "is_admin": bool(info.get("is_admin")), "is_banned": bool(info.get("is_banned"))}
        for email, info in sorted(data["users"].items())
    ]
    auth_data = _load_authenticated_data()
    authenticated_users = [
        {"email": email, **(info or {})}
        for email, info in sorted(auth_data["users"].items(), key=lambda item: item[0])
    ]
    settings = _load_security_settings()
    using_custom_data = DATA_DIR.resolve() != _BUNDLED_DATA_DIR.resolve()
    return render_template(
        "admin_users.html",
        users=users,
        authenticated_users=authenticated_users,
        login_required=settings.get("login_required", True),
        domain=ALLOWED_DOMAIN,
        user_email=session.get("user_email"),
        data_dir=str(DATA_DIR),
        persistence_custom=using_custom_data,
    )


@app.get("/api/admin/users")
def api_admin_users_get():
    if not _is_logged_in():
        return jsonify({"ok": False, "error": "No autenticado."}), 401
    if not _is_admin():
        return jsonify({"ok": False, "error": "No autorizado."}), 403
    data = _load_access_data()
    users = [
        {"email": email, "is_admin": bool(info.get("is_admin")), "is_banned": bool(info.get("is_banned"))}
        for email, info in sorted(data["users"].items())
    ]
    auth_data = _load_authenticated_data()
    authenticated_users = [{"email": email, **(info or {})} for email, info in sorted(auth_data["users"].items())]
    settings = _load_security_settings()
    return jsonify(
        {
            "ok": True,
            "users": users,
            "authenticated_users": authenticated_users,
            "login_required": bool(settings.get("login_required", True)),
        }
    )


@app.post("/api/admin/users")
def api_admin_users_post():
    if not _is_logged_in():
        return jsonify({"ok": False, "error": "No autenticado."}), 401
    if not _is_admin():
        return jsonify({"ok": False, "error": "No autorizado."}), 403

    payload = request.get_json(force=True) or {}
    action = str(payload.get("action", "")).strip().lower()
    if not action and "login_required" in payload:
        action = "set_login_required"
    if not action and "is_banned" in payload and payload.get("email"):
        action = "set_ban"
    if not action and "is_admin" in payload and payload.get("email"):
        action = "set_admin"
    email = _normalize_email(payload.get("email", ""))
    data = _load_access_data()
    users = data["users"]

    if action == "add":
        if not email:
            return jsonify({"ok": False, "error": "Email requerido."}), 400
        users[email] = {
            "is_admin": bool(payload.get("is_admin", False)),
            "is_banned": bool(payload.get("is_banned", False)),
        }
        _save_access_data(data)
        return jsonify({"ok": True, "message": f"Usuario {email} agregado/actualizado."})

    if action == "remove":
        if not email:
            return jsonify({"ok": False, "error": "Email requerido."}), 400
        if email == session.get("user_email"):
            return jsonify({"ok": False, "error": "No puedes quitarte a ti mismo."}), 400
        users.pop(email, None)
        _save_access_data(data)
        return jsonify({"ok": True, "message": f"Usuario {email} eliminado."})

    if action == "set_admin":
        if not email or email not in users:
            return jsonify({"ok": False, "error": "Usuario no encontrado."}), 404
        users[email]["is_admin"] = bool(payload.get("is_admin", False))
        _save_access_data(data)
        return jsonify({"ok": True, "message": f"Permiso admin actualizado para {email}."})

    if action == "set_ban":
        if not email or email not in users:
            return jsonify({"ok": False, "error": "Usuario no encontrado."}), 404
        if email == session.get("user_email") and bool(payload.get("is_banned", False)):
            return jsonify({"ok": False, "error": "No puedes banear tu propia cuenta activa."}), 400
        users[email]["is_banned"] = bool(payload.get("is_banned", False))
        _save_access_data(data)
        return jsonify({"ok": True, "message": f"Estado de bloqueo actualizado para {email}."})

    if action == "set_login_required":
        settings = _load_security_settings()
        settings["login_required"] = bool(payload.get("login_required", True))
        _save_security_settings(settings)
        return jsonify(
            {
                "ok": True,
                "message": "Configuración de login actualizada.",
                "login_required": settings["login_required"],
            }
        )

    return jsonify({"ok": False, "error": "Acción inválida."}), 400


@app.get("/api/admin/settings")
def api_admin_settings_get():
    if not _is_logged_in():
        return jsonify({"ok": False, "error": "No autenticado."}), 401
    if not _is_admin():
        return jsonify({"ok": False, "error": "No autorizado."}), 403
    settings = _load_security_settings()
    return jsonify({"ok": True, "login_required": bool(settings.get("login_required", True))})


@app.post("/api/admin/settings")
def api_admin_settings_post():
    if not _is_logged_in():
        return jsonify({"ok": False, "error": "No autenticado."}), 401
    if not _is_admin():
        return jsonify({"ok": False, "error": "No autorizado."}), 403
    payload = request.get_json(force=True) or {}
    settings = _load_security_settings()
    settings["login_required"] = bool(payload.get("login_required", True))
    _save_security_settings(settings)
    return jsonify(
        {
            "ok": True,
            "message": "Configuración de login actualizada.",
            "login_required": settings["login_required"],
        }
    )


@app.get("/api/admin/request-log")
def api_admin_request_log():
    if not _is_logged_in():
        return jsonify({"ok": False, "error": "No autenticado."}), 401
    if not _is_admin():
        return jsonify({"ok": False, "error": "No autorizado."}), 403
    return jsonify({"ok": True, "entries": list(_request_audit_log)})


@app.route("/assets/images/<path:filename>")
@login_required
def assets_images(filename: str):
    images_dir = BASE_DIR / "images"
    return send_from_directory(images_dir, filename)


@app.route("/editor-images/<path:filename>")
def editor_images(filename: str):
    images_dir = Path(__file__).resolve().parent / "images"
    return send_from_directory(images_dir, filename)


@app.get("/api/keepalive")
def api_keepalive():
    return jsonify({"ok": True, "ts": datetime.now(timezone.utc).isoformat()})


@app.get("/api/state")
@login_required
def api_state_get():
    return jsonify({"ok": True, "state": STATE.serialize()})


@app.post("/api/state")
@login_required
def api_state_set():
    payload = request.get_json(force=True) or {}
    STATE.load_payload(payload)
    return jsonify({"ok": True, "state": STATE.serialize()})


@app.post("/api/execute-step")
@login_required
def api_execute_step():
    payload = request.get_json(force=True) or {}
    STATE.load_payload(payload)
    return jsonify({"ok": True, "state": STATE.ejecutar_una()})


@app.post("/api/reset")
@login_required
def api_reset():
    return jsonify({"ok": True, "state": STATE.reiniciar()})


@app.post("/api/infer")
@login_required
def api_infer():
    payload = request.get_json(force=True) or {}
    code = str(payload.get("code", STATE.code))
    ops = []
    for linea in code.split("\n"):
        proc = preprocesar_linea_microop(linea)
        if not proc:
            continue
        instr = parser.parse(proc)
        if instr:
            for t in instr:
                if t is not None and t[0] is not None:
                    ops.append(t[0])
    if not ops:
        return jsonify({"ok": True, "inference": "Sin instrucciones para inferir", "mode": ""})
    return jsonify(
        {
            "ok": True,
            "inference": Inferidor.inferir(ops),
            "mode": Inferidor.clasificar_modo_direccionamiento(ops),
        }
    )


@app.post("/api/generate")
@login_required
def api_generate():
    payload = request.get_json(force=True) or {}
    expresion = str(payload.get("expression", "")).strip()
    modo = payload.get("mode", None)
    if not expresion:
        return jsonify({"ok": False, "error": "La instrucción no puede estar vacía."}), 400
    try:
        ops = generar(expresion, modo)
        ok, detalle = Inferidor.verificar_equivalencia(expresion, ops)
        if not ok:
            raise ErrorGeneracion(
                "La secuencia generada no cumple semánticamente la instrucción solicitada.\n"
                f"{detalle}"
            )
        return jsonify({"ok": True, "ops": ops, "message": f"Generadas {len(ops)} instrucciones."})
    except ErrorGeneracion as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/trace")
@login_required
def api_trace():
    payload = request.get_json(force=True) or {}
    code = str(payload.get("code", STATE.code))
    mode = str(payload.get("trace_mode", "fetch"))
    mar_pc_dec = bool(payload.get("mar_pc_decimal", False))
    compact = bool(payload.get("compact", True))
    cpu = VonNeuman()
    regs = payload.get("registers", {})
    mem = payload.get("memory", [])
    cpu.PC = _to_bitarray(regs.get("PC", "0" * 12), 12)
    cpu.ACC = _to_bitarray(regs.get("ACC", "0" * 12), 12)
    cpu.GPR = _to_bitarray(regs.get("GPR", "0" * 12), 12)
    cpu.F = _to_bitarray(regs.get("F", "0"), 1)
    cpu.M = _to_bitarray(regs.get("M", "0" * 12), 12)
    if isinstance(mem, list):
        for i in range(min(256, len(mem))):
            cpu.RAM.escribir(i, int(_sanitize_bin(mem[i], 12), 2))

    filas, err, mem_info = simular_traza(
        code,
        cpu,
        prefijo_fetch=(mode == "fetch"),
        mar_pc_decimal=mar_pc_dec,
        omitir_repetidos=compact,
    )
    return jsonify(
        {
            "ok": True,
            "rows": filas,
            "error": err,
            "memory_info": mem_info,
            "explanation": texto_explicacion_codigo(code),
        }
    )


def _start_self_keepalive_if_configured() -> None:
    url = os.environ.get("EDITOR_WEB_SELF_KEEPALIVE_URL", "").strip()
    if not url:
        return
    interval = max(120, int(os.environ.get("EDITOR_WEB_SELF_KEEPALIVE_INTERVAL_SEC", "480")))

    def _loop():
        import requests

        while True:
            try:
                requests.get(url, timeout=25)
            except Exception:
                pass
            time.sleep(interval)

    threading.Thread(target=_loop, daemon=True, name="editor_web_keepalive").start()


_start_self_keepalive_if_configured()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
