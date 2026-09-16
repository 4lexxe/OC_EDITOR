"""Casos reproducibles basados en el material de la cátedra, sin plantillas de resultados."""

FETCH = "PC -> MAR\nM -> GPR, PC+1 -> PC\nGPR(OP) -> OPR\n"

EJEMPLOS_TRAZA = [
    {
        "id": "practica-directo",
        "titulo": "Clase práctica · M ← M − ACC + F",
        "fuente": "OC26. Clase Práctica TP5_Arquitectura.pdf · páginas 15–16",
        "descripcion": "Modo directo. PC=$20, M[$20]=$983, M[$83]=$012, ACC=$007, F=1. Resultado: M[$83]=$00C en 14 ciclos.",
        "registros": {"PC": 0x20, "ACC": 0x007, "GPR": 0, "F": 1, "M": 0},
        "memoria": {0x20: 0x983, 0x83: 0x012},
        "codigo": FETCH + """GPR(AD) -> MAR
M -> GPR
ACC! -> ACC
ACC+1 -> ACC
GPR+ACC -> ACC
ACC -> GPR
0 -> ACC
ROL F, ACC
GPR+ACC -> ACC
ACC -> GPR
GPR -> M""",
    },
    {
        "id": "tp5-indirecto",
        "titulo": "TP5 · Ejercicio 8 · Indirecto",
        "fuente": "OC26_2C. TP5 - Arquitectura de Computadoras.pdf · página 4, ejercicio 8",
        "descripcion": "PC=$10, M[$10]=$43B, M[$3B]=$C48, M[$48]=$007, ACC=$143, F=1. Seguí los dos accesos hasta el operando; el resultado calculado es M[$48]=$024.",
        "registros": {"PC": 0x10, "ACC": 0x143, "GPR": 0, "F": 1, "M": 0},
        "memoria": {0x10: 0x43B, 0x3B: 0xC48, 0x48: 0x007},
        "codigo": FETCH + """GPR(AD) -> MAR
M -> GPR
GPR(AD) -> MAR
M -> GPR
0 -> ACC
ROL F, ACC
ROL F, ACC
GPR+ACC -> ACC
0 -> F
ROL F, ACC
0 -> F
ROL F, ACC
ACC -> GPR
GPR -> M""",
    },
    {
        "id": "tp5-directo",
        "titulo": "TP5 · Ejercicio 9 · M ← M + 2ACC − 3F",
        "fuente": "TP5, página 4, ejercicio 9; resolución del Repaso, página 8",
        "descripcion": "PC=$8F, M[$8F]=$237, M[$37]=$042, ACC=$013, F=1. La secuencia del repaso calcula M[$37]=$065 y permite seguir las dos escrituras intermedias.",
        "registros": {"PC": 0x8F, "ACC": 0x013, "GPR": 0, "F": 1, "M": 0},
        "memoria": {0x8F: 0x237, 0x37: 0x042},
        "codigo": FETCH + """GPR(AD) -> MAR
ACC -> GPR
GPR+ACC -> ACC
M -> GPR
GPR+ACC -> ACC
ACC -> GPR
GPR -> M
0 -> ACC
ROL F, ACC
ACC -> GPR
GPR+ACC -> ACC
GPR+ACC -> ACC
ACC! -> ACC
ACC+1 -> ACC
M -> GPR
GPR+ACC -> ACC
ACC -> GPR
GPR -> M""",
    },
]
