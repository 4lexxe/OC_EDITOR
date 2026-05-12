"""
Generador de microoperaciones a partir de una expresión de alto nivel.

Soporta expresiones del tipo:
    ACC <- N*ACC + K
    ACC <- N*ACC - K
    ACC <- N*M + K
    ACC <- N*M ± K*F   (análogo a M <- N*M ± K*F; F registro de estado)
    ACC <- ca*ACC + cm*M + cf*F + K  (coeficientes enteros; cf negativo resta F)
    ACC <- -N*ACC
    M   <- N*M - ACC
    M   <- -N*M
    M   <- N*M - K*F   (K>0: resta K veces F; vía patrón ACC <- ACC - F)
    M   <- N*M + K*F   (K>0: suma K veces F; vía 0/ROL F/GPR+ACC)
    ACC/M <- ACC/2 (+ F vía ROR), ACC/M <- ACC/4 - F, etc.
    ACC <- ACC/n, M <- ACC/n  (n = 2, 4, 8, … potencias de 2; varios ROR con F=0)
    ACC <- ACC - F, M <- M + ACC + K (directo/indirecto en apuntes).
    M   <- ca*ACC + cm*M + K  (ca, cm enteros distintos de cero, sin F en la expresión).
    M   <- ca*ACC + K  (sin término M; escribe ACC escalado + constante en memoria)
    M   <- ca*ACC + cm*M + cf*F + K  (lineal con F; ej. M <- ACC + 2M - F + 1)
    M   <- M/2 + cf*F + K  (ROR con F=0; ej. M <- M/2 - 4F - 2)

    generar(expr, modo='implicado'|'directo'|'indirecto') antepone fetch y,
    en indirecto, duplica el primer acceso GPR(AD)->MAR; M->GPR.

Usa sympy para parsear la expresión y luego genera la secuencia óptima.
"""
from sympy import symbols, sympify, expand, Rational, Integer, factor, simplify
from sympy import Mul, Add, Pow, Number


ACC, GPR, M, F = symbols("ACC GPR M F", integer=True)


class ErrorGeneracion(Exception):
    pass


def _es_coeficiente_entero_sympy(c) -> bool:
    """
    True solo si c es SymPy Integer. int(Rational(1, 2)) da 0 en Python;
    sin esto, M <- M/2 - 4F - 2 se confundía con M <- -4F - 2.
    """
    return getattr(c, "is_Integer", False) is True


# Fetch estándar (apuntes: modo implícito/directo/indirecto comparten estas 3 microops)
FETCH_CICLO_INSTRUCCION = [
    "PC -> MAR",
    "M -> GPR, PC+1->PC",
    "GPR(OP) -> OPR",
]

_PAR_MEM_DIRECTO = ["GPR(AD) -> MAR", "M -> GPR"]


def _cuerpo_div_acc_potencia_de_2(expr, destino: str) -> list | None:
    """
    ACC <- ACC/n o M <- ACC/n cuando la expresión es exactamente ACC/n (sin F ni otros símbolos)
    y n es 2, 4, 8, …: repetir (0->F, ROR) log2(n) veces.
    ACC/3, ACC/5, etc.: no se puede con solo esta plantilla → ErrorGeneracion.
    """
    if F in expr.free_symbols:
        return None
    if expr.free_symbols != {ACC}:
        return None
    quo = simplify(expr / ACC)
    if not quo.is_Rational or quo.p != 1:
        return None
    n = int(quo.q)
    if n < 2:
        return None
    if expand(expr - ACC / Integer(n)) != 0:
        return None
    if not _es_potencia_de_2(n):
        raise ErrorGeneracion(
            f"ACC/{n}: el generador solo arma división por 2, 4, 8, 16, … "
            f"(potencias de 2). ACC/3, ACC/5, ACC/6, etc. no van con ROR solos."
        )
    k = n.bit_length() - 1
    ops: list[str] = []
    for _ in range(k):
        ops += ["0 -> F", "ROR F, ACC"]
    if destino == "M":
        ops += ["ACC -> GPR", "GPR -> M"]
    return ops


def _normalizar_modo(modo: str | None) -> str | None:
    if modo is None or not str(modo).strip():
        return None
    m = str(modo).strip().lower()
    if m in ("solo", "ejecucion", "ejecución", "no", "ninguno", "none"):
        return None
    if m in ("implicado", "inherente", "implicito", "implícito"):
        return "implicado"
    if m in ("directo", "dir"):
        return "directo"
    if m in ("indirecto", "ind"):
        return "indirecto"
    raise ErrorGeneracion(
        f"Modo de direccionamiento desconocido: {modo!r}. "
        "Usá: implicado | directo | indirecto (o vacío solo ejecución)."
    )


