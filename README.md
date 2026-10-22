# 🗳️ Análise dos Resultados das Eleições Municipais de 2020

**Quem ganhou, com que eficiência, como isso mudou de 2016 a 2024 e por que tanta gente deixou de votar.**

<div align="center">
<img src="Imagens/Capa.png" width="400px">
</div>

[![Testes](https://github.com/RafaelSilva89/Analise_dos_resultados_da_eleicao-2020/actions/workflows/testes.yml/badge.svg)](https://github.com/RafaelSilva89/Analise_dos_resultados_da_eleicao-2020/actions/workflows/testes.yml)

**Python · Pandas · GeoPandas · Scikit-learn · Gradient Boosting · API do IBGE · Pytest · GitHub Actions · Streamlit · CRISP-DM**

| 📊 Destaques | |
|---|---|
| Base | **518.675 candidaturas** de 2020 em **5.567 municípios** (TSE), mais as eleições de **2012 a 2024**, indicadores do **IBGE** e dados de **Covid-19** |
| Concentração | **5 partidos** elegeram **57%** dos prefeitos e **48%** dos vereadores em 2020 |
| Mudança | De 2016 para 2024, o **PSD** virou o maior partido (538 → **886** prefeitos) e o **PSDB** perdeu 2 de cada 3 prefeituras (799 → **271**) |
| Abstenção | **17,6%** (2016) → **23,1%** (2020, pandemia) → **21,7%** (2024); de **13,9%** nas cidades pequenas a **25,8%** nas grandes |
| Modelo | Estima a abstenção esperada de cada município com erro médio de **2,0 pontos percentuais** (explica **80%** das diferenças). Um modelo **multi-eleição** acerta 2024 com erro de **2,3 p.p.**, contra 3,4 do modelo de uma eleição só |
| Coligações | Quem concorreu sozinho a prefeito venceu **9%** das vezes; com 8 ou mais partidos na aliança, **67%** |
| Qualidade dos dados | A v2 corrigiu **erros da base original**: colunas com o nome errado, **114 candidatos do 2º turno** contados como eleitos e **7 códigos IBGE trocados** |
| Entrega | Notebook CRISP-DM, **19 testes automatizados** (rodando no GitHub Actions) e **app Streamlit** com mapa interativo, consulta por município, evolução 2016–2024 e simulador para a próxima eleição |

---

## 📑 Sumário

1. [Contexto do problema](#1-contexto-do-problema)
2. [Objetivo](#2-objetivo)
3. [Bases de dados](#3-bases-de-dados)
4. [Estrutura do projeto](#4-estrutura-do-projeto)
5. [Como executar](#5-como-executar)
6. [Etapas do projeto (CRISP-DM)](#6-etapas-do-projeto-crisp-dm)
7. [Principais descobertas da análise exploratória](#7-principais-descobertas-da-análise-exploratória)
8. [Construção do modelo de abstenção](#8-construção-do-modelo-de-abstenção)
9. [Resultado do modelo](#9-resultado-do-modelo)
10. [App interativo (Streamlit)](#10-app-interativo-streamlit)
11. [O que mudou da v1 para a v2](#11-o-que-mudou-da-v1-para-a-v2)
12. [Insights](#12-insights)
13. [Limites](#13-limites)
14. [Próximos passos](#14-próximos-passos)

---

## 1. Contexto do problema

<img src="Imagens/Capa2.png" width="150px" align="right">

A cada eleição, o **Tribunal Superior Eleitoral (TSE)** publica os resultados de todos os municípios do país. Em 2020, os brasileiros escolheram **prefeitos** (vence o mais votado) e **vereadores** (as cadeiras da Câmara são divididas conforme os votos de cada partido). Foi também a primeira eleição durante a **pandemia de Covid-19**, o que tornou a **abstenção**, ou seja, o eleitor que não vai votar, um dos temas centrais.

São centenas de milhares de registros que, bem analisados, respondem perguntas úteis para **partidos** (onde somos fortes? lançar mais candidatos compensa?), **órgãos eleitorais** (onde faltou mais gente do que o esperado?) e **imprensa e cidadãos** (quem ganhou, onde e com que força?).

## 2. Objetivo

> **Perguntas de negócio:**
> 1. Quais partidos mais elegeram, e o quanto esse resultado é **concentrado**?
> 2. Quais partidos foram mais **eficientes** (elegeram mais por candidato lançado)? **Alianças** maiores vencem mais?
> 3. Como **abstenção**, votos **brancos e nulos** e **concorrência** mudam com o tamanho da cidade, o estado e o perfil da população?
> 4. O partido que elege o prefeito costuma ter a **maior bancada** na Câmara Municipal?
> 5. Qual **abstenção é esperada** para um município, e quais cidades fugiram muito desse padrão?
> 6. Como os partidos e a abstenção **mudaram de 2016 para 2024**?

## 3. Bases de dados

**Base principal:** resultados do **1º turno de 2020** do [portal de dados abertos do TSE](https://dadosabertos.tse.jus.br/dataset/), reunidos em um único arquivo (`Datasets/clean_data.csv`, 80 MB). Cada linha é **um candidato**, e as informações do município (eleitores, comparecimento, brancos, nulos) se repetem em todas as linhas daquele município.

| Coluna original | Nome na v2 | Significado |
|---|---|---|
| `uf`, `nome_municipio`, `capital` | `uf`, `municipio`, `capital` | Estado, município e se é capital |
| `job` / `job_count` | `cargo` / `vagas` | Prefeito ou vereador / número de vagas |
| `elector_count` ⚠️ | `eleito` | **Não** é o número de eleitores: é a marcação **"s"/"n" de eleito** |
| `elector_presence` / `absentees` | `comparecimento` / `abstencoes` | Eleitores que votaram / que não votaram |
| *(criada)* | `aptos` | Eleitores aptos = comparecimento + abstenções |
| `blank_votes` / `total_null_votes` / `vote_count` | `votos_brancos` / `votos_nulos` / `total_votos` | Votos brancos, nulos e total do município |
| `candidate_name` / `main_party` / `candidate_vote_count` | `candidato` / `partido` / `votos` | Candidato, partido e votos recebidos |

O dicionário completo, com as 29 colunas, está no notebook (Fase 02, item 2.1).

**Bases complementares** (baixadas e resumidas pelo notebook com `ATUALIZAR_DADOS = True`):

| Arquivo | Fonte | Conteúdo |
|---|---|---|
| `painel_municipios_2016_2024.csv` | TSE + IBGE + Covid | 1 linha por município e eleição: eleitores, abstenção (e a da eleição anterior, desde 2012), nível nacional, candidatos, vagas, PIB per capita, % urbana, % de idosos e, em 2020, casos e óbitos de Covid |
| `prefeitos_eleitos_2016_2024.csv` | TSE | Prefeito eleito em cada município no **resultado final** (2º turno e julgamentos) |
| `vereadores_partido_uf_2016_2024.csv` | TSE | Candidatos e eleitos a vereador por eleição, estado e partido |

Os dados do IBGE vêm da API do SIDRA: população estimada (2016, 2020, 2024), PIB dos municípios (2020), população urbana (Censo 2010) e população com 60 anos ou mais (Censo 2022). Os dados de Covid-19 por município vêm do repositório público [wcota/covid19br](https://github.com/wcota/covid19br), até a véspera do 1º turno (14/11/2020). O arquivo `Datasets/uf.json` tem o contorno dos estados, usado nos mapas.

## 4. Estrutura do projeto

```
Analise_dos_resultados_da_eleicao-2020/
├── Datasets/
│   ├── clean_data.csv                         # base principal (TSE 2020, 1 linha por candidato)
│   ├── uf.json                                # contorno dos estados (mapas)
│   ├── painel_municipios_2016_2024.csv        # TSE + IBGE por município e eleição
│   ├── prefeitos_eleitos_2016_2024.csv        # resultado final para prefeito
│   ├── vereadores_partido_uf_2016_2024.csv    # vereadores por partido e estado
│   ├── municipios.csv                         # 2020: 1 linha por município e cargo (gerada no notebook)
│   └── eleitos.csv                            # 2020: candidatos eleitos (gerada no notebook)
├── Imagens/                                   # gráficos gerados pelos notebooks
├── Model/
│   ├── modelo_abstencao.pkl                   # modelo de 2020 + faixa de erro (usado pelo app)
│   ├── modelo_abstencao_multieleicao.pkl      # modelo multi-eleição para a próxima eleição
│   └── *.json                                 # fichas dos modelos (métricas, hiperparâmetros, avisos)
├── docs/
│   └── decisoes_analiticas.md                 # registro das decisões do projeto (DA-01 a DA-09)
├── reports/
│   ├── comparacao_modelos.csv                 # métricas dos 7 algoritmos na validação
│   └── erro_por_uf.csv                        # tradução do erro por estado
├── Notebooks/
│   ├── Análise dos resultados da eleição - 2020.ipynb        # versão original
│   └── Análise dos resultados da eleição - 2020 - v2.ipynb   # versão reorganizada (CRISP-DM)
├── src/
│   ├── eleicao.py                             # leitura, tabelas por município/partido e base do modelo
│   ├── dados_externos.py                      # download e resumo de TSE (2012–2024), IBGE e Covid-19
│   ├── selecao.py                             # seleção de variáveis (Random Forest + Informação Mútua)
│   ├── estatistica.py                         # testes das hipóteses (com tamanho de efeito) e regra do IQR
│   ├── avaliacao.py                           # ml_error, relatório de validação, comparação, tradução do erro e ficha
│   └── graficos.py                            # funções de gráficos
├── tests/
│   └── test_eleicao.py                        # 19 testes automatizados (pytest)
├── .github/workflows/testes.yml               # roda os testes a cada push (GitHub Actions)
├── app.py                                     # app Streamlit
├── pytest.ini
├── requirements.txt
└── README.md
```

## 5. Como executar

```bash
# 1. Clonar o repositório
git clone https://github.com/RafaelSilva89/Analise_dos_resultados_da_eleicao-2020.git
cd Analise_dos_resultados_da_eleicao-2020

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. Rodar os testes
pytest

# 4. Abrir o notebook e executar todas as células (gera as tabelas e o modelo usados pelo app)
jupyter notebook "Notebooks/Análise dos resultados da eleição - 2020 - v2.ipynb"

# 5. Abrir o app
streamlit run app.py
```

## 6. Etapas do projeto (CRISP-DM)

| Fase | O que foi feito |
|---|---|
| **01. Entendimento do negócio** | Definição das 6 perguntas e do público |
| **02. Preparação dos dados** | Correção do significado das colunas e dos códigos IBGE, outliers pela regra do IQR, tabelas por município e partido, EDA com 14 hipóteses (cada uma com teste estatístico e tamanho de efeito) |
| **03. Modelagem** | Divisão 60/20/20, seleção de variáveis, 7 algoritmos (uma seção cada) com validação cruzada, ajuste fino, faixa de erro, calibração e teste anti-vazamento |
| **04. Avaliação** | Erro no teste, **tradução do erro por estado**, municípios fora do padrão, variáveis mais importantes, **teste fora do tempo (2024)** e **modelo multi-eleição** |
| **05. Implantação** | Tabelas e modelo salvos, simulação de cenários e app Streamlit |

## 7. Principais descobertas da análise exploratória

### 🔎 Antes de tudo: entender o que a base diz

A primeira descoberta foi sobre a **própria base**:
- A coluna `elector_count` ("número de eleitores") tem só os valores **"s"** e **"n"**: é a marcação de **eleito**.
- Para prefeito, essa marcação também vale para os **2 candidatos que foram ao 2º turno**. Contando os marcados por município: **5.405** prefeitos eleitos no 1º turno, **57** municípios com 2º turno (todos acima de 200 mil eleitores, como manda a lei), **104** sem resultado por candidatura **sub judice** e **Macapá**, com eleição adiada pelo apagão no Amapá.
- **7 municípios** têm o **código IBGE trocado** (ex.: Laje-BA aponta para Lajedão). Sem corrigir, Laje apareceria com 5 eleitores por habitante.

### H1, H2 e H9: poucos partidos concentram o poder local

<div align="center">
<img src="Imagens/Pareto prefeitos eleitos por partido.png" width="800px">
</div>

**MDB, PP, PSD, PSDB e DEM** elegeram **57%** dos prefeitos e, na mesma ordem, **48%** dos vereadores. Com o **resultado final** (2º turno e julgamentos), o ranking não muda: o MDB vai de 775 para **793** prefeitos e também foi o que mais venceu no 2º turno (10 cidades).

### H10: de 2016 para 2024, o mapa partidário mudou

<div align="center">
<img src="Imagens/Prefeitos eleitos por partido 2016 2020 2024.png" width="750px">
</div>

Somando os partidos que se fundiram (DEM + PSL = **UNIÃO**, PTB + Patriota = **PRD**), o **PSD** saltou de 538 para **886** prefeitos e o **Republicanos** de 105 para 433. O **PSDB** caiu de 799 para **271**, e o **MDB** deixou de ser o maior partido (1.044 → 859).

### H3: lançar mais candidatos não garante eficiência

<div align="center">
<img src="Imagens/Taxa de sucesso para prefeito por partido.png" width="650px">
</div>

Em média, **29%** dos candidatos a prefeito venceram no 1º turno. O **PP** elegeu **46%** dos seus; o **PT** lançou **1.224** candidatos, quase tantos quanto o PSDB (1.273), e elegeu **179 (15%)**, contra **512** do PSDB.

### H4, H5, H6 e H11: quanto maior a cidade, mais gente falta, e a pandemia deixou marca

<div align="center">
<img src="Imagens/Abstencao 2016 2020 2024.png" width="750px">
</div>

| Eleitores no município | Abstenção 2020 (mediana) | Brancos + nulos para prefeito | Candidatos por vaga de vereador |
|---|---|---|---|
| Até 10 mil | **13,9%** | 4,1% | 4,4 |
| 10 a 50 mil | 20,1% | 5,5% | 8,3 |
| 50 a 200 mil | 24,1% | 9,3% | 17,7 |
| Mais de 200 mil | **25,8%** | **12,5%** | **26,4** |

A abstenção no Brasil foi de **17,6%** em 2016, subiu para **23,1%** em 2020 e caiu só para **21,7%** em 2024. Nas cidades grandes, ela praticamente não voltou.

### H14: alianças maiores vencem mais (mas não só por causa da aliança)

<div align="center">
<img src="Imagens/Coligacoes tamanho da alianca.png" width="750px">
</div>

Em 2020, as coligações eram permitidas só para prefeito. Quem concorreu **sozinho** venceu **9%** das vezes, bem abaixo da chance esperada (26%, se todos tivessem a mesma chance). Com **8 ou mais partidos**, a vitória chegou a **67%**. Os pares que mais venceram juntos foram **MDB + PP** (534 prefeituras) e **PP + PSD** (476). **Cautela:** as alianças grandes se formam em torno de quem já é favorito, então parte desse efeito é do candidato, não da aliança.

### H7: o partido do prefeito tem a maior bancada, mas não a maioria

Em **67%** dos municípios, o partido do prefeito eleito ficou com a **maior bancada** da Câmara (88,6% nas cidades com mais de 200 mil eleitores). Mas a mediana é de só **33% das cadeiras**: o prefeito quase sempre depende de **alianças**.

### H8 e H12: estado e urbanização pesam

<div align="center">
<img src="Imagens/Mapa da abstencao por UF.png" width="600px">
</div>

A abstenção vai de **15,4%** no Piauí a **28,1%** no Rio de Janeiro (**Nordeste 18,5%**, **Sudeste 26,3%**). Com os dados do IBGE, a **urbanização** é o indicador mais ligado à abstenção (de 13,5% nos municípios mais rurais a 22,6% nos mais urbanos); o efeito da renda é pequeno.

### H13: a Covid local quase não explica a abstenção

A correlação entre os óbitos de Covid por 100 mil habitantes até a véspera da eleição e a abstenção foi de só **0,17**, e os dados de Covid não melhoraram o modelo. A pandemia aumentou a abstenção **no país todo** (H11), mas os municípios mais atingidos não faltaram muito mais do que os outros: o efeito foi **geral**.

## 8. Construção do modelo de abstenção

**Pergunta:** *qual abstenção é esperada para um município, dado o seu perfil?* Com essa referência, dá para encontrar cidades onde faltou **muito mais (ou muito menos) gente do que o esperado** e investigar o motivo.

1. **10 variáveis conhecidas antes da eleição**, em 3 grupos:
   - **eleição:** estado, capital, número de eleitores (em log10), candidatos a prefeito e por vaga de vereador;
   - **IBGE:** PIB per capita, % de população urbana, % de idosos e eleitores por habitante;
   - **histórico:** abstenção do município na eleição anterior (2016).
2. **Sem "colar a resposta":** comparecimento, brancos e nulos ficaram de fora, pois são **resultados da própria votação** (*vazamento de dados*).
3. **Treino, validação e teste:** 60% dos municípios para treinar, 20% para comparar os algoritmos e ajustar (validação) e 20% guardados para o teste final. A comparação também usa **validação cruzada** (média ± desvio).
4. **Seleção de variáveis:** a relevância de cada coluna foi medida por **Random Forest** ("quais perguntas o modelo mais usou") e por **Informação Mútua** ("quanto a variável, sozinha, conta sobre a abstenção"). Os dois apontam a **abstenção anterior**, o **tamanho do município** e a **concorrência para vereador** como as mais relevantes. Como confirmação, cada grupo novo foi testado separadamente. O IBGE reduziu o erro de 2,77 para 2,62 p.p.; a abstenção anterior, para **2,02 p.p.** A Covid não ajudou (2,03 p.p.) e ficou de fora.
5. **7 algoritmos comparados**, cada um com a sua seção (métricas no padrão do projeto Rossmann: MAE, MAPE, RMSE e R², e erro no treino × validação para detectar sobreajuste), e **ajuste fino** do melhor (**HistGradientBoosting**):

| Algoritmo | MAE na validação | R² | MAE na validação cruzada |
|---|---|---|---|
| **HistGradientBoosting** ✅ | **1,98 p.p.** | **0,82** | **2,02 ± 0,04** |
| LightGBM | 2,00 p.p. | 0,82 | 2,03 ± 0,04 |
| XGBoost | 2,06 p.p. | 0,81 | 2,10 ± 0,04 |
| Random Forest | 2,08 p.p. | 0,80 | 2,10 ± 0,05 |
| Regressão Linear | 2,23 p.p. | 0,78 | 2,30 ± 0,04 |
| Lasso | 2,36 p.p. | 0,75 | 2,46 ± 0,08 |
| Média (referência) | 4,93 p.p. | 0,00 | 5,04 ± 0,15 |

<div align="center">
<img src="Imagens/Comparacao de modelos.png" width="650px">
</div>

6. **Faixa de erro:** em vez de um limiar (que só faz sentido em classificação), medimos o quanto a previsão costuma errar. Em 80% dos municípios, a abstenção real fica entre **3,2 p.p. abaixo e 2,9 p.p. acima** da prevista.
7. **Teste anti-vazamento:** com a taxa de comparecimento como entrada, o erro "cairia" para **0,04 p.p.** (R² de 0,999), porque ela é 1 − abstenção. Por isso o modelo usa só informações conhecidas **antes** da eleição.

> 💡 **Analogia:** o modelo funciona como um "termômetro de referência". Ele diz qual seria a abstenção normal para uma cidade com aquele histórico, tamanho e perfil. Quando a abstenção real foge muito disso, vale investigar.

## 9. Resultado do modelo

| Métrica | Prever sempre a média | Modelo final (teste 2020) | Modelo de 2020 aplicado a 2024 | **Modelo multi-eleição em 2024** |
|---|---|---|---|---|
| Erro médio (MAE) | 4,89 p.p. | **2,02 p.p.** | 3,42 p.p. | **2,27 p.p.** |
| R² (quanto das diferenças é explicado) | 0% | **80%** | 40% | **73%** |
| Viés médio | — | +0,1 p.p. | +2,8 p.p. | −0,5 p.p. |
| Ordenação dos municípios (Spearman) | — | **0,89** | 0,86 | 0,85 |

**Em linguagem de negócio:** se o modelo prevê 20% de abstenção para uma cidade, o erro típico é de 2 pontos para cima ou para baixo, e em 80% dos casos a abstenção real fica entre 16,8% e 22,9%. Ele é **bem calibrado** em todas as faixas.

**Tradução do erro por estado:** o modelo é mais preciso no Amazonas (erro médio de 1,1 p.p.), Rio de Janeiro (1,4) e São Paulo (1,5) e menos preciso no Maranhão (2,8) e em Rondônia (2,7). Em São Paulo, a abstenção prevista é de 22,0%, com melhor cenário de 20,5% e pior de 23,5%.

<div align="center">
<img src="Imagens/Traducao do erro.png" width="850px">
</div>

<div align="center">
<img src="Imagens/Importancia das variaveis.png" width="650px">
</div>

A **abstenção da eleição anterior** é, de longe, o que mais explica a abstenção, seguida do **tamanho** e do **estado**: a abstenção de uma cidade é muito estável ao longo do tempo.

**Teste fora do tempo e modelo multi-eleição:** aplicado à eleição de **2024**, o modelo de 2020 continuou **ordenando bem** os municípios, mas **superestimou o nível** em 2,8 p.p.: ele aprendeu a subida da pandemia (2016 → 2020), e de 2020 para 2024 a abstenção caiu. A solução foi um **modelo multi-eleição**:
- treinado com **2016 e 2020** juntos;
- prevê a **diferença de cada município para o nível nacional**;
- o nível nacional entra depois, como **cenário**.

Em 2024, o erro caiu de 3,42 para **2,27 p.p.** Esse é o modelo usado no app para simular a **próxima eleição**.

<div align="center">
<img src="Imagens/Modelo multi-eleicao 2024.png" width="800px">
</div>

**Municípios fora do padrão em 2020:** em **Ivatuba (PR)**, a abstenção quase dobrou (12,9% → 24,1%) e em **Jataí (GO)** foi de 15,7% para 31,7%. No outro extremo, **Fronteira dos Vales (MG)** teve 8,9%, contra 22,0% esperados.

## 10. App interativo (Streamlit)

O app tem 4 abas:
1. **📊 Painel:** escolha o Brasil ou um estado e veja eleitores, abstenção, brancos/nulos, um **mapa interativo** (abstenção, brancos/nulos ou partido com mais prefeitos) e os partidos que mais elegeram.
2. **🏙️ Município:** escolha uma cidade e veja o prefeito eleito (ou o resultado do 2º turno e do julgamento), a composição da Câmara, a abstenção **real × esperada** e o histórico de 2016, 2020 e 2024.
3. **📈 2016 → 2024:** prefeitos eleitos por partido nas 3 eleições e a abstenção de cada uma.
4. **🔮 Simulador:** informe o perfil de um município e receba a **abstenção esperada** com a faixa de erro, pelo modelo de 2020 ou pelo **modelo multi-eleição**, informando a abstenção nacional esperada para a próxima eleição.

```bash
streamlit run app.py
```

> ℹ️ O app usa os CSVs de `Datasets/` e o `Model/modelo_abstencao.pkl`, gerados ao executar o notebook até a Fase 05.

## 11. O que mudou da v1 para a v2

A versão original foi mantida em `Notebooks/` para mostrar a evolução.

| # | Versão original (v1) | Problema | Versão v2 |
|---|---|---|---|
| 1 | Dicionário de dados: `elector_count` = número de eleitores | A coluna é a marcação de **eleito** (s/n) | Colunas traduzidas com o significado correto e `aptos` calculado |
| 2 | **5.519** prefeitos eleitos | Incluía os **114 candidatos** que foram ao **2º turno** | **5.405** eleitos no 1º turno, com 2º turno e sub judice separados, e o **resultado final** do TSE |
| 3 | Estatísticas calculadas sobre as linhas de candidatos ("comparecimento de 13,19%", "média de 8.581.663 votos nominais") | Cada município aparecia uma vez **por candidato** | Tabela com **1 linha por município**: abstenção real de **23,1%** |
| 4 | "Quanto mais candidatos, mais eleitos" (correlação de 0,9) | A correlação refletia só o **tamanho** dos partidos | **Taxa de sucesso** por partido (PP 46% x PT 15%) |
| 5 | Mapas com marcadores na capital mostrando o total do estado | Difícil comparar estados de tamanhos diferentes | Mapa de **abstenção (%)** por estado e mapa interativo no app |
| 6 | Só 2020 e só dados do TSE | Sem comparação nem contexto socioeconômico | Eleições de **2012 a 2024**, indicadores do **IBGE**, dados de **Covid** e análise de **coligações** |
| 7 | — | `codigo_ibge` trocado em 7 municípios na base | Correção automática comparando os nomes, com teste |
| 8 | Só análise descritiva | — | **Modelo de abstenção esperada**, com teste fora do tempo, e **modelo multi-eleição** para a próxima eleição |
| 9 | Caminho `Dataset/` no código | A pasta se chama `Datasets/`: o notebook não rodava | Caminhos corrigidos, funções em `src/` e **19 testes** com `pytest` rodando no **GitHub Actions** |
| 10 | Hipóteses só com gráficos | Não diferencia efeito real de acaso | **Testes estatísticos** com tamanho de efeito em todas as 14 hipóteses |
| 11 | Sem registro das decisões | — | `docs/decisoes_analiticas.md`, fichas dos modelos em JSON e pasta `reports/` |

## 12. Insights

1. **Conferir o significado das colunas antes de calcular:** nomes errados e códigos trocados levaram a v1 a contar 114 prefeitos a mais e a uma abstenção sem sentido.
2. **5 partidos dominam o poder local:** 57% dos prefeitos e 48% dos vereadores em 2020.
3. **O mapa partidário mudou rápido:** de 2016 para 2024, o PSD virou o maior partido e o PSDB perdeu 2 de cada 3 prefeituras.
4. **Eficiência importa mais que volume:** o PP elegeu 46% dos candidatos a prefeito, o PT 15%.
5. **Cidade grande e urbana = mais abstenção, mais brancos e nulos e mais concorrência.**
6. **A abstenção subiu na pandemia e não voltou em 2024**, principalmente nas cidades grandes.
7. **O prefeito quase nunca tem maioria própria** na Câmara: a mediana é de 33% das cadeiras.
8. **A abstenção de uma cidade é muito estável:** com o histórico, o tamanho, o estado e o IBGE, o modelo explica 80% das diferenças entre municípios.
9. **Separar o município do contexto nacional melhora a previsão:** o modelo de uma eleição errou o patamar de 2024; o multi-eleição reduziu o erro de 3,4 para 2,3 p.p.
10. **Alianças importam:** sozinho, 9% de vitórias; com 8 ou mais partidos, 67% (em parte porque as alianças se formam em torno dos favoritos).
11. **A Covid local quase não explica a abstenção entre municípios:** o efeito da pandemia foi geral.

## 13. Limites

- **Resultado final parcial:** dos 104 municípios sub judice, 51 tiveram o prefeito definido em eleição suplementar, que não entra nesta base.
- **Indicadores do IBGE de anos diferentes:** a urbanização é do Censo 2010 (o mais recente com essa divisão) e a idade, do Censo 2022.
- **Sem dados de escolaridade e de distância até as seções**, que provavelmente explicam parte dos 20% que o modelo não explica.
- **Nível nacional como cenário:** o modelo multi-eleição precisa que se informe a abstenção nacional esperada; ele não a prevê.
- **Coligações:** a análise mostra associação, não causa (alianças se formam em torno dos favoritos).
- **Fusões de partidos:** para comparar 2016 e 2024, partidos que se fundiram foram somados com o nome atual. Isso é uma simplificação: parte dos políticos mudou de partido nas fusões.

## 14. Próximos passos

1. **Prever o nível nacional** da próxima eleição (série histórica desde 2000 e indicadores de interesse), em vez de tratá-lo como cenário.
2. **Acrescentar escolaridade** (Censo 2022) e a **distância média até as seções eleitorais**.
3. **Medir o efeito causal das alianças**, comparando candidatos parecidos com e sem aliança.
4. **Estudar o recadastramento biométrico**, que cancelou títulos e pode explicar parte das mudanças de abstenção.
5. **Publicar o app** no Streamlit Community Cloud e gravar um GIF para este README.

---

**Autor:** Rafael R. Silva · [GitHub](https://github.com/RafaelSilva89)
