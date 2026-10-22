"""Leitura e indicadores da base do 1º turno das eleições municipais de 2020 (TSE)."""
import numpy as np
import pandas as pd

# Nomes originais (em inglês) -> nomes em português.
# Atenção: na base original a coluna `elector_count` NÃO é o número de eleitores, e sim a marcação
# "s"/"n" de candidato eleito. O número de eleitores aptos é comparecimento + abstenções.
COLUNAS = {
    'uf': 'uf',
    'type_id': 'tipo_eleicao',
    'codigo_tse': 'codigo_tse',
    'nome_municipio': 'municipio',
    'capital': 'capital',
    'codigo_ibge': 'codigo_ibge',
    'job_count': 'vagas',
    'elector_count': 'eleito',
    'elector_presence': 'comparecimento',
    'absentees': 'abstencoes',
    'nominal_votes': 'votos_nominais',
    'blank_votes': 'votos_brancos',
    'total_null_votes': 'votos_nulos',
    'null_votes': 'votos_nulos_eleitor',
    'technical_null_votes': 'votos_nulos_tecnicos',
    'valid_votes': 'votos_validos',
    'nulled_votes': 'votos_anulados',
    'judically_nulled_votes': 'votos_anulados_sub_judice',
    'vote_count': 'total_votos',
    'candidate_number': 'numero',
    'candidate_name': 'candidato',
    'candidate_coligation': 'coligacao',
    'candidate_vice_name': 'vice',
    'candidate_vote_destination': 'situacao_voto',
    'candidate_vote_count': 'votos',
    'legend_votes': 'votos_legenda',
    'job': 'cargo',
    'main_party': 'partido',
}

# Colunas que se repetem em todas as linhas de um mesmo município e cargo
COLUNAS_MUNICIPIO = ['uf', 'codigo_tse', 'municipio', 'capital', 'cargo', 'vagas', 'comparecimento', 'abstencoes',
                     'aptos', 'votos_brancos', 'votos_nulos', 'votos_anulados_sub_judice', 'total_votos']

LIMITE_SEGUNDO_TURNO = 200_000  # só municípios com mais de 200 mil eleitores podem ter 2º turno

REGIOES = {
    'Norte': ['AC', 'AM', 'AP', 'PA', 'RO', 'RR', 'TO'],
    'Nordeste': ['AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE'],
    'Centro-Oeste': ['GO', 'MS', 'MT'],
    'Sudeste': ['ES', 'MG', 'RJ', 'SP'],
    'Sul': ['PR', 'RS', 'SC'],
}
REGIAO_DA_UF = {uf: regiao for regiao, ufs in REGIOES.items() for uf in ufs}

# Variáveis do modelo de abstenção: todas conhecidas ANTES da votação, em 3 grupos
FEATURES_ELEICAO = ['uf', 'capital', 'log_aptos', 'candidatos_prefeito', 'candidatos_por_vaga_vereador']
FEATURES_IBGE = ['log_pib_per_capita', 'pct_urbana', 'pct_idosos', 'eleitores_por_habitante']
FEATURES_HISTORICO = ['abstencao_anterior']
FEATURES = FEATURES_ELEICAO + FEATURES_IBGE + FEATURES_HISTORICO


def carregar_base(caminho):
    """Lê o CSV, renomeia as colunas para português e cria `aptos` (eleitores aptos a votar)."""
    df = pd.read_csv(caminho, index_col=0).rename(columns=COLUNAS)
    df['eleito'] = df['eleito'].eq('s')
    df['aptos'] = df['comparecimento'] + df['abstencoes']
    return df


def situacao_prefeito(df):
    """Resultado da disputa para prefeito em cada município.

    Na base, os 2 candidatos que foram para o 2º turno também estão marcados com eleito = "s".
    - 1 marcado  -> "Eleito no 1º turno"
    - 2 marcados -> "2º turno"
    - nenhum     -> "Indefinido (sub judice)": a candidatura mais votada estava sendo julgada.
    - sem votos  -> "Eleição adiada": Macapá (AP) votou em dezembro por causa do apagão no Amapá.
    """
    prefeitos = df[df['cargo'] == 'prefeito']
    marcados = prefeitos.groupby('codigo_tse')['eleito'].sum()
    sem_votos = prefeitos.groupby('codigo_tse')['total_votos'].max() == 0
    situacao = pd.Series('Indefinido (sub judice)', index=marcados.index, name='situacao')
    situacao[marcados == 1] = 'Eleito no 1º turno'
    situacao[marcados == 2] = '2º turno'
    situacao[sem_votos] = 'Eleição adiada'
    return situacao


