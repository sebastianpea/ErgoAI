"""
Pruebas del Motor RAG Estático en Memoria (Track 4 Jabil X-RAIC 2026).
Verifica:
1. Cero importación de motores de base de datos (sqlite3, drivers externos).
2. Recuperación exacta de las 8 condiciones de 16-PE30-6500-00023.pdf y NOM-036.
3. Desempeño ultrarrápido (< 5 ms por búsqueda).
4. Enriquecimiento de recomendaciones y endpoint API /rag/consultar.
"""

import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from backend.app.core_agent.ergo_agent import ErgoAIAgent
from backend.app.core_agent.in_memory_rag import InMemoryRAG
from backend.app.core_agent.knowledge_retriever import InMemoryNormativeRetriever
from backend.app.core_agent.llm_factory import LLMFactory
from backend.app.core_agent.models import RecomendacionErgonomica
from backend.app.core_ergonomics.generador_recomendaciones import generar
from backend.app.core_ergonomics.modelos import ContextoTarea
from backend.app.session_store.config_loader import NormativeConfigLoader
from backend.app.settings import CONFIG_DIR, JABIL_REGLAS_PATH
from backend.main import create_app


class TestInMemoryRAG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = NormativeConfigLoader(CONFIG_DIR)
        cls.config.validate_all()
        cls.jabil = cls.config.get_jabil_standards()
        cls.kb = cls.config.get_nom036_kb()
        cls.rag = InMemoryRAG(cls.jabil, cls.kb)
        cls.client = TestClient(create_app(sembrar=False))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_cero_base_de_datos(self):
        """Verifica que el RAG no importe sqlite3 ni motores de bases de datos."""
        modulos_prohibidos = ["sqlite3", "psycopg", "psycopg2", "redis", "chromadb"]
        for mod in modulos_prohibidos:
            self.assertNotIn(mod, sys.modules, f"Violación de regla: '{mod}' está importado en el entorno")

    def test_recuperacion_8_condiciones_oficiales_jabil(self):
        """Verifica que las 8 condiciones del manual de Jabil y NOM-036 se recuperen con precisión."""
        condiciones_esperadas = {
            "carga_individual_mayor_14kg": {
                "seccion": "Sección 6.4.1",
                "pagina": 12,
                "hoja_excel": "Levantamiento (1)",
                "layer": "Equipos",
                "moc": "MOC 16-HS80-8000-00021",
            },
            "restriccion_postural_alturas_verticales": {
                "seccion": "Sección 6.4.3 y 6.4.4",
                "pagina": 12,
                "hoja_excel": "Levantamiento (1) / Transporte (2) y Hoja EAWS",
                "layer": "Equipos",
            },
            "materiales_lejos_zonas_alcance": {
                "seccion": "Sección 7.2.2.2",
                "pagina": 21,
                "hoja_excel": "1 Mov - Sección A (Zonas de Alcance de Material)",
                "layer": "Mobiliario",
            },
            "altura_mesa_espacio_piernas_pies": {
                "seccion": "Sección 7.2.3 y 7.3.3",
                "pagina": 21,
                "hoja_excel": "1 Mov - Sección B y E (Antropometría y Accesibilidad)",
                "layer": "Mobiliario",
            },
            "trabajo_pie_prolongado_ley_silla": {
                "seccion": "Sección 7.2.1, 7.2.2 y 7.3.3.1",
                "pagina": 18,
                "layer": "Mobiliario",
            },
            "inspeccion_postura_conveyor": {
                "seccion": "Sección 7.3.3.2",
                "pagina": 23,
                "layer": "Equipos",
            },
            "pasillos_empuje_arrastre_amr": {
                "seccion": "Sección 7.1.1, 7.1.2, 7.1.3 y Anexo 10.2",
                "pagina": 15,
                "layer": "Pasillos",
            },
            "gobernanza_relayout_moc": {
                "seccion": "Sección 6.2.3, 6.3.12, 6.3.19 y Sección 8",
                "pagina": 4,
                "layer": "Servicios",
                "moc": "MOC 16-HS80-8000-00021 / 16-FS80-8000-00010",
            },
        }

        for cond, esperados in condiciones_esperadas.items():
            clausula = self.rag.recuperar_por_condicion(cond)
            self.assertIsNotNone(clausula, f"No se encontró la cláusula para condición: {cond}")
            self.assertEqual(clausula.seccion, esperados["seccion"])
            self.assertEqual(clausula.pagina, esperados["pagina"])
            self.assertEqual(clausula.layer_autocad, esperados["layer"])
            if "hoja_excel" in esperados:
                self.assertEqual(clausula.hoja_excel_jabil, esperados["hoja_excel"])
            if "moc" in esperados:
                self.assertEqual(clausula.tramite_moc, esperados["moc"])

    def test_desempeno_busqueda_en_milisegundos(self):
        """Verifica que la búsqueda léxica responda en menos de 5 milisegundos."""
        t0 = time.perf_counter()
        res = self.rag.buscar("límite 14 kg lifter asistencia mecánica", top_k=3)
        dt_ms = (time.perf_counter() - t0) * 1000

        self.assertLess(dt_ms, 5.0, f"Búsqueda lenta: {dt_ms:.2f} ms")
        self.assertGreater(len(res), 0)
        self.assertEqual(res[0].clausula.condicion, "carga_individual_mayor_14kg")

    def test_enriquecimiento_de_recomendaciones(self):
        """Verifica que generador_recomendaciones inyecte las citas de Jabil y NOM-036."""
        angulos = {"tronco": 45.0, "brazo": 65.0, "cuello": 25.0, "piernas": 10.0}
        ctx = ContextoTarea(carga_kg=16.0, agarre="regular", actividad=1)
        reba_cfg = self.config.get_reba_tables()

        recs = generar(angulos, ctx, "levantamiento", 9, reba_cfg, self.jabil, self.rag)
        r1 = next(r for r in recs if r["id"] == "R1")

        self.assertIn("justificacion_rag", r1)
        self.assertIn("16-PE30-6500-00023 Sección 6.4.1 (Pág. 12)", r1["justificacion_rag"])
        self.assertEqual(r1["layer_autocad"], "Equipos")
        self.assertEqual(r1["hoja_excel_jabil"], "Levantamiento (1)")
        self.assertEqual(r1["tramite_moc"], "MOC 16-HS80-8000-00021")

    def test_endpoint_api_rag_consultar(self):
        """Verifica el endpoint POST /rag/consultar."""
        payload = {"consulta": "Ley Silla descanso 5 minutos", "top_k": 2}
        r = self.client.post("/rag/consultar", json=payload)
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()

        self.assertGreater(data["total_coincidencias"], 0)
        self.assertLess(data["tiempo_ms"], 50.0)
        primer = data["resultados"][0]
        self.assertEqual(primer["condicion"], "trabajo_pie_prolongado_ley_silla")
        self.assertEqual(primer["layer_autocad"], "Mobiliario")
        self.assertIn("Ley Silla", primer["norma_vinculada"])


