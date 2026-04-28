"""
Inferidor de instrucciones de alto nivel mediante ejecución simbólica.

En vez de hardcodear patrones, simula cada operación usando variables
simbólicas (sympy). Al final muestra qué expresión matemática quedó
en cada registro modificado.
"""
from __future__ import annotations

import re

from sympy import symbols, simplify, factor, Not, Symbol, collect, expand, sympify
from sympy import Rational, Integer
from sympy.printing import sstr


# Símbolos iniciales para cada registro
ACC0, GPR0, M0, F0 = symbols("ACC GPR M F", integer=True)
# F0 es variable simbólica (valor desconocido al inicio)

# Plantilla emitida por Generador._acc_en_div4_menos_f (ver ACC/4 - F).
_PLANTILLA_DIV4_MENOS_F_NUCLEO = (
    "ZERO_F",
    "ROR_F_ACC",
    "ZERO_F",
    "ROR_F_ACC",
    "ACC_TO_GPR",
    "ZERO_ACC",
    "ROL_F_ACC",
    "NOT_ACC",
    "INC_ACC",
    "SUM_ACC_GPR",
)
_PLANTILLA_DIV4_MENOS_F_M = _PLANTILLA_DIV4_MENOS_F_NUCLEO + ("ACC_TO_GPR", "GPR_TO_M")

# Prefijo fetch atómico (misma convención que Generador.FETCH_CICLO_INSTRUCCION).
_FETCH_ATOMICA = ("PC_TO_MAR", "M_TO_GPR", "INC_PC", "GPR_OP_TO_OPR")

_MAPA_TEXTO_A_INTERNO = {
    "PC -> MAR": "PC_TO_MAR",
    "M -> GPR, PC+1->PC": "M_TO_GPR_INC_PC",
    "M -> GPR": "M_TO_GPR",
    "M -> ACC": "M_TO_ACC",
    "GPR(OP) -> OPR": "GPR_OP_TO_OPR",
    "GPR(AD) -> MAR": "GPR_AD_TO_MAR",
    "ACC -> GPR": "ACC_TO_GPR",
    "GPR -> ACC": "GPR_TO_ACC",
    "GPR -> M": "GPR_TO_M",
    "ACC+GPR -> ACC": "SUM_ACC_GPR",
    "GPR+ACC -> ACC": "SUM_ACC_GPR",
    "ACC+1 -> ACC": "INC_ACC",
    "GPR+1 -> GPR": "INC_GPR",
    "ACC! -> ACC": "NOT_ACC",
    "F! -> F": "NOT_F",
    "0 -> ACC": "ZERO_ACC",
    "0 -> F": "ZERO_F",
    "ROL F, ACC": "ROL_F_ACC",
    "ROR F, ACC": "ROR_F_ACC",
}


def _ops_tras_fetch_si_hay(ops: list) -> list:
    ops = [o for o in ops if o]
    if len(ops) >= 4 and tuple(ops[:4]) == _FETCH_ATOMICA:
        return ops[4:]
    return ops


# Ejecución de la filmina "M <- Acc + M + 2 (directo)" sin la línea roja GPR(AD)->MAR.
_CUERPO_DIRECTO_M_ACC_2_SIN_MAR = (
    "M_TO_GPR",
    "SUM_ACC_GPR",
    "INC_ACC",
    "INC_ACC",
    "ACC_TO_GPR",
    "GPR_TO_M",
)


def clasificar_modo_direccionamiento(ops: list) -> str:
    """
    Según apuntes: sin GPR(AD)->MAR en ejecución → implicado;
    una vez → directo; dos o más → indirecto.
    Si hay fetch estándar de 4 microops al inicio, no cuenta para el modo.
    """
    exec_ops = _ops_tras_fetch_si_hay(list(ops))
    n = sum(1 for o in exec_ops if o == "GPR_AD_TO_MAR")
    if n == 0:
        if len(exec_ops) >= len(_CUERPO_DIRECTO_M_ACC_2_SIN_MAR) and tuple(
            exec_ops[: len(_CUERPO_DIRECTO_M_ACC_2_SIN_MAR)]
        ) == _CUERPO_DIRECTO_M_ACC_2_SIN_MAR:
            return (
                "Directo (cuerpo como apuntes; falta GPR(AD)->MAR antes del primer M->GPR)"
            )
        return "Implicado (inherente)"
    if n == 1:
        return "Directo"
    return "Indirecto"


