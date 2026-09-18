"""Regresiones de presentación y cálculo de microoperaciones."""
import unittest
from unittest.mock import patch

from bitstring import BitArray
from sympy import Mod, floor, lambdify

from compilador.AnalizadorSintactico import parser, preprocesar_linea_microop
from modelo import Inferidor
from modelo.formato_apuntes import FormatoApuntes, normalizar_divisiones
from modelo.Generador import generar
from modelo.Von_Neumann import VonNeuman


CODIGO = """PC -> MAR
M -> GPR
GPR(OP) -> OPR
0 -> F
ROR F, ACC
0 -> F
ROR F, ACC
ACC! -> ACC
ACC + 1 -> ACC
ACC -> GPR
0 -> ACC
ROL F, ACC
RoL F, ACC
ACC + GPR -> ACC
ACC + 1 -> ACC
"""


def parsear(codigo):
    return [op[0] for linea in codigo.splitlines()
            for op in (parser.parse(preprocesar_linea_microop(linea)) or []) if op]


class InferenciaApuntesTest(unittest.TestCase):
    def test_secuencia_del_usuario(self):
        detalle = Inferidor.inferir_detallado(parsear(CODIGO))
        self.assertEqual(detalle["instruccion"], "ACC <- -ACC/4 + 2F_extraido1 + 1")
        self.assertIn("bit 2 de ACC inicial", " ".join(detalle["notas"]))
        self.assertIn("sin decimales", " ".join(detalle["notas"]))
        self.assertNotRegex(str(detalle), r"floor\(|Mod\(")

    def test_resultado_contra_cpu_para_todos_los_acc_de_12_bits(self):
        ops = parsear(CODIGO)
        expr = dict(Inferidor._inferir_expresiones(ops))["ACC"]
        evaluar = lambdify(Inferidor.ACC0, expr, modules="math")
        cpu = VonNeuman()
        nombres = {"ZERO_F": "ZERO_TO_F", "ZERO_ACC": "ZERO_TO_ACC"}
        ejecutar = [getattr(cpu, nombres.get(op, op)) for op in ops]
        for valor in range(4096):
            cpu.ACC = BitArray(uint=valor, length=12)
            cpu.F = BitArray(uint=valor % 2, length=1)
            for op in ejecutar:
                op()
            esperado = -(valor // 4) + 2 * ((valor >> 1) & 1) + 1
            self.assertEqual(cpu.ACC.uint, esperado & 0xFFF, valor)
            self.assertEqual(int(evaluar(valor)) & 0xFFF, cpu.ACC.uint, valor)

    def test_divisiones_y_signos_en_todos_los_registros(self):
        for simbolo in (Inferidor.ACC0, Inferidor.M0, Inferidor.GPR0):
            expr = -floor(floor(simbolo / 2) / 2) + 1
            formato = FormatoApuntes([expr])
            self.assertEqual(formato.texto(expr), f"-{simbolo}/4 + 1")
            expr = 2 * floor(floor(simbolo / 4) / 2)
            self.assertEqual(FormatoApuntes([expr]).texto(expr), f"2*({simbolo}/8)")

    def test_no_se_fusionan_bits_distintos_ni_f_inicial(self):
        acc, f = Inferidor.ACC0, Inferidor.F0
        expr = f + Mod(acc, 2) + 2 * Mod(floor(acc / 2), 2)
        formato = FormatoApuntes([expr])
        texto = formato.texto(expr)
        self.assertIn("F_extraido1", texto)
        self.assertIn("F_extraido2", texto)
        self.assertNotIn(f, formato.aliases.values())
        self.assertEqual(len(formato.notas()), 4)

    def test_aliases_compartidos_entre_destinos(self):
        ops = parsear(CODIGO) + ["ACC_TO_GPR", "GPR_TO_M"]
        detalle = Inferidor.inferir_detallado(ops)
        self.assertEqual(detalle["instruccion"],
                         "M <- -ACC/4 + 2F_extraido1 + 1  |  ACC <- -ACC/4 + 2F_extraido1 + 1")
        self.assertEqual(len(detalle["notas"]), 3)

    def test_division_compuesta_y_resto_general(self):
        acc = Inferidor.ACC0
        expr = floor((acc + 1) / 4) + Mod(acc, 3)
        formato = FormatoApuntes([expr])
        self.assertIn("(ACC + 1)/4", formato.texto(expr))
        self.assertIn("resto(ACC; 3)", formato.texto(expr))
        self.assertNotRegex(formato.texto(expr), r"floor\(|Mod\(")

    def test_no_se_agrupan_divisiones_que_no_corresponden(self):
        acc = Inferidor.ACC0
        expr = floor(3 * floor(acc / 2) / 2)
        evaluar = lambdify(acc, normalizar_divisiones(expr), modules="math")
        self.assertEqual(evaluar(3), 1)

    def test_generador_sigue_verificando_sus_resultados(self):
        for instruccion in (
            "ACC <- 8ACC + 2", "ACC <- ACC/2", "ACC <- ACC/4", "ACC <- ACC/8",
            "ACC <- ACC/2 - 4F - 2", "ACC <- ACC - F",
            "M <- 3M - ACC", "M <- -3M - F", "M <- ACC/4", "M <- 2M - 5F - 1",
        ):
            with self.subTest(instruccion=instruccion):
                ok, detalle = Inferidor.verificar_equivalencia(instruccion, generar(instruccion))
                self.assertTrue(ok, detalle)
                self.assertNotRegex(detalle, r"floor\(|Mod\(")

    def test_no_aprueba_f_extraido_como_f_inicial(self):
        ok, detalle = Inferidor.verificar_equivalencia("ACC <- ACC/4 - F", generar("ACC <- ACC/4 - F"))
        self.assertFalse(ok)
        self.assertIn("F_inicial", detalle)
        self.assertIn("F_extraido1", detalle)

    def test_verificacion_no_depende_del_texto_mostrado(self):
        with patch.object(FormatoApuntes, "instruccion", return_value="Texto de presentación"):
            ok, _ = Inferidor.verificar_equivalencia("ACC <- ACC/8", generar("ACC <- ACC/8"))
            self.assertTrue(ok)
            ok, _ = Inferidor.verificar_equivalencia("ACC <- ACC/4", generar("ACC <- ACC/8"))
            self.assertFalse(ok)

    def test_secuencia_vacia_no_deja_notas(self):
        self.assertEqual(Inferidor.inferir_detallado([]),
                         {"instruccion": "Sin instrucciones", "notas": []})


if __name__ == "__main__":
    unittest.main()