class TestErgoAgentCleanArchitecture(unittest.TestCase):
    """Pruebas unitarias de Clean Architecture: InMemoryNormativeRetriever, LLMFactory y ErgoAIAgent."""

    def test_in_memory_normative_retriever_search_tags(self):
        retriever = InMemoryNormativeRetriever(JABIL_REGLAS_PATH)
        self.assertGreater(len(retriever.knowledge_base), 0)
        texto = retriever.search(["carga", "peso", ">14kg"])
        self.assertIn("14.0 kg", texto)
        self.assertIn("16-PE30-6500-00023", texto)

    def test_llm_factory_agnostico_por_variable_entorno(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "OLLAMA",
                "MODEL_NAME": "qwen2.5",
                "OLLAMA_BASE_URL": "http://llm_engine:11434",
            },
        ), patch("backend.app.core_agent.llm_factory.socket.gethostbyname", return_value="127.0.0.1"), patch(
            "backend.app.core_agent.llm_factory.urllib.request.urlopen"
        ) as transporte:
            transporte.return_value.__enter__.return_value.read.return_value = (
                b'{"models": [{"name": "llama3.2:latest"}, {"name": "qwen2.5:7b"}]}'
            )
            llm = LLMFactory.get_llm()
            self.assertEqual(llm.__class__.__name__, "ChatOllama")
            self.assertTrue(llm.model.startswith("qwen2.5"))
            self.assertEqual(llm.model, "qwen2.5:7b")
            self.assertIn("11434", llm.base_url)
            self.assertEqual(llm.base_url, "http://llm_engine:11434")
            transporte.assert_called_once()
            self.assertEqual(transporte.call_args.args[0].full_url, "http://llm_engine:11434/api/tags")

        with self.assertRaises(ValueError):
            with patch.dict(os.environ, {"LLM_PROVIDER": "PROVEEDOR_INEXISTENTE"}):
                LLMFactory.get_llm()

    def test_ergo_agent_inyeccion_dependencias_y_json_output_parser(self):
        retriever = InMemoryNormativeRetriever(JABIL_REGLAS_PATH)
        respuesta_llm_simulada = json.dumps(
            {
                "jerarquia": "INGENIERIA",
                "titulo": "Instalar lifter y mesa elevadora hidráulica",
                "descripcion_tecnica": (
                    "Integrar asistencia mecánica tipo lifter de vacío para eliminar el "
                    "levantamiento manual de cajas de 18 kg desde el piso."
                ),
                "fundamento_normativo": (
                    "Estándar Jabil 16-PE30-6500-00023 Sección 6.4.1 (Pág. 12, límite de 14.0 kg) "
                    "y NOM-036-1-STPS-2018 Numeral 8.3 b) Tabla 1."
                ),
            },
            ensure_ascii=False,
        )
        fake_llm = FakeListChatModel(responses=[respuesta_llm_simulada])

        # Inyección de dependencias explícita en el constructor
        agente = ErgoAIAgent(llm=fake_llm, retriever=retriever)
        resultado = agente.evaluar_caso(
            anomalia="El operador manipula cajas de 18 kg desde el suelo flexionando el tronco a 48 grados.",
            reba_score=11,
            palabras_clave=["carga", "peso", ">14kg"],
        )

        validado = RecomendacionErgonomica.model_validate(resultado)
        self.assertEqual(validado.jerarquia, "INGENIERIA")
        self.assertEqual(
            set(resultado.keys()),
            {"jerarquia", "titulo", "descripcion_tecnica", "fundamento_normativo"},
        )

    def test_endpoint_generar_plan_ergoai_http(self):
        """Verifica la orquestación web: trigger del botón -> LLM LangChain -> tarjeta 'propuesta' (sin duplicar al repetir) -> bitácora."""
        import tempfile
        respuesta_simulada = json.dumps(
            {
                "jerarquia": "INGENIERIA",
                "titulo": "Implementar brazo asistido lifter en estación SMT",
                "descripcion_tecnica": "Instalar lifter articulado neumático para eliminar el levantamiento manual sobre 14 kg.",
                "fundamento_normativo": "Jabil 16-PE30-6500-00023 Sección 6.4.1 (Pág. 12) / NOM-036-1-STPS-2018.",
            },
            ensure_ascii=False,
        )
        fake_llm = FakeListChatModel(responses=[respuesta_simulada, respuesta_simulada])

        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(workspace_dir=Path(tmp), sembrar=True))
            with client, patch("backend.app.core_agent.llm_factory.LLMFactory.get_llm", return_value=fake_llm):
                # 1. Disparar el trigger HTTP del botón web dos veces seguidas
                res1 = client.post("/casos/C-001/generar-plan-ia", json={"usuario": "Dr. Auditor", "rol": "ergonomia"})
                self.assertEqual(res1.status_code, 200, res1.text)
                pendientes_1 = res1.json()["validacion"]["pendientes"]

                res2 = client.post("/casos/C-001/generar-plan-ia", json={"usuario": "Dr. Auditor", "rol": "ergonomia"})
                self.assertEqual(res2.status_code, 200, res2.text)
                data = res2.json()

                # 2. Verificar que no se acumulan duplicados pendientes y que actualiza la tarjeta con enriquecimiento RAG
                self.assertEqual(data["validacion"]["pendientes"], pendientes_1)
                self.assertEqual(len([r for r in data["recomendaciones"] if r["id"].startswith("AI")]), 0)
                tarjeta = data["recomendaciones"][0]
                self.assertEqual(tarjeta["nivel_control"], "ingenieria")
                self.assertEqual(tarjeta["estado"], "propuesta")
                self.assertIn("lifter", tarjeta["titulo"].lower())
                self.assertIn("16-PE30-6500-00023", tarjeta["referencia"])
                self.assertIsNotNone(tarjeta["justificacion_rag"])

                # 3. Verificar trazabilidad en la bitácora audit_trail
                res_bitacora = client.get("/bitacora?id_caso=C-001")
                self.assertEqual(res_bitacora.status_code, 200)
                eventos = [e for e in res_bitacora.json() if e["accion"] == "plan_ia_generado"]
                self.assertGreater(len(eventos), 0)
                self.assertEqual(eventos[-1]["usuario"], "Dr. Auditor")

    def test_ceguera_inducida_filtro_por_tipo_prueba(self):
        """
        Verifica que si el operador realiza un levantamiento, el RAG jamás entregue
        fragmentos de empuje de carros ni mantenimiento de llantas (y viceversa).
        """
        retriever = InMemoryNormativeRetriever(JABIL_REGLAS_PATH)

        # Caso 1: Levantamiento (1) intentando contaminar con keywords de carros/llantas
        ctx_lev = retriever.search(
            keywords=["carga", "ruedas", "mantenimiento", "carro"],
            tipo_prueba="Levantamiento (1)",
        )
        self.assertIn("14.0 kg", ctx_lev)
        self.assertNotIn("ruedas de poliuretano", ctx_lev)
        self.assertNotIn("mantenimiento preventivo", ctx_lev)

        # Caso 2: con auxiliar (5) intentando contaminar con keywords de lifter >14kg
        ctx_aux = retriever.search(
            keywords=["ruedas", "mantenimiento", ">14kg", "lifter"],
            tipo_prueba="con auxiliar (5)",
        )
        self.assertIn("ruedas de poliuretano", ctx_aux)
        self.assertNotIn("manipulador ingrávido", ctx_aux)

    def test_patron_strategy_nom036_calculo_aislado(self):
        """
        Verifica el Patrón Strategy en nom036_calculator.py para las 5 pruebas de
        16-PE80-6500-00014-H.xlsm: Levantamiento (1), Transporte (2), Equipo (3),
        sin auxiliar (4) y con auxiliar (5).
        """
        from backend.app.core_ergonomics.nom036_calculator import EnrutadorNom036
        from backend.app.session_store import NormativeConfigLoader
        from backend.app.settings import CONFIG_DIR

        tablas = NormativeConfigLoader(CONFIG_DIR).get_nom036_tables()

        # 1. Transporte (2): evalúa carga asimétrica sobre torso y distancia de transporte
        res_transporte = EnrutadorNom036.evaluar(
            "Transporte (2)",
            {
                "carga_kg": 16.0,
                "brazo_grados": 35.0,
                "asimetria_torso": "un_hombro",
                "distancia_transporte_m": 15.0,
                "obstaculos_ruta": 1,
            },
            tablas,
        )
        self.assertEqual(res_transporte.hoja_excel, "Transporte (2)")
        etiquetas_tr = [f.etiqueta for f in res_transporte.factores]
        self.assertIn("Carga asimétrica sobre el torso", etiquetas_tr)
        self.assertIn("Distancia de transporte", etiquetas_tr)
        self.assertNotIn("Condición de mantenimiento del equipo auxiliar", etiquetas_tr)

        # 2. con auxiliar (5): evalúa tipo de equipo, 21 pts si es inaceptable y condición de mantenimiento
        res_aux = EnrutadorNom036.evaluar(
            "con auxiliar (5)",
            {
                "tipo_equipo": "1_2_ruedas",
                "carga_kg": 120.0,  # inaceptable para 1-2 ruedas -> 21 puntos
                "condicion_mantenimiento": "malo",  # 4 puntos
                "tronco_grados": 30.0,
            },
            tablas,
        )
        self.assertEqual(res_aux.hoja_excel, "con auxiliar (5)")
        factor_peso = next(f for f in res_aux.factores if f.codigo == "A")
        factor_mant = next(f for f in res_aux.factores if f.codigo == "F")
        self.assertEqual(factor_peso.valor, 21)
        self.assertEqual(factor_mant.valor, 4)
        self.assertEqual(res_aux.color, "morado")
        self.assertIn("Riesgo Muy Alto", res_aux.resumen_inmutable)


if __name__ == "__main__":
    unittest.main()
