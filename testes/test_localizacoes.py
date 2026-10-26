import pathlib
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from localizacoes import limpar_local, normalizar_local_evento
from normalizar_eventos import location_identity, invalidate_stale_coordinates

class TestePartidas(unittest.TestCase):
    def test_horarios_e_gps_nao_sao_local(self):
        testes={
            'Palácio Nacional de Sintra ( Palácio da Vila) Hora de Fim 23:00 (31-Out-2026) A hora de fim é a': 'Palácio Nacional de Sintra ( Palácio da Vila)',
            'Cabril (Pastelaria e Padaria de Cabril) 08h15 – Início da Etapa 16 da Grande Rota': 'Cabril (Pastelaria e Padaria de Cabril)',
            'Tourém (Localização': 'Tourém',
            'Cruz da Jogadas (junto à Rota das Faias - início do per': 'Cruz da Jogadas',
            'Posto de Turismo de Manteigas Coordenadas GPS Lat: N 40': 'Posto de Turismo de Manteigas',
            'Padaria Pitões, R. Outeiro 24, 5470-370 Pitões das Junias, Portugal': 'Padaria Pitões, R. Outeiro 24, 5470-370 Pitões das Junias, Portugal',
            'Regoufe, Arouca (Localização': 'Regoufe, Arouca',
        }
        for raw, expected in testes.items():
            with self.subTest(raw=raw):
                self.assertEqual(limpar_local(raw), expected)

    def test_locais_genericos_nao_se_tornam_moradas(self):
        self.assertIsNone(limpar_local('Parque de Merendas','Hike Land'))
        for raw in ('Horário INÍCIO: 10:00H FINAL: 16:00H Em frente ao café',
                    'Horário INÍCIO: 10:00H FINAL: 16:00H Estacionamento jun',
                    'Horário INÍCIO: 10:00H FINAL: 17:00H Junto ao cruzeiro'):
            with self.subTest(raw=raw):
                self.assertIsNone(limpar_local(raw,'Montanhas do Norte'))

    def test_finais_de_moradas_interrompidos(self):
        casos = {
            'Parque Desportivo Municipal de Mafra, R': 'Parque Desportivo Municipal de Mafra',
            'Entrada principal da Mesquita de Lisboa - Rua da Mesquita, n': 'Entrada principal da Mesquita de Lisboa - Rua da Mesquita',
            'Salinas do Samouco, Alcochete Hora de': 'Salinas do Samouco, Alcochete',
            'Largo do Chafariz de Dentro, Lisboa Coo': 'Largo do Chafariz de Dentro, Lisboa',
            'Junto à Igreja Matriz, Av': 'Junto à Igreja Matriz',
        }
        for raw, esperado in casos.items():
            with self.subTest(raw=raw):
                self.assertEqual(limpar_local(raw), esperado)

    def test_town_gps_invalido(self):
        e={'organizer':'RB Hiking & Trekking','start':'Tourém (Localização','town':'41°54’30','time':'09:00','url':'https://barbosa-trekking.pt/'}
        self.assertEqual(normalizar_local_evento(e),2)
        self.assertEqual(e['start'],'Tourém')
        self.assertEqual(e['town'],'Por confirmar')
        self.assertEqual(e['time'],'09:00')

    def test_mudanca_editorial_nao_descarta_gps(self):
        antigo={'start':'Posto de Turismo de Óbidos Coordenadas GPS Lat: 39.35','town':'Por confirmar','lat':39.35,'lon':-9.15,'verified':True}
        novo={'start':'Posto de Turismo de Óbidos','town':'Por confirmar','lat':39.35,'lon':-9.15,'verified':True}
        self.assertEqual(location_identity(antigo), location_identity(novo))
        self.assertFalse(invalidate_stale_coordinates(novo,antigo))
        self.assertEqual(novo['lat'],39.35)

if __name__=='__main__':unittest.main()
