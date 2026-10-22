"""Testes das funções de src/. Rodar na raiz do projeto: pytest"""
import pandas as pd
import pytest

from src.dados_externos import corrigir_codigos_ibge, montar_painel, partido_atual, prefeitos_eleitos_final
from src.eleicao import (COLUNAS, bancada_do_prefeito, carregar_base, classificar_porte, pareto,
                         prefeitos_eleitos, resumo_partidos, situacao_prefeito, tabela_municipios)


def candidato(codigo, cargo, partido, eleito, vagas=1, comparecimento=900, abstencoes=100, municipio=None):
    """Uma linha no formato da base original do TSE (nomes de colunas em inglês)."""
    return {'uf': 'SP', 'type_id': 11 if cargo == 'prefeito' else 13, 'codigo_tse': codigo,
            'nome_municipio': municipio or f'CIDADE {codigo}', 'capital': 0, 'codigo_ibge': 3500000 + codigo,
            'job_count': vagas, 'elector_count': 's' if eleito else 'n', 'elector_presence': comparecimento,
            'absentees': abstencoes, 'nominal_votes': 800, 'blank_votes': 50, 'total_null_votes': 50,
            'null_votes': 50, 'technical_null_votes': 0, 'valid_votes': 800, 'nulled_votes': 0,
            'judically_nulled_votes': 0, 'vote_count': comparecimento, 'candidate_number': 10,
            'candidate_name': 'FULANO', 'candidate_coligation': partido, 'candidate_vice_name': '',
            'candidate_vote_destination': 'Válido', 'candidate_vote_count': 100, 'legend_votes': None,
            'job': cargo, 'main_party': partido}


@pytest.fixture
def base(tmp_path):
    """4 municípios: 1 com prefeito eleito, 1 com 2º turno, 1 sem resultado (sub judice) e 1 sem votos (adiada)."""
    linhas = [
        # Município 1: prefeito do MDB eleito; Câmara com 3 cadeiras (MDB 2, PT 1)
        candidato(1, 'prefeito', 'MDB', True), candidato(1, 'prefeito', 'PT', False),
        candidato(1, 'vereador', 'MDB', True, vagas=3), candidato(1, 'vereador', 'MDB', True, vagas=3),
        candidato(1, 'vereador', 'PT', True, vagas=3), candidato(1, 'vereador', 'PSD', False, vagas=3),
        # Município 2: dois candidatos marcados = 2º turno
        candidato(2, 'prefeito', 'PSDB', True, comparecimento=300_000, abstencoes=100_000),
        candidato(2, 'prefeito', 'PT', True, comparecimento=300_000, abstencoes=100_000),
        # Município 3: ninguém marcado = sub judice
        candidato(3, 'prefeito', 'PP', False), candidato(3, 'prefeito', 'PL', False),
        # Município 4: sem votos = eleição adiada
        candidato(4, 'prefeito', 'PP', False, comparecimento=0, abstencoes=0),
    ]
    caminho = tmp_path / 'base.csv'
    pd.DataFrame(linhas).to_csv(caminho)
    return carregar_base(caminho)


def test_carregar_base_traduz_colunas_e_cria_aptos(base):
    assert set(COLUNAS.values()) <= set(base.columns)
    assert base['eleito'].dtype == bool
    assert (base['aptos'] == base['comparecimento'] + base['abstencoes']).all()


def test_situacao_prefeito_separa_os_4_casos(base):
    situacao = situacao_prefeito(base)
    assert situacao.to_dict() == {1: 'Eleito no 1º turno', 2: '2º turno', 3: 'Indefinido (sub judice)',
                                  4: 'Eleição adiada'}


def test_prefeitos_eleitos_ignora_quem_foi_ao_segundo_turno(base):
    eleitos = prefeitos_eleitos(base)
    assert eleitos['codigo_tse'].tolist() == [1]
    assert eleitos['partido'].tolist() == ['MDB']


def test_tabela_municipios_calcula_taxas_e_exclui_eleicao_adiada(base):
    mun = tabela_municipios(base)
    assert 4 not in mun['codigo_tse'].values
    linha = mun[(mun['codigo_tse'] == 2)].iloc[0]
    assert linha['abstencao'] == pytest.approx(0.25)
    assert linha['porte'] == 'Mais de 200 mil'
    vereador = mun[(mun['codigo_tse'] == 1) & (mun['cargo'] == 'vereador')].iloc[0]
    assert vereador['candidatos_por_vaga'] == pytest.approx(4 / 3)


def test_classificar_porte_respeita_os_limites():
    porte = classificar_porte(pd.Series([10_000, 10_001, 200_000, 200_001]))
    assert porte.tolist() == ['Até 10 mil', '10 a 50 mil', '50 a 200 mil', 'Mais de 200 mil']