def _infer_si_div4_menos_f(ops: list) -> str | None:
    """
    La simulación simbólica pierde F tras ROR (F pasa a 0). Esta secuencia
    implementa igualmente ACC/4 - F; la reconocemos por patrón (Generador).
    """
    if len(ops) >= len(_PLANTILLA_DIV4_MENOS_F_M) and tuple(
        ops[-len(_PLANTILLA_DIV4_MENOS_F_M) :]
    ) == _PLANTILLA_DIV4_MENOS_F_M:
        return "M <- ACC/4 - F"
    if len(ops) >= len(_PLANTILLA_DIV4_MENOS_F_NUCLEO) and tuple(
        ops[-len(_PLANTILLA_DIV4_MENOS_F_NUCLEO) :]
    ) == _PLANTILLA_DIV4_MENOS_F_NUCLEO:
        return "ACC <- ACC/4 - F"
    return None


def _limpiar_formato_simbolico(s: str) -> str:
    import re

    s = re.sub(r'(\d)\*([A-Z]+)', r'\1\2', s)  # 3*M -> 3M
    s = re.sub(r'(?<!\d)-1([A-Z])', r'-\1', s)  # -1ACC -> -ACC
    s = re.sub(r'([A-Z]+)/2', r'\1/2', s)
    return s


def _str_suma_orden_apuntes(expr) -> str:
    """
    Convierte una suma en texto con términos ordenados legibles:
    si aparece M → M, F, ACC, GPR; si no pero aparece ACC → ACC, GPR, M, F.
    """
    e = expand(simplify(expr))
    if not e.is_Add:
        return _limpiar_formato_simbolico(sstr(e))
    u = e.free_symbols
    if M0 in u:
        order = (M0, F0, ACC0, GPR0)
    elif ACC0 in u:
        order = (ACC0, GPR0, M0, F0)
    else:
        order = (M0, F0, ACC0, GPR0)
    prio = {sym: i for i, sym in enumerate(order)}

    def term_priority(t):
        for s in order:
            if t.has(s):
                return prio[s]
        return 99

    terms = sorted(e.args, key=lambda t: (term_priority(t), sstr(t)))
    first = sstr(terms[0])
    rest: list[str] = []
    for t in terms[1:]:
        st = sstr(t)
        if st.startswith("-"):
            rest.append(" - " + st[1:].lstrip())
        else:
            rest.append(" + " + st)
    return _limpiar_formato_simbolico(first + "".join(rest))


def _expr_string_canonica(expr) -> str:
    """String legible tipo apuntes."""
    e = expand(simplify(expr))
    if e.is_Add:
        return _str_suma_orden_apuntes(e)
    for sym in (M0, F0, ACC0, GPR0):
        if sym in e.free_symbols:
            e = collect(e, sym)
    return _limpiar_formato_simbolico(sstr(e))


def _equivalente_reorden_apuntes(s: str) -> str:
    """Reescribe '-ACC + …' como '… - ACC' cuando sea el mismo polinomio en apuntes."""
    if s.startswith("-ACC + "):
        return s[len("-ACC + ") :].strip() + " - ACC"
    return s


def _fmt_instruccion(destino_arrow: str, expr) -> str:
    """Texto destino <- expr: canónica (SymPy) y equivalente tipo apuntes si difiere."""
    can = _expr_string_canonica(expr)
    equiv = _equivalente_reorden_apuntes(can)
    if equiv == can:
        return f"{destino_arrow} <- {can}"
    return f"{destino_arrow} <- canónica: {can}  |  equivalente: {equiv}"


def _not12(expr):
    """
    Complemento a 1 de 12 bits: ~x en aritmética de 12 bits = -x - 1
    (equivalente a XOR con 0xFFF)
    """
    return -expr - 1


def _parsear_instruccion_objetivo(instruccion: str):
    if "<-" not in instruccion:
        return None, None
    dest_raw, expr_raw = instruccion.split("<-", 1)
    destino = dest_raw.strip().upper()
    if destino not in ("ACC", "M", "GPR"):
        return None, None
    expr_txt = expr_raw.strip()
    expr_txt = re.sub(r"\b(acc|gpr|m|f)\b", lambda m: m.group().upper(), expr_txt, flags=re.IGNORECASE)
    expr_txt = re.sub(r"(\d)(ACC|GPR|M\b|F\b)", r"\1*\2", expr_txt)
    try:
        expr = expand(sympify(expr_txt, locals={"ACC": ACC0, "GPR": GPR0, "M": M0, "F": F0}))
    except Exception:
        return None, None
    return destino, expr


