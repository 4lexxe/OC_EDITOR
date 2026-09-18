"""Procedencia de F, independiente de sus valores concretos (0 y 1).

Las expresiones booleanas se internan para seguir copias, rotaciones y sumas
sin confundir dos bits que casualmente tienen el mismo valor.
"""
from __future__ import annotations


class SeguimientoF:
    def __init__(self):
        self.nodos = [None, None]
        self.ids = {}
        self.depende = [False, False]
        self.original = self._nodo(("entrada", "F_inicial"), True)
        self.registros = {r: [self._nodo(("entrada", r, i), False) for i in range(12)]
                          for r in ("ACC", "GPR", "M")}
        self.registros["F"] = [self.original]
        self.historial = []
        self.ultimo_origen = "F inicial"
        self.memoria_con_f = False

    def _nodo(self, clave, depende):
        if clave not in self.ids:
            self.ids[clave] = len(self.nodos)
            self.nodos.append(clave)
            self.depende.append(depende)
        return self.ids[clave]

    def _bin(self, op, a, b):
        if a > b:
            a, b = b, a
        if op == "xor":
            if a == b:
                return 0
            if a == 0:
                return b
            if a == 1 and self.nodos[b] and self.nodos[b][:2] == ("xor", 1):
                return self.nodos[b][2]
        if op == "and":
            if a == 0:
                return 0
            if a == 1 or a == b:
                return b
        if op == "or":
            if a == 0 or a == b:
                return b
            if a == 1:
                return 1
        return self._nodo((op, a, b), self.depende[a] or self.depende[b])

    def _suma(self, a, b):
        salida, acarreo = [], 0
        for x, y in zip(a, b):
            xy = self._bin("xor", x, y)
            salida.append(self._bin("xor", xy, acarreo))
            acarreo = self._bin("or", self._bin("and", x, y), self._bin("and", xy, acarreo))
        return salida

    def estado(self):
        f = self.registros["F"][0]
        if f == self.original:
            tipo, actual = "inicial", "F = F_inicial (el original)"
        elif f in (0, 1):
            tipo, actual = "constante", f"F = {f}; ya no contiene el F inicial"
        elif f == self._bin("xor", 1, self.original):
            tipo, actual = "invertido", "F = 1 − F_inicial (original invertido)"
        else:
            tipo, actual = "extraido", f"F es {self.ultimo_origen}; no lo confundas con F_inicial"
        portadores = [r for r, bits in self.registros.items() if any(self.depende[b] for b in bits)]
        if self.memoria_con_f:
            portadores.append("RAM escrita")
        if portadores:
            conservacion = "Hay información que depende de F_inicial en: " + ", ".join(portadores) + "."
        else:
            conservacion = "Se perdió F_inicial: ya no queda información suya en los registros ni en la RAM escrita."
        return {"tipo": tipo, "actual": actual, "portadores": portadores,
                "conservacion": conservacion, "resumen": actual + ". " + conservacion}

    def avanzar(self, ops, ciclo):
        antes = {r: list(bits) for r, bits in self.registros.items()}
        cambios = {}
        evento = None
        for op in ops:
            acc, gpr, f = antes["ACC"], antes["GPR"], antes["F"][0]
            if op in ("ROL_F_ACC", "ROR_F_ACC"):
                izquierda = op == "ROL_F_ACC"
                cambios["ACC"] = [f] + acc[:-1] if izquierda else acc[1:] + [f]
                cambios["F"] = [acc[-1] if izquierda else acc[0]]
                self.ultimo_origen = f"el bit {'12' if izquierda else '1'} de ACC antes del ciclo {ciclo}"
                evento = (f"{'ROL' if izquierda else 'ROR'}: F anterior entra en el bit "
                          f"{'1' if izquierda else '12'} de ACC; F recibe {self.ultimo_origen}.")
            elif op in ("ZERO_ACC", "ZERO_F"):
                reg = "ACC" if op == "ZERO_ACC" else "F"
                cambios[reg] = [0] * len(antes[reg])
                if reg == "F":
                    evento = "0 → F: se borra el contenido anterior de F."
            elif op in ("NOT_ACC", "NOT_F"):
                reg = "ACC" if op == "NOT_ACC" else "F"
                cambios[reg] = [self._bin("xor", 1, b) for b in antes[reg]]
                if reg == "F":
                    evento = "F! → F: se invierte el contenido anterior de F."
            elif op == "SUM_ACC_GPR":
                cambios["ACC"] = self._suma(acc, gpr)
            elif op in ("INC_ACC", "INC_GPR"):
                reg = "ACC" if op == "INC_ACC" else "GPR"
                cambios[reg] = self._suma(antes[reg], [1] + [0] * 11)
            elif op in ("ACC_TO_GPR", "GPR_TO_ACC", "M_TO_GPR", "M_TO_ACC", "GPR_TO_M"):
                origen, destino = op.split("_TO_")
                cambios[destino] = list(antes[origen])
                if destino == "M" and any(self.depende[b] for b in antes[origen]):
                    self.memoria_con_f = True
            elif op in ("GPR_AD_TO_MAR", "PC_TO_MAR"):
                # La dirección efectiva no identifica simbólicamente el dato leído.
                direccion_depende = op == "GPR_AD_TO_MAR" and any(self.depende[b] for b in gpr[:8])
                cambios["M"] = [self._nodo(("memoria", ciclo, i), self.memoria_con_f or direccion_depende) for i in range(12)]
        self.registros.update(cambios)
        estado = self.estado()
        if evento:
            self.historial.append({"ciclo": ciclo, "evento": evento, **estado})
        return estado


def analizar_f(ciclos):
    seguimiento = SeguimientoF()
    for ciclo, ops in enumerate(ciclos, 1):
        seguimiento.avanzar(ops, ciclo)
    return {**seguimiento.estado(), "historial": seguimiento.historial,
            "convencion": "F_inicial es el bit al comenzar. Las sumas conservan F; las rotaciones lo reemplazan."}
