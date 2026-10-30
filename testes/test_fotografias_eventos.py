"""A fotografia JSON-LD deve pertencer à ficha consultada."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from normalizar_eventos import extract_event_image


class FotografiasEventos(unittest.TestCase):
    url = 'https://clube.pt/eventos/serra'
    photo = 'https://clube.pt/fotos/serra.jpg'
    other = {'@type': 'Event', 'url': 'https://clube.pt/eventos/rio',
             'image': 'https://clube.pt/fotos/rio.jpg'}

    def html(self, *nodes):
        return ''.join('<script type="application/ld+json">' + json.dumps(node)
                       + '</script>' for node in nodes)

    def event(self, **fields):
        return {'@type': 'Event', 'url': self.url, 'image': self.photo, **fields}

    def test_escolhe_evento_certo_independentemente_da_ordem(self):
        for nodes in ([self.event(), self.other], [self.other, self.event()]):
            for html in (self.html(nodes), self.html({'@graph': nodes}), self.html(*nodes)):
                with self.subTest(html=html):
                    self.assertEqual(extract_event_image(html, self.url), self.photo)

    def test_evento_de_outra_ficha_nao_fornece_fotografia(self):
        self.assertIsNone(extract_event_image(self.html(self.other), self.url))

    def test_ambiguidades_nao_fornecem_fotografia(self):
        for nodes in ([self.event(url=''), self.other],
                      [self.event(url=''), self.event(url='')],
                      [self.event(), self.event(image=self.other['image'])]):
            with self.subTest(nodes=nodes):
                self.assertIsNone(extract_event_image(self.html(nodes), self.url))

    def test_unico_evento_sem_identificador_mantem_compatibilidade(self):
        self.assertEqual(extract_event_image(self.html(self.event(url='')), self.url), self.photo)

    def test_identificador_com_fragmento_e_barra_final(self):
        event = self.event(url='', **{'@id': self.url + '/#event'})
        self.assertEqual(extract_event_image(self.html([event, self.other]), self.url), self.photo)

    def test_sem_foto_propria_nao_usa_a_de_outro_evento(self):
        for image in (None, 'https://clube.pt/logo.png'):
            with self.subTest(image=image):
                self.assertIsNone(extract_event_image(
                    self.html([self.event(image=image), self.other]), self.url))

    def test_metadados_sociais_mantem_prioridade(self):
        html = '<meta property="og:image" content="/fotos/capa.jpg">' + self.html(self.event())
        self.assertEqual(extract_event_image(html, self.url), 'https://clube.pt/fotos/capa.jpg')

    def test_formatos_de_imagem_e_json_invalido(self):
        for image in ({'url': self.photo}, {'contentUrl': self.photo},
                      ['https://clube.pt/logo.png', self.photo]):
            with self.subTest(image=image):
                html = '<script type="application/ld+json">invalid</script>'
                html += self.html(self.event(image=image))
                self.assertEqual(extract_event_image(html, self.url), self.photo)


if __name__ == '__main__':
    unittest.main()