def _duplicar_primera_carga_memoria(nucleo: list) -> list:
    """Indirecto: segundo par GPR(AD)->MAR, M->GPR al inicio (filminas)."""
    if len(nucleo) >= 2 and nucleo[:2] == _PAR_MEM_DIRECTO:
        return _PAR_MEM_DIRECTO + _PAR_MEM_DIRECTO + nucleo[2:]
    raise ErrorGeneracion(
        "Modo indirecto: la ejecución debe empezar con GPR(AD) -> MAR y M -> GPR."
    )


def _finalizar(nucleo: list, modo_n: str | None) -> list:
    if modo_n is None:
        return nucleo
    if modo_n == "implicado":
        if any(x == "GPR(AD) -> MAR" for x in nucleo):
            raise ErrorGeneracion(
                "Modo implicado/inherente: no debe haber GPR(AD) -> MAR en la ejecución."
            )
        return FETCH_CICLO_INSTRUCCION + nucleo
    if modo_n == "directo":
        return FETCH_CICLO_INSTRUCCION + nucleo
    if modo_n == "indirecto":
        return FETCH_CICLO_INSTRUCCION + _duplicar_primera_carga_memoria(nucleo)
    return nucleo


def generar(expresion: str, modo: str | None = None) -> list:
    """
    Recibe una expresión como 'ACC <- 8*ACC + 2' o 'M <- 3M - ACC'
    y devuelve la lista de microoperaciones equivalente.

    La expresión se simplifica con SymPy (p. ej. M <- -((6*M+2*F)/2) es lo mismo
    que M <- -3*M - F: el 2 de 2F y el /2 se cancelan en álgebra, no implican
    dos microbloques de F).

    modo opcional: 'implicado' | 'directo' | 'indirecto' antepone el fetch
    PC->MAR; M->GPR,PC+1->PC; GPR(OP)->OPR y en indirecto duplica el primer
    par GPR(AD)->MAR; M->GPR (ver filminas de direccionamiento).

    Retorna lista de strings (instrucciones en sintaxis del compilador).
    Lanza ErrorGeneracion si no puede generar la secuencia.
    """
    # ── Parsear el destino y la expresión ────────────────────────────
    if "<-" in expresion:
        partes = expresion.split("<-", 1)
    elif "->" in expresion:
        partes = expresion.split("->", 1)
    else:
        raise ErrorGeneracion("Formato inválido. Usá: DEST <- expresion")

    destino_str = partes[0].strip().upper()
    expr_str    = partes[1].strip()

    if destino_str not in ("ACC", "M", "GPR"):
        raise ErrorGeneracion(f"Destino '{destino_str}' no soportado. Usá ACC, M o GPR.")

    # Normalizar la expresión para sympy
    import re
    F = symbols("F", integer=True)
    # Convertir a mayúsculas los nombres de registros
    expr_str = re.sub(r'\b(acc|gpr|mar|m|f)\b', lambda m: m.group().upper(), expr_str, flags=re.IGNORECASE)
    # Insertar * entre número y variable: 4M -> 4*M, 3ACC -> 3*ACC, 2048F -> 2048*F
    expr_str = re.sub(r'(\d)(ACC|GPR|M\b|F\b)', r'\1*\2', expr_str)
    expr_str = expr_str.strip()
    try:
        expr = expand(sympify(expr_str, locals={"ACC": ACC, "GPR": GPR, "M": M, "F": F}))
    except Exception as e:
        raise ErrorGeneracion(f"No se pudo parsear la expresión: {e}")

    modo_n = _normalizar_modo(modo)
    ops = []

    # ACC <- ACC - F  (apuntes: direccionamiento implicado + ciclo fetch opcional)
    esperado_acc_menos_f = ACC - F
    if destino_str == "ACC" and expand(expr - esperado_acc_menos_f) == 0:
        ops = [
            "ACC -> GPR",
            "0 -> ACC",
            "ROL F, ACC",
            "ACC! -> ACC",
            "ACC+1 -> ACC",
            "GPR+ACC -> ACC",
        ]
        return _finalizar(ops, modo_n)

    # ── Caso con F (ROR/ROL) ────────────────────────────────────────
    F_sym = symbols("F", integer=True)
    coef_f_expr = expr.coeff(F_sym) if F_sym in expr.free_symbols else Integer(0)

    # ACC <- ACC/2 + 2048*F  →  ROR F, ACC
    if destino_str == "ACC" and coef_f_expr == 2048 and expr.coeff(ACC) == Rational(1, 2):
        ops.append("ROR F, ACC")
        k = int(expr - Rational(1,2)*ACC - 2048*F_sym)
        ops += _agregar_constante(k)
        return _finalizar(ops, modo_n)

    # M <- ACC/2 + 2048*F  →  ROR F, ACC + guardar en M
    if destino_str == "M" and coef_f_expr == 2048 and expr.coeff(ACC) == Rational(1, 2):
        ops.append("ROR F, ACC")
        ops += ["ACC -> GPR", "GPR -> M"]
        return _finalizar(ops, modo_n)

    # ACC <- ACC/n, M <- ACC/n  (n = 2^k; sin F en la expresión)
    if destino_str == "ACC" and coef_f_expr == 0:
        cdiv = _cuerpo_div_acc_potencia_de_2(expr, "ACC")
        if cdiv is not None:
            return _finalizar(cdiv, modo_n)
    if destino_str == "M" and coef_f_expr == 0:
        cdiv = _cuerpo_div_acc_potencia_de_2(expr, "M")
        if cdiv is not None:
            return _finalizar(cdiv, modo_n)

    # ACC/4 - F  →  dos ROR con F=0, luego ROL para copiar F al ACC y restar (GPR+ACC)
    # Usar la misma instancia F que en sympify (línea anterior).
    esperado_div4_menos_f = Rational(1, 4) * ACC - F
    if destino_str == "ACC" and expand(expr - esperado_div4_menos_f) == 0:
        ops += _acc_en_div4_menos_f()
        if modo_n == "indirecto":
            raise ErrorGeneracion(
                "ACC <- ACC/4 - F no lleva doble indirección a memoria; "
                "usá implicado o solo ejecución (o indirecto solo cuando el destino es M)."
            )
        return _finalizar(ops, modo_n)
    if destino_str == "M" and expand(expr - esperado_div4_menos_f) == 0:
        # El núcleo aritmético no empieza con GPR(AD)->MAR; el indirecto de los apuntes
        # antepone 1× (directo) o 2× (indirecto) el par carga antes del cálculo y el guardado.
        cuerpo = _acc_en_div4_menos_f() + ["ACC -> GPR", "GPR -> M"]
        if modo_n == "implicado":
            raise ErrorGeneracion(
                "M <- ACC/4 - F escribe en M: elegí 'Ciclo completo — directo' o '… indirecto'."
            )
        if modo_n == "directo":
            cuerpo = _PAR_MEM_DIRECTO + cuerpo
        elif modo_n == "indirecto":
            cuerpo = _PAR_MEM_DIRECTO + _PAR_MEM_DIRECTO + cuerpo
        if modo_n in ("directo", "indirecto"):
            return FETCH_CICLO_INSTRUCCION + cuerpo
        return cuerpo

    # ACC <- ACC/2 + cf*F + K (interpretación cátedra): F es {0,1} estable y cf*F es aritmético.
    # Estrategia: guardar ACC en M, capturar F en ACC (0; ROL), escalar por cf,
    # guardar ese término en GPR, restaurar ACC y dividir por 2 con F=0, sumar, y ajustar K.
    if destino_str == "ACC" and expr.coeff(ACC) == Rational(1, 2) and F_sym in expr.free_symbols:
        resto_acc_half = expand(expr - Rational(1, 2) * ACC - coef_f_expr * F_sym)
        if (
            coef_f_expr != Integer(0)
            and coef_f_expr != Integer(2048)
            and not resto_acc_half.free_symbols
            and _es_coeficiente_entero_sympy(coef_f_expr)
            and _es_coeficiente_entero_sympy(resto_acc_half)
        ):
            cf_i = int(coef_f_expr)
            k_i = int(resto_acc_half)
            ops = [
                "ACC -> GPR",
                "GPR -> M",
                "0 -> ACC",
                "ROL F, ACC",   # ACC = F (0/1), F queda 0
            ]
            ops += _multiplicar_ACC_sin_memoria_M(cf_i)  # ACC = cf*F (cátedra)
            ops += [
                "ACC -> GPR",   # guardar término cf*F
                "M -> ACC",     # restaurar ACC original
                "0 -> F",
                "ROR F, ACC",   # ACC = ACC/2 (lógico)
                "GPR+ACC -> ACC",
            ]
            ops += _agregar_constante(k_i)
            return _finalizar(ops, modo_n)

    # ACC <- 2*ACC + F  →  ROL F, ACC
    if destino_str == "ACC" and coef_f_expr == 1 and expr.coeff(ACC) == 2:
        ops.append("ROL F, ACC")
        k = int(expr - 2*ACC - F_sym)
        ops += _agregar_constante(k)
        return _finalizar(ops, modo_n)

    # M <- 2*ACC + F  →  ROL F, ACC + guardar en M
    if destino_str == "M" and coef_f_expr == 1 and expr.coeff(ACC) == 2:
        ops.append("ROL F, ACC")
        ops += ["ACC -> GPR", "GPR -> M"]
        return _finalizar(ops, modo_n)

    # ── Caso: ACC <- N*ACC + K ───────────────────────────────────────
    if destino_str == "ACC":
        coef_acc = expr.coeff(ACC)
        coef_gpr = expr.coeff(GPR)
        coef_m   = expr.coeff(M)
        constante = expr - coef_acc * ACC - coef_gpr * GPR - coef_m * M

        # ACC <- N*M + K (carga desde memoria; K debe ser número, sin F ni otros símbolos)
        if coef_m != 0 and coef_acc == 0 and coef_gpr == 0 and not constante.free_symbols:
            try:
                n = int(coef_m)
                k = int(constante)
            except (TypeError, ValueError):
                pass
            else:
                ops += _cargar_M_en_GPR()
                ops += _multiplicar_GPR(n, ops_acc_zero=True)
                ops += _agregar_constante(k)
                return _finalizar(ops, modo_n)

        # ACC <- N*M + K*F  (tipo ACC <- 3M - F; mismo patrón ±F que M <- N*M ± K*F)
        if (
            coef_m != 0
            and coef_acc == 0
            and coef_gpr == 0
            and F in expr.free_symbols
            and M in expr.free_symbols
        ):
            coef_f_am = expr.coeff(F)
            resto_am = expand(expr - coef_m * M - coef_f_am * F)
            if resto_am == 0:
                try:
                    n_am = int(coef_m)
                    kf_am = int(coef_f_am)
                except (TypeError, ValueError):
                    pass
                else:
                    if n_am == 0:
                        raise ErrorGeneracion(
                            "ACC <- 0*M + K*F no es un caso útil; revisá la expresión."
                        )
                    ops += _cargar_M_en_GPR()
                    ops += _multiplicar_GPR(n_am, ops_acc_zero=True)
                    if kf_am == 0:
                        return _finalizar(ops, modo_n)
                    if kf_am < 0:
                        ops += _acc_restar_f_veces(-kf_am)
                    else:
                        ops += _acc_sumar_f_veces(kf_am)
                    return _finalizar(ops, modo_n)

        # ACC <- N*ACC + K
        if coef_acc != 0 and coef_m == 0 and coef_gpr == 0 and not constante.free_symbols:
            try:
                n = int(coef_acc)
                k = int(constante)
            except (TypeError, ValueError):
                pass
            else:
                ops += _multiplicar_ACC(n)
                ops += _agregar_constante(k)
                return _finalizar(ops, modo_n)

        # ACC <- N*ACC + K*GPR
        if coef_acc != 0 and coef_gpr != 0 and coef_m == 0 and not constante.free_symbols:
            try:
                n = int(coef_acc)
                kg = int(coef_gpr)
                k = int(constante)
            except (TypeError, ValueError):
                pass
            else:
                ops += _multiplicar_ACC(n)
                # Sumar kg veces GPR
                for _ in range(abs(kg)):
                    if kg > 0:
                        ops.append("GPR+ACC -> ACC")
                    else:
                        ops += ["ACC! -> ACC", "ACC+1 -> ACC",
                                "GPR+ACC -> ACC",
                                "ACC! -> ACC", "ACC+1 -> ACC"]
                ops += _agregar_constante(k)
                return _finalizar(ops, modo_n)

        # ACC <- ca*ACC + cm*M + cf*F + K  (lineal general; sin GPR en el RHS)
        coef_f_lin = expr.coeff(F)
        resto_lin = expand(expr - coef_acc * ACC - coef_m * M - coef_f_lin * F - coef_gpr * GPR)
        if (
            coef_gpr == 0
            and not resto_lin.free_symbols
            and _es_coeficiente_entero_sympy(coef_acc)
            and _es_coeficiente_entero_sympy(coef_m)
            and _es_coeficiente_entero_sympy(coef_f_lin)
            and _es_coeficiente_entero_sympy(resto_lin)
        ):
            try:
                ca_i = int(coef_acc)
                cm_i = int(coef_m)
                cf_i = int(coef_f_lin)
                k_i = int(resto_lin)
            except (TypeError, ValueError):
                pass
            else:
                ops = _cuerpo_acc_lineal_general(ca_i, cm_i, cf_i, k_i)
                return _finalizar(ops, modo_n)

    # ── Caso: M <- expresion ─────────────────────────────────────────
    if destino_str == "M":
        coef_m   = expr.coeff(M)
        coef_acc = expr.coeff(ACC)
        coef_gpr = expr.coeff(GPR)
        constante = expr - coef_m * M - coef_acc * ACC - coef_gpr * GPR

        # M <- 4F - M/2  (Ejemplo apuntes; manipulación algebraica -> −(−8F+M)/2)
        esperado_4f_menos_m2 = 4 * F - Rational(1, 2) * M
        if expand(expr - esperado_4f_menos_m2) == 0:
            ops = _cuerpo_m_4f_menos_m_medio_apuntes()
            return _finalizar(ops, modo_n)

        # M <- M + ACC + K  (apuntes: directo / indirecto sobre memoria)
        if coef_m == 1 and coef_acc == 1 and coef_gpr == 0 and not constante.free_symbols:
            try:
                k = int(constante)
            except (TypeError, ValueError):
                pass
            else:
                ops = ["GPR(AD) -> MAR", "M -> GPR", "GPR+ACC -> ACC"]
                ops += _agregar_constante(k)
                ops += ["ACC -> GPR", "GPR -> M"]
                return _finalizar(ops, modo_n)

        # M <- ca*ACC + K  (sin M en el RHS; p. ej. M <- ACC + 1)
        if (
            coef_m == 0
            and coef_acc != 0
            and coef_gpr == 0
            and F not in expr.free_symbols
            and not constante.free_symbols
            and _es_coeficiente_entero_sympy(coef_acc)
            and _es_coeficiente_entero_sympy(constante)
        ):
            try:
                ca_mk = int(coef_acc)
                k_mk = int(constante)
            except (TypeError, ValueError):
                pass
            else:
                ops = ["GPR(AD) -> MAR"]
                ops += _multiplicar_ACC_sin_memoria_M(ca_mk)
                ops += _agregar_constante(k_mk)
                ops += ["ACC -> GPR", "GPR -> M"]
                return _finalizar(ops, modo_n)

        # M <- M/2 + cf*F + K  (sin ACC en el RHS; ROR lógico, F=0 antes del ROR)
        if coef_acc == 0 and coef_gpr == 0 and coef_m == Rational(1, 2):
            coef_f_h = expr.coeff(F)
            resto_h = expand(expr - Rational(1, 2) * M - coef_f_h * F)
            if (
                not resto_h.free_symbols
                and _es_coeficiente_entero_sympy(coef_f_h)
                and _es_coeficiente_entero_sympy(resto_h)
            ):
                ops = _cuerpo_m_mitad_mas_cf_f_mas_k(int(coef_f_h), int(resto_h))
                return _finalizar(ops, modo_n)

        # M <- N*M - ACC  (clásico de la materia)
        if (
            coef_m != 0
            and coef_acc == -1
            and coef_gpr == 0
            and constante == 0
            and _es_coeficiente_entero_sympy(coef_m)
        ):
            n = int(coef_m)
            ops += _cargar_M_en_GPR()
            # NOT ACC + INC → -ACC
            ops += ["ACC! -> ACC", "ACC+1 -> ACC"]
            # Sumar GPR N veces
            for _ in range(n):
                ops.append("GPR+ACC -> ACC")
            ops += ["ACC -> GPR", "GPR -> M"]
            return _finalizar(ops, modo_n)

        # M <- -N*M
        if (
            coef_m != 0
            and coef_acc == 0
            and coef_gpr == 0
            and constante == 0
            and _es_coeficiente_entero_sympy(coef_m)
        ):
            n = int(coef_m)
            ops += _cargar_M_en_GPR()
            ops += ["0 -> ACC"]
            ops.append("GPR+ACC -> ACC")
            ops += _rol_n(int(abs(n)).bit_length() - 1)
            if n < 0:
                ops += ["ACC! -> ACC", "ACC+1 -> ACC"]
            ops += ["ACC -> GPR", "GPR -> M"]
            return _finalizar(ops, modo_n)

        # M <- N*M + K  (solo si K es entero sin símbolos)
        if coef_m != 0 and coef_acc == 0 and constante != 0:
            if (
                not constante.free_symbols
                and _es_coeficiente_entero_sympy(coef_m)
                and _es_coeficiente_entero_sympy(constante)
            ):
                try:
                    n = int(coef_m)
                    k = int(constante)
                except (TypeError, ValueError):
                    pass
                else:
                    ops += _cargar_M_en_GPR()
                    ops += _multiplicar_GPR(n, ops_acc_zero=True)
                    ops += _agregar_constante(k)
                    ops += ["ACC -> GPR", "GPR -> M"]
                    return _finalizar(ops, modo_n)

        # M <- N*M + K*F  (consigna tipo M <- 6M - 3F directo; F = registro de estado del apunte)
        coef_f_m = expr.coeff(F)
        if (
            coef_m != 0
            and coef_acc == 0
            and coef_gpr == 0
            and F in expr.free_symbols
            and M in expr.free_symbols
        ):
            resto = expand(expr - coef_m * M - coef_f_m * F)
            if resto == 0 and _es_coeficiente_entero_sympy(coef_m) and _es_coeficiente_entero_sympy(coef_f_m):
                try:
                    n = int(coef_m)
                    kf = int(coef_f_m)
                except (TypeError, ValueError):
                    pass
                else:
                    if n == 0:
                        raise ErrorGeneracion(
                            "M <- 0*M + K*F no es un caso útil; revisá la expresión."
                        )
                    ops += _cargar_M_en_GPR()
                    ops += _multiplicar_GPR(n, ops_acc_zero=True)
                    if kf == 0:
                        ops += ["ACC -> GPR", "GPR -> M"]
                        return _finalizar(ops, modo_n)
                    if kf < 0:
                        ops += _acc_restar_f_veces(-kf)
                    else:
                        ops += _acc_sumar_f_veces(kf)
                    ops += ["ACC -> GPR", "GPR -> M"]
                    return _finalizar(ops, modo_n)

        # M <- ca*ACC + cm*M + K  (lineal mixta; solo enteros, sin F ni GPR en el RHS)
        if (
            coef_m != 0
            and coef_acc != 0
            and coef_gpr == 0
            and F not in expr.free_symbols
            and not constante.free_symbols
            and _es_coeficiente_entero_sympy(coef_acc)
            and _es_coeficiente_entero_sympy(coef_m)
            and _es_coeficiente_entero_sympy(constante)
        ):
            try:
                ca_i = int(coef_acc)
                cm_i = int(coef_m)
                k_i = int(constante)
            except (TypeError, ValueError):
                pass
            else:
                ops = _cuerpo_m_lineal_mixto(ca_i, cm_i, k_i)
                return _finalizar(ops, modo_n)

        # M <- ca*ACC + cm*M + cf*F + K  (lineal con F; sin GPR en el RHS)
        coef_f_mxf = expr.coeff(F)
        resto_mxf = expand(expr - coef_acc * ACC - coef_m * M - coef_f_mxf * F - coef_gpr * GPR)
        if (
            coef_gpr == 0
            and F in expr.free_symbols
            and not resto_mxf.free_symbols
            and _es_coeficiente_entero_sympy(coef_acc)
            and _es_coeficiente_entero_sympy(coef_m)
            and _es_coeficiente_entero_sympy(coef_f_mxf)
            and _es_coeficiente_entero_sympy(resto_mxf)
        ):
            try:
                ca_x = int(coef_acc)
                cm_x = int(coef_m)
                cf_x = int(coef_f_mxf)
                k_x = int(resto_mxf)
            except (TypeError, ValueError):
                pass
            else:
                ops = _cuerpo_acc_lineal_general(ca_x, cm_x, cf_x, k_x)
                ops += ["ACC -> GPR", "GPR -> M"]
                return _finalizar(ops, modo_n)

    if destino_str == "M":
        ca = expr.coeff(ACC)
        cm = expr.coeff(M)
        cg = expr.coeff(GPR)
        if ca != 0 and cm != 0 and cg == 0 and F not in expr.free_symbols:
            ex_s = str(expand(expr)).replace("\u2212", "-")
            raise ErrorGeneracion(
                "No hay generación automática para M con ACC y M mezclados: coeficientes no "
                "enteros o constante no numérica.\n\n"
                f"Expresión: M <- {ex_s}\n\n"
                "Soportado: M <- ca*ACC + cm*M + K, M <- ca*ACC + cm*M + cf*F + K, M <- M/2 + cf*F + K."
            )

    raise ErrorGeneracion(
        f"No sé generar microoperaciones para: {destino_str} <- {expr}\n"
        f"Expresiones soportadas:\n"
        f"  ACC <- N*ACC + K\n"
        f"  ACC <- N*M + K\n"
        f"  ACC <- N*M ± K*F  (F registro de estado; ej. ACC <- 3M - F)\n"
        f"  ACC <- ca*ACC + cm*M + cf*F + K  (enteros; ej. ACC <- ACC + 3M - 2F + 1)\n"
        f"  M   <- N*M - ACC\n"
        f"  M   <- -N*M\n"
        f"  M   <- N*M + K\n"
        f"  M   <- N*M ± K*F  |  M <- 6*M - 3*F  |  M <- 4*M + 2*F  (F registro de estado)\n"
        f"  M   <- ACC/4 - F  |  ACC <- ACC/4 - F\n"
        f"  ACC <- ACC/n, M <- ACC/n  (n = 2, 4, 8, …; no ACC/3 ni ACC/5 automático)\n"
        f"  ACC <- ACC - F  |  M <- M + ACC + K\n"
        f"  M   <- ca*ACC + K  |  M <- ACC + 1  (sin término M; ca entero ≠ 0)\n"
        f"  M   <- ca*ACC + cm*M + K  |  M <- ca*ACC + cm*M + cf*F + K  (polinomio lineal con F)\n"
        f"  M   <- M/2 + cf*F + K  (ej. M <- M/2 - 4F - 2)\n"
        f"  Opcional: segundo argumento modo='implicado'|'directo'|'indirecto' (ciclo fetch).\n"
        f"  M   <- 4F - M/2  |  M<-4*F-M/2 (ejercicio tipo Ejemplo apuntes)"
    )


