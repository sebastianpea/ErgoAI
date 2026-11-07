"""Pruebas del motor determinista REBA, geometría angular y simulador residual."""

import unittest
from dataclasses import dataclass

from backend.app.core_ergonomics.angle_geometry import extraer_angulos_laterales
from backend.app.core_ergonomics.modelos import ContextoTarea, Efecto, Modificadores
from backend.app.core_ergonomics.nom036_calculator import color_total
from backend.app.core_ergonomics.reba_calculator import RebaCalculator
from backend.app.core_ergonomics.residual_simulator import simular
from backend.app.session_store import NormativeConfigLoader


@dataclass
class P:
    id: int
    x: float
    y: float
    confianza: float = 0.9


def esqueleto(hombro, codo, muneca, cadera, rodilla, tobillo, oreja, nariz):
    """Lado izquierdo COCO-17 con confianza alta; lado derecho ausente."""
    pts = {0: nariz, 3: oreja, 5: hombro, 7: codo, 9: muneca, 11: cadera, 13: rodilla, 15: tobillo}
    return [P(i, *xy) for i, xy in pts.items()]


class TestReba(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = NormativeConfigLoader()
        cls.calc = RebaCalculator(cls.loader.get_reba_tables())

    def test_tablas_completas(self):
        t = self.loader.get_reba_tables()
        self.assertEqual(len(t["table_a_matrix"]["values"]), 5)
        self.assertEqual(len(t["table_b_matrix"]["values"]), 6)
        self.assertEqual(len(t["table_c_matrix"]), 12)
        self.assertTrue(all(len(f) == 12 for f in t["table_c_matrix"]))

    def test_postura_neutra_puntaje_minimo(self):
        r = self.calc.calcular({"tronco": 0, "cuello": 10, "piernas": 0, "brazo": 0, "antebrazo": 80}, ContextoTarea())
        self.assertEqual((r.grupo_a, r.grupo_b, r.tabla_c, r.final, r.nivel), (1, 1, 1, 1, "inapreciable"))

    def test_rangos_tronco(self):
        ctx = ContextoTarea()
        casos = {0: 1, 15: 2, -15: 2, -30: 3, 40: 3, 75: 4}
        for grados, esperado in casos.items():
            self.assertEqual(self.calc.tronco(grados, ctx).puntaje, esperado, grados)

    def test_rangos_brazo_y_modificadores(self):
        self.assertEqual(self.calc.brazo(100, ContextoTarea()).puntaje, 4)
        self.assertEqual(self.calc.brazo(-30, ContextoTarea()).puntaje, 2)
        ctx = ContextoTarea(modificadores=Modificadores(brazo_abducido_o_rotado=True, hombro_elevado=True))
        self.assertEqual(self.calc.brazo(100, ctx).puntaje, 6)
        ctx = ContextoTarea(modificadores=Modificadores(brazo_apoyado=True))
        self.assertEqual(self.calc.brazo(0, ctx).puntaje, 1)  # nunca baja de 1

    def test_ejemplo_clasico(self):
        # Tronco 3, cuello 2, piernas 2 → Tabla A = 5 (+carga 1 = 6)
        # Brazo 3, antebrazo 2, muñeca 2 → Tabla B = 5 (+agarre 1 = 6)
        # Tabla C[6][6] = 8; +1 actividad = 9 (alto)
        ctx = ContextoTarea(carga_kg=8, agarre="regular", actividad=1, apoyo_unilateral=True, muneca_grados=20)
        r = self.calc.calcular({"tronco": 30, "cuello": 25, "piernas": 0, "brazo": 60, "antebrazo": 40}, ctx)
        self.assertEqual((r.grupo_a, r.grupo_b, r.tabla_c, r.final, r.nivel), (5, 5, 8, 9, "alto"))

    def test_carga(self):
        self.assertEqual(self.calc.puntaje_carga(ContextoTarea(carga_kg=4.9)), 0)
        self.assertEqual(self.calc.puntaje_carga(ContextoTarea(carga_kg=10)), 1)
        self.assertEqual(self.calc.puntaje_carga(ContextoTarea(carga_kg=16, carga_brusca=True)), 3)

    def test_geometria_lateral(self):
        # Operador mirando a la derecha, tronco inclinado 45° hacia el frente
        pts = esqueleto(hombro=(200, 200), codo=(200, 300), muneca=(300, 300), cadera=(100, 300),
                        rodilla=(100, 400), tobillo=(100, 500), oreja=(270, 130), nariz=(290, 140))
        a = extraer_angulos_laterales(pts)
        self.assertAlmostEqual(a["tronco"].grados, 45.0, places=1)
        self.assertAlmostEqual(a["antebrazo"].grados, 90.0, places=1)
        self.assertAlmostEqual(a["piernas"].grados, 0.0, places=1)
        self.assertAlmostEqual(a["brazo"].grados, 45.0, places=1)  # brazo vertical, tronco a 45°
        self.assertAlmostEqual(a["cuello"].grados, 0.0, places=1)
        self.assertIsNone(a["muneca"].grados)
        self.assertEqual(a["brazo"].lado, "izq")

    def test_geometria_simetrica_espejo(self):
        # El mismo operador reflejado (mirando a la izquierda) debe dar los mismos ángulos
        derecha = esqueleto((200, 200), (200, 300), (300, 300), (100, 300), (100, 400), (100, 500), (270, 130), (290, 140))
        izquierda = [P(p.id, 1000 - p.x, p.y) for p in derecha]
        a, b = extraer_angulos_laterales(derecha), extraer_angulos_laterales(izquierda)
        for seg in ("tronco", "cuello", "brazo", "antebrazo", "piernas"):
            self.assertAlmostEqual(a[seg].grados, b[seg].grados, places=1, msg=seg)

    def test_residual(self):
        ctx = ContextoTarea(carga_kg=16, agarre="regular", actividad=1)
        angulos = {"tronco": 45, "cuello": 10, "piernas": 0, "brazo": 60, "antebrazo": 80}
        antes = self.calc.calcular(angulos, ctx)
        despues = simular(self.calc, angulos, ctx, [Efecto(carga_kg=0), Efecto(angulos={"tronco": 0, "brazo": 10})])
        self.assertLess(despues.final, antes.final)
        self.assertEqual(despues.carga, 0)

    def test_residual_prevalece_la_accion_mas_efectiva(self):
        ctx = ContextoTarea()
        angulos = {"tronco": 47.5, "cuello": 10, "piernas": 0, "brazo": 10, "antebrazo": 80}
        mejor = Efecto(angulos={"tronco": 0})
        menor = Efecto(angulos={"tronco": 32.5})
        a = simular(self.calc, angulos, ctx, [mejor, menor])
        b = simular(self.calc, angulos, ctx, [menor, mejor])
        self.assertEqual(a.segmentos["tronco"].puntaje, 1)
        self.assertEqual(a.final, b.final)  # el orden de las recomendaciones no importa

    def test_efecto_rechaza_campos_desconocidos(self):
        with self.assertRaises(ValueError):
            Efecto.model_validate({"carga": 0})
        with self.assertRaises(ValueError):
            simular(self.calc, {}, ContextoTarea(), [Efecto(modificadores={"inexistente": True})])

    def test_bandas_nom036(self):
        t = self.loader.get_nom036_tables()
        self.assertEqual(color_total(0, t), "verde")
        self.assertEqual(color_total(12, t), "amarillo")
        self.assertEqual(color_total(14, t), "rojo")
        self.assertEqual(color_total(22, t), "morado")


if __name__ == "__main__":
    unittest.main()
