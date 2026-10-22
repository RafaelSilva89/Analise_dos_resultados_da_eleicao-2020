"""Download e resumo de dados públicos complementares: TSE (eleições 2016, 2020 e 2024) e IBGE (SIDRA).

Os arquivos brutos do TSE são grandes (até 140 MB cada). Por isso, o notebook baixa, resume por município
e salva só as tabelas resumidas em Datasets/ (algumas centenas de KB), usadas nas análises e no app.
"""
import re
import unicodedata
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import numpy as np
import pandas as pd

URL_TSE = 'https://cdn.tse.jus.br/estatistica/sead/odsele/{tipo}/{tipo}_{ano}.zip'
URL_SIDRA = 'https://apisidra.ibge.gov.br/values/{consulta}'
ANOS = [2016, 2020, 2024]
ELEICAO_ORDINARIA = 2  # o TSE também publica eleições suplementares, que ficam de fora

SITUACOES_ELEITO = ['ELEITO', 'ELEITO POR QP', 'ELEITO POR MÉDIA']
SITUACOES_SEM_VOTACAO = ['#NULO', '#NULO#']  # candidatura indeferida, renúncia etc.

# Partidos que mudaram de nome ou se fundiram entre 2016 e 2024 recebem o nome mais recente,
# para que a comparação entre as eleições seja justa (ex.: DEM + PSL = UNIÃO, criado em 2022).
SUCESSAO_PARTIDOS = {
    'PMDB': 'MDB', 'PR': 'PL', 'PRB': 'REPUBLICANOS', 'PPS': 'CIDADANIA', 'PTN': 'PODE', 'PT do B': 'AVANTE',
    'PEN': 'PATRIOTA', 'PSDC': 'DC', 'PHS': 'PODE', 'PRP': 'PATRIOTA', 'PPL': 'PC do B', 'PC': 'PC do B',
    'DEM': 'UNIÃO', 'PSL': 'UNIÃO', 'PTB': 'PRD', 'PATRIOTA': 'PRD', 'PROS': 'SOLIDARIEDADE', 'SD': 'SOLIDARIEDADE',
    'PSC': 'PODE', 'PODEMOS': 'PODE', 'PMN': 'MOBILIZA', 'PTC': 'AGIR', 'PCdoB': 'PC do B',
}

# Colunas que mudaram de nome entre os anos nos arquivos do TSE
NOMES_ANTIGOS_TSE = {'QT_VAGAS': 'QT_VAGA'}

IDADES_60_MAIS = [93095, 93096, 93097, 93098, 49108, 49109, 60040, 60041, 6653]  # classificação 287 (Censo 2022)


def partido_atual(sigla):
    """Sigla do partido no nome mais recente (aplica fusões e mudanças de nome em sequência, ex.: PEN -> PATRIOTA -> PRD)."""
    while sigla in SUCESSAO_PARTIDOS:
        sigla = SUCESSAO_PARTIDOS[sigla]
    return sigla