def _cuerpo_m_4f_menos_m_medio_apuntes() -> list:
    """
    Secuencia del ejercicio M <- 4F - M/2 en modo directo (carga M en GPR,
    cuatro ROL para 8F, negaciones y suma con M, negar, un ROR /2, escribir).
    """
    return [
        "GPR(AD) -> MAR",
        "M -> GPR",
        "0 -> ACC",
        "ROL F, ACC",
        "ROL F, ACC",
        "ROL F, ACC",
        "ROL F, ACC",
        "ACC! -> ACC",
        "ACC+1 -> ACC",
        "GPR+ACC -> ACC",
        "ACC! -> ACC",
        "ACC+1 -> ACC",
        "ROR F, ACC",
        "ACC -> GPR",
        "GPR -> M",
    ]


def _acc_en_div4_menos_f() -> list:
    """
    ACC <- ACC/4 - F (12 bits): dos desplazamientos lógicos a la derecha
    (ROR con F=0) y resta de F vía ROL + complemento a 2 + suma con el cociente.
    """
    return [
        "0 -> F",
        "ROR F, ACC",
        "0 -> F",
        "ROR F, ACC",
        "ACC -> GPR",
        "0 -> ACC",
        "ROL F, ACC",
        "ACC! -> ACC",
        "ACC+1 -> ACC",
        "GPR+ACC -> ACC",
    ]


