"""Avaliação dos modelos de regressão: métricas (padrão ml_error), relatório de validação, comparação e ficha."""
import json
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

from src.graficos import COR_DESTAQUE, COR_PRINCIPAL, salvar, titulo


def ml_error(nome, y, yhat):
    """Métricas de regressão de um modelo, com os erros em pontos percentuais (p.p.) de abstenção.

    MAE: erro absoluto médio · MAPE: erro percentual médio (em relação à abstenção real) ·
    RMSE: raiz do erro quadrático médio (pune mais os erros grandes) · R²: parte das diferenças explicada ·
    MPE: erro percentual médio COM sinal (positivo = o modelo superestima).
    """
    y, yhat = np.asarray(y), np.asarray(yhat)
    return pd.DataFrame({
        'MAE (p.p.)': mean_absolute_error(y, yhat) * 100,
        'MAPE': np.mean(np.abs((y - yhat) / y)),
        'RMSE (p.p.)': root_mean_squared_error(y, yhat) * 100,
        'R²': r2_score(y, yhat),
        'MPE': np.mean((yhat - y) / y),
    }, index=[nome])


def relatorio_validacao(nome, modelo, X_treino, y_treino, X_validacao, y_validacao, nome_arquivo=None):
    """Avalia um modelo já treinado na validação, no formato padrão do projeto.

    Mostra: amostra gabarito x previsão, métricas (ml_error), MAE no treino x validação (sobreajuste) e
    os gráficos de previsto x real e de distribuição do erro. Devolve (métricas, previsões da validação).
    """
    previsto = modelo.predict(X_validacao)
    print('AMOSTRA: GABARITO x PREVISÃO DA MÁQUINA (abstenção)')
    display(pd.DataFrame({'Gabarito': np.asarray(y_validacao), 'Previsão da máquina': previsto,
                          'Erro (p.p.)': (previsto - np.asarray(y_validacao)) * 100}).head(6).round(3))

    metricas = ml_error(nome, y_validacao, previsto)
    mae_treino = mean_absolute_error(y_treino, modelo.predict(X_treino)) * 100
    metricas['MAE treino (p.p.)'] = mae_treino
    print('=' * 50)
    print(f'MÉTRICAS DE VALIDAÇÃO: {nome}')
    print('=' * 50)
    print(metricas.drop(columns='MAE treino (p.p.)').round(4).T.to_string(header=False))
    print(f'\nMAE no treino: {mae_treino:.2f} p.p. | na validação: {metricas["MAE (p.p.)"].iloc[0]:.2f} p.p. '
          f'| diferença: {metricas["MAE (p.p.)"].iloc[0] - mae_treino:+.2f} p.p.')

    fig, axs = plt.subplots(1, 2, figsize=(13, 4.5))
    axs[0].scatter(previsto, y_validacao, s=8, alpha=0.35, color=COR_PRINCIPAL)
    limites = [min(previsto.min(), np.min(y_validacao)), max(previsto.max(), np.max(y_validacao))]
    axs[0].plot(limites, limites, color=COR_DESTAQUE, ls='--', label='Previsão perfeita')
    axs[0].set(xlabel='Abstenção prevista', ylabel='Abstenção real', title='Previsto x real')
    axs[0].legend(frameon=False)
    sns.histplot((previsto - np.asarray(y_validacao)) * 100, bins=40, color=COR_PRINCIPAL, ax=axs[1])
    axs[1].axvline(0, color=COR_DESTAQUE, ls='--')
    axs[1].set(xlabel='Erro (previsto - real, p.p.)', ylabel='Municípios', title='Distribuição do erro')
    for ax in axs[:1]:
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    sns.despine()
    plt.suptitle(nome, fontsize=14, x=0.01, ha='left', y=1.02)
    if nome_arquivo:
        salvar(nome_arquivo)
    plt.show()
    return metricas, previsto


def plot_comparacao_modelos(comparacao, nome_arquivo, referencia='Média (referência)'):
    """Painel com uma barra por modelo em cada métrica e a linha do modelo de referência (que só chuta a média)."""
    modelos = comparacao.index.tolist()
    cores = [COR_DESTAQUE if m == referencia else COR_PRINCIPAL for m in modelos]
    fig, axes = plt.subplots(1, 4, figsize=(22, 5))
    for ax, metrica in zip(axes, ['MAE (p.p.)', 'MAPE', 'RMSE (p.p.)', 'R²']):
        valores = comparacao[metrica]
        ax.barh(modelos, valores, color=cores, alpha=0.85)
        for i, v in enumerate(valores):
            ax.text(v, i, f' {v:.3f}' if metrica in ('R²', 'MAPE') else f' {v:.2f}', va='center', fontsize=9)
        if referencia in comparacao.index:
            ax.axvline(comparacao.loc[referencia, metrica], color='gray', ls='--', lw=1, label='modelo que chuta a média')
        ax.set_title(metrica + (' (maior é melhor)' if metrica == 'R²' else ' (menor é melhor)'), fontweight='bold')
        ax.invert_yaxis()
        sns.despine(ax=ax)
    axes[0].legend(frameon=False, loc='lower right', fontsize=9)
    titulo('Comparação dos modelos na validação')
    salvar(nome_arquivo)
    plt.show()


def erro_por_grupo(y, previsto, grupos):
    """Tradução do erro para o negócio: erro médio por grupo (ex.: UF) e cenários de melhor e pior caso."""
    tabela = pd.DataFrame({'real': np.asarray(y), 'previsto': np.asarray(previsto), 'grupo': np.asarray(grupos)})
    tabela['erro_abs'] = (tabela['previsto'] - tabela['real']).abs()
    resumo = tabela.groupby('grupo').agg(municipios=('real', 'size'), abstencao_real=('real', 'mean'),
                                         abstencao_prevista=('previsto', 'mean'), MAE=('erro_abs', 'mean'))
    resumo['MAPE'] = (tabela.assign(ape=tabela['erro_abs'] / tabela['real']).groupby('grupo')['ape'].mean())
    resumo['pior cenário'] = resumo['abstencao_prevista'] + resumo['MAE']
    resumo['melhor cenário'] = resumo['abstencao_prevista'] - resumo['MAE']
    return resumo.sort_values('MAE', ascending=False)


def salvar_ficha_modelo(caminho, **campos):
    """Grava a ficha do modelo (JSON): tudo o que é preciso saber para usá-lo corretamente."""
    ficha = {'data_treino': datetime.now().strftime('%Y-%m-%d %H:%M'), **campos}
    with open(caminho, 'w', encoding='utf-8') as arquivo:
        json.dump(ficha, arquivo, ensure_ascii=False, indent=2, default=float)
    return ficha
