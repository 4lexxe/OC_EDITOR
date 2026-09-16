import unittest
from modelo.ejercicios import obtener_ejercicios, obtener_ejercicio_por_id
from modelo.validador_ejercicios import validar_solucion_ejercicio

class TestEjercicios(unittest.TestCase):
    def test_todos_los_ejercicios_tienen_solucion_valida(self):
        ejercicios = obtener_ejercicios()
        self.assertGreaterEqual(len(ejercicios), 8)
        
        for ej in ejercicios:
            ej_id = ej["id"]
            sol = ej.get("solucion_referencia", "")
            self.assertTrue(sol, f"El ejercicio {ej_id} debe tener una solución de referencia.")
            
            resultado = validar_solucion_ejercicio(ej_id, sol)
            self.assertTrue(
                resultado["ok"],
                f"La solución de referencia para '{ej_id}' ({ej['titulo']}) falló la validación: {resultado.get('feedback')}"
            )
            self.assertEqual(resultado["casos_aprobados"], resultado["casos_totales"])

    def test_tryhard_parcial_especifico(self):
        ej = obtener_ejercicio_por_id("e10-tryhard-parcial-doble-division")
        self.assertIsNotNone(ej)
        self.assertEqual(ej["dificultad"], "tryhard")
        
        # Test con la solución exacta del prompt del usuario
        sol_usuario_tryhard = """GPR(AD) -> MAR
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
GPR -> M"""
        res = validar_solucion_ejercicio("e10-tryhard-parcial-doble-division", sol_usuario_tryhard)
        self.assertTrue(res["ok"])
        self.assertEqual(res["casos_aprobados"], res["casos_totales"])

    def test_solucion_invalida_detecta_error(self):
        # Código que solo hace NOP o cambia ACC erróneamente
        codigo_invalido = "0 -> ACC"
        res = validar_solucion_ejercicio("e1-complemento-a-dos", codigo_invalido)
        self.assertFalse(res["ok"])
        self.assertIn("esperado", res["feedback"].lower())

    def test_error_sintaxis_detectado(self):
        codigo_sintaxis_mala = "ACC + 999 -> ACC"
        res = validar_solucion_ejercicio("e1-complemento-a-dos", codigo_sintaxis_mala)
        self.assertFalse(res["ok"])
        self.assertIn("error de sintaxis", res.get("error", "").lower())

if __name__ == "__main__":
    unittest.main()
