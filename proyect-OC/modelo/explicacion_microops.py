"""
Texto breve en español: qué hace cada microoperación reconocida por el analizador.
"""
from __future__ import annotations

# Claves = nombres internos emitidos por AnalizadorSintactico (tupla [0])
EXPLICACION_MICROOP: dict[str, str] = {
    "ACC_TO_GPR": "Copia el valor de ACC a GPR.",
    "GPR_TO_ACC": "Copia el valor de GPR a ACC.",
    "GPR_TO_M": "Escribe GPR en la palabra de RAM seleccionada por MAR; M muestra el dato escrito.",
    "M_TO_GPR": "Lee el registro M y copia el valor a GPR.",
    "SUM_ACC_GPR": "Suma ACC + GPR en 12 bits; el resultado queda en ACC y F conserva su valor.",
    "INC_ACC": "Suma 1 a ACC (incremento).",
    "INC_GPR": "Suma 1 a GPR.",
    "INC_PC": "Suma 1 al contador de programa PC (siguiente palabra de instrucción).",
    "NOT_ACC": "Complemento a 1 de ACC (12 bits); resultado en ACC.",
    "NOT_F": "Invierte el bit de rotación F (0↔1).",
    "ZERO_ACC": "Pone ACC en cero.",
    "ZERO_F": "Pone F en cero.",
    "ROL_F_ACC": "Rota ACC un bit a la izquierda; F entra como bit menos significativo.",
    "ROR_F_ACC": "Rota ACC un bit a la derecha; F entra como bit más significativo.",
    "GPR_AD_TO_MAR": "Carga en MAR la dirección tomada del campo AD de GPR (acceso a memoria).",
    "GPR_OP_TO_OPR": "Copia a OPR el código de operación de 4 bits tomado de GPR(OP).",
    "PC_TO_MAR": "Copia PC a MAR (típico de la fase de búsqueda/fetch de instrucción).",
}


def texto_explicacion_codigo(texto_editor: str) -> str:
    """
    Recorre las líneas del editor en orden y devuelve un texto corto:
    por cada línea válida, la instrucción tal cual y una frase de efecto.
    """
    from compilador.AnalizadorSintactico import parsear_ciclo, preprocesar_linea_microop

    lineas = texto_editor.split("\n")
    partes: list[str] = []
    hay_algo = False

    for num, linea_raw in enumerate(lineas, start=1):
        linea = preprocesar_linea_microop(linea_raw)
        if not linea:
            continue
        hay_algo = True
        try:
            parsed = parsear_ciclo(linea)
        except Exception:
            parsed = None
        if not parsed:
            partes.append(f"Línea {num}: {linea}\n   → No se reconoce la sintaxis en esta línea.\n")
            continue

        explics: list[str] = []
        for op in parsed:
            explics.append(EXPLICACION_MICROOP.get(op, f"Efecto interno ({op})."))

        if not explics:
            partes.append(f"Línea {num}: {linea}\n   → (sin operación reconocida)\n")
        else:
            union = " ".join(explics) if len(explics) == 1 else "En el mismo ciclo, con los valores de entrada: " + " · ".join(explics)
            partes.append(f"Línea {num}: {linea}\n   → {union}\n")

    if not hay_algo:
        return "Escribí microoperaciones en el editor para ver qué hace cada línea."

    return "\n".join(partes).rstrip() + "\n"