def prefeitos_eleitos(df):
    """Uma linha por prefeito eleito no 1º turno (exclui municípios com 2º turno ou sem resultado)."""
    situacao = situacao_prefeito(df)
    definidos = situacao[situacao == 'Eleito no 1º turno'].index
    return df[(df['cargo'] == 'prefeito') & df['eleito'] & df['codigo_tse'].isin(definidos)]


def tabela_municipios(df):
    """Uma linha por município e cargo, com as taxas de abstenção, brancos/nulos e concorrência.

    Municípios sem votos registrados (eleição adiada) ficam de fora, pois não têm taxas a calcular.
    """
    df = df[df['total_votos'] > 0]
    candidatos = df.groupby(['codigo_tse', 'cargo']).size().rename('candidatos')
    mun = (df.drop_duplicates(['codigo_tse', 'cargo'])[COLUNAS_MUNICIPIO]
           .join(candidatos, on=['codigo_tse', 'cargo']))
    mun['abstencao'] = mun['abstencoes'] / mun['aptos']
    mun['brancos_nulos'] = (mun['votos_brancos'] + mun['votos_nulos']) / mun['total_votos']
    mun['candidatos_por_vaga'] = mun['candidatos'] / mun['vagas']
    mun['porte'] = classificar_porte(mun['aptos'])
    return mun.reset_index(drop=True)


def classificar_porte(aptos):
    """Faixas de tamanho do município pelo número de eleitores aptos."""
    faixas = [0, 10_000, 50_000, LIMITE_SEGUNDO_TURNO, np.inf]
    rotulos = ['Até 10 mil', '10 a 50 mil', '50 a 200 mil', 'Mais de 200 mil']
    return pd.cut(aptos, bins=faixas, labels=rotulos)


def pareto(contagem):
    """Tabela de Pareto: quantidade, % do total e % acumulado (ordenada da maior para a menor)."""
    tabela = contagem.sort_values(ascending=False).to_frame('Quantidade')
    tabela['%'] = tabela['Quantidade'] / tabela['Quantidade'].sum()
    tabela['% acumulado'] = tabela['%'].cumsum()
    return tabela


def resumo_partidos(df):
    """Candidatos, eleitos e taxa de sucesso (eleitos / candidatos) por partido e cargo."""
    eleitos_prefeito = prefeitos_eleitos(df).groupby('partido').size()
    vereadores = df[df['cargo'] == 'vereador']
    resumo = pd.DataFrame({
        'candidatos_prefeito': df[df['cargo'] == 'prefeito'].groupby('partido').size(),
        'prefeitos_eleitos': eleitos_prefeito,
        'candidatos_vereador': vereadores.groupby('partido').size(),
        'vereadores_eleitos': vereadores[vereadores['eleito']].groupby('partido').size(),
    }).fillna(0).astype(int)
    resumo['sucesso_prefeito'] = resumo['prefeitos_eleitos'] / resumo['candidatos_prefeito']
    resumo['sucesso_vereador'] = resumo['vereadores_eleitos'] / resumo['candidatos_vereador']
    return resumo.sort_values('prefeitos_eleitos', ascending=False)


def bancada_do_prefeito(df):
    """Para cada prefeito eleito no 1º turno: quantas cadeiras o partido dele ganhou na Câmara Municipal."""
    prefeitos = prefeitos_eleitos(df)[['codigo_tse', 'uf', 'municipio', 'partido', 'aptos']]
    vereadores = df[(df['cargo'] == 'vereador') & df['eleito']]
    cadeiras = vereadores.groupby(['codigo_tse', 'partido']).size().rename('cadeiras').reset_index()
    total = cadeiras.groupby('codigo_tse')['cadeiras'].sum().rename('total_cadeiras')
    maior = cadeiras.groupby('codigo_tse')['cadeiras'].max().rename('maior_bancada')

    tabela = (prefeitos.merge(cadeiras, on=['codigo_tse', 'partido'], how='left')
              .join(total, on='codigo_tse').join(maior, on='codigo_tse'))
    tabela['cadeiras'] = tabela['cadeiras'].fillna(0).astype(int)
    tabela['% cadeiras'] = tabela['cadeiras'] / tabela['total_cadeiras']
    tabela['maior_bancada_e_do_prefeito'] = tabela['cadeiras'].eq(tabela['maior_bancada'])
    return tabela


def base_modelo(painel, ano=2020):
    """Uma linha por município da eleição `ano`, com as variáveis do modelo (FEATURES) e o alvo `abstencao`.

    painel: tabela com 1 linha por município e eleição (src.dados_externos.montar_painel).
    """
    base = painel[painel['ano'] == ano].set_index('codigo_tse')
    base = base.assign(log_aptos=np.log10(base['aptos']), log_pib_per_capita=np.log10(base['pib_per_capita']))
    return base[['municipio', 'aptos'] + FEATURES + ['abstencao']]
