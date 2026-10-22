# Registro de decisões analíticas

Este documento registra as principais decisões do projeto, no formato
**Contexto → Decisão → Alternativas consideradas → Consequência → Onde está**.
Cada decisão tem um código (DA-XX) para ser citada em commits e pull requests.

Os números vêm das saídas do notebook [`Notebooks/Análise dos resultados da eleição - 2020 - v2.ipynb`](../Notebooks/).

| Código | Decisão |
|---|---|
| [DA-01](#da-01--significado-real-das-colunas) | Significado real das colunas da base |
| [DA-02](#da-02--2º-turno-e-sub-judice-separados) | 2º turno e sub judice separados dos eleitos |
| [DA-03](#da-03--correção-dos-códigos-ibge) | Correção dos códigos IBGE |
| [DA-04](#da-04--partidos-somados-pelo-nome-atual) | Partidos somados pelo nome atual (fusões) |
| [DA-05](#da-05--variáveis-vetadas-por-vazamento) | Variáveis vetadas por vazamento |
| [DA-06](#da-06--divisão-602020-com-validação-cruzada) | Divisão 60/20/20 com validação cruzada |
| [DA-07](#da-07--histgradientboosting-como-modelo-final) | HistGradientBoosting como modelo final |
| [DA-08](#da-08--covid-fora-do-modelo) | Covid fora do modelo |
| [DA-09](#da-09--modelo-multi-eleição-para-eleições-futuras) | Modelo multi-eleição para eleições futuras |

---

## DA-01 — Significado real das colunas

- **Contexto:** a coluna `elector_count` ("número de eleitores") tem só os valores "s" e "n".
- **Decisão:** traduzir as colunas com o significado correto (`elector_count` → `eleito`) e calcular `aptos` = comparecimento + abstenções.
- **Alternativas consideradas:** confiar no nome das colunas (como a versão original), que levou a uma "taxa de comparecimento de 13,19%".
- **Consequência:** abstenção real de 23,1% em 2020.
- **Onde está:** `COLUNAS` e `carregar_base` em `src/eleicao.py`; item 2.1 da Fase 02.

## DA-02 — 2º turno e sub judice separados

- **Contexto:** os 2 candidatos que foram ao 2º turno também estão marcados como eleitos.
- **Decisão:** classificar cada município pelo número de marcados: 1 = eleito no 1º turno, 2 = 2º turno, 0 = sub judice; e trazer o resultado final do arquivo de candidatos do TSE.
- **Alternativas consideradas:** contar todos os marcados (5.519 "prefeitos", como na versão original).
- **Consequência:** 5.405 eleitos no 1º turno, 57 municípios com 2º turno, 104 sub judice; 5.494 com resultado final.
- **Onde está:** `situacao_prefeito` e `prefeitos_eleitos` em `src/eleicao.py`; H9.

## DA-03 — Correção dos códigos IBGE

- **Contexto:** 7 municípios têm o código IBGE trocado na base (ex.: Laje-BA aponta para Lajedão).
- **Decisão:** trocar o código só quando o nome do TSE bate com exatamente um outro município da mesma UF.
- **Alternativas consideradas:** cruzar só pelo código (Laje teria 5 eleitores por habitante) ou só pelo nome (falha em grafias diferentes, como Itapagé x Itapajé).
- **Consequência:** dados do IBGE corretos para todos os municípios.
- **Onde está:** `corrigir_codigos_ibge` em `src/dados_externos.py` (com teste).

## DA-04 — Partidos somados pelo nome atual

- **Contexto:** entre 2016 e 2024 vários partidos se fundiram ou mudaram de nome (DEM + PSL = UNIÃO, PTB + Patriota = PRD).
- **Decisão:** comparar as eleições somando os partidos com o nome mais recente (`partido_atual`).
- **Alternativas consideradas:** comparar pelos nomes originais, o que faria partidos "sumirem" entre as eleições.
- **Consequência:** comparação justa (ex.: UNIÃO 297 → 588 prefeitos); simplificação documentada nos limites.
- **Onde está:** `SUCESSAO_PARTIDOS` em `src/dados_externos.py`; H10.

## DA-05 — Variáveis vetadas por vazamento

- **Contexto:** comparecimento, votos brancos e nulos são resultados da própria votação.
- **Decisão:** usar no modelo só informações conhecidas antes da eleição.
- **Alternativas consideradas:** incluir esses resultados, o que daria R² de 0,999 (com a taxa de comparecimento) e um modelo inútil.
- **Consequência:** o teste anti-vazamento mostra o erro "caindo" para 0,04 p.p. com o comparecimento, contra 1,97 p.p. do modelo legítimo.
- **Onde está:** item 4 da Fase 02 e item 9 da Fase 03.

## DA-06 — Divisão 60/20/20 com validação cruzada

- **Contexto:** o teste precisa ser usado uma única vez, e a comparação entre algoritmos precisa ser estável.
- **Decisão:** treino 60% (3.340), validação 20% (1.113) e teste 20% (1.114); validação cruzada de 5 partes em treino + validação como complemento (média ± desvio).
- **Alternativas consideradas:** só validação cruzada no treino (versão anterior da v2).
- **Consequência:** os dois métodos concordam na ordem dos algoritmos, com desvios de 0,04 a 0,08 p.p.
- **Onde está:** itens 4.1, 5 e 6 da Fase 03.

## DA-07 — HistGradientBoosting como modelo final

- **Contexto:** foram comparados Média (referência), Regressão Linear, Lasso, Random Forest, XGBoost, LightGBM e HistGradientBoosting.
- **Decisão:** HistGradientBoosting ajustado por Random Search (taxa de aprendizado 0,02, 400 árvores, até 31 folhas), treinado em treino + validação.
- **Alternativas consideradas:** LightGBM (praticamente empatado: 2,03 ± 0,04 p.p.) e Regressão Linear (mais simples, 0,25 p.p. atrás).
- **Consequência:** MAE de 2,02 p.p. e R² de 0,80 no teste; faixa de 80% de −3,2 a +2,9 p.p.
- **Onde está:** itens 5 a 8 da Fase 03; `Model/modelo_abstencao.json`.

## DA-08 — Covid fora do modelo

- **Contexto:** os dados de Covid por município reduzem o erro só de 2,08 para 2,06 p.p. na validação cruzada do treino.
- **Decisão:** não incluir a Covid no modelo.
- **Alternativas consideradas:** incluir as 3 variáveis de Covid.
- **Consequência:** o ganho é menor que a variação normal (~0,06 p.p.), e a Covid só existe em 2020: o modelo continua utilizável em outras eleições.
- **Onde está:** H13 e item 4.3 da Fase 03.

## DA-09 — Modelo multi-eleição para eleições futuras

- **Contexto:** aplicado a 2024, o modelo de 2020 superestimou o nível em 2,8 p.p. (aprendeu a subida da pandemia).
- **Decisão:** treinar um segundo modelo com 2016 + 2020, prevendo a diferença de cada município para o nível nacional; o nível entra como cenário.
- **Alternativas consideradas:** usar só o modelo de 2020, ou acrescentar o ano como variável (impossível para uma eleição futura).
- **Consequência:** erro em 2024 cai de 3,42 para 2,27 p.p. (R² de 0,40 para 0,73); é o modelo usado no simulador do app.
- **Onde está:** item 4.2 da Fase 04; `Model/modelo_abstencao_multieleicao.json`.