def _extraer_expr_inferida(resultado_inferido: str, destino: str):
    partes = [p.strip() for p in resultado_inferido.split("|")]
    pref = f"{destino} <-"
    for p in partes:
        if not p.startswith(pref):
            continue
        rhs = p[len(pref):].strip()
        if rhs.startswith("canónica:"):
            rhs = rhs[len("canónica:"):].strip()
            if "  equivalente:" in rhs:
                rhs = rhs.split("  equivalente:", 1)[0].strip()
        rhs = re.sub(r"(\d)(ACC|GPR|M\b|F\b)", r"\1*\2", rhs)
        try:
            return expand(sympify(rhs, locals={"ACC": ACC0, "GPR": GPR0, "M": M0, "F": F0}))
        except Exception:
            return None
    return None


def verificar_equivalencia(instruccion: str, microops_texto: list[str]) -> tuple[bool, str]:
    """
    Verifica por equivalencia algebraica si una secuencia de microops implementa la instrucción.
    Compara la expresión objetivo contra la inferida simbólicamente.
    """
    destino, expr_obj = _parsear_instruccion_objetivo(instruccion)
    if destino is None or expr_obj is None:
        return False, "No se pudo parsear la instrucción objetivo."

    ops_internas: list[str] = []
    for op in microops_texto:
        txt = (op or "").strip()
        if not txt:
            continue
        cod = _MAPA_TEXTO_A_INTERNO.get(txt)
        if cod is None:
            return False, f"Microoperación no reconocida para verificación: {txt}"
        if cod == "M_TO_GPR_INC_PC":
            ops_internas.extend(["M_TO_GPR", "INC_PC"])
        else:
            ops_internas.append(cod)

    resultado = inferir(ops_internas)
    expr_inf = _extraer_expr_inferida(resultado, destino)
    if expr_inf is None:
        return False, f"No se pudo inferir expresión para {destino}. Inferido: {resultado}"

    if expand(expr_obj - expr_inf) == 0:
        return True, resultado
    return False, f"Objetivo: {destino} <- {_expr_string_canonica(expr_obj)} | Inferido: {resultado}"


