"""Banco de ejercicios y desafíos de microprogramación para la arquitectura Von Neumann básica.
Incluye niveles progresivos desde operaciones elementales hasta problemas de parcial TRYHARD.
"""

from __future__ import annotations
from typing import TypedDict, List, Dict, Any, Optional

FETCH_CODE = """PC -> MAR
M -> GPR, PC+1 -> PC
GPR(OP) -> OPR"""

class CasoPrueba(TypedDict, total=False):
    nombre: str
    registros: Dict[str, int]
    memoria: Dict[int, int]
    esperado_registros: Optional[Dict[str, int]]
    esperado_memoria: Optional[Dict[int, int]]

class Ejercicio(TypedDict, total=False):
    id: str
    titulo: str
    dificultad: str  # "basico", "intermedio", "avanzado", "tryhard"
    dificultad_label: str
    modo: str        # "implicado", "directo", "indirecto"
    modo_label: str
    categoria: str
    formula_display: str
    enunciado: str
    condiciones: List[str]
    fuente: str
    estado_inicial_sugerido: Dict[str, Any]
    incluir_fetch: bool
    solucion_referencia: str
    explicacion_solucion: str
    pistas: List[str]
    casos_prueba: List[CasoPrueba]


EJERCICIOS: List[Ejercicio] = [
    # =========================================================================
    # NIVEL 1: BÁSICO / IMPLICADO (Fundamentos de registros y ALU)
    # =========================================================================
    {
        "id": "e1-complemento-a-dos",
        "titulo": "Inversión de signo: ACC <- -ACC",
        "dificultad": "basico",
        "dificultad_label": "Básico",
        "modo": "implicado",
        "modo_label": "Modo Implicado",
        "categoria": "Aritmética básica",
        "formula_display": "ACC <- -ACC",
        "enunciado": "Calculá el complemento a 2 del acumulador para cambiar su signo aritmético.",
        "condiciones": [
            "Utilizar únicamente microoperaciones de la arquitectura.",
            "Recordar que -ACC = NOT(ACC) + 1.",
            "Modo implicado (sin accesos a operandos en memoria)."
        ],
        "fuente": "Teoría Taub Cap. 9 · Aritmética en Complemento a 2",
        "estado_inicial_sugerido": {
            "PC": 0x10,
            "ACC": 0x005,
            "F": 0,
            "GPR": 0,
            "M": 0,
            "memoria": {}
        },
        "incluir_fetch": False,
        "solucion_referencia": """ACC! -> ACC
ACC+1 -> ACC""",
        "explicacion_solucion": "1. `ACC! -> ACC` invierte bit a bit el acumulador (complemento a 1).\n2. `ACC+1 -> ACC` suma 1 obteniendo el complemento a 2 (valor negativo).",
        "pistas": [
            "Para negar un número en complemento a 2 se aplica NOT y luego se suma 1.",
            "Usá `ACC! -> ACC` seguido de `ACC+1 -> ACC`."
        ],
        "casos_prueba": [
            {
                "nombre": "ACC = 5 (positivo)",
                "registros": {"PC": 0x10, "ACC": 5, "F": 0, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": (-5) & 0xFFF}
            },
            {
                "nombre": "ACC = -8 (negativo)",
                "registros": {"PC": 0x10, "ACC": (-8) & 0xFFF, "F": 0, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 8}
            },
            {
                "nombre": "ACC = 0",
                "registros": {"PC": 0x10, "ACC": 0, "F": 0, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 0}
            }
        ]
    },
    {
        "id": "e2-multiplicacion-por-dos",
        "titulo": "Multiplicación: ACC <- 2 * ACC",
        "dificultad": "basico",
        "dificultad_label": "Básico",
        "modo": "implicado",
        "modo_label": "Modo Implicado",
        "categoria": "Aritmética básica",
        "formula_display": "ACC <- 2 * ACC",
        "enunciado": "Multiplicá el contenido del acumulador por 2 sin perder su valor en registros auxiliares.",
        "condiciones": [
            "Utilizar GPR como registro intermedio para realizar la suma.",
            "ACC final debe ser el doble del valor inicial."
        ],
        "fuente": "TP5 - Arquitectura de Computadoras",
        "estado_inicial_sugerido": {
            "PC": 0x10,
            "ACC": 0x00A,
            "F": 0,
            "GPR": 0,
            "M": 0,
            "memoria": {}
        },
        "incluir_fetch": False,
        "solucion_referencia": """ACC -> GPR
GPR+ACC -> ACC""",
        "explicacion_solucion": "1. `ACC -> GPR` copia el valor a GPR.\n2. `GPR+ACC -> ACC` suma ACC consigo mismo (ACC + ACC = 2*ACC).",
        "pistas": [
            "Multiplicar por 2 es equivalente a sumar el número consigo mismo.",
            "Copiá ACC a GPR y luego sumá GPR con ACC."
        ],
        "casos_prueba": [
            {
                "nombre": "ACC = 10",
                "registros": {"PC": 0x10, "ACC": 10, "F": 0, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 20}
            },
            {
                "nombre": "ACC = 35",
                "registros": {"PC": 0x10, "ACC": 35, "F": 0, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 70}
            }
        ]
    },
    {
        "id": "e3-resta-flag-f",
        "titulo": "Resta de Flag: ACC <- ACC - F",
        "dificultad": "basico",
        "dificultad_label": "Básico",
        "modo": "implicado",
        "modo_label": "Modo Implicado",
        "categoria": "Operaciones con F",
        "formula_display": "ACC <- ACC - F",
        "enunciado": "Restá el valor del bit de flag F al acumulador utilizando el complemento de F.",
        "condiciones": [
            "Si F=1, el resultado debe ser ACC - 1.",
            "Si F=0, el resultado debe ser ACC.",
            "Recordar que en aritmética C2: ACC - F = ACC + NOT(F)."
        ],
        "fuente": "OC26. Clase Práctica TP5 · Operaciones con F",
        "estado_inicial_sugerido": {
            "PC": 0x10,
            "ACC": 0x00E,
            "F": 1,
            "GPR": 0,
            "M": 0,
            "memoria": {}
        },
        "incluir_fetch": False,
        "solucion_referencia": """ACC -> GPR
0 -> ACC
ROL F, ACC
ACC! -> ACC
ACC+1 -> ACC
GPR+ACC -> ACC""",
        "explicacion_solucion": "1. Guarda ACC en GPR.\n2. Limpia ACC y rota F dentro de ACC.\n3. Aplica complemento a 2 para obtener -F.\n4. Suma GPR + (-F) en ACC.",
        "pistas": [
            "Guardá ACC en GPR primero con `ACC -> GPR`.",
            "Podés rotar F dentro de un ACC limpio, negarlo y sumárselo a GPR."
        ],
        "casos_prueba": [
            {
                "nombre": "ACC = 14, F = 1 (resultado 13)",
                "registros": {"PC": 0x10, "ACC": 14, "F": 1, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 13}
            },
            {
                "nombre": "ACC = 20, F = 0 (resultado 20)",
                "registros": {"PC": 0x10, "ACC": 20, "F": 0, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 20}
            }
        ]
    },
    {
        "id": "e4-division-por-dos",
        "titulo": "División entera: ACC <- ACC / 2",
        "dificultad": "basico",
        "dificultad_label": "Básico",
        "modo": "implicado",
        "modo_label": "Modo Implicado",
        "categoria": "Desplazamientos y rotaciones",
        "formula_display": "ACC <- [ACC / 2]",
        "enunciado": "Dividí el valor positivo de ACC por 2 mediante desplazamiento a la derecha (limpiando el bit de acarreo F).",
        "condiciones": [
            "Limpiar F antes de la rotación para no introducir bits residuales en MSB.",
            "Utilizar `ROR F, ACC`."
        ],
        "fuente": "Taub Cap. 9 · Rotaciones y Divisiones Binarias",
        "estado_inicial_sugerido": {
            "PC": 0x10,
            "ACC": 0x018,
            "F": 1,
            "GPR": 0,
            "M": 0,
            "memoria": {}
        },
        "incluir_fetch": False,
        "solucion_referencia": """0 -> F
ROR F, ACC""",
        "explicacion_solucion": "1. `0 -> F` pone el bit de acarreo en cero.\n2. `ROR F, ACC` desplaza todos los bits de ACC una posición a la derecha, insertando el 0 de F en la posición más significativa.",
        "pistas": [
            "Un desplazamiento a la derecha de 1 bit equivale a dividir por 2.",
            "No olvides limpiar el flag F con `0 -> F` antes de rotar."
        ],
        "casos_prueba": [
            {
                "nombre": "ACC = 24 (0x18) -> 12 (0x0C)",
                "registros": {"PC": 0x10, "ACC": 24, "F": 1, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 12}
            },
            {
                "nombre": "ACC = 50 (0x32) -> 25 (0x19)",
                "registros": {"PC": 0x10, "ACC": 50, "F": 0, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 25}
            }
        ]
    },

    # =========================================================================
    # NIVEL 2: INTERMEDIO / DIRECTO (Accesos a memoria RAM)
    # =========================================================================
    {
        "id": "e5-suma-directa-memoria",
        "titulo": "Suma en memoria: M <- M + ACC",
        "dificultad": "intermedio",
        "dificultad_label": "Intermedio",
        "modo": "directo",
        "modo_label": "Modo Directo",
        "categoria": "Acceso a memoria directo",
        "formula_display": "M <- M + ACC",
        "enunciado": "En modo directo, leé el operando de memoria apuntado por el campo de dirección de la instrucción, sumale el acumulador y guardá el resultado en la misma posición de memoria.",
        "condiciones": [
            "Direccionamiento directo: el campo AD de la instrucción contiene la dirección de memoria.",
            "Guardar el resultado en M (RAM[MAR])."
        ],
        "fuente": "OC26. Clase Práctica TP5 · Ejercicios de Memoria",
        "estado_inicial_sugerido": {
            "PC": 0x20,
            "ACC": 0x005,
            "F": 0,
            "GPR": 0x183,  # Instrucción con AD=0x83
            "M": 0,
            "memoria": {0x83: 0x010}
        },
        "incluir_fetch": False,
        "solucion_referencia": """GPR(AD) -> MAR
M -> GPR
GPR+ACC -> ACC
ACC -> GPR
GPR -> M""",
        "explicacion_solucion": "1. `GPR(AD) -> MAR` direcciona la posición del operando.\n2. `M -> GPR` lee el dato de memoria.\n3. `GPR+ACC -> ACC` realiza la suma.\n4. `ACC -> GPR` y `GPR -> M` escriben el resultado en memoria.",
        "pistas": [
            "Primero cargá MAR con la dirección del operando `GPR(AD) -> MAR`.",
            "Leé el dato a GPR con `M -> GPR`.",
            "Sumá en ACC, pasá a GPR y escribí con `GPR -> M`."
        ],
        "casos_prueba": [
            {
                "nombre": "M[0x83] = 16, ACC = 5 -> M[0x83] = 21",
                "registros": {"PC": 0x20, "ACC": 5, "F": 0, "GPR": 0x183, "M": 0},
                "memoria": {0x83: 16},
                "esperado_memoria": {0x83: 21}
            },
            {
                "nombre": "M[0x83] = 100, ACC = 45 -> M[0x83] = 145",
                "registros": {"PC": 0x20, "ACC": 45, "F": 0, "GPR": 0x183, "M": 0},
                "memoria": {0x83: 100},
                "esperado_memoria": {0x83: 145}
            }
        ]
    },
    {
        "id": "e6-resta-directa-memoria",
        "titulo": "Resta en memoria: M <- M - ACC",
        "dificultad": "intermedio",
        "dificultad_label": "Intermedio",
        "modo": "directo",
        "modo_label": "Modo Directo",
        "categoria": "Acceso a memoria directo",
        "formula_display": "M <- M - ACC",
        "enunciado": "Restá el contenido del acumulador al valor almacenado en la memoria en modo directo: M[AD] <- M[AD] - ACC.",
        "condiciones": [
            "Recordar que M - ACC = M + (-ACC).",
            "Negar ACC en C2 antes o después de leer M.",
            "Escribir el resultado final en memoria."
        ],
        "fuente": "OC26_2C. TP5 - Arquitectura de Computadoras",
        "estado_inicial_sugerido": {
            "PC": 0x30,
            "ACC": 0x008,
            "F": 0,
            "GPR": 0x240,  # AD=0x40
            "M": 0,
            "memoria": {0x40: 0x020}
        },
        "incluir_fetch": False,
        "solucion_referencia": """GPR(AD) -> MAR
ACC! -> ACC
ACC+1 -> ACC
M -> GPR
GPR+ACC -> ACC
ACC -> GPR
GPR -> M""",
        "explicacion_solucion": "1. `GPR(AD) -> MAR` carga la dirección.\n2. `ACC!` y `ACC+1` calculan -ACC.\n3. `M -> GPR` lee M.\n4. `GPR+ACC -> ACC` efectúa M + (-ACC).\n5. `ACC -> GPR` y `GPR -> M` guardan el resultado.",
        "pistas": [
            "Para restar ACC a M, calculá el complemento a 2 de ACC (`ACC!` y `ACC+1`).",
            "Luego sumale el dato leído de memoria `GPR+ACC -> ACC`."
        ],
        "casos_prueba": [
            {
                "nombre": "M[0x40] = 32, ACC = 8 -> M[0x40] = 24",
                "registros": {"PC": 0x30, "ACC": 8, "F": 0, "GPR": 0x240, "M": 0},
                "memoria": {0x40: 32},
                "esperado_memoria": {0x40: 24}
            },
            {
                "nombre": "M[0x40] = 50, ACC = 15 -> M[0x40] = 35",
                "registros": {"PC": 0x30, "ACC": 15, "F": 0, "GPR": 0x240, "M": 0},
                "memoria": {0x40: 50},
                "esperado_memoria": {0x40: 35}
            }
        ]
    },
    {
        "id": "e7-tp5-ej9-directo",
        "titulo": "Fórmula compuesta: M <- M + 2ACC - 3F",
        "dificultad": "intermedio",
        "dificultad_label": "Intermedio",
        "modo": "directo",
        "modo_label": "Modo Directo",
        "categoria": "Parciales y TP5",
        "formula_display": "M <- M + 2ACC - 3F",
        "enunciado": "Implementá la microprogramación completa de la operación clásica del TP5: sumar dos veces el acumulador a memoria y restar tres veces el flag F.",
        "condiciones": [
            "Modo directo.",
            "El resultado debe quedar escrito en la posición M[AD].",
            "Manejar correctamente el cálculo de -3F o restas sucesivas."
        ],
        "fuente": "TP5 Ejercicio 9 · Repaso 1er Parcial pág. 8",
        "estado_inicial_sugerido": {
            "PC": 0x8F,
            "ACC": 0x013,
            "F": 1,
            "GPR": 0x237,  # AD=0x37
            "M": 0,
            "memoria": {0x37: 0x042}
        },
        "incluir_fetch": False,
        "solucion_referencia": """GPR(AD) -> MAR
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
        "explicacion_solucion": "1. Multiplica ACC por 2 y le suma M, guardando temporalmente M+2ACC en memoria.\n2. Rota F a ACC y calcula 3F con GPR.\n3. Niega en C2 (-3F) y le suma el M intermedio, grabando el resultado final.",
        "pistas": [
            "Primero podés calcular M + 2ACC y grabarlo en memoria como paso intermedio.",
            "Luego obtené F en ACC, sumalo 3 veces, aplicale complemento a 2 y sumáselo a la memoria."
        ],
        "casos_prueba": [
            {
                "nombre": "M[0x37] = 0x42 (66), ACC = 0x13 (19), F = 1 -> M[0x37] = 0x65 (101)",
                "registros": {"PC": 0x8F, "ACC": 0x13, "F": 1, "GPR": 0x237, "M": 0},
                "memoria": {0x37: 0x42},
                "esperado_memoria": {0x37: 0x65}
            },
            {
                "nombre": "M[0x37] = 50, ACC = 10, F = 0 -> M[0x37] = 70",
                "registros": {"PC": 0x8F, "ACC": 10, "F": 0, "GPR": 0x237, "M": 0},
                "memoria": {0x37: 50},
                "esperado_memoria": {0x37: 70}
            }
        ]
    },

    # =========================================================================
    # NIVEL 3: AVANZADO / INDIRECTO (Punteros y doble acceso a memoria)
    # =========================================================================
    {
        "id": "e8-suma-indirecta",
        "titulo": "Suma indirecta: M <- M + ACC",
        "dificultad": "avanzado",
        "dificultad_label": "Avanzado",
        "modo": "indirecto",
        "modo_label": "Modo Indirecto",
        "categoria": "Direccionamiento Indirecto",
        "formula_display": "M <- M + ACC  (Indirecto)",
        "enunciado": "En direccionamiento indirecto, el campo AD de la instrucción contiene la dirección del puntero. Debes acceder al puntero, luego a la dirección efectiva final, sumar ACC y escribir el resultado en la celda efectiva.",
        "condiciones": [
            "Realizar el doble direccionamiento: `GPR(AD) -> MAR; M -> GPR; GPR(AD) -> MAR`.",
            "Sumar ACC y escribir el resultado en la memoria apuntada."
        ],
        "fuente": "Variante propuesta del direccionamiento indirecto de TP5, ejercicio 8",
        "estado_inicial_sugerido": {
            "PC": 0x10,
            "ACC": 0x009,
            "F": 0,
            "GPR": 0x43B,  # AD=0x3B (puntero a 0x48)
            "M": 0,
            "memoria": {0x3B: 0x048, 0x48: 0x020}
        },
        "incluir_fetch": False,
        "solucion_referencia": """GPR(AD) -> MAR
M -> GPR
GPR(AD) -> MAR
M -> GPR
GPR+ACC -> ACC
ACC -> GPR
GPR -> M""",
        "explicacion_solucion": "1. `GPR(AD) -> MAR` direcciona la tabla de punteros (0x3B).\n2. `M -> GPR` lee la dirección efectiva (0x48).\n3. `GPR(AD) -> MAR` direcciona el dato final en 0x48.\n4. `M -> GPR` lee el dato (0x20).\n5. `GPR+ACC -> ACC` suma (0x20 + 0x09 = 0x29).\n6. `ACC -> GPR` y `GPR -> M` escriben en 0x48.",
        "pistas": [
            "El modo indirecto requiere dos lecturas a MAR antes del dato: primero la dirección del puntero y luego el puntero a MAR.",
            "Recordá la secuencia clásica: `GPR(AD) -> MAR; M -> GPR; GPR(AD) -> MAR`."
        ],
        "casos_prueba": [
            {
                "nombre": "M[0x3B]=0x48, M[0x48]=32, ACC=9 -> M[0x48]=41",
                "registros": {"PC": 0x10, "ACC": 9, "F": 0, "GPR": 0x43B, "M": 0},
                "memoria": {0x3B: 0x048, 0x48: 32},
                "esperado_memoria": {0x48: 41}
            },
            {
                "nombre": "M[0x3B]=0x50, M[0x50]=100, ACC=50 -> M[0x50]=150",
                "registros": {"PC": 0x10, "ACC": 50, "F": 0, "GPR": 0x43B, "M": 0},
                "memoria": {0x3B: 0x050, 0x50: 100},
                "esperado_memoria": {0x50: 150}
            }
        ]
    },
    {
        "id": "e9-resta-y-acumulacion-indirecta",
        "titulo": "Acumulador: ACC <- 3M - 2ACC",
        "dificultad": "avanzado",
        "dificultad_label": "Avanzado",
        "modo": "indirecto",
        "modo_label": "Modo Indirecto",
        "categoria": "Direccionamiento Indirecto",
        "formula_display": "ACC <- 3M - 2ACC  (Indirecto)",
        "enunciado": "Calculá el triple del dato en memoria menos el doble del acumulador inicial en modo indirecto. El resultado final debe quedar en ACC.",
        "condiciones": [
            "Modo indirecto (resolver el puntero).",
            "Preservar el dato en memoria (no sobreescribir M).",
            "Resultado en ACC."
        ],
        "fuente": "Parciales OC Help · Ejercicios de Microprogramación",
        "estado_inicial_sugerido": {
            "PC": 0x15,
            "ACC": 0x004,
            "F": 0,
            "GPR": 0x420,  # AD=0x20 -> puntero a 0x60
            "M": 0,
            "memoria": {0x20: 0x060, 0x60: 0x00A}
        },
        "incluir_fetch": False,
        "solucion_referencia": """GPR(AD) -> MAR
M -> GPR
GPR(AD) -> MAR
ACC -> GPR
GPR+ACC -> ACC
ACC! -> ACC
ACC+1 -> ACC
M -> GPR
GPR+ACC -> ACC
GPR+ACC -> ACC
GPR+ACC -> ACC""",
        "explicacion_solucion": "1. Resuelve el direccionamiento indirecto (`GPR(AD)->MAR; M->GPR; GPR(AD)->MAR`) dejando MAR en la celda efectiva.\n2. Multiplica ACC*2 y calcula -2ACC en C2 en el acumulador.\n3. Lee el dato M a GPR con `M -> GPR`.\n4. Suma 3 veces GPR a ACC obteniendo 3M - 2ACC en el acumulador.",
        "pistas": [
            "Podés calcular primero -2ACC en el acumulador y guardarlo antes de resolver el puntero.",
            "Una vez leído M a GPR, sumáselo 3 veces a ACC con `GPR+ACC -> ACC`."
        ],
        "casos_prueba": [
            {
                "nombre": "M[0x60] = 10, ACC = 4 -> ACC = 3*10 - 2*4 = 22",
                "registros": {"PC": 0x15, "ACC": 4, "F": 0, "GPR": 0x420, "M": 0},
                "memoria": {0x20: 0x060, 0x60: 10},
                "esperado_registros": {"ACC": 22}
            },
            {
                "nombre": "M[0x60] = 5, ACC = 2 -> ACC = 3*5 - 2*2 = 11",
                "registros": {"PC": 0x15, "ACC": 2, "F": 0, "GPR": 0x420, "M": 0},
                "memoria": {0x20: 0x060, 0x60: 5},
                "esperado_registros": {"ACC": 11}
            }
        ]
    },

    # =========================================================================
    # NIVEL 4: 🔥 TRYHARD — NIVEL PARCIAL (Complejos con multiplicaciones y divisiones)
    # =========================================================================
    {
        "id": "e10-tryhard-parcial-doble-division",
        "titulo": "🔥 TRYHARD: M <- 3M - ((ACC/4)/2) + 2",
        "dificultad": "tryhard",
        "dificultad_label": "🔥 Tryhard",
        "modo": "indirecto",
        "modo_label": "Modo Indirecto",
        "categoria": "Examen Parcial",
        "formula_display": "M <- 3M - ((ACC/4)/2) + 2  (Indirecto)",
        "enunciado": "Ejercicio nivel TRYHARD de Examen Parcial.\nCombiná doble división sucesiva (ACC/4 dividido por 2 = ACC/8), negación en C2, multiplicación del dato en memoria por 3, suma de constante +2 y escritura final en memoria mediante direccionamiento indirecto.",
        "condiciones": [
            "Utilizar únicamente microoperaciones de la arquitectura básica.",
            "Resolver mediante direccionamiento indirecto (doble acceso de dirección).",
            "Considerar divisiones exactas sin desbordamiento.",
            "El resultado final debe quedar almacenado en la memoria efectiva M."
        ],
        "fuente": "Práctica propuesta con las operaciones de TP5 y el repaso del primer parcial",
        "estado_inicial_sugerido": {
            "PC": 0x25,
            "ACC": 0x020,  # 32 -> 32/8 = 4
            "F": 0,
            "GPR": 0x410,  # AD=0x10 -> puntero a 0x55
            "M": 0,
            "memoria": {0x10: 0x055, 0x55: 0x00A}  # M=10 -> 3*10 - 4 + 2 = 28
        },
        "incluir_fetch": False,
        "solucion_referencia": """GPR(AD) -> MAR
M -> GPR
GPR(AD) -> MAR

0 -> F
ROR F, ACC
0 -> F
ROR F, ACC
0 -> F
ROR F, ACC

ACC! -> ACC
ACC+1 -> ACC

M -> GPR
GPR+ACC -> ACC
GPR+ACC -> ACC
GPR+ACC -> ACC

ACC+1 -> ACC
ACC+1 -> ACC

ACC -> GPR
GPR -> M""",
        "explicacion_solucion": "1. `GPR(AD)->MAR; M->GPR; GPR(AD)->MAR` direcciona la celda efectiva.\n2. Tres `ROR F, ACC` con `0 -> F` dividen ACC por 8 (equivalente a (ACC/4)/2).\n3. `ACC!` y `ACC+1` calculan - (ACC/8).\n4. `M -> GPR` lee el dato y 3 sumas `GPR+ACC -> ACC` incorporan 3M.\n5. Dos `ACC+1 -> ACC` suman +2.\n6. `ACC -> GPR` y `GPR -> M` escriben el resultado final en memoria.",
        "pistas": [
            "Primero prepará la dirección efectiva en MAR mediante el doble acceso indirecto.",
            "Tres rotaciones a la derecha (`0 -> F; ROR F, ACC`) dividen ACC entre 8 (4 * 2).",
            "Negá el cociente en complemento a 2 (`ACC!` y `ACC+1`).",
            "Leé M a GPR, sumalo 3 veces a ACC, sumá 2 con incrementos y guardá en memoria con `GPR -> M`."
        ],
        "casos_prueba": [
            {
                "nombre": "M=10, ACC=32 -> M = 3(10) - (32/8) + 2 = 30 - 4 + 2 = 28 (0x1C)",
                "registros": {"PC": 0x25, "ACC": 32, "F": 0, "GPR": 0x410, "M": 0},
                "memoria": {0x10: 0x055, 0x55: 10},
                "esperado_memoria": {0x55: 28}
            },
            {
                "nombre": "M=6, ACC=16 -> M = 3(6) - (16/8) + 2 = 18 - 2 + 2 = 18 (0x12)",
                "registros": {"PC": 0x25, "ACC": 16, "F": 0, "GPR": 0x410, "M": 0},
                "memoria": {0x10: 0x055, 0x55: 6},
                "esperado_memoria": {0x55: 18}
            },
            {
                "nombre": "M=15, ACC=0 -> M = 3(15) - 0 + 2 = 47 (0x2F)",
                "registros": {"PC": 0x25, "ACC": 0, "F": 0, "GPR": 0x410, "M": 0},
                "memoria": {0x10: 0x055, 0x55: 15},
                "esperado_memoria": {0x55: 47}
            }
        ]
    },
    {
        "id": "e11-tryhard-parcial-directo-flag",
        "titulo": "🔥 TRYHARD: M <- 2M - 5F - 1",
        "dificultad": "tryhard",
        "dificultad_label": "🔥 Tryhard",
        "modo": "directo",
        "modo_label": "Modo Directo",
        "categoria": "Examen Parcial",
        "formula_display": "M <- 2M - 5F - 1  (Directo)",
        "enunciado": "Ejercicio de Parcial: Multiplicá por 2 el valor en memoria, restá 5 veces el valor del flag F y restá 1 en modo directo.",
        "condiciones": [
            "Modo directo.",
            "Generar 5F en ACC rotando F y sumando con GPR.",
            "Negar 5F en C2 y restar 1.",
            "Escribir el resultado final en memoria M[AD]."
        ],
        "fuente": "Práctica propuesta de memoria y F, basada en la arquitectura de TP5",
        "estado_inicial_sugerido": {
            "PC": 0x30,
            "ACC": 0x000,
            "F": 1,
            "GPR": 0x220,  # AD=0x20
            "M": 0,
            "memoria": {0x20: 0x014}  # M=20 -> 2(20) - 5(1) - 1 = 34
        },
        "incluir_fetch": False,
        "solucion_referencia": """GPR(AD) -> MAR
0 -> ACC
ROL F, ACC
ACC -> GPR
GPR+ACC -> ACC
GPR+ACC -> ACC
GPR+ACC -> ACC
GPR+ACC -> ACC
ACC! -> ACC
M -> GPR
GPR+ACC -> ACC
GPR+ACC -> ACC
ACC -> GPR
GPR -> M""",
        "explicacion_solucion": "1. Direcciona MAR y extrae F al acumulador.\n2. Suma 4 veces F con GPR obteniendo 5F en ACC.\n3. `ACC!` calcula -(5F) - 1 directamente por definición de C1.\n4. Suma 2 veces M leído a GPR y guarda en memoria.",
        "pistas": [
            "Extraé el bit F a ACC con `0 -> ACC; ROL F, ACC`.",
            "Recordá que `ACC!` equivale a `-ACC - 1` en aritmética binaria.",
            "Sumá dos veces el dato de memoria con `GPR+ACC -> ACC`."
        ],
        "casos_prueba": [
            {
                "nombre": "M = 20, F = 1 -> 2(20) - 5(1) - 1 = 34 (0x22)",
                "registros": {"PC": 0x30, "ACC": 0, "F": 1, "GPR": 0x220, "M": 0},
                "memoria": {0x20: 20},
                "esperado_memoria": {0x20: 34}
            },
            {
                "nombre": "M = 15, F = 0 -> 2(15) - 5(0) - 1 = 29 (0x1D)",
                "registros": {"PC": 0x30, "ACC": 0, "F": 0, "GPR": 0x220, "M": 0},
                "memoria": {0x20: 15},
                "esperado_memoria": {0x20: 29}
            }
        ]
    },
    {
        "id": "e12-multiplicacion-por-cuatro",
        "titulo": "Multiplicación: ACC <- 4 * ACC",
        "dificultad": "basico",
        "dificultad_label": "Básico",
        "modo": "implicado",
        "modo_label": "Modo Implicado",
        "categoria": "Aritmética básica",
        "formula_display": "ACC <- 4 * ACC",
        "enunciado": "Multiplicá el contenido del acumulador por 4 utilizando sumas sucesivas con GPR.",
        "condiciones": [
            "Modo implicado.",
            "Calcular 2*ACC primero y luego duplicar nuevamente."
        ],
        "fuente": "Taub Cap. 9 · Multiplicaciones Binarias",
        "estado_inicial_sugerido": {
            "PC": 0x10,
            "ACC": 0x007,
            "F": 0,
            "GPR": 0,
            "M": 0,
            "memoria": {}
        },
        "incluir_fetch": False,
        "solucion_referencia": """ACC -> GPR
GPR+ACC -> ACC
ACC -> GPR
GPR+ACC -> ACC""",
        "explicacion_solucion": "1. `ACC -> GPR; GPR+ACC -> ACC` duplica ACC (2*ACC).\n2. `ACC -> GPR; GPR+ACC -> ACC` duplica nuevamente obteniendo 4*ACC.",
        "pistas": [
            "Duplicar dos veces equivale a multiplicar por 4.",
            "Copiá a GPR y sumá a ACC en dos rondas."
        ],
        "casos_prueba": [
            {
                "nombre": "ACC = 7 -> ACC = 28 (0x1C)",
                "registros": {"PC": 0x10, "ACC": 7, "F": 0, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 28}
            },
            {
                "nombre": "ACC = 25 -> ACC = 100 (0x64)",
                "registros": {"PC": 0x10, "ACC": 25, "F": 0, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 100}
            }
        ]
    },
    {
        "id": "e13-division-por-cuatro",
        "titulo": "División entera: ACC <- [ACC / 4]",
        "dificultad": "intermedio",
        "dificultad_label": "Intermedio",
        "modo": "implicado",
        "modo_label": "Modo Implicado",
        "categoria": "Desplazamientos y rotaciones",
        "formula_display": "ACC <- [ACC / 4]",
        "enunciado": "Dividí el valor positivo del acumulador por 4 realizando dos desplazamientos a la derecha consecutivos y limpiando F en cada paso.",
        "condiciones": [
            "Limpiar F con `0 -> F` antes de cada rotación `ROR F, ACC`."
        ],
        "fuente": "Taub Cap. 9 · Divisiones en Potencias de 2",
        "estado_inicial_sugerido": {
            "PC": 0x10,
            "ACC": 0x028,
            "F": 1,
            "GPR": 0,
            "M": 0,
            "memoria": {}
        },
        "incluir_fetch": False,
        "solucion_referencia": """0 -> F
ROR F, ACC
0 -> F
ROR F, ACC""",
        "explicacion_solucion": "1. Primer `0 -> F` y `ROR` divide por 2.\n2. Segundo `0 -> F` y `ROR` divide nuevamente por 2 (división total por 4).",
        "pistas": [
            "Dividir por 4 requiere dos rotaciones a la derecha.",
            "Recordá limpiar el bit F antes de cada `ROR`."
        ],
        "casos_prueba": [
            {
                "nombre": "ACC = 40 (0x28) -> 10 (0x0A)",
                "registros": {"PC": 0x10, "ACC": 40, "F": 1, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 10}
            },
            {
                "nombre": "ACC = 100 (0x64) -> 25 (0x19)",
                "registros": {"PC": 0x10, "ACC": 100, "F": 0, "GPR": 0, "M": 0},
                "memoria": {},
                "esperado_registros": {"ACC": 25}
            }
        ]
    },
    {
        "id": "e14-tp5-ej8-indirecto",
        "titulo": "Variante de TP5: M <- M + 4F",
        "dificultad": "avanzado",
        "dificultad_label": "Avanzado",
        "modo": "indirecto",
        "modo_label": "Modo Indirecto",
        "categoria": "Direccionamiento Indirecto",
        "formula_display": "M <- M + 4F  (Indirecto)",
        "enunciado": "Variante para practicar el modo indirecto de TP5: multiplicá el bit de flag F por 4 mediante rotaciones a la izquierda en ACC, sumale el dato de memoria y guardá el resultado.",
        "condiciones": [
            "Modo indirecto.",
            "Multiplicar F por 4 colocando F en ACC y rotando con ceros.",
            "Guardar el resultado en la posición efectiva de memoria."
        ],
        "fuente": "Variante propuesta basada en TP5, ejercicio 8, página 4; no es la fórmula original",
        "estado_inicial_sugerido": {
            "PC": 0x10,
            "ACC": 0x000,
            "F": 1,
            "GPR": 0x43B,  # AD=0x3B -> puntero a 0x48
            "M": 0,
            "memoria": {0x3B: 0x048, 0x48: 0x020}  # M=32 -> 32 + 4(1) = 36
        },
        "incluir_fetch": False,
        "solucion_referencia": """GPR(AD) -> MAR
M -> GPR
GPR(AD) -> MAR
0 -> ACC
ROL F, ACC
0 -> F
ROL F, ACC
0 -> F
ROL F, ACC
M -> GPR
GPR+ACC -> ACC
ACC -> GPR
GPR -> M""",
        "explicacion_solucion": "1. Resuelve indirecto dejando MAR en la celda efectiva.\n2. `0 -> ACC; ROL F, ACC` pasa F al bit 0 de ACC.\n3. Dos rotaciones con `0 -> F` multiplican ACC por 4 (4*F).\n4. `M -> GPR` lee el dato y lo suma con 4F.\n5. Guarda el resultado en memoria con `GPR -> M`.",
        "pistas": [
            "Para hacer 4*F, meté F en ACC y rotá a la izquierda dos veces con `0 -> F; ROL F, ACC`.",
            "Leé M a GPR, sumalo a ACC y guardalo con `GPR -> M`."
        ],
        "casos_prueba": [
            {
                "nombre": "M[0x48] = 32, F = 1 -> 32 + 4 = 36 (0x24)",
                "registros": {"PC": 0x10, "ACC": 0, "F": 1, "GPR": 0x43B, "M": 0},
                "memoria": {0x3B: 0x048, 0x48: 32},
                "esperado_memoria": {0x48: 36}
            },
            {
                "nombre": "M[0x48] = 50, F = 0 -> 50 + 0 = 50 (0x32)",
                "registros": {"PC": 0x10, "ACC": 0, "F": 0, "GPR": 0x43B, "M": 0},
                "memoria": {0x3B: 0x048, 0x48: 50},
                "esperado_memoria": {0x48: 50}
            }
        ]
    },
    {
        "id": "e15-tryhard-multiplicacion-memoria",
        "titulo": "🔥 TRYHARD: M <- 4M - 3ACC - 2F",
        "dificultad": "tryhard",
        "dificultad_label": "🔥 Tryhard",
        "modo": "indirecto",
        "modo_label": "Modo Indirecto",
        "categoria": "Examen Parcial",
        "formula_display": "M <- 4M - 3ACC - 2F  (Indirecto)",
        "enunciado": "Problema de Parcial Avanzado: Multiplicá por 4 el dato en memoria efectiva, restale el triple del acumulador y el doble del flag F en direccionamiento indirecto.",
        "condiciones": [
            "Modo indirecto.",
            "Preservar las operaciones intermedias correctamente.",
            "Escribir el resultado final en memoria."
        ],
        "fuente": "Desafío propuesto de práctica basado en la arquitectura de la cátedra",
        "estado_inicial_sugerido": {
            "PC": 0x20,
            "ACC": 0x003,
            "F": 1,
            "GPR": 0x415,  # AD=0x15 -> puntero a 0x70
            "M": 0,
            "memoria": {0x15: 0x070, 0x70: 0x00A}  # M=10 -> 4(10) - 3(3) - 2(1) = 29
        },
        "incluir_fetch": False,
        "solucion_referencia": """GPR(AD) -> MAR
M -> GPR
GPR(AD) -> MAR

ACC -> GPR
GPR+ACC -> ACC
GPR+ACC -> ACC
ACC! -> ACC
ACC+1 -> ACC
ACC -> GPR

0 -> ACC
ROL F, ACC
0 -> F
ROL F, ACC
ACC! -> ACC
ACC+1 -> ACC
GPR+ACC -> ACC
ACC -> GPR

M -> GPR
GPR+ACC -> ACC
GPR+ACC -> ACC
GPR+ACC -> ACC
GPR+ACC -> ACC

ACC -> GPR
GPR -> M""",
        "explicacion_solucion": "1. Direcciona la celda efectiva.\n2. Calcula 3ACC y su complemento a 2 (-3ACC), guardándolo temporalmente en GPR.\n3. Rota F para obtener 2F, calcula su C2 (-2F) y lo suma con -3ACC en el acumulador.\n4. Lee M a GPR y suma 4 veces M.\n5. Guarda el resultado final 4M - 3ACC - 2F en memoria.",
        "pistas": [
            "Primero prepará MAR con la dirección efectiva.",
            "Calculá -3ACC y -2F acumulados.",
            "Leé M y sumalo 4 veces a ese acumulador."
        ],
        "casos_prueba": [
            {
                "nombre": "M = 10, ACC = 3, F = 1 -> 4(10) - 3(3) - 2(1) = 29 (0x1D)",
                "registros": {"PC": 0x20, "ACC": 3, "F": 1, "GPR": 0x415, "M": 0},
                "memoria": {0x15: 0x070, 0x70: 10},
                "esperado_memoria": {0x70: 29}
            },
            {
                "nombre": "M = 8, ACC = 2, F = 0 -> 4(8) - 3(2) - 0 = 26 (0x1A)",
                "registros": {"PC": 0x20, "ACC": 2, "F": 0, "GPR": 0x415, "M": 0},
                "memoria": {0x15: 0x070, 0x70: 8},
                "esperado_memoria": {0x70: 26}
            }
        ]
    }
]

from modelo.ejercicios_parciales import ejercicios_parciales

EJERCICIOS.extend(ejercicios_parciales())


def obtener_ejercicios() -> List[Ejercicio]:
    return EJERCICIOS

def obtener_ejercicio_por_id(ejercicio_id: str) -> Optional[Ejercicio]:
    for ej in EJERCICIOS:
        if ej["id"] == ejercicio_id:
            return ej
    return None
