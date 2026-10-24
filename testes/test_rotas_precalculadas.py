"""Testes offline: a cache não inventa GPS e só calcula rotas em falta."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import precalcular_rotas as rotas


class RotasTest(unittest.TestCase):
    def test_capitais_e_validade(self):
        self.assertEqual(len(rotas.CAPITAIS), 18)
        self.assertTrue(rotas.valid_gps({"lat": 40.6405, "lon": -8.6538, "verified": True, "start": "Aveiro"}))
        self.assertFalse(rotas.valid_gps({"lat": 40.6405, "lon": -8.6538, "start": "Aveiro"}))
        self.assertFalse(rotas.valid_gps({"lat": 40.6405, "lon": -8.6538, "verified": True, "start": "Por confirmar"}))
        self.assertFalse(rotas.valid_gps({"lat": 32.64, "lon": -16.9, "verified": True, "start": "Funchal"}))
        self.assertTrue(rotas.due(None, date(2026, 10, 25)))
        self.assertFalse(rotas.due({"km": 42.5, "minutes": 46, "updated": "2026-10-25"}, date(2026, 10, 25)))

    def test_deduplicar_e_retoma(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog = Path(folder) / "eventos.json"
            dest = Path(folder) / "rotas_precalculadas.json"
            e = {"id": "a", "date": "2026-11-01", "lat": 40.6405, "lon": -8.6538, "start": "Centro", "verified": True}
            catalog.write_text(json.dumps({"events": [e, {**e, "id": "b"}, {"date": "2026-11-01", "start": "Por confirmar"}]}))
            calls = []
            def fake_route(origin, point):
                calls.append(origin)
                return {"km": 42.5, "minutes": 44, "updated": "2026-10-25"}
            with patch.object(rotas, "CATALOGUE", catalog), patch.object(rotas, "OUTPUT", dest):
                first = rotas.build_cache(date(2026, 10, 25), budget=2, requester=fake_route)
                self.assertEqual(len(first["locations"]), 1)
                self.assertEqual(len(calls), 2)
                again = rotas.build_cache(date(2026, 10, 25), budget=2, requester=fake_route)
                self.assertEqual(len(calls), 4)
                self.assertEqual(len(again["locations"][rotas.coord_key(e["lat"], e["lon"])]["routes"]), 4)


if __name__ == "__main__":
    unittest.main()