# ----------------------------------------------------------------------------------- TSE
def baixar_tse(tipo, ano, pasta):
    """Baixa um arquivo do portal de dados abertos do TSE (se ainda não existir na pasta) e devolve o caminho."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f'{tipo}_{ano}.zip'
    if not destino.exists():
        urlretrieve(URL_TSE.format(tipo=tipo, ano=ano), destino)
    return destino


def ler_csv_tse(caminho_zip, colunas):
    """Lê o CSV nacional (_BRASIL.csv) de dentro do zip do TSE."""
    with zipfile.ZipFile(caminho_zip) as arquivo:
        nome = next(n for n in arquivo.namelist() if n.endswith('_BRASIL.csv'))
        dados = pd.read_csv(arquivo.open(nome), sep=';', encoding='latin-1',
                            usecols=lambda coluna: coluna in colunas or coluna in NOMES_ANTIGOS_TSE)
    return dados.rename(columns=NOMES_ANTIGOS_TSE)


def resumir_votacao(caminho_zip):
    """Eleitores, abstenção, brancos e nulos por município no 1º turno (eleição para prefeito)."""
    colunas = ['ANO_ELEICAO', 'CD_TIPO_ELEICAO', 'NR_TURNO', 'SG_UF', 'SG_UE', 'DS_CARGO', 'QT_APTOS',
               'QT_COMPARECIMENTO', 'QT_ABSTENCOES', 'QT_VOTOS_BRANCOS', 'QT_TOTAL_VOTOS_NULOS']
    votacao = ler_csv_tse(caminho_zip, colunas)
    votacao = votacao[(votacao['CD_TIPO_ELEICAO'] == ELEICAO_ORDINARIA) & (votacao['NR_TURNO'] == 1)
                      & (votacao['DS_CARGO'].str.upper() == 'PREFEITO')]
    resumo = (votacao.groupby(['ANO_ELEICAO', 'SG_UE', 'SG_UF'], as_index=False)
              [['QT_APTOS', 'QT_COMPARECIMENTO', 'QT_ABSTENCOES', 'QT_VOTOS_BRANCOS', 'QT_TOTAL_VOTOS_NULOS']].sum())
    resumo.columns = ['ano', 'codigo_tse', 'uf', 'aptos', 'comparecimento', 'abstencoes', 'votos_brancos',
                      'votos_nulos']
    return resumo


def ler_candidatos(caminho_zip):
    """Candidatos a prefeito e vereador das eleições ordinárias, com o partido no nome mais recente."""
    colunas = ['ANO_ELEICAO', 'CD_TIPO_ELEICAO', 'NR_TURNO', 'SG_UF', 'SG_UE', 'DS_CARGO', 'SG_PARTIDO',
               'DS_SIT_TOT_TURNO']
    cand = ler_csv_tse(caminho_zip, colunas)
    cand = cand[(cand['CD_TIPO_ELEICAO'] == ELEICAO_ORDINARIA)
                & cand['DS_CARGO'].str.upper().isin(['PREFEITO', 'VEREADOR'])]
    cand = cand.rename(columns={'ANO_ELEICAO': 'ano', 'NR_TURNO': 'turno', 'SG_UF': 'uf', 'SG_UE': 'codigo_tse',
                                'SG_PARTIDO': 'partido_original', 'DS_SIT_TOT_TURNO': 'situacao'})
    cand['cargo'] = cand['DS_CARGO'].str.lower()
    cand['partido'] = cand['partido_original'].map(partido_atual)
    return cand.drop(columns=['CD_TIPO_ELEICAO', 'DS_CARGO'])


def resumir_candidatos(cand, caminho_vagas):
    """Por município: candidatos a prefeito, candidatos a vereador e vagas de vereador (1º turno)."""
    no_1turno = cand[(cand['turno'] == 1) & ~cand['situacao'].isin(SITUACOES_SEM_VOTACAO)]
    contagem = no_1turno.pivot_table(index=['ano', 'codigo_tse'], columns='cargo', aggfunc='size', fill_value=0)
    contagem = contagem.rename(columns={'prefeito': 'candidatos_prefeito', 'vereador': 'candidatos_vereador'})

    vagas = ler_csv_tse(caminho_vagas, ['ANO_ELEICAO', 'CD_TIPO_ELEICAO', 'SG_UE', 'DS_CARGO', 'QT_VAGA'])
    vagas = vagas[(vagas['CD_TIPO_ELEICAO'] == ELEICAO_ORDINARIA) & (vagas['DS_CARGO'].str.upper() == 'VEREADOR')]
    vagas = vagas.rename(columns={'ANO_ELEICAO': 'ano', 'SG_UE': 'codigo_tse', 'QT_VAGA': 'vagas_vereador'})
    return contagem.join(vagas.set_index(['ano', 'codigo_tse'])['vagas_vereador']).reset_index()


def prefeitos_eleitos_final(cand):
    """Prefeito eleito em cada município, considerando o 2º turno e as decisões judiciais já registradas."""
    eleitos = cand[(cand['cargo'] == 'prefeito') & (cand['situacao'] == 'ELEITO')]
    # Quem venceu no 2º turno também aparece no 1º turno como "2º TURNO": fica a linha do turno decisivo
    eleitos = eleitos.sort_values('turno').drop_duplicates(['ano', 'codigo_tse'], keep='last')
    return eleitos[['ano', 'codigo_tse', 'uf', 'turno', 'partido_original', 'partido']].reset_index(drop=True)


def vereadores_por_partido(cand):
    """Candidatos e eleitos a vereador por ano, estado e partido (nome mais recente)."""
    vereadores = cand[(cand['cargo'] == 'vereador') & ~cand['situacao'].isin(SITUACOES_SEM_VOTACAO)]
    return (vereadores.assign(eleito=vereadores['situacao'].isin(SITUACOES_ELEITO))
            .groupby(['ano', 'uf', 'partido'], as_index=False)
            .agg(candidatos=('eleito', 'size'), eleitos=('eleito', 'sum')))


# ----------------------------------------------------------------------------------- IBGE
def consultar_sidra(consulta):
    """Consulta a API do SIDRA (IBGE) e devolve um DataFrame (a 1ª linha da resposta é o cabeçalho)."""
    dados = pd.read_json(URL_SIDRA.format(consulta=consulta))
    dados.columns = dados.iloc[0]
    dados = dados.iloc[1:].rename(columns={'Município (Código)': 'codigo_ibge', 'Valor': 'valor'})
    dados['codigo_ibge'] = dados['codigo_ibge'].astype(int)
    dados['valor'] = pd.to_numeric(dados['valor'], errors='coerce')  # "-" e "..." viram NaN
    return dados


def baixar_ibge():
    """Indicadores por município: população (2016, 2020, 2024), PIB per capita 2020, % urbana e % de idosos."""
    consulta_populacao = consultar_sidra('t/6579/n6/all/v/9324/p/2016,2020,2024')
    populacao = consulta_populacao.pivot_table(index='codigo_ibge', columns='Ano', values='valor')
    populacao.columns = [f'populacao_{ano}' for ano in populacao.columns]
    # "Laje - BA" -> nome e UF, usados para conferir os códigos IBGE da base do TSE
    nomes = consulta_populacao.drop_duplicates('codigo_ibge').set_index('codigo_ibge')['Município'].str.rsplit(' - ', n=1)
    populacao['nome_ibge'] = nomes.str[0]
    populacao['uf_ibge'] = nomes.str[1]

    pib = consultar_sidra('t/5938/n6/all/v/37/p/2020').set_index('codigo_ibge')['valor'] * 1000  # mil R$ -> R$

    situacao = consultar_sidra('t/202/n6/all/v/93/p/2010/c1/all').pivot_table(
        index='codigo_ibge', columns='Situação do domicílio', values='valor')

    # A API limita o tamanho de cada resposta: as faixas de idade são pedidas em blocos de 3
    blocos = [[100362]] + [IDADES_60_MAIS[i:i + 3] for i in range(0, len(IDADES_60_MAIS), 3)]
    idade = pd.concat(consultar_sidra(f"t/9514/n6/all/v/93/p/2022/c2/6794/c287/{','.join(map(str, bloco))}/c286/113635")
                      for bloco in blocos)
    eh_total = idade['Idade (Código)'].astype(int) == 100362
    total = idade[eh_total].set_index('codigo_ibge')['valor']
    idosos = idade[~eh_total].groupby('codigo_ibge')['valor'].sum()

    ibge = populacao.assign(
        pib_per_capita=pib / populacao['populacao_2020'],
        pct_urbana=situacao['Urbana'] / situacao['Total'],
        pct_idosos=idosos / total,
    )
    return ibge.reset_index()


# ----------------------------------------------------------------------------------- Painel
def normalizar_nome(nome):
    """'Santa Bárbara d'Oeste' -> 'SANTABARBARADOESTE' (sem acentos, espaços e pontuação)."""
    texto = unicodedata.normalize('NFKD', str(nome)).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'[^A-Z]', '', texto)


