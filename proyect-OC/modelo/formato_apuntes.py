"""Presentación de expresiones sin exponer la sintaxis interna de SymPy."""
from __future__ import annotations

import re

from sympy import Mod, Symbol, default_sort_key, expand, floor, simplify
from sympy.printing.str import StrPrinter


def normalizar_divisiones(expr):
    """Agrupa divisiones enteras sucesivas sin convertirlas en división decimal."""
    if not expr.args:
        return expr
    expr = expr.func(*(normalizar_divisiones(arg) for arg in expr.args))
    if expr.func == floor:
        numerador, denominador = expr.args[0].as_numer_denom()
        if numerador.func == floor and denominador.is_Integer and denominador > 0:
            return normalizar_divisiones(floor(numerador.args[0] / denominador))
    return expr


class _ImpresorApuntes(StrPrinter):
    def _print_floor(self, expr):
        numerador, denominador = expr.args[0].as_numer_denom()
        if denominador == 1:
            return f"parte entera de ({self._print(numerador)})"
        texto = self._print(numerador)
        if not numerador.is_Atom:
            texto = f"({texto})"
        divisor = self._print(denominador)
        if not denominador.is_Atom:
            divisor = f"({divisor})"
        return f"{texto}/{divisor}"

    def _print_Mod(self, expr):
        valor, divisor = expr.args
        if divisor == 4096:
            return f"palabra12({self._print(valor)})"
        return f"resto({self._print(valor)}; {self._print(divisor)})"

    def _print_Add(self, expr, order=None):
        nombres = {str(s) for s in expr.free_symbols}
        orden = ("M", "F", "ACC", "GPR") if "M" in nombres else ("ACC", "GPR", "M", "F")

        def prioridad(termino):
            nombres_termino = {str(s) for s in termino.free_symbols}
            for indice, nombre in enumerate(orden):
                if nombre in nombres_termino:
                    return indice, default_sort_key(termino)
            return (len(orden) if nombres_termino else 99), default_sort_key(termino)

        partes = []
        for termino in sorted(expr.args, key=prioridad):
            negativo = termino.could_extract_minus_sign()
            texto = self._print(-termino if negativo else termino)
            if partes:
                partes.append((" - " if negativo else " + ") + texto)
            else:
                partes.append(("-" if negativo else "") + texto)
        return "".join(partes)

    def _print_Mul(self, expr):
        # Una división entera multiplicada debe conservar su agrupación:
        # 2*(ACC/4) no es lo mismo que (2ACC)/4 para ACC impar.
        coef, resto = expr.as_coeff_Mul()
        if resto.func == floor and coef == -1:
            return "-" + self._print(resto)
        return super()._print_Mul(expr)

    def parenthesize(self, item, level, strict=False):
        if item.func == floor:
            return f"({self._print(item)})"
        return super().parenthesize(item, level, strict=strict)


class FormatoApuntes:
    """Una leyenda común para todos los registros de una misma inferencia.

    Los bits extraídos reciben nombres F, F1, F2… sin confundirlos con el F
    inicial ni fusionar dos bits distintos. Los alias son solo de presentación.
    """

    def __init__(self, expresiones):
        self.expresiones = [normalizar_divisiones(simplify(e)) for e in expresiones]
        bits = set()
        simbolos = set()
        for expr in self.expresiones:
            bits.update(m for m in expr.atoms(Mod) if m.args[1] == 2)
            simbolos.update(expr.free_symbols)
        bits = sorted(bits, key=default_sort_key)
        f_ocupado = any(str(s) == "F" for s in simbolos)
        self.aliases = {
            bit: Symbol(f"F_extraido{i + 1}", integer=True)
            for i, bit in enumerate(bits)
        }
        self.impresor = _ImpresorApuntes()

    def texto(self, expr, *, usar_aliases=True):
        expr = normalizar_divisiones(simplify(expr))
        if usar_aliases:
            expr = expr.xreplace(self.aliases)
        expr = expr.xreplace({s: Symbol("F_inicial", integer=True) for s in expr.free_symbols if str(s) == "F"})
        texto = self.impresor.doprint(expand(expr))
        return re.sub(r"(\d)\*(ACC|GPR|M|F_inicial|F_extraido\d+)\b", r"\1\2", texto)

    def instruccion(self, destino, expr):
        return f"{destino} <- {self.texto(expr)}"

    def notas(self):
        notas = []
        if any(str(s) == "F" for e in self.expresiones for s in e.free_symbols):
            notas.append("F_inicial es el F al comenzar la secuencia; una rotación puede reemplazarlo.")
        if any(e.has(floor) for e in self.expresiones):
            notas.append("Las divisiones se toman en entero, redondeando hacia abajo (sin decimales).")
        for bit, alias in self.aliases.items():
            valor = bit.args[0]
            if valor.is_Symbol:
                descripcion = f"el último bit de {valor} inicial"
            elif valor.func == floor:
                numerador, denominador = valor.args[0].as_numer_denom()
                n = int(denominador) if denominador.is_Integer else 0
                if numerador.is_Symbol and n > 0 and n & (n - 1) == 0:
                    posicion = n.bit_length()
                    descripcion = f"el bit {posicion} de {numerador} inicial, contando desde la derecha"
                else:
                    descripcion = f"el último bit de ({self.texto(valor, usar_aliases=False)})"
            else:
                descripcion = f"el último bit de ({self.texto(valor, usar_aliases=False)})"
            notas.append(f"{alias} representa {descripcion} (0 o 1), extraído por la rotación.")
        if any(m.args[1] == 4096 for e in self.expresiones for m in e.atoms(Mod)):
            notas.append("palabra12(valor) conserva los 12 bits del resultado (entre 000 y FFF en hexadecimal).")
        if any(m.args[1] not in (2, 4096) for e in self.expresiones for m in e.atoms(Mod)):
            notas.append("resto(valor; divisor) es lo que sobra al hacer la división entera.")
        return notas