# ── Utilidades de generación ──────────────────────────────────────────

def _cargar_M_en_GPR() -> list:
    """GPR(AD) -> MAR, M -> GPR"""
    return ["GPR(AD) -> MAR", "M -> GPR"]


def _cuerpo_m_mitad_mas_cf_f_mas_k(cf: int, k: int) -> list:
    """M <- M/2 + cf*F + K: carga M, suma en ACC, ROR (/2), luego ±F y constante, escribe M."""
    ops = [
        "GPR(AD) -> MAR",
        "M -> GPR",
        "0 -> ACC",
        "GPR+ACC -> ACC",
        "0 -> F",
        "ROR F, ACC",
    ]
    if cf < 0:
        ops += _acc_restar_f_veces(-cf)
    elif cf > 0:
        ops += _acc_sumar_f_veces(cf)
    ops += _agregar_constante(k)
    ops += ["ACC -> GPR", "GPR -> M"]
    return ops


def _multiplicar_ACC_sin_memoria_M(n: int) -> list:
    """
    ACC <- n * ACC usando solo ACC y GPR (no escribe en la celda M).
    _multiplicar_ACC reutiliza M como temporal para algunos |n| no potencia de 2;
    con destino M <- ... eso corrompería el operando.
    """
    if n == 0:
        return ["0 -> ACC"]
    if n == 1:
        return []
    if n == -1:
        return ["ACC! -> ACC", "ACC+1 -> ACC"]
    ops: list = []
    negativo = n < 0
    n_abs = abs(n)
    ops.append("ACC -> GPR")
    for _ in range(n_abs - 1):
        ops.append("GPR+ACC -> ACC")
    if negativo:
        ops += ["ACC! -> ACC", "ACC+1 -> ACC"]
    return ops


