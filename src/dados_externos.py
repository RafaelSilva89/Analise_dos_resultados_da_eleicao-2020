"""Download e resumo de dados públicos complementares: TSE (eleições 2012 a 2024), IBGE (SIDRA) e Covid-19.

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
ANO_ANTERIOR_A_2016 = 2012  # só a abstenção, para criar a "abstenção anterior" das linhas de 2016
URL_COVID = 'https://raw.githubusercontent.com/wcota/covid19br/master/cases-brazil-cities-time_2020.csv.gz'
VESPERA_ELEICAO_2020 = '2020-11-14'  # 1º turno em 15/11/2020
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


# ----------------------------------------------------------------------------------- Covid-19
def resumir_covid(covid, data_limite=VESPERA_ELEICAO_2020, dias_recentes=14):
    """Casos e óbitos acumulados por 100 mil habitantes até `data_limite` e casos dos últimos `dias_recentes` dias.

    covid: série diária acumulada por município (colunas date, ibgeID, totalCases_per_100k_inhabitants,
    deaths_per_100k_inhabitants), no formato do repositório wcota/covid19br.
    Municípios sem nenhum caso até a data não aparecem na série: ficam com zero no painel.
    """
    covid = covid[covid['ibgeID'] > 1_000_000].copy()  # tira totais nacionais/estaduais e casos sem município
    covid['date'] = pd.to_datetime(covid['date'])
    limite = pd.Timestamp(data_limite)

    def acumulado_ate(data):
        ate = covid[covid['date'] <= data].sort_values('date').groupby('ibgeID').last()
        return ate[['totalCases_per_100k_inhabitants', 'deaths_per_100k_inhabitants']]

    agora = acumulado_ate(limite)
    antes = acumulado_ate(limite - pd.Timedelta(days=dias_recentes)).reindex(agora.index, fill_value=0)
    resumo = pd.DataFrame({
        'casos_100k': agora['totalCases_per_100k_inhabitants'],
        'obitos_100k': agora['deaths_per_100k_inhabitants'],
        # correções retroativas da série podem deixar a diferença negativa: nesses casos, zero
        'casos_14d_100k': (agora['totalCases_per_100k_inhabitants']
                           - antes['totalCases_per_100k_inhabitants']).clip(lower=0),
    })
    return resumo.rename_axis('codigo_ibge').reset_index()


def baixar_covid(url=URL_COVID, data_limite=VESPERA_ELEICAO_2020):
    """Baixa a série de Covid-19 por município (2020) e resume até a véspera do 1º turno."""
    colunas = ['date', 'ibgeID', 'totalCases_per_100k_inhabitants', 'deaths_per_100k_inhabitants']
    return resumir_covid(pd.read_csv(url, usecols=colunas), data_limite)


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


def montar_painel(votacao, candidatos, ibge, municipios_2020, covid=None):
    """Une TSE + IBGE (+ Covid) em uma tabela com 1 linha por município e eleição (2016, 2020, 2024).

    votacao: pode trazer também 2012, usado só para a abstenção anterior das linhas de 2016.
    municipios_2020: base de 2020 (codigo_tse, codigo_ibge, municipio e capital), usada para ligar TSE e IBGE.
    covid: resumo de `resumir_covid`, ligado só às linhas de 2020 (municípios sem casos ficam com zero).
    Cria a abstenção da eleição anterior e o número de eleitores por habitante.
    """
    votacao = votacao[votacao['aptos'] > 0]
    anterior = votacao.assign(ano=votacao['ano'] + 4, abstencao_anterior=votacao['abstencoes'] / votacao['aptos'])
    totais = votacao.groupby('ano')[['abstencoes', 'aptos']].sum()
    nivel_nacional = totais['abstencoes'] / totais['aptos']
    votacao = votacao[votacao['ano'].isin(ANOS)]

    chave = municipios_2020[['codigo_tse', 'codigo_ibge', 'uf', 'municipio', 'capital']].drop_duplicates('codigo_tse')
    chave, _ = corrigir_codigos_ibge(chave, ibge)
    chave = chave.drop(columns='uf')
    painel = (votacao.merge(candidatos, on=['ano', 'codigo_tse'], how='inner')
              .merge(chave, on='codigo_tse', how='inner')
              .merge(ibge, on='codigo_ibge', how='left'))
    painel['abstencao'] = painel['abstencoes'] / painel['aptos']
    painel['candidatos_por_vaga_vereador'] = painel['candidatos_vereador'] / painel['vagas_vereador']
    populacao_do_ano = np.select([painel['ano'] == ano for ano in ANOS],
                                 [painel[f'populacao_{ano}'] for ano in ANOS])
    painel['eleitores_por_habitante'] = painel['aptos'] / populacao_do_ano

    painel = painel.merge(anterior[['ano', 'codigo_tse', 'abstencao_anterior']], on=['ano', 'codigo_tse'], how='left')
    # Nível nacional de cada eleição: o modelo multi-eleição aprende a diferença de cada município para ele
    painel['abstencao_nacional'] = painel['ano'].map(nivel_nacional)
    painel['abstencao_nacional_anterior'] = (painel['ano'] - 4).map(nivel_nacional)
    if covid is not None:
        painel = painel.merge(covid, on='codigo_ibge', how='left')
        colunas_covid = [c for c in covid.columns if c != 'codigo_ibge']
        eh_2020 = painel['ano'] == 2020
        painel.loc[eh_2020, colunas_covid] = painel.loc[eh_2020, colunas_covid].fillna(0)
        painel.loc[~eh_2020, colunas_covid] = np.nan
    return (painel.drop(columns=[f'populacao_{ano}' for ano in ANOS] + ['nome_ibge', 'uf_ibge'])
            .sort_values(['ano', 'codigo_tse']))


def atualizar_bases(municipios_2020, pasta_bruta, pasta_saida):
    """Baixa TSE (2012 a 2024), IBGE e Covid-19, resume e salva 3 CSVs pequenos em `pasta_saida`.

    Os arquivos brutos do TSE (cerca de 300 MB) ficam em `pasta_bruta`, que não vai para o repositório.
    """
    pasta_saida = Path(pasta_saida)
    votacao = pd.concat(resumir_votacao(baixar_tse('detalhe_votacao_munzona', ano, pasta_bruta))
                        for ano in [ANO_ANTERIOR_A_2016] + ANOS)
    candidatos = pd.concat(ler_candidatos(baixar_tse('consulta_cand', ano, pasta_bruta)) for ano in ANOS)
    resumo_candidatos = pd.concat(
        resumir_candidatos(candidatos[candidatos['ano'] == ano], baixar_tse('consulta_vagas', ano, pasta_bruta))
        for ano in ANOS)

    montar_painel(votacao, resumo_candidatos, baixar_ibge(), municipios_2020, covid=baixar_covid()).to_csv(
        pasta_saida / 'painel_municipios_2016_2024.csv', index=False)
    prefeitos_eleitos_final(candidatos).to_csv(pasta_saida / 'prefeitos_eleitos_2016_2024.csv', index=False)
    vereadores_por_partido(candidatos).to_csv(pasta_saida / 'vereadores_partido_uf_2016_2024.csv', index=False)