def corrigir_codigos_ibge(chave, ibge):
    """Corrige códigos IBGE trocados na base do TSE comparando os nomes dos municípios dentro de cada UF.

    Só troca o código quando o nome do TSE não bate com o nome do IBGE daquele código, mas bate com
    exatamente um outro município da mesma UF. Diferenças só de grafia (ex.: Itapagé x Itapajé) são mantidas.
    """
    nomes = ibge.assign(nome=ibge['nome_ibge'].map(normalizar_nome))
    codigo_por_nome = nomes.drop_duplicates(['uf_ibge', 'nome'], keep=False).set_index(['uf_ibge', 'nome'])['codigo_ibge']
    nome_do_codigo = nomes.set_index('codigo_ibge')['nome']

    chave = chave.copy()
    nome_tse = chave['municipio'].map(normalizar_nome)
    codigo_certo = pd.Series(list(zip(chave['uf'], nome_tse)), index=chave.index).map(codigo_por_nome)
    trocado = (nome_tse != chave['codigo_ibge'].map(nome_do_codigo)) & codigo_certo.notna()
    chave.loc[trocado, 'codigo_ibge'] = codigo_certo[trocado].astype(int)
    return chave, chave.loc[trocado, ['uf', 'municipio', 'codigo_ibge']]


def montar_painel(votacao, candidatos, ibge, municipios_2020):
    """Une TSE + IBGE em uma tabela com 1 linha por município e eleição (2016, 2020, 2024).

    municipios_2020: base de 2020 (codigo_tse, codigo_ibge, municipio e capital), usada para ligar TSE e IBGE.
    Cria a abstenção da eleição anterior e o número de eleitores por habitante.
    """
    chave = municipios_2020[['codigo_tse', 'codigo_ibge', 'uf', 'municipio', 'capital']].drop_duplicates('codigo_tse')
    chave, _ = corrigir_codigos_ibge(chave, ibge)
    chave = chave.drop(columns='uf')
    painel = (votacao.merge(candidatos, on=['ano', 'codigo_tse'], how='inner')
              .merge(chave, on='codigo_tse', how='inner')
              .merge(ibge, on='codigo_ibge', how='left'))
    painel = painel[painel['aptos'] > 0]
    painel['abstencao'] = painel['abstencoes'] / painel['aptos']
    painel['candidatos_por_vaga_vereador'] = painel['candidatos_vereador'] / painel['vagas_vereador']
    populacao_do_ano = np.select([painel['ano'] == ano for ano in ANOS],
                                 [painel[f'populacao_{ano}'] for ano in ANOS])
    painel['eleitores_por_habitante'] = painel['aptos'] / populacao_do_ano

    anterior = painel[['ano', 'codigo_tse', 'abstencao']].assign(ano=lambda t: t['ano'] + 4)
    painel = painel.merge(anterior.rename(columns={'abstencao': 'abstencao_anterior'}),
                          on=['ano', 'codigo_tse'], how='left')
    return (painel.drop(columns=[f'populacao_{ano}' for ano in ANOS] + ['nome_ibge', 'uf_ibge'])
            .sort_values(['ano', 'codigo_tse']))


