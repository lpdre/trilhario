"""Regressões para datas, nomes, encontro e lotação nas fichas oficiais."""
import unittest

from bs4 import BeautifulSoup

from normalizar_eventos import (
    caminhando_end_date,
    parse_caminhando_card,
    parse_caminhando_detail,
    merge_exact_duplicates,
)
from recolher import extra_source_meta, parse_meta


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

    def test_late_gps_enrichment_merges_monsanto_with_manual_fallback(self):
        base = dict(id="web-monsanto", title="Caminhando por Trilhos e Miradouros de Monsanto - 11kms",
                    date="2026-11-01", time="09:30", organizer="Caminhando.pt",
                    url="https://caminhando.pt/eventos/caminhando-por-trilhos-e-miradouros-de-monsanto-9kms",
                    start="R. A, 1500-640 Lisboa (Parque de Estacionamento - Campolide Este)",
                    km=None, verified=False)
        old_fallback = dict(id="caminhando-monsanto-20261101", title=base["title"],
                    date=base["date"], time=base["time"], organizer=base["organizer"],
                    url=base["url"] + "/", start="Parque de estacionamento, entrada do Parque Florestal de Monsanto, Campolide",
                    km=11, verified=True, lat=38.736361111111115, lon=-9.172516666666667)
        # Na primeira passagem as designações diferentes impedem a fusão.
        self.assertEqual(len(merge_exact_duplicates([dict(base), dict(old_fallback)])), 2)
        # A página oficial confirma depois o mesmo GPS para ambas.
        base.update(verified=True, lat=38.73636111, lon=-9.17251667)
        merged = merge_exact_duplicates([base, old_fallback], preferred_ids={"web-monsanto"})
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "web-monsanto")
        self.assertEqual(merged[0]["km"], 11)
        self.assertIn("caminhando-monsanto-20261101", merged[0]["alias_ids"])

    def test_distinct_sessions_never_merge(self):
        a = dict(id="one", title="Caminhada Lisboa", date="2026-11-01",
                 time="09:00", organizer="Caminhando.pt", start="Parque",
                 url="https://caminhando.pt/eventos/caminhada-lisboa",
                 verified=True, lat=38.73636111, lon=-9.17251667)
        b = dict(a, id="two", time="15:00")
        self.assertEqual(len(merge_exact_duplicates([a, b])), 2)

    def test_explicit_distance_in_caminhando_title_is_retained(self):
        event = {
            "organizer": "Caminhando.pt",
            "title": "Caminhando por Trilhos e Miradouros de Monsanto - 11kms",
            "date": "2026-11-01",
            "url": "https://caminhando.pt/eventos/caminhando-por-trilhos-e-miradouros-de-monsanto-9kms",
            "km": None,
        }
        parse_meta(BeautifulSoup("<main>Trilhos em Monsanto.</main>", "html.parser"), event)
        self.assertEqual(event["km"], 11)

    def test_multiday_title_distance_is_not_taken_as_total(self):
        event = {"organizer":"Caminhando.pt",
                 "title":"Fim-de-semana na Serra - 11kms", "date":"2026-11-07",
                 "km":None, "multiDay":True}
        parse_meta(BeautifulSoup("<main>Dois dias de caminhadas.</main>","html.parser"),event)
        self.assertIsNone(event["km"])


if __name__ == "__main__":
    unittest.main()