def inferir(ops: list) -> str:
    """
    Simula simbólicamente la secuencia de ops y devuelve la instrucción
    de alto nivel que implementan (ej: 'M <- 3M - ACC').
    """
    if not ops:
        return "Sin instrucciones"

    ops = [op for op in ops if op]

    # ── Descartar fase fetch/decodificación (mismo prefijo que clasificar_modo) ──
    if len(ops) >= 4 and tuple(ops[:4]) == _FETCH_ATOMICA:
        ops = ops[4:]
    else:
        FETCH_OPS = {"PC_TO_MAR", "INC_PC", "INC_GPR", "GPR_OP_TO_OPR"}
        while ops and ops[0] in FETCH_OPS:
            ops = ops[1:]

    if not ops:
        return "Ciclo fetch / decodificación"

    div4f = _infer_si_div4_menos_f(ops)
    if div4f:
        return div4f

    # ── Detectar si F se usa sin haber sido inicializado en 0 ────────
    # Ignorar ops de setup (carga de memoria, fetch) al buscar el primer uso de F
    SETUP_OPS = {"PC_TO_MAR", "INC_PC", "INC_GPR", "GPR_OP_TO_OPR",
                 "GPR_AD_TO_MAR", "M_TO_GPR", "GPR_TO_ACC", "ACC_TO_GPR",
                 "ZERO_ACC", "INC_ACC"}
    f_inicial = Integer(0)
    for op in ops:
        if op in SETUP_OPS:
            continue
        if op in ("ROL_F_ACC", "ROR_F_ACC"):
            f_inicial = F0   # F desconocido antes del primer ROL/ROR
            break
        if op == "ZERO_F":
            f_inicial = Integer(0)  # F explícitamente puesto en 0
            break

    # ── Estado simbólico inicial ─────────────────────────────────────
    state = {
        "ACC": ACC0,
        "GPR": GPR0,
        "M":   M0,
        "F":   f_inicial,
    }

    # ── Ejecutar cada operación simbólicamente ───────────────────────
    for i, op in enumerate(ops):

        acc = state["ACC"]
        gpr = state["GPR"]
        m   = state["M"]
        f   = state["F"]

        if op == "INC_ACC":
            state["ACC"] = simplify(acc + 1)

        elif op == "INC_GPR":
            state["GPR"] = simplify(gpr + 1)

        elif op == "NOT_ACC":
            state["ACC"] = simplify(_not12(acc))

        elif op == "NOT_F":
            # F es 1 bit (apuntes): 0↔1, no complemento a 12 bits
            if f == Integer(0):
                state["F"] = Integer(1)
            elif f == Integer(1):
                state["F"] = Integer(0)
            else:
                state["F"] = simplify(1 - f)

        elif op == "ROL_F_ACC":
            # ROL: ACC*2 + F (12 bits en hardware). Si ACC==0, inyecta F en el LSB
            # (bloques “±F” del apunte). Dejar F=0 siempre hace que repeticiones
            # colapsen (-3M-2F → -3M-F). Tras inyectar, el bit F de estado se
            # relee igual en cada micropaso → restauramos F0 cuando el siguiente
            # paso es NOT (resta F) o SUM (suma con GPR / cierre de +F).
            # Cadenas ROL,ROL,… (p. ej. varios ROL seguidos) no cumplen acc==0 en
            # el 2.º ROL o el next no es NOT/SUM → F queda 0 (carry encadenado).
            new_acc = simplify(acc * 2 + f)
            state["ACC"] = new_acc
            nxt = ops[i + 1] if i + 1 < len(ops) else None
            if simplify(acc) == 0 and nxt in ("NOT_ACC", "SUM_ACC_GPR"):
                state["F"] = F0
            else:
                state["F"] = Integer(0)

        elif op == "ROR_F_ACC":
            # ROR: desplaza derecha 1 bit, F entra como bit más significativo
            # Resultado: (ACC + F*4096) / 2  pero expresado como entero
            # Cuando F=0: ACC >> 1 = ACC/2
            # Usamos división entera simbólica: floor(ACC/2) + F*2048
            from sympy import floor as sym_floor
            if f == Integer(0):
                new_acc = simplify(acc / 2)
            else:
                new_acc = simplify(acc / 2 + f * 2048)
            state["ACC"] = new_acc
            state["F"]   = Integer(0)

        elif op == "SUM_ACC_GPR":
            state["ACC"] = simplify(acc + gpr)

        elif op == "ACC_TO_GPR":
            state["GPR"] = state["ACC"]

        elif op == "GPR_TO_ACC":
            state["ACC"] = state["GPR"]

        elif op == "ZERO_ACC":
            state["ACC"] = Integer(0)

        elif op == "ZERO_F":
            state["F"] = Integer(0)

        elif op == "GPR_AD_TO_MAR":
            # Carga M desde RAM según dirección en GPR
            # Simbólicamente: M = M[GPR], lo representamos como M0
            state["M"] = M0

        elif op == "M_TO_GPR":
            state["GPR"] = state["M"]

        elif op == "M_TO_ACC":
            state["ACC"] = state["M"]

        elif op == "GPR_TO_M":
            state["M"] = state["GPR"]

        elif op == "PC_TO_MAR":
            pass  # fetch, ignorado

        elif op == "INC_PC":
            pass  # ignorado

        elif op == "GPR_OP_TO_OPR":
            pass  # ignorado

        # ops no conocidas se ignoran silenciosamente

    # ── Determinar qué registros cambiaron ───────────────────────────
    iniciales = {"ACC": ACC0, "GPR": GPR0, "M": M0, "F": F0}
    cambios = {}
    for reg, inicial in iniciales.items():
        final = simplify(state[reg])
        if final != inicial:
            cambios[reg] = final

    if not cambios:
        return "Sin efecto observable"

    # ── Elegir el destino más relevante ─────────────────────────────
    # Si M cambió y su valor NO depende solo de GPR/ACC sin cambio real → mostrar M
    # Prioridad: M > ACC > GPR
    # Pero si M solo cambió por un GPR_TO_M al final, el resultado real es ACC
    lineas: list[str] = []
    ultimo_op = ops[-1] if ops else ""

    if "M" in cambios and ultimo_op in ("GPR_TO_M", "M_TO_GPR"):
        lineas.append(_fmt_instruccion("M", cambios["M"]))
        # Si ACC también cambió, mostrar ambos efectos para no ocultar información.
        if "ACC" in cambios:
            lineas.append(_fmt_instruccion("ACC", cambios["ACC"]))
    elif "ACC" in cambios:
        lineas.append(_fmt_instruccion("ACC", cambios["ACC"]))
        if "M" in cambios and ultimo_op == "GPR_TO_M":
            lineas.append(_fmt_instruccion("M", cambios["M"]))
    elif "M" in cambios:
        lineas.append(_fmt_instruccion("M", cambios["M"]))

    if not lineas:
        lineas = [_fmt_instruccion(r, v) for r, v in cambios.items()]

    return "  |  ".join(lineas)
