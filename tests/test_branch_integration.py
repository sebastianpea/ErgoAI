"""Router integration without models, seeded cases, or persistent workspace data."""
import io
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.app.services.casos import DatosInvalidos
from backend.app.vision.estimador import estimador


class TestBranchIntegration(unittest.TestCase):
    def test_backend_import_without_opencv(self):
        code = """
import sys
import logging
logging.disable(logging.CRITICAL)
sys.modules['cv2'] = None
from backend.main import create_app
from fastapi.testclient import TestClient
response = TestClient(create_app(sembrar=False)).get('/salud')
assert response.status_code == 200
assert response.json() == {'ok': True}
"""
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))

    def test_quick_analysis_rejects_invalid_context_without_side_effects(self):
        with tempfile.TemporaryDirectory(prefix='ergoai-quick-') as root:
            with TestClient(create_app(workspace_dir=Path(root), sembrar=False)) as client:
                before = {path: client.get(path).json() for path in ['/casos', '/metricas/dashboard', '/bitacora']}
                _, image = cv2.imencode('.jpg', np.zeros((32, 32, 3), np.uint8))
                with patch.object(estimador, 'analizar', return_value=SimpleNamespace(personas=0)) as analyze:
                    for data in [{'carga_kg': value} for value in ['-1', 'nan', 'inf', '-inf']] + [{'tipo_tarea': 'invalida'}]:
                        with self.subTest(data=data):
                            response = client.post('/vision/analizar-rapido', data=data, files={'foto': ('test.jpg', image.tobytes(), 'image/jpeg')})
                            self.assertEqual(response.status_code, 422, response.text)
                            detail = response.json()['detail']
                            self.assertIsInstance(detail, list)
                            field = next(iter(data))
                            self.assertEqual(detail[0]['loc'], ['body', field])
                    analyze.assert_not_called()
                self.assertEqual({path: client.get(path).json() for path in before}, before)

    def test_cli_no_person_returns_only_safe_pixels(self):
        from scripts import capturar_y_analizar as cli
        image = np.full((32, 32, 3), 199, np.uint8)
        with patch.object(estimador, 'analizar', return_value=SimpleNamespace(personas=0)):
            safe, detail = cli.analizar_fotografia(image)
        self.assertEqual(detail, {'ok': False, 'error': 'No se detectó ninguna persona en la imagen con suficiente claridad.'})
        self.assertEqual(safe.shape, image.shape)
        self.assertTrue(np.all(safe == 0))
        self.assertTrue(np.all(image == 199))

    def test_cli_detected_person_retains_reba_and_annotated_output(self):
        from scripts import capturar_y_analizar as cli
        from tests.test_vision import _resultado
        image = np.full((720, 1280, 3), 199, np.uint8)
        protected = image.copy()
        protected[:320] = 0
        with patch.object(estimador, 'analizar', return_value=_resultado(protected)):
            annotated, detail = cli.analizar_fotografia(image, carga_kg=10)
        self.assertTrue(detail['ok'])
        self.assertEqual(detail['personas'], 1)
        self.assertTrue(detail['rostro_anonimizado'])
        self.assertGreaterEqual(detail['reba_final'], 1)
        self.assertEqual(annotated.shape, image.shape)
        self.assertTrue(np.all(annotated[150:200, :100] == 0))
        self.assertTrue(np.all(image == 199))

    def test_legacy_report_returns_pdf_for_api_accept(self):
        with tempfile.TemporaryDirectory(prefix='ergoai-report-') as root:
            pdf = Path(root) / 'informe.pdf'
            pdf.write_bytes(b'%PDF-1.4 fixture')
            client = TestClient(create_app(workspace_dir=Path(root), sembrar=False))
            with patch('backend.app.api.routes_reports.PdfReportBuilder.build', return_value=pdf) as build:
                response = client.get('/casos/C-001/informe', headers={'Accept': 'application/pdf'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b'%PDF-1.4 fixture')
            self.assertEqual(response.headers['content-type'], 'application/pdf')
            self.assertEqual(response.headers['content-disposition'], 'attachment; filename="informe_C-001.pdf"')
            build.assert_called_once_with('C-001', 'casos_jabil_workspace/C-001/outputs/informe.pdf')

    def test_existing_list_dashboard_and_protected_media(self):
        app = create_app(sembrar=False)
        service = Mock()
        app.state.servicio = service
        service.listar.return_value = []
        service.dashboard.return_value = dict(total_casos=0)
        service.imagen_media_protegida.return_value = np.zeros((8, 8, 3), np.uint8)
        client = TestClient(app)
        response = client.get('/casos')
        self.assertEqual((response.status_code, response.json()), (200, []))
        response = client.get('/metricas/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total_casos'], 0)
        response = client.get('/media/C-001/lateral.jpg')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(response.headers['content-type'], 'image/png')
        self.assertTrue(response.content.startswith(b'\x89PNG'))
        service.imagen_media_protegida.assert_called_once_with('C-001', 'lateral.jpg')

    def test_additive_routes_and_public_contracts(self):
        app = create_app(sembrar=False)
        service = Mock()
        app.state.servicio = service
        client = TestClient(app)  # no lifespan: no workspace or model loading
        routes = [(method, route.path) for route in app.routes for method in getattr(route, 'methods', [])]
        self.assertEqual(len(routes), len(set(routes)))
        for path in ['/casos/pagina', '/metricas/dashboard', '/metricas/impacto', '/media/{id_caso}/{archivo}']:
            self.assertIn(('GET', path), routes)
        for extension, mime in [('excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'), ('pdf', 'application/pdf')]:
            exporter = getattr(service, 'exportar_' + extension)
            exporter.return_value = io.BytesIO(b'export fixture')
            response = client.get(f'/casos/C-001/exportar/{extension}')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.content, b'export fixture')
            self.assertEqual(response.headers['content-type'], mime)
            self.assertIn('attachment; filename=Informe_Ergonomico_C-001.', response.headers['content-disposition'])
            exporter.assert_called_once_with('C-001')
            exporter.side_effect = DatosInvalidos('Informe pendiente')
            response = client.get(f'/casos/C-001/exportar/{extension}')
            self.assertEqual((response.status_code, response.json()), (422, {'detail': 'Informe pendiente'}))
        for content, detail in [(b'', 'El archivo de fotografía está vacío.'), (b'invalid', 'Formato de imagen inválido. Se espera JPG o PNG.')]:
            response = client.post('/vision/analizar-rapido', files={'foto': ('test.jpg', content, 'image/jpeg')})
            self.assertEqual((response.status_code, response.json()), (422, {'detail': detail}))
        _, image = cv2.imencode('.jpg', np.zeros((32, 32, 3), np.uint8))
        with patch.object(estimador, 'analizar', return_value=SimpleNamespace(personas=0)):
            response = client.post('/vision/analizar-rapido', files={'foto': ('test.jpg', image.tobytes(), 'image/jpeg')})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertGreaterEqual(result.pop('tiempo_ms'), 0)
        self.assertEqual(result, dict(ok=False, personas=0, rostro_anonimizado=False, reba_final=0, reba_nivel='sin_dato', grupo_a=0, grupo_b=0, tabla_c=0, angulos=[], imagen_anotada_b64=None, advertencia='No se detectó a ninguna persona con suficiente claridad en la toma.'))
        self.assertEqual(service.method_calls, [unittest.mock.call.exportar_excel('C-001'), unittest.mock.call.exportar_excel('C-001'), unittest.mock.call.exportar_pdf('C-001'), unittest.mock.call.exportar_pdf('C-001')])
