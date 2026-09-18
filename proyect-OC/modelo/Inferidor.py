"""
Inferidor de instrucciones de alto nivel mediante ejecución simbólica.

En vez de hardcodear patrones, simula cada operación usando variables
simbólicas (sympy). Al final muestra qué expresión matemática quedó
en cada registro modificado.
"""
from __future__ import annotations

import re

from sympy import symbols, simplify, expand, sympify, Integer, floor, Mod
from modelo.formato_apuntes import FormatoApuntes, normalizar_divisiones
from modelo.seguimiento_f import analizar_f


# Símbolos iniciales para cada registro
ACC0, GPR0, M0, F0 = symbols("ACC GPR M F", integer=True)
# F0 es variable simbólica (valor desconocido al inicio)

# Prefijo fetch atómico (misma convención que Generador.FETCH_CICLO_INSTRUCCION).
_FETCH_ATOMICA = ("PC_TO_MAR", "M_TO_GPR", "INC_PC", "GPR_OP_TO_OPR")


def _remover_todos_ciclos_fetch(ops: list) -> list:
    """
    Quita cada aparición consecutiva del fetch estándar de 4 microops.
    Si en el editor se pegan dos programas (fetch + cuerpo + fetch + cuerpo),
    sin esto el segundo fetch queda en medio y corrompe la simulación simbólica.
    """
    ops = [o for o in ops if o]
    out: list = []
    i = 0
    n = len(ops)
    while i < n:
        if i + 4 <= n and tuple(ops[i : i + 4]) == _FETCH_ATOMICA:
            i += 4
            continue
        out.append(ops[i])
        i += 1
    return out


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
    """Ops de ejecución: sin ningún ciclo fetch estándar de 4 microops."""
    return _remover_todos_ciclos_fetch([o for o in ops if o])


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


def _normalizar_texto_expr_apuntes_para_sym(expr_txt: str) -> str:
    """
    En apuntes «ACC/n» (n potencia de 2) es división entera; para SymPy usamos floor(ACC/n).
    Se reemplaza de mayor a menor n para no confundir «ACC/22» con «ACC/2».
    """
    t = expr_txt.strip()
    for n in (4096, 2048, 1024, 512, 256, 128, 64, 32, 16, 8, 4, 2):
        t = re.sub(
            rf"(?<![A-Za-z0-9_*])(ACC|GPR|M)\s*/\s*{n}(?![A-Za-z0-9_*])",
            rf"(floor(\1/{n}))",
            t,
            flags=re.IGNORECASE,
        )
    return t


_SYMPY_LOCALS = {"ACC": ACC0, "GPR": GPR0, "M": M0, "F": F0, "floor": floor, "Mod": Mod}


def _equiv_en_dominio_acc_12_bits(expr_obj, expr_inf) -> bool:
    """
    Si solo aparece ACC0 (palabra de 12 bits), comprobar igualdad en 0..4095.
    Cubre casos donde expand() no prueba floor(ACC/4) == floor(floor(ACC/2)/2).
    """
    syms = expr_obj.free_symbols | expr_inf.free_symbols
    if syms - {ACC0}:
        return False
    diff = expr_obj - expr_inf
    for v in range(4096):
        if diff.subs(ACC0, Integer(v)) != 0:
            return False
    return True


def _presentar_resultado(resultado) -> dict:
    if isinstance(resultado, str):
        return {"instruccion": resultado, "notas": []}
    formato = FormatoApuntes([expr for _, expr in resultado])
    return {
        "instruccion": "  |  ".join(formato.instruccion(dest, expr) for dest, expr in resultado),
        "notas": formato.notas(),
    }


def inferir_detallado(ops: list, ciclos: list | None = None) -> dict:
    """Instrucción en notación de apuntes y aclaraciones para web y escritorio."""
    resultado = _presentar_resultado(_inferir_expresiones(ops, ciclos=ciclos))
    if ops:
        analisis = analizar_f(ciclos if ciclos is not None else [[op] for op in ops if op])
        resultado["analisis_f"] = analisis
        resultado["notas"].append(analisis["resumen"])
    return resultado


def inferir(ops: list) -> str:
    """Interfaz compatible: devuelve únicamente la instrucción legible."""
    return inferir_detallado(ops)["instruccion"]


def _not12(expr):
    """
    Complemento a 1 de 12 bits: ~x en aritmética de 12 bits = -x - 1
    (equivalente a XOR con 0xFFF)
    """
    return -expr - 1


