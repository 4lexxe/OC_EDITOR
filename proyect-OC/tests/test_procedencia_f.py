import unittest

from bitstring import BitArray
from sympy import lambdify

from compilador.AnalizadorSintactico import parsear_ciclo
from modelo import Inferidor
from modelo.Generador import generar, ErrorGeneracion
from modelo.ciclos import ejecutar_ciclo
from modelo.ejercicios import obtener_ejercicio_por_id
from modelo.ejercicios_parciales import ejercicios_parciales
from modelo.seguimiento_f import analizar_f
from modelo.validador_ejercicios import validar_solucion_ejercicio
from modelo.Von_Neumann import VonNeuman


class ProcedenciaFTest(unittest.TestCase):
    def test_generacion_implicada_no_usa_ram_y_multiplica_sin_perder_f(self):
        for n in (3, 5, 6, 8, -3):
            texto = generar(f"ACC <- {n}*ACC", modo="implicado")
            self.assertNotIn("GPR -> M", texto)
            cpu = VonNeuman()
            cpu.ACC = BitArray(uint=317, length=12)
            cpu.F = BitArray(uint=1, length=1)
            for linea in texto[3:]:
                ejecutar_ciclo(cpu, parsear_ciclo(linea))
            self.assertEqual(cpu.ACC.uint, (317*n) & 4095)
            self.assertEqual(cpu.F.uint, 1)
        with self.assertRaises(ErrorGeneracion):
            generar("ACC <- ACC/2 - 4F - 2", modo="implicado")

    def test_borrado_y_copia_del_original_son_distintos(self):
        perdido = analizar_f([["ZERO_F"]])
        self.assertFalse(perdido["portadores"])
        self.assertIn("Se perdió", perdido["conservacion"])
        copiado = analizar_f([["ZERO_ACC"], ["ROL_F_ACC"], ["ACC_TO_GPR"], ["ZERO_ACC"]])
        self.assertEqual(copiado["tipo"], "constante")
        self.assertEqual(copiado["portadores"], ["GPR"])

    def test_f_extraido_no_es_el_original_aunque_ambos_valgan_cero(self):
        analisis = analizar_f([["ROR_F_ACC"]])
        self.assertEqual(analisis["tipo"], "extraido")
        self.assertIn("bit 1 de ACC", analisis["actual"])
        self.assertIn("ACC", analisis["portadores"])

    def test_rotacion_completa_recupera_original_y_suma_lo_conserva(self):
        analisis = analizar_f([["ROL_F_ACC"]] * 13 + [["SUM_ACC_GPR"]])
        self.assertEqual(analisis["tipo"], "inicial")
        self.assertEqual(len(analisis["historial"]), 13)

    def test_inversion_doble_y_ciclos_simultaneos(self):
        self.assertEqual(analizar_f([["NOT_F"]])["tipo"], "invertido")
        self.assertEqual(analizar_f([["NOT_F"], ["NOT_F"]])["tipo"], "inicial")
        a = analizar_f([["ZERO_ACC"], ["ROL_F_ACC"], ["ACC_TO_GPR", "ZERO_ACC"]])
        self.assertEqual(a["portadores"], ["GPR"])

    def test_inferencia_lee_el_estado_anterior_en_un_ciclo_compartido(self):
        ops = ["ACC_TO_GPR", "SUM_ACC_GPR"]
        expr = dict(Inferidor._inferir_expresiones(ops, ciclos=[ops]))["ACC"]
        self.assertEqual(expr, Inferidor.ACC0 + Inferidor.GPR0)
        self.assertEqual(dict(Inferidor._inferir_expresiones(["INC_GPR"]))["GPR"], Inferidor.GPR0 + 1)

    def test_cuatro_parciales_y_variantes_en_todo_el_dominio_anunciado(self):
        parametros = [(5, 2, 2, -1), (5, -8, 1, -1), (1, -8, 4, 1),
                      (1, 8, 2, -1), (5, -8, 2, 0), (3, -8, 4, 1)]
        for ej, (a, b, divisor, k) in zip(ejercicios_parciales(), parametros):
            ciclos = [parsear_ciclo(l) for l in ej["solucion_referencia"].splitlines()]
            for acc in range(401):
                for f in (0, 1):
                    cpu = VonNeuman()
                    cpu.ACC = BitArray(uint=acc, length=12)
                    cpu.F = BitArray(uint=f, length=1)
                    cpu.GPR = BitArray(uint=(4095 - acc), length=12)
                    for ops in ciclos:
                        ejecutar_ciclo(cpu, ops)
                    self.assertEqual(cpu.ACC.uint, ((a*acc+b*f)//divisor+k) & 4095, (ej["id"], acc, f))

    def test_validacion_detecta_perdida_original_y_accesos_prohibidos(self):
        ej = obtener_ejercicio_por_id("p3-cuarto-2f")
        resultado = validar_solucion_ejercicio(ej["id"], "0 -> F\n" + ej["solucion_referencia"])
        self.assertFalse(resultado["ok"])
        self.assertTrue(any(not caso["paso"] and caso["f_inicial"] == 1 for caso in resultado["detalles_casos"]))
        self.assertIn("Se perdió", resultado["analisis_f"]["conservacion"])
        resultado = validar_solucion_ejercicio(ej["id"], ej["solucion_referencia"] + "\nGPR -> M")
        self.assertFalse(resultado["ok"])
        self.assertIn("sin accesos", resultado["error"])

    def test_inferencia_rotaciones_y_f_original_contra_cpu(self):
        programas = [
            ["ROR_F_ACC"], ["ROL_F_ACC", "ROR_F_ACC"],
            ["NOT_ACC", "ROR_F_ACC"], ["ROL_F_ACC", "ZERO_ACC", "ROL_F_ACC"],
            ["ACC_TO_GPR", "ZERO_ACC", "ROL_F_ACC", "NOT_ACC", "INC_ACC", "SUM_ACC_GPR", "ZERO_ACC", "ROL_F_ACC"],
        ]
        for ops in programas:
            expresiones = dict(Inferidor._inferir_expresiones(ops))
            expr = expresiones.get("ACC", Inferidor.ACC0)
            evaluar = lambdify((Inferidor.ACC0, Inferidor.GPR0, Inferidor.F0), expr, modules="math")
            for acc in (0, 1, 2, 511, 1024, 2047, 2048, 4095):
                for f in (0, 1):
                    cpu = VonNeuman()
                    cpu.ACC = BitArray(uint=acc, length=12)
                    cpu.GPR = BitArray(uint=17, length=12)
                    cpu.F = BitArray(uint=f, length=1)
                    for op in ops:
                        ejecutar_ciclo(cpu, [op])
                    self.assertEqual(cpu.ACC.uint, int(evaluar(acc, 17, f)) & 4095, (ops, acc, f))


if __name__ == "__main__":
    unittest.main()
