"""Regressões para datas, nomes, encontro e lotação nas fichas oficiais."""
import unittest

from bs4 import BeautifulSoup

from normalizar_eventos import (
    caminhando_end_date,
    parse_caminhando_card,
    parse_caminhando_detail,
)
from recolher import extra_source_meta


ROTA = "Caminhando na Rota das Faias - Serra da Estrela"
URL = "https://caminhando.pt/eventos/caminhando-na-rota-das-faias-serra-da-estrela"
CALENDAR = (
    "(nov 7) 7:00 08 (nov 8) 19:30 " + ROTA
    + " 7:00 - 19:30 (8) Terminal Rodoviário Junto à Estação do Orient"
)
OFFICIAL_HTML = """
<main>
<h1>Caminhando na Rota das Faias - Serra da Estrela</h1>
<div>(nov 7) 7:00 08 (nov 8) 19:30 EVENTOLotado</div>
<h3>Horário</h3> 7 (Sábado) 7:00 - 8 (Domingo) 19:30
<h3>Ponto de Encontro</h3>
Terminal Rodoviário Junto à Estação do Oriente (PERTO DO AKI)
<h3>Detalhes do Evento</h3>
<p>Visita à Serra da Estrela, com atividades em 2 dias.</p>
</main>
"""


class CaminhandoMultidayRegressao(unittest.TestCase):
    def test_card_must_not_include_calendar_dates_in_title(self):
        event = parse_caminhando_card(CALENDAR, "2026-11-07")
        self.assertEqual(event["title"], ROTA)
        self.assertEqual(event["time"], "07:00")
        self.assertEqual(event["endTime"], "19:30")
        self.assertEqual(event["endDate"], "2026-11-08")
        self.assertTrue(event["multiDay"])
        self.assertNotIn("start", event)  # Morada truncada no cartão.

    def test_official_detail_has_meeting_point_and_sold_out(self):
        event = parse_caminhando_detail(OFFICIAL_HTML, URL, "2026-11-07")
        self.assertEqual(event["title"], ROTA)
        self.assertEqual(event["time"], "07:00")
        self.assertEqual(event["endDate"], "2026-11-08")
        self.assertEqual(event["endTime"], "19:30")
        self.assertIn("Terminal Rodoviário", event["start"])
        self.assertEqual(event["status"], "Esgotado")
        self.assertNotIn("duration", event)  # Não confundir horas entre dias.

    def test_collector_publishes_fixed_fields(self):
        event = {
            "organizer": "Caminhando.pt",
            "date": "2026-11-07",
            "url": URL,
            "title": CALENDAR,
            "time": "",
            "start": "Por confirmar",
            "town": "Por confirmar",
        }
        extra_source_meta(BeautifulSoup(OFFICIAL_HTML, "html.parser"),
                          event, "Caminhando.pt")
        self.assertEqual(event["title"], ROTA)
        self.assertEqual(event["time"], "07:00")
        self.assertEqual(event["status"], "Esgotado")
        self.assertTrue(event["multiDay"])
        self.assertIn("Oriente", event["start"])

    def test_related_events_do_not_mark_an_event_as_sold_out(self):
        html = OFFICIAL_HTML.replace("EVENTOLotado", "EVENTO")
        html += "<aside>Eventos relacionados ESGOTADO</aside>"
        event = parse_caminhando_detail(html, URL, "2026-11-07")
        self.assertEqual(event["status"], "")

    def test_last_day_across_month_and_year(self):
        self.assertEqual(caminhando_end_date("2026-11-30", 1), "2026-12-01")
        self.assertEqual(caminhando_end_date("2026-12-31", 1, "jan"), "2027-01-01")
        self.assertIsNone(caminhando_end_date("2026-11-07", 7, "nov"))

    def test_legacy_single_day_card_still_works(self):
        card = ("09:20 14:00 Caminhando à Descoberta da Ponta dos Corvos "
                "09:20 - 14:00 Rua do Rouxinol - Corroios")
        out = parse_caminhando_card(card, "2026-11-07")
        self.assertEqual(out["title"], "Caminhando à Descoberta da Ponta dos Corvos")
        self.assertEqual(out["time"], "09:20")
        self.assertEqual(out["duration"], 4.6667)

    def test_trekking_roots_meeting_point_differs_from_hike_destination(self):
        html = """<main>
          <h1>Rota das Faias e o Melhor do Outono de Manteigas</h1>
          <span>ESGOTADO</span>
          <h2>Descrição</h2>
          <p>Transporte do Porto e de Braga.</p>
          <h2>Coordenadas GPS</h2> 41.162813, -8.592803
        </main>"""
        event = {
            "organizer": "Trekking Roots",
            "start": "Manteigas",
            "town": "Manteigas",
        }
        extra_source_meta(BeautifulSoup(html, "html.parser"),
                          event, "Trekking Roots")
        self.assertEqual(event["start"], "Porto (ponto de encontro)")
        self.assertEqual(event["town"], "Manteigas")
        self.assertEqual(event["status"], "Esgotado")
        self.assertTrue(event["gpsFromAnnouncement"])


if __name__ == "__main__":
    unittest.main()