def atualizar_bases(municipios_2020, pasta_bruta, pasta_saida):
    """Baixa TSE (2016, 2020, 2024) e IBGE, resume e salva 3 CSVs pequenos em `pasta_saida`.

    Os arquivos brutos do TSE (cerca de 300 MB) ficam em `pasta_bruta`, que não vai para o repositório.
    """
    pasta_saida = Path(pasta_saida)
    votacao = pd.concat(resumir_votacao(baixar_tse('detalhe_votacao_munzona', ano, pasta_bruta)) for ano in ANOS)
    candidatos = pd.concat(ler_candidatos(baixar_tse('consulta_cand', ano, pasta_bruta)) for ano in ANOS)
    resumo_candidatos = pd.concat(
        resumir_candidatos(candidatos[candidatos['ano'] == ano], baixar_tse('consulta_vagas', ano, pasta_bruta))
        for ano in ANOS)

    montar_painel(votacao, resumo_candidatos, baixar_ibge(), municipios_2020).to_csv(
        pasta_saida / 'painel_municipios_2016_2024.csv', index=False)
    prefeitos_eleitos_final(candidatos).to_csv(pasta_saida / 'prefeitos_eleitos_2016_2024.csv', index=False)
    vereadores_por_partido(candidatos).to_csv(pasta_saida / 'vereadores_partido_uf_2016_2024.csv', index=False)
