import ply.yacc as yacc
from compilador.AnalizadorLexico import tokens

def p_acciones(p):
    '''acciones : acciones accion
               | acciones COMMA accion
               | accion
    '''
    if len(p) == 2:
        p[0] = [p[1]]
    elif len(p) == 3:
        p[0] = p[1] + [p[2]]
    else:
        p[0] = p[1] + [p[3]]


def p_accion(p):
    '''accion : ROL F COMMA ACC
              | ROR F COMMA ACC
              | NOT ACC
              | NOT F
              | ACC NOT ARROW ACC
              | F NOT ARROW F
              | ZERO ARROW ACC
              | ZERO ARROW F
              | ACC PLUS ONE ARROW ACC
              | GPR PLUS ONE ARROW GPR
              | ACC PLUS GPR ARROW ACC
              | GPR PLUS ACC ARROW ACC
              | ACC ARROW GPR
              | GPR ARROW ACC
              | GPR ARROW M
              | M ARROW GPR
              | M ARROW ACC
              | GPR LPAREN AD RPAREN ARROW MAR
              | GPR LPAREN AD RPAREN ARROW OPR
              | GPR LPAREN OP RPAREN ARROW OPR
              | PC PLUS ONE ARROW PC
              | PC ARROW MAR
    '''

    t1 = p.slice[1].type

    # ROL / ROR
    if t1 == 'ROL':
        p[0] = ("ROL_F_ACC",)

    elif t1 == 'ROR':
        p[0] = ("ROR_F_ACC",)

    # NOT prefijo: ! ACC  |  ! F
    elif t1 == 'NOT':
        if p.slice[2].type == 'ACC':
            p[0] = ("NOT_ACC",)
        else:
            p[0] = ("NOT_F",)

    # NOT sufijo: ACC! -> ACC  |  F! -> F
    elif t1 == 'ACC' and len(p) == 5 and p.slice[2].type == 'NOT':
        p[0] = ("NOT_ACC",)
    elif t1 == 'F' and len(p) == 5 and p.slice[2].type == 'NOT':
        p[0] = ("NOT_F",)

    # ZERO → ACC / F  (antes que transferencias simples)
    elif t1 == 'ZERO':
        if p.slice[3].type == 'ACC':
            p[0] = ("ZERO_ACC",)
        else:
            p[0] = ("ZERO_F",)

    # INCREMENTOS: ACC+1 -> ACC  |  GPR+1 -> GPR  |  PC+1 -> PC
    elif len(p) == 6 and p.slice[3].type == 'ONE':
        if t1 == 'ACC':
            p[0] = ("INC_ACC",)
        elif t1 == 'PC':
            p[0] = ("INC_PC",)
        else:
            p[0] = ("INC_GPR",)

    # SUMA: ACC+GPR -> ACC  |  GPR+ACC -> ACC
    elif len(p) == 6 and p.slice[3].type in ('GPR', 'ACC'):
        p[0] = ("SUM_ACC_GPR",)

    # TRANSFERENCIAS simples: X -> Y
    elif len(p) == 4 and p.slice[2].type == 'ARROW':
        if t1 == 'ACC':
            p[0] = ("ACC_TO_GPR",)
        elif t1 == 'GPR' and p.slice[3].type == 'ACC':
            p[0] = ("GPR_TO_ACC",)
        elif t1 == 'GPR' and p.slice[3].type == 'M':
            p[0] = ("GPR_TO_M",)
        elif t1 == 'M':
            if p.slice[3].type == 'GPR':
                p[0] = ("M_TO_GPR",)
            else:
                p[0] = ("M_TO_ACC",)
        elif t1 == 'PC' and p.slice[3].type == 'MAR':
            p[0] = ("PC_TO_MAR",)

    # GPR(AD) → MAR / OPR  |  GPR(OP) → OPR (notación de apuntes)
    elif t1 == 'GPR' and len(p) > 3 and p.slice[3].type == 'OP' and p.slice[6].type == 'OPR':
        p[0] = ("GPR_OP_TO_OPR",)
    elif t1 == 'GPR' and len(p) > 3 and p.slice[3].type == 'AD':
        if p.slice[6].type == 'OPR':
            p[0] = ("GPR_OP_TO_OPR",)
        else:
            p[0] = ("GPR_AD_TO_MAR",)


def p_error(p):
    if p:
        print(f"  [Sintaxis] Línea {p.lineno}: token inesperado '{p.value}' (tipo: {p.type})")
        print(f"  Instrucciones válidas:")
        print(f"    ROL F,ACC  |  ROR F,ACC")
        print(f"    ! ACC  |  ! F  |  ACC! -> ACC  |  F! -> F")
        print(f"    0 -> ACC  |  0 -> F")
        print(f"    ACC+1 -> ACC  |  GPR+1 -> GPR")
        print(f"    ACC+GPR -> ACC  |  GPR+ACC -> ACC")
        print(f"    ACC -> GPR  |  GPR -> ACC")
        print(f"    GPR -> M  |  M -> GPR")
        print(f"    GPR(AD) -> MAR  |  GPR(OP) -> OPR")
    else:
        print("  [Sintaxis] Error al final del programa (instrucción incompleta)")


# En el ejecutable onefile, escribir parser.out en _MEI puede fallar.
# Desactivamos escritura de tablas/debug y usamos logger nulo para evitar
# excepciones internas de PLY al reportar warnings de E/S.
parser = yacc.yacc(
    debug=False,
    write_tables=False,
    errorlog=yacc.NullLogger(),
)


def preprocesar_linea_microop(linea: str) -> str:
    """
    Quita comentarios al final de línea para permitir anotaciones humanas.
    Marcadores soportados: ';' (estilo ensamblador), '#' y '//'.
    Sin esto, una anotación como «GPR+ACC -> ACC  ; 3M» hace fallar el léxico
    y la línea completa se ignora al inferir o ejecutar.
    """
    linea = linea.strip()
    if not linea:
        return linea
    corte = len(linea)
    for marcador in (";", "//", "#"):
        idx = linea.find(marcador)
        if idx != -1:
            corte = min(corte, idx)
    if corte < len(linea):
        linea = linea[:corte].strip()
    return linea