"""App Streamlit: painel das eleições municipais (1º turno de 2020, com 2016 e 2024) e simulador de abstenção."""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

RAIZ = Path(__file__).resolve().parent
sys.path.append(str(RAIZ))
from src.eleicao import base_modelo  # noqa: E402

st.set_page_config(page_title='Eleições municipais 2020', page_icon='🗳️', layout='wide')


@st.cache_data
def carregar_dados():
    pasta = RAIZ / 'Datasets'
    municipios = pd.read_csv(pasta / 'municipios.csv')
    eleitos = pd.read_csv(pasta / 'eleitos.csv')
    painel = pd.read_csv(pasta / 'painel_municipios_2016_2024.csv')
    prefeitos_final = pd.read_csv(pasta / 'prefeitos_eleitos_2016_2024.csv')
    with open(pasta / 'uf.json', encoding='utf-8') as arquivo:
        mapa_uf = json.load(arquivo)
    return municipios, eleitos, painel, prefeitos_final, mapa_uf


@st.cache_resource
def carregar_modelos():
    pasta = RAIZ / 'Model'
    return joblib.load(pasta / 'modelo_abstencao.pkl'), joblib.load(pasta / 'modelo_abstencao_multieleicao.pkl')


def pct(valor):
    return f'{valor:.1%}'.replace('.', ',')


def milhar(valor):
    return f'{valor:,.0f}'.replace(',', '.')


municipios, eleitos, painel, prefeitos_final, mapa_uf = carregar_dados()
artefato, artefato_multi = carregar_modelos()
modelo = artefato['modelo']
prefeito = municipios[municipios['cargo'] == 'prefeito']
base_2020 = base_modelo(painel, 2020)

st.title('🗳️ Eleições municipais 2020: 1º turno')
st.caption('Dados abertos do TSE e do IBGE · 5.566 municípios com eleição para prefeito · '
           'Projeto de portfólio de Rafael R. Silva')

aba_painel, aba_municipio, aba_evolucao, aba_simulador = st.tabs(
    ['📊 Painel', '🏙️ Município', '📈 2016 → 2024', '🔮 Simulador de abstenção'])

# ----------------------------------------------------------------------------- Painel
with aba_painel:
    uf = st.selectbox('Região', ['Brasil'] + sorted(prefeito['uf'].unique()), key='uf_painel')
    filtro_mun = prefeito if uf == 'Brasil' else prefeito[prefeito['uf'] == uf]
    situacao_ok = filtro_mun.loc[filtro_mun['situacao'] == 'Eleito no 1º turno', 'codigo_tse']
    eleitos_uf = eleitos[eleitos['codigo_tse'].isin(filtro_mun['codigo_tse'])]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Municípios', milhar(len(filtro_mun)))
    col2.metric('Eleitores aptos', milhar(filtro_mun['aptos'].sum()))
    col3.metric('Abstenção', pct(filtro_mun['abstencoes'].sum() / filtro_mun['aptos'].sum()))
    col4.metric('Brancos + nulos (prefeito)',
                pct((filtro_mun['votos_brancos'] + filtro_mun['votos_nulos']).sum() / filtro_mun['total_votos'].sum()))

    st.caption('Situação da disputa para prefeito no 1º turno: '
               + ' · '.join(f'{k}: {v}' for k, v in filtro_mun['situacao'].value_counts().items()))

    # Mapa interativo por estado
    indicador = st.radio('Indicador do mapa', ['Abstenção', 'Brancos + nulos (prefeito)', 'Partido com mais prefeitos'],
                         horizontal=True)
    por_uf = prefeito.groupby('uf')[['abstencoes', 'aptos', 'votos_brancos', 'votos_nulos', 'total_votos']].sum()
    por_uf['Abstenção'] = por_uf['abstencoes'] / por_uf['aptos']
    por_uf['Brancos + nulos (prefeito)'] = (por_uf['votos_brancos'] + por_uf['votos_nulos']) / por_uf['total_votos']
    final_2020 = prefeitos_final[prefeitos_final['ano'] == 2020]
    por_uf['Partido com mais prefeitos'] = final_2020.groupby('uf')['partido_original'].agg(
        lambda s: s.value_counts().index[0])
    por_uf = por_uf.reset_index()

    opcoes_mapa = dict(geojson=mapa_uf, locations='uf', featureidkey='properties.UF_05', color=indicador,
                       hover_name='uf', fitbounds='locations', height=520)
    if indicador == 'Partido com mais prefeitos':
        figura = px.choropleth(por_uf, **opcoes_mapa)
    else:
        figura = px.choropleth(por_uf, color_continuous_scale='YlOrRd', hover_data={indicador: ':.1%'}, **opcoes_mapa)
        figura.update_coloraxes(colorbar_tickformat='.0%')
    figura.update_geos(visible=False)
    figura.update_layout(margin={'l': 0, 'r': 0, 't': 0, 'b': 0})
    st.plotly_chart(figura, width='stretch')
    st.caption('"Partido com mais prefeitos" usa o resultado final de 2020 (inclui o 2º turno). '
               'O DF não tem eleição municipal.')

    col_a, col_b = st.columns(2)
    prefeitos_partido = (eleitos_uf[(eleitos_uf['cargo'] == 'prefeito') & eleitos_uf['codigo_tse'].isin(situacao_ok)]
                         ['partido'].value_counts().head(10))
    vereadores_partido = eleitos_uf[eleitos_uf['cargo'] == 'vereador']['partido'].value_counts().head(10)
    col_a.subheader('Prefeitos eleitos no 1º turno (top 10)')
    col_a.bar_chart(prefeitos_partido, horizontal=True, color='#1F4E79')
    col_b.subheader('Vereadores eleitos (top 10)')
    col_b.bar_chart(vereadores_partido, horizontal=True, color='#C0392B')

# ----------------------------------------------------------------------------- Município
with aba_municipio:
    col_uf, col_cidade = st.columns([1, 3])
    uf_mun = col_uf.selectbox('Estado', sorted(prefeito['uf'].unique()), key='uf_mun')
    cidades = prefeito[prefeito['uf'] == uf_mun].sort_values('municipio')
    nome = col_cidade.selectbox('Município', cidades['municipio'])
    cidade = cidades[cidades['municipio'] == nome].iloc[0]
    codigo = cidade['codigo_tse']

    st.subheader(f"{nome} ({uf_mun}) · {cidade['situacao']}")
    eleitos_cidade = eleitos[eleitos['codigo_tse'] == codigo]
    candidatos_prefeito = eleitos_cidade[eleitos_cidade['cargo'] == 'prefeito'].sort_values('votos', ascending=False)
    final = prefeitos_final[(prefeitos_final['ano'] == 2020) & (prefeitos_final['codigo_tse'] == codigo)]

    if cidade['situacao'] == 'Eleito no 1º turno':
        eleito = candidatos_prefeito.iloc[0]
        st.success(f"Prefeito eleito: **{eleito['candidato']}** ({eleito['partido']}) com {milhar(eleito['votos'])} votos")
    elif cidade['situacao'] == '2º turno':
        nomes = ' x '.join(f"**{c['candidato']}** ({c['partido']})" for _, c in candidatos_prefeito.iterrows())
        vencedor = f" · Venceu no 2º turno: **{final['partido_original'].iloc[0]}**" if len(final) else ''
        st.info(f'Foram para o 2º turno: {nomes}{vencedor}')
    else:
        resultado = (f"Depois do julgamento, o TSE registrou como eleito o candidato do "
                     f"**{final['partido_original'].iloc[0]}**." if len(final)
                     else 'Não há prefeito eleito registrado na eleição ordinária (o cargo foi decidido em eleição suplementar).')
        st.warning(f'Resultado indefinido no 1º turno (candidatura sub judice). {resultado}')

    if codigo in base_2020.index:
        linha = base_2020.loc[[codigo]]
        esperada = modelo.predict(linha[artefato['features']])[0]
        col1, col2, col3 = st.columns(3)
        col1.metric('Eleitores aptos', milhar(cidade['aptos']))
        col2.metric('Abstenção real', pct(cidade['abstencao']),
                    delta=f"{(cidade['abstencao'] - esperada) * 100:+.1f}".replace('.', ',') + ' p.p. vs esperado',
                    delta_color='inverse')
        col3.metric('Abstenção esperada pelo modelo', pct(esperada))
        st.caption('O modelo foi treinado com quase todos os municípios, incluindo este; a comparação é ilustrativa.')

        historico = painel[painel['codigo_tse'] == codigo].set_index('ano')['abstencao']
        st.write('**Abstenção nas 3 eleições municipais:** '
                 + ' · '.join(f'{ano}: {pct(valor)}' for ano, valor in historico.items()))

    camara = eleitos_cidade[eleitos_cidade['cargo'] == 'vereador']['partido'].value_counts()
    if len(camara):
        st.subheader(f'Composição da Câmara Municipal ({camara.sum()} cadeiras)')
        st.bar_chart(camara, horizontal=True, color='#1F4E79')

# ----------------------------------------------------------------------------- Evolução
with aba_evolucao:
    st.write('Prefeitos eleitos por partido (resultado final, com 2º turno). Partidos que se fundiram aparecem com o '
             'nome atual: **UNIÃO** = DEM + PSL, **PRD** = PTB + Patriota, **PODE** inclui o PSC.')
    evolucao = prefeitos_final.pivot_table(index='partido', columns='ano', aggfunc='size', fill_value=0)
    evolucao = evolucao.sort_values(2024, ascending=False).head(12)
    st.bar_chart(evolucao.rename(columns=str), stack=False, horizontal=True, height=520)

    nacional = painel.groupby('ano')[['abstencoes', 'aptos']].sum()
    colunas = st.columns(len(nacional))
    for coluna, (ano, linha) in zip(colunas, nacional.iterrows()):
        coluna.metric(f'Abstenção em {ano}', pct(linha['abstencoes'] / linha['aptos']))

# ----------------------------------------------------------------------------- Simulador
with aba_simulador:
    st.write('Informe o perfil de um município para estimar a **abstenção esperada**. '
             'Os valores iniciais são os do município típico (mediana).')
    tipo_modelo = st.radio('Modelo', ['Padrão de 2020', 'Próxima eleição (multi-eleição)'], horizontal=True,
                           help='O modelo multi-eleição foi treinado com 2016, 2020 e 2024 e recebe a abstenção '
                                'nacional esperada como cenário.')
    mediana = base_2020.median(numeric_only=True)
    col1, col2, col3 = st.columns(3)
    uf_sim = col1.selectbox('Estado', sorted(prefeito['uf'].unique()), key='uf_sim')
    aptos = col1.number_input('Eleitores aptos', min_value=1_000, max_value=9_000_000, value=20_000, step=1_000)
    capital = col1.checkbox('É capital do estado')
    candidatos = col2.slider('Candidatos a prefeito', 1, 20, 3)
    por_vaga = col2.slider('Candidatos a vereador por vaga', 1.0, 40.0, 8.0, step=0.5)
    anterior = col2.slider('Abstenção do município na eleição anterior', 0.0, 0.40,
                           float(round(mediana['abstencao_anterior'], 2)), step=0.01, format='%.2f')
    pib = col3.number_input('PIB per capita (R$)', min_value=3_000, max_value=500_000,
                            value=int(round(10 ** mediana['log_pib_per_capita'], -3)), step=1_000)
    urbana = col3.slider('Parcela da população urbana', 0.0, 1.0, float(round(mediana['pct_urbana'], 2)),
                         step=0.01, format='%.2f')
    idosos = col3.slider('Parcela da população com 60 anos ou mais', 0.05, 0.40,
                         float(round(mediana['pct_idosos'], 2)), step=0.01, format='%.2f')
    por_habitante = col3.slider('Eleitores por habitante', 0.3, 1.5,
                                float(round(mediana['eleitores_por_habitante'], 2)), step=0.01)

    entrada = pd.DataFrame([{'uf': uf_sim, 'capital': int(capital), 'log_aptos': np.log10(aptos),
                             'candidatos_prefeito': candidatos, 'candidatos_por_vaga_vereador': por_vaga,
                             'log_pib_per_capita': np.log10(pib), 'pct_urbana': urbana, 'pct_idosos': idosos,
                             'eleitores_por_habitante': por_habitante, 'abstencao_anterior': anterior}])
    if tipo_modelo == 'Padrão de 2020':
        escolhido = artefato
        previsao = modelo.predict(entrada[artefato['features']])[0]
    else:
        escolhido = artefato_multi
        nivel = st.slider('Abstenção nacional esperada na próxima eleição', 0.10, 0.30,
                          float(round(artefato_multi['nivel_ultima_eleicao'], 3)), step=0.005, format='%.3f',
                          help='Referências: 17,6% em 2016, 23,1% em 2020 e 21,7% em 2024.')
        # A abstenção anterior do município é comparada ao nível nacional da última eleição (2024)
        entrada['abstencao_anterior_relativa'] = anterior - artefato_multi['nivel_ultima_eleicao']
        previsao = artefato_multi['modelo'].predict(entrada[artefato_multi['features']])[0] + nivel
    st.metric('Abstenção esperada', pct(previsao))
    st.caption(f"Em 80% dos casos, a abstenção real ficou entre {pct(previsao + escolhido['erro_p10'])} e "
               f"{pct(previsao + escolhido['erro_p90'])} para um perfil como este.")

    media_uf = prefeito[prefeito['uf'] == uf_sim]
    st.caption(f"Para comparação: a abstenção em {uf_sim} foi de "
               f"{pct(media_uf['abstencoes'].sum() / media_uf['aptos'].sum())}.")
