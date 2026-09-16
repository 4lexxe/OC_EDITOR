import unittest

from bitstring import BitArray

from compilador.AnalizadorSintactico import parsear_ciclo
from modelo.ciclos import ejecutar_ciclo
from modelo.ejemplos_traza import EJEMPLOS_TRAZA, FETCH
from modelo.traza import simular_traza
from modelo.Von_Neumann import VonNeuman


def cpu_ejemplo(ejemplo):
    cpu = VonNeuman()
    for reg, valor in ejemplo["registros"].items():
        setattr(cpu, reg, BitArray(uint=valor, length=1 if reg == "F" else 8 if reg == "PC" else 12))
    for direccion, valor in ejemplo["memoria"].items():
        cpu.RAM.escribir(direccion, valor)
    return cpu


class TrazaTeoriaTest(unittest.TestCase):
    def test_clase_practica_paginas_15_y_16(self):
        ejemplo = EJEMPLOS_TRAZA[0]
        cpu = cpu_ejemplo(ejemplo)
        filas, error, memoria = simular_traza(ejemplo["codigo"], cpu, prefijo_fetch=True, estado_inicial=True)
        self.assertIsNone(error)
        self.assertEqual(len(filas), 15)
        for ciclo, esperado in {
            1: {"PC": "20", "MAR": "20", "M": "983"},
            2: {"PC": "21", "GPR": "983", "GPR_OP": "9", "GPR_AD": "83"},
            3: {"OPR": "9"}, 4: {"MAR": "83", "M": "012"},
            5: {"GPR": "012"}, 6: {"ACC": "FF8"}, 7: {"ACC": "FF9"},
            8: {"ACC": "00B", "F": "1"}, 9: {"GPR": "00B"},
            10: {"ACC": "000"}, 11: {"ACC": "001", "F": "0"},
            12: {"ACC": "00C"}, 13: {"GPR": "00C"}, 14: {"M": "00C"},
        }.items():
            with self.subTest(ciclo=ciclo):
                for registro, valor in esperado.items():
                    self.assertEqual(filas[ciclo][registro], valor)
        self.assertIn("M[$83] = $00C", memoria)
        self.assertEqual(cpu.RAM.leer(0x83).uint, 0x012, "La traza no modifica la CPU del editor")

    def test_ejercicios_indirecto_y_directo_del_tp5(self):
        for ejemplo, direccion, esperado, ciclos in [
            (EJEMPLOS_TRAZA[1], 0x48, "024", 17),
            (EJEMPLOS_TRAZA[2], 0x37, "065", 21),
        ]:
            filas, error, memoria = simular_traza(ejemplo["codigo"], cpu_ejemplo(ejemplo))
            self.assertIsNone(error)
            self.assertEqual(len(filas), ciclos)
            self.assertEqual(filas[-1]["M"], esperado)
            self.assertIn(f"M[${direccion:02X}] = ${esperado}", memoria)
        filas, _, _ = simular_traza(EJEMPLOS_TRAZA[1]["codigo"], cpu_ejemplo(EJEMPLOS_TRAZA[1]))
        self.assertEqual(filas[3]["MAR"], "3B")
        self.assertEqual(filas[5]["MAR"], "48")

    def test_ciclo_compartido_y_fetch_sin_duplicar(self):
        for codigo in ("ACC+1 -> ACC", FETCH + "ACC+1 -> ACC"):
            filas, error, _ = simular_traza(codigo, VonNeuman(), prefijo_fetch=True)
            self.assertIsNone(error)
            self.assertEqual(len(filas), 4)
            self.assertEqual(filas[1]["ops"], ["M_TO_GPR", "INC_PC"])
            self.assertEqual([f["fase"] for f in filas], ["Búsqueda"] * 3 + ["Ejecución"])

    def test_compacto_conserva_estado_completo(self):
        filas, _, _ = simular_traza("0 -> F\nACC+1 -> ACC", VonNeuman(),
                                    omitir_repetidos=True, estado_inicial=True)
        self.assertEqual(filas[1]["F"], "")
        self.assertEqual(filas[1]["valores"]["F"], "0")
        self.assertEqual(filas[2]["cambios"], ["ACC"])

    def test_anchos_y_desbordamiento_pc(self):
        cpu = VonNeuman()
        self.assertEqual([len(getattr(cpu, r)) for r in ("PC", "MAR", "OPR", "ACC", "F")], [8, 8, 4, 12, 1])
        cpu.PC = BitArray(uint=255, length=8)
        cpu.INC_PC()
        self.assertEqual(cpu.PC.uint, 0)

    def test_suma_no_modifica_f_incluso_con_carry(self):
        for f, acc, gpr in ((1, 2, 3), (0, 4095, 1)):
            cpu = VonNeuman()
            cpu.F = BitArray(uint=f, length=1)
            cpu.ACC = BitArray(uint=acc, length=12)
            cpu.GPR = BitArray(uint=gpr, length=12)
            cpu.SUM_ACC_GPR()
            self.assertEqual(cpu.F.uint, f)
            self.assertEqual(cpu.ACC.uint, (acc + gpr) & 0xFFF)

    def test_ciclo_usa_entradas_anteriores(self):
        cpu = VonNeuman()
        cpu.ACC = BitArray(uint=3, length=12)
        cpu.GPR = BitArray(uint=7, length=12)
        ejecutar_ciclo(cpu, ["ACC_TO_GPR", "GPR_TO_ACC"])
        self.assertEqual((cpu.ACC.uint, cpu.GPR.uint), (7, 3))

    def test_error_no_ejecuta_fragmentos_ni_escrituras_en_conflicto(self):
        for codigo in ("ACC+1 -> ACC @", "ACC+1 -> ACC, 0 -> ACC", "ACC+1 -> ACC,", "basura ACC+1 -> ACC"):
            filas, error, _ = simular_traza(codigo, VonNeuman(), estado_inicial=True)
            self.assertIsNotNone(error, codigo)
            self.assertEqual(len(filas), 1)
        filas, error, _ = simular_traza("ACC+1 -> ACC\nACC+1 ->", VonNeuman())
        self.assertEqual(len(filas), 1)
        self.assertIn("Línea 2", error)

    def test_flechas_y_comentarios_del_material(self):
        self.assertEqual(parsear_ciclo("M→GPR, PC+1→PC ; búsqueda"), ["M_TO_GPR", "INC_PC"])

    def test_codigo_vacio_no_inventa_un_fetch(self):
        filas, error, _ = simular_traza("# comentario", VonNeuman(), prefijo_fetch=True)
        self.assertEqual(filas, [])
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