def _acc_restar_gpr_repetido(k: int) -> list:
    """ACC <- ACC - k*GPR con GPR cargado (cada paso resta una vez GPR; k >= 0)."""
    if k < 0:
        raise ValueError(k)
    ops: list = []
    for _ in range(k):
        ops += [
            "ACC! -> ACC",
            "ACC+1 -> ACC",
            "GPR+ACC -> ACC",
            "ACC! -> ACC",
            "ACC+1 -> ACC",
        ]
    return ops


def _cuerpo_m_lineal_mixto(ca: int, cm: int, k: int) -> list:
    """
    Núcleo: M <- ca*ACC + cm*M + K.
    Al entrar, ACC = valor inicial del acumulador del apunte; tras _cargar_M_en_GPR,
    GPR = M inicial.
    """
    if ca == 0 or cm == 0:
        raise ValueError("ca y cm deben ser no nulos para la plantilla lineal mixta")
    ops: list = []
    ops += _multiplicar_ACC_sin_memoria_M(ca)
    ops += _cargar_M_en_GPR()
    if cm > 0:
        for _ in range(cm):
            ops.append("GPR+ACC -> ACC")
    else:
        ops += _acc_restar_gpr_repetido(-cm)
    ops += _agregar_constante(k)
    ops += ["ACC -> GPR", "GPR -> M"]
    return ops


