import ply.lex as lex
import re

tokens = (
    'ACC',
    'AD',
    'PC',
    'OP',
    'OPR',
    'GPR',
    'MAR',
    'M',
    'ROL',
    'ROR',
    'F',
    'NOT',
    'COMMA',
    'LPAREN',
    'RPAREN',
    'ONE',
    'PLUS',
    'ARROW',
    'ZERO',
)

# Palabras clave — orden importa: más largas primero para evitar conflictos
t_MAR = r'MAR'
t_ACC = r'ACC'
t_GPR = r'GPR'
t_ROL = r'ROL'
t_ROR = r'ROR'
t_OPR = r'OPR'
t_AD  = r'AD'
t_OP  = r'OP'
t_PC  = r'PC'
t_M   = r'M'
t_F   = r'F'

# Símbolos
t_NOT    = r'!'
t_COMMA  = r','
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_ONE    = r'1'
t_ZERO   = r'0'
t_PLUS   = r'\+'
t_ARROW  = r'->|:=|<-|:'

t_ignore = ' \t'

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def t_error(t):
    if getattr(t.lexer, "estricto", False):
        raise ValueError(f"Carácter no válido: {t.value[0]!r}")
    print(f"  [Léxico] Línea {t.lexer.lineno}: carácter ilegal '{t.value[0]}'")
    t.lexer.skip(1)


lexer = lex.lex(reflags=re.IGNORECASE)