def _parsear_instruccion_objetivo(instruccion: str):
    from modelo.Generador import normalizar_expresion_texto
    norm = normalizar_expresion_texto(instruccion)
    if "<-" not in norm:
        return None, None
    dest_raw, expr_raw = norm.split("<-", 1)
    destino = dest_raw.strip().upper()
    if destino not in ("ACC", "M", "GPR"):
        return None, None
    expr_txt = _normalizar_texto_expr_apuntes_para_sym(expr_raw.strip())
    try:
        expr = expand(sympify(expr_txt, locals=_SYMPY_LOCALS))
    except Exception:
        return None, None
    return destino, expr


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

    expresiones = _inferir_expresiones(ops_internas)
    resultado = _presentar_resultado(expresiones)["instruccion"]
    expr_inf = None if isinstance(expresiones, str) else dict(expresiones).get(destino)
    if expr_inf is None:
        return False, f"No se pudo inferir expresión para {destino}. Inferido: {resultado}"

    # Comparamos árboles simbólicos, nunca volvemos a interpretar texto de la UI.
    # F del objetivo siempre es F inicial; nunca sustituirlo por un bit extraído.
    expr_inf = normalizar_divisiones(expr_inf)
    expr_obj = normalizar_divisiones(expr_obj)
    if simplify(expr_obj - expr_inf) == 0:
        return True, resultado
    if _equiv_en_dominio_acc_12_bits(expr_obj, expr_inf):
        return True, resultado
    objetivo = FormatoApuntes([expr_obj]).instruccion(destino, expr_obj)
    return False, f"Objetivo: {objetivo} | Inferido: {resultado}"


def _palabra12(expr):
    """Valor sin signo de una expresión en una palabra de 12 bits."""
    if expr in (ACC0, GPR0, M0, F0) or (expr.is_number and 0 <= expr < 4096):
        return expr
    if expr.func == floor:
        numerador, denominador = expr.args[0].as_numer_denom()
        if denominador.is_Integer and denominador >= 1 and _palabra12(numerador) == numerador:
            return expr
    return Mod(expr, 4096)


def _inferir_expresiones(ops: list, ciclos: list | None = None):
    """
    Devuelve pares (registro, expresión exacta), o un mensaje si no hay efectos.
    La presentación se aplica después, sin alterar el cálculo simbólico.
    """
    if not ops:
        return "Sin instrucciones"

    grupos = [[op] for op in ops if op] if ciclos is None else ciclos
    pares = [(ciclo, op) for ciclo, grupo in enumerate(grupos) for op in grupo if op]
    trabajo = []
    indice = 0
    while indice < len(pares):
        if tuple(op for _, op in pares[indice:indice + 4]) == _FETCH_ATOMICA:
            indice += 4
        else:
            trabajo.append(pares[indice])
            indice += 1
    # Fetch incompleto al inicio (p. ej. solo PC->MAR pegado suelto)
    FETCH_OPS = {"PC_TO_MAR", "INC_PC", "GPR_OP_TO_OPR"}
    while trabajo and trabajo[0][1] in FETCH_OPS:
        trabajo = trabajo[1:]
    ops = [op for _, op in trabajo]

    if not ops:
        return "Ciclo fetch / decodificación"

    # ── Estado simbólico inicial ─────────────────────────────────────
    state = {
        "ACC": ACC0,
        "GPR": GPR0,
        "M":   M0,
        "F":   F0,
    }

    # ── Ejecutar cada operación simbólicamente ───────────────────────
    ciclo_anterior = None
    for ciclo, op in trabajo:
        if ciclo != ciclo_anterior:
            entrada = dict(state)
            ciclo_anterior = ciclo
        acc, gpr, m, f = (entrada[r] for r in ("ACC", "GPR", "M", "F"))

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
            state["ACC"] = simplify(acc * 2 + f)
            # El bit 12 saliente reemplaza F, incluso si antes contenía F inicial.
            state["F"] = simplify(Mod(floor(acc / 2048), 2))

        elif op == "ROR_F_ACC":
            # El F anterior entra por el bit 12. Nunca asumir que F desconocido es 1.
            palabra = _palabra12(acc)
            state["ACC"] = simplify(floor(palabra / 2) + 2048 * f)
            state["F"] = simplify(Mod(acc, 2))

        elif op == "SUM_ACC_GPR":
            state["ACC"] = simplify(acc + gpr)
            # La suma de Taub conserva el flip-flop F.

        elif op == "ACC_TO_GPR":
            state["GPR"] = acc

        elif op == "GPR_TO_ACC":
            state["ACC"] = gpr

        elif op == "ZERO_ACC":
            state["ACC"] = Integer(0)

        elif op == "ZERO_F":
            state["F"] = Integer(0)

        elif op == "GPR_AD_TO_MAR":
            # Carga M desde RAM según dirección en GPR
            # Simbólicamente: M = M[GPR], lo representamos como M0
            state["M"] = M0

        elif op == "M_TO_GPR":
            state["GPR"] = m

        elif op == "M_TO_ACC":
            state["ACC"] = m

        elif op == "GPR_TO_M":
            state["M"] = gpr

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
    lineas: list[tuple] = []
    ultimo_op = ops[-1] if ops else ""

    if "M" in cambios and ultimo_op in ("GPR_TO_M", "M_TO_GPR"):
        lineas.append(("M", cambios["M"]))
        # Si ACC también cambió, mostrar ambos efectos para no ocultar información.
        if "ACC" in cambios:
            lineas.append(("ACC", cambios["ACC"]))
    elif "ACC" in cambios:
        lineas.append(("ACC", cambios["ACC"]))
        if "M" in cambios and ultimo_op == "GPR_TO_M":
            lineas.append(("M", cambios["M"]))
    elif "M" in cambios:
        lineas.append(("M", cambios["M"]))

    if not lineas:
        lineas = list(cambios.items())

    return lineas