def _cuerpo_acc_lineal_general(ca: int, cm: int, cf: int, k: int) -> list:
    """
    Núcleo: ACC <- ca*ACC + cm*M + cf*F + K.
    cf < 0 resta |cf| veces F (patrón del apunte). Orden: escalar ACC, sumar M, ±F, constante.
    """
    ops: list = []
    ops += _multiplicar_ACC_sin_memoria_M(ca)
    if cm != 0:
        ops += _cargar_M_en_GPR()
        if cm > 0:
            for _ in range(cm):
                ops.append("GPR+ACC -> ACC")
        else:
            ops += _acc_restar_gpr_repetido(-cm)
    if cf != 0:
        if cf < 0:
            ops += _acc_restar_f_veces(-cf)
        else:
            ops += _acc_sumar_f_veces(cf)
    ops += _agregar_constante(k)
    return ops


def _acc_restar_una_f() -> list:
    """Un paso ACC <- ACC - F (mismo patrón que el caso ACC <- ACC - F del generador)."""
    return [
        "ACC -> GPR",
        "0 -> ACC",
        "ROL F, ACC",
        "ACC! -> ACC",
        "ACC+1 -> ACC",
        "GPR+ACC -> ACC",
    ]


def _acc_restar_f_veces(k: int) -> list:
    """Resta k veces el efecto -F del apunte (k entero >= 0)."""
    if k < 0:
        raise ValueError(k)
    ops: list = []
    for _ in range(k):
        ops.extend(_acc_restar_una_f())
    return ops


