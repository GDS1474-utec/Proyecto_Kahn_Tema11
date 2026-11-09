import json
import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from animacion import compilar, cargar_grafo, construir_pasos


class KahnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ejecutable = compilar()

    def probar_grafo(self, archivo):
        grafo = cargar_grafo(RAIZ / "grafos" / archivo)
        pasos = construir_pasos(self.ejecutable, grafo)
        return grafo, pasos[-1][2]

    def test_grafo_aciclico(self):
        grafo, final = self.probar_grafo("principal.json")
        self.assertFalse(final.ciclo)
        self.assertEqual(len(final.orden), 7)
        self.assertEqual(len(final.eliminadas), len(grafo["aristas_idx"]))
        self.assertEqual(final.orden, list(range(7)))

    def test_deteccion_de_ciclo(self):
        _, final = self.probar_grafo("con_ciclo.json")
        self.assertTrue(final.ciclo)
        self.assertLess(len(final.orden), 5)

    def test_un_vertice(self):
        _, final = self.probar_grafo("un_vertice.json")
        self.assertFalse(final.ciclo)
        self.assertEqual(final.orden, [0])

    def test_ciclo_directo(self):
        entrada = "2 2\n0 1\n1 0\n"
        resultado = subprocess.run([str(self.ejecutable)], input=entrada, text=True,
                                   capture_output=True, check=True)
        eventos = [json.loads(x) for x in resultado.stdout.splitlines()]
        self.assertEqual(eventos[-1]["tipo"], "ciclo")

    def test_arista_invalida(self):
        entrada = "2 1\n0 5\n"
        resultado = subprocess.run([str(self.ejecutable)], input=entrada,
                                   text=True, capture_output=True)
        self.assertNotEqual(resultado.returncode, 0)

    def test_dos_componentes(self):
        entrada = "5 2\n0 2\n1 3\n"
        resultado = subprocess.run([str(self.ejecutable)], input=entrada, text=True,
                                   capture_output=True, check=True)
        eventos = [json.loads(x) for x in resultado.stdout.splitlines()]
        orden = [e["u"] for e in eventos if e["tipo"] == "extraer"]
        self.assertEqual(set(orden), set(range(5)))
        self.assertLess(orden.index(0), orden.index(2))
        self.assertLess(orden.index(1), orden.index(3))
        self.assertEqual(eventos[-1]["tipo"], "finalizar")


if __name__ == "__main__":
    unittest.main()