def test_pareto_soma_100_por_cento_e_ordena():
    tabela = pareto(pd.Series({'B': 1, 'A': 3}))
    assert tabela.index.tolist() == ['A', 'B']
    assert tabela['% acumulado'].iloc[-1] == pytest.approx(1.0)
    assert tabela['%'].tolist() == pytest.approx([0.75, 0.25])


def test_resumo_partidos_calcula_taxa_de_sucesso(base):
    resumo = resumo_partidos(base)
    assert resumo.loc['MDB', 'prefeitos_eleitos'] == 1
    assert resumo.loc['MDB', 'sucesso_vereador'] == pytest.approx(1.0)
    assert resumo.loc['PT', 'sucesso_prefeito'] == pytest.approx(0.0)  # ida ao 2º turno não conta como eleito


def test_bancada_do_prefeito(base):
    bancada = bancada_do_prefeito(base).iloc[0]
    assert bancada['cadeiras'] == 2
    assert bancada['% cadeiras'] == pytest.approx(2 / 3)
    assert bancada['maior_bancada_e_do_prefeito']


def test_partido_atual_aplica_fusoes_em_sequencia():
    assert partido_atual('PEN') == 'PRD'      # PEN -> PATRIOTA -> PRD
    assert partido_atual('DEM') == 'UNIÃO'
    assert partido_atual('PMDB') == 'MDB'
    assert partido_atual('PT') == 'PT'        # sem mudança


def test_prefeitos_eleitos_final_fica_com_o_turno_decisivo():
    cand = pd.DataFrame({
        'ano': [2020, 2020, 2020], 'codigo_tse': [1, 1, 2], 'uf': ['SP'] * 3, 'cargo': ['prefeito'] * 3,
        'turno': [1, 2, 1], 'situacao': ['ELEITO', 'ELEITO', 'NÃO ELEITO'],
        'partido_original': ['PSDB'] * 2 + ['PT'], 'partido': ['PSDB'] * 2 + ['PT'],
    })
    final = prefeitos_eleitos_final(cand)
    assert final[['codigo_tse', 'turno']].values.tolist() == [[1, 2]]


def test_montar_painel_cria_abstencao_anterior():
    votacao = pd.DataFrame({'ano': [2016, 2020], 'codigo_tse': [1, 1], 'uf': ['SP'] * 2, 'aptos': [1000, 1000],
                            'comparecimento': [900, 800], 'abstencoes': [100, 200], 'votos_brancos': [10, 10],
                            'votos_nulos': [10, 10]})
    candidatos = pd.DataFrame({'ano': [2016, 2020], 'codigo_tse': [1, 1], 'candidatos_prefeito': [2, 3],
                               'candidatos_vereador': [18, 27], 'vagas_vereador': [9, 9]})
    ibge = pd.DataFrame({'codigo_ibge': [3500001], 'populacao_2016': [1200], 'populacao_2020': [1250],
                         'populacao_2024': [1300], 'pib_per_capita': [20_000], 'pct_urbana': [0.5],
                         'pct_idosos': [0.2], 'nome_ibge': ['Cidade 1'], 'uf_ibge': ['SP']})
    municipios = pd.DataFrame({'codigo_tse': [1], 'codigo_ibge': [3500001], 'uf': ['SP'], 'municipio': ['CIDADE 1'],
                               'capital': [0]})
    painel = montar_painel(votacao, candidatos, ibge, municipios).set_index('ano')
    assert pd.isna(painel.loc[2016, 'abstencao_anterior'])
    assert painel.loc[2020, 'abstencao_anterior'] == pytest.approx(0.1)
    assert painel.loc[2020, 'eleitores_por_habitante'] == pytest.approx(1000 / 1250)
    assert painel.loc[2020, 'candidatos_por_vaga_vereador'] == pytest.approx(3)


def test_corrigir_codigos_ibge_troca_so_codigos_errados():
    ibge = pd.DataFrame({'codigo_ibge': [1, 2, 3], 'nome_ibge': ['Laje', 'Lajedão', 'Itapajé'],
                         'uf_ibge': ['BA', 'BA', 'CE']})
    chave = pd.DataFrame({'uf': ['BA', 'BA', 'CE'], 'municipio': ['LAJE', 'LAJEDÃO', 'ITAPAGÉ'],
                          'codigo_ibge': [2, 1, 3]})  # Laje e Lajedão trocados; Itapagé só muda a grafia
    corrigida, trocados = corrigir_codigos_ibge(chave, ibge)
    assert corrigida['codigo_ibge'].tolist() == [1, 2, 3]
    assert trocados['municipio'].tolist() == ['LAJE', 'LAJEDÃO']