def _acc_sumar_una_f() -> list:
    """
    ACC <- ACC + F (F en {0,1}): guardar ACC, 0, ROL F,ACC carga F en ACC bajo, sumar con GPR.
    """
    return [
        "ACC -> GPR",
        "0 -> ACC",
        "ROL F, ACC",
        "GPR+ACC -> ACC",
    ]


def _acc_sumar_f_veces(k: int) -> list:
    """Suma k veces F al acumulador (k entero >= 0)."""
    if k < 0:
        raise ValueError(k)
    ops: list = []
    for _ in range(k):
        ops.extend(_acc_sumar_una_f())
    return ops


def _rol_n(n: int) -> list:
    """Genera N pares ZERO_F + ROL para multiplicar por 2^N."""
    ops = []
    for _ in range(n):
        ops += ["0 -> F", "ROL F, ACC"]
    return ops


def _multiplicar_ACC(n: int) -> list:
    """
    Genera microops para ACC <- n * ACC.
    Usa duplicaciones sucesivas (ACC -> GPR, GPR+ACC -> ACC).
    """
    if n == 0:
        return ["0 -> ACC"]
    if n == 1:
        return []
    if n == -1:
        return ["ACC! -> ACC", "ACC+1 -> ACC"]

    ops = []
    negativo = n < 0
    n = abs(n)

    # Factorizamos n como producto de potencias de 2 y sumas
    # Estrategia: duplicar ACC hasta llegar a n
    # Ejemplo: n=8 → x2, x2, x2  (3 duplicaciones)
    # Ejemplo: n=6 → x2 (ACC=2A), guardar, x2 (ACC=4A), sumar GPR → 6A
    # Usamos la representación binaria para la cadena de adiciones (método shift-and-add)
    bits = bin(n)[2:]  # ej: 8 -> '1000', 6 -> '110'

    # Empezamos con resultado = ACC (1 vez)
    # Por cada bit siguiente: duplicar; si es 1, sumar ACC original
    # Para esto necesitamos guardar ACC original en M
    if _es_potencia_de_2(n):
        # Caso simple: solo ROL
        k = n.bit_length() - 1
        ops += _rol_n(k)
    else:
        # Método shift-and-add usando M como temporal
        ops.append("GPR -> M")       # guardar ACC original en M (via GPR=ACC previo)
        ops.append("ACC -> GPR")
        ops.append("GPR+ACC -> ACC") # ACC = 2*ACC

        acum_bits = 2
        for bit in bits[2:]:  # saltamos el primer '1' ya procesado
            # Duplicar
            ops.append("ACC -> GPR")
            ops.append("GPR+ACC -> ACC")
            acum_bits *= 2
            if bit == '1':
                # Recuperar ACC original de M y sumar
                ops.append("M -> GPR")
                ops.append("GPR+ACC -> ACC")
                acum_bits += 1  # aproximado, no exacto para todos los casos

    if negativo:
        ops += ["ACC! -> ACC", "ACC+1 -> ACC"]

    return ops


def _multiplicar_GPR(n: int, ops_acc_zero: bool = False) -> list:
    """Genera ops para ACC <- n * GPR (GPR ya tiene el valor de M)."""
    ops = []
    if ops_acc_zero:
        ops.append("0 -> ACC")

    negativo = n < 0
    n = abs(n)

    for _ in range(n):
        ops.append("GPR+ACC -> ACC")

    if negativo:
        ops += ["ACC! -> ACC", "ACC+1 -> ACC"]

    return ops


def _agregar_constante(k: int) -> list:
    """Genera ops para ACC <- ACC + k usando INC_ACC repetido."""
    if k == 0:
        return []
    ops = []
    if k > 0:
        for _ in range(k):
            ops.append("ACC+1 -> ACC")
    else:
        # Restar: negamos ACC, sumamos |k|, negamos de nuevo
        ops += ["ACC! -> ACC", "ACC+1 -> ACC"]
        for _ in range(abs(k)):
            ops.append("ACC+1 -> ACC")
        ops += ["ACC! -> ACC", "ACC+1 -> ACC"]
    return ops


def _es_potencia_de_2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0
