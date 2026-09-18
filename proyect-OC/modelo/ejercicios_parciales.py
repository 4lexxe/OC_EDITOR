"""Ejercicios de las imágenes aportadas y variantes identificadas como tales."""

# Desplazamiento aritmético usando exclusivamente microoperaciones de Taub.
# ROL extrae el signo; GPR guarda la palabra y SUM la restaura sin cambiar F.
_MITAD = ["ACC -> GPR", "ROL F, ACC", "0 -> ACC", "GPR+ACC -> ACC", "ROR F, ACC"]
_MENOS_UNO = ["ACC! -> ACC", "ACC+1 -> ACC", "ACC! -> ACC"]


def _solucion(multiplicador, coef_f_numerador, divisiones, constante):
    ops = []
    if multiplicador > 1:
        ops = ["ACC -> GPR"] + ["GPR+ACC -> ACC"] * (multiplicador - 1)
    ops += ["ACC -> GPR", "0 -> ACC", "ROL F, ACC"]
    for _ in range(abs(coef_f_numerador).bit_length() - 1):
        ops += ["0 -> F", "ROL F, ACC"]
    if coef_f_numerador < 0:
        ops += ["ACC! -> ACC", "ACC+1 -> ACC"]
    ops += ["GPR+ACC -> ACC"]
    ops += _MITAD * divisiones
    ops += ["ACC+1 -> ACC"] * max(0, constante)
    ops += _MENOS_UNO * max(0, -constante)
    return "\n".join(ops)


def ejercicios_parciales():
    especificaciones = [
        ("p1-5acc-mitad-f", "5ACC/2 + F_inicial − 1", 5, 2, 1, -1,
         "Parcial aportado por el usuario · imagen 1"),
        ("p2-5acc-8f", "5ACC − 8F_inicial − 1", 5, -8, 0, -1,
         "Parcial aportado por el usuario · imagen 2"),
        ("p3-cuarto-2f", "ACC/4 − 2F_inicial + 1", 1, -8, 2, 1,
         "Parcial aportado por el usuario · imagen 3"),
        ("p4-mitad-4f", "ACC/2 + 4F_inicial − 1", 1, 8, 1, -1,
         "Parcial aportado por el usuario · imagen 4"),
        ("p5-catedra-5acc-mitad-4f", "5ACC/2 − 4F_inicial", 5, -8, 1, 0,
         "OC26_2C. TP5 · Arquitectura de Computadoras, página 2, ejercicio h"),
        ("p6-variante-3acc-cuarto-2f", "3ACC/4 − 2F_inicial + 1", 3, -8, 2, 1,
         "Variante propuesta para practicar, basada en TP5 y en los parciales aportados"),
    ]
    ejercicios = []
    for ident, formula, mult, coef_f, divs, const, fuente in especificaciones:
        casos = []
        for acc in (0, 1, 2, 3, 4, 7, 8, 15, 31, 127, 255, 399, 400):
            for f in (0, 1):
                resultado = (mult * acc + coef_f * f) // (2 ** divs) + const
                casos.append({
                    "nombre": f"ACC inicial = {acc}, F inicial = {f} → resultado {resultado}",
                    "registros": {"PC": 0x20, "ACC": acc, "F": f, "GPR": 0xA57, "M": 0x319},
                    "memoria": {}, "esperado_registros": {"ACC": resultado},
                })
        ejercicios.append({
            "id": ident, "titulo": f"Parcial · ACC ← {formula}",
            "formula_display": f"ACC ← {formula} (implicado)",
            "dificultad": "tryhard" if divs else "avanzado",
            "dificultad_label": "Desafío de parcial" if divs else "Avanzado",
            "modo": "implicado", "modo_label": "Modo implicado",
            "categoria": "Parciales · conservación de F", "fuente": fuente,
            "enunciado": "Escribí las microoperaciones que producen la fórmula a partir de ACC y F iniciales. "
                         "Identificá dónde guardás F antes de que una rotación lo reemplace. "
                         "Verificá también los casos en que el resultado es negativo.",
            "condiciones": [
                "F_inicial es el F al comenzar, nunca el bit que sale después de un ROR o ROL.",
                "Para esta práctica: 0 ≤ ACC inicial ≤ 400; F inicial puede ser 0 o 1.",
                "Las fracciones se evalúan sobre el numerador completo y redondean hacia abajo; 5ACC/2 significa (5×ACC)/2.",
                "Palabras de 12 bits. Los negativos se representan en complemento a 2.",
                "Solo ciclo de ejecución: sin búsqueda ni accesos a RAM. GPR es auxiliar y F final puede cambiar.",
                "La solución debe funcionar sin suponer un valor inicial de GPR o M.",
            ],
            "sin_memoria": True, "incluir_fetch": False,
            "estado_inicial_sugerido": {"PC": 0x20, "ACC": 7, "F": 1, "GPR": 0xA57, "M": 0x319, "memoria": {}},
            "solucion_referencia": _solucion(mult, coef_f, divs, const),
            "explicacion_solucion": (
                f"1. Formar {mult}ACC y guardarlo en GPR. SUM no modifica F.\n"
                f"2. Con 0 → ACC y ROL, copiar F_inicial al bit 1 de ACC. F pasa a 0, pero el original queda en ACC.\n"
                f"3. Construir {coef_f}F_inicial y sumar GPR: el numerador queda en ACC.\n"
                f"4. Dividir {divs} veces por 2. Guardar ACC en GPR, usar ROL para extraer el signo, "
                "restaurar ACC con 0 → ACC y SUM y hacer ROR. Así también funcionan los numeradores negativos.\n"
                f"5. Aplicar el término constante {const}. Para restar 1: NOT, INC, NOT.\n"
                "El dominio propuesto mantiene el numerador entre −2048 y 2047 antes de dividir."
            ),
            "pistas": [
                "Guardá el término con ACC en GPR; luego 0 → ACC y ROL permiten capturar F_inicial.",
                f"Reuní la expresión como ({mult}ACC + ({coef_f})F_inicial)/{2 ** divs} + ({const}).",
                "Si el numerador es negativo, 0 → F antes de ROR no conserva el signo. Extraé su bit 12 con ROL, guardando y restaurando ACC.",
            ],
            "casos_prueba": casos,
        })
    return ejercicios
