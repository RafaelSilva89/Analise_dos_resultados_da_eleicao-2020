"""Funções de gráficos usadas no notebook. Cada gráfico é salvo na pasta Imagens/ do projeto."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import matplotlib.ticker as mtick
import seaborn as sns

PASTA_IMAGENS = Path(__file__).resolve().parents[1] / 'Imagens'

COR_PRINCIPAL = '#1F4E79'
COR_DESTAQUE = '#C0392B'
COR_NEUTRA = '#B0B7C3'


def salvar(nome_arquivo):
    plt.savefig(PASTA_IMAGENS / f'{nome_arquivo}.png', bbox_inches='tight', dpi=110)


def titulo(texto, subtitulo=None):
    """Título e subtítulo alinhados à esquerda, acima da área do gráfico (espaçamento em polegadas)."""
    altura = plt.gcf().get_figheight()
    topo = plt.gcf().subplotpars.top
    plt.figtext(0.01, topo + 0.45 / altura, texto, ha='left', va='bottom', fontsize=16)
    if subtitulo:
        plt.figtext(0.01, topo + 0.15 / altura, subtitulo, ha='left', va='bottom', fontsize=11, color='#656565',
                    style='italic')


def pct(valor, casas=0):
    """0.1234 -> '12%' (ou '12,3%' com casas=1)."""
    return f'{valor:.{casas}%}'.replace('.', ',')


def pp(valor, casas=2, sinal=False):
    """Pontos percentuais: 2.8 -> '2,80 p.p.' (ou '+2,80 p.p.' com sinal=True)."""
    texto = f'{valor:+.{casas}f}' if sinal else f'{valor:.{casas}f}'
    return texto.replace('.', ',') + ' p.p.'


def plot_pareto(tabela, titulo_grafico, nome_arquivo, subtitulo=None, top=None):
    """Barras com a quantidade por categoria e linha com o % acumulado (gráfico de Pareto)."""
    dados = tabela.head(top) if top else tabela
    fig, ax = plt.subplots(figsize=(15, 6))
    barras = ax.bar(dados.index, dados['Quantidade'], color=COR_PRINCIPAL)
    ax.bar_label(barras, labels=[f'{v:,}'.replace(',', '.') for v in dados['Quantidade']], padding=2, fontsize=9)
    ax.set_yticks([])
    ax.tick_params(axis='x', rotation=45)
    plt.setp(ax.get_xticklabels(), ha='right')

    ax2 = ax.twinx()
    ax2.plot(dados.index, dados['% acumulado'], color=COR_DESTAQUE, marker='o')
    for x, y in zip(dados.index, dados['% acumulado']):
        ax2.annotate(pct(y), (x, y), textcoords='offset points', xytext=(0, 7), ha='center', fontsize=8,
                     color=COR_DESTAQUE, bbox={'boxstyle': 'round,pad=0.15', 'fc': 'white', 'ec': 'none'})
    ax2.set_ylim(0, 1.1)
    ax2.set_yticks([])
    for eixo in (ax, ax2):
        sns.despine(ax=eixo, left=True, right=True)
    titulo(titulo_grafico, subtitulo)
    salvar(nome_arquivo)
    plt.show()


def plot_barras_h(serie, titulo_grafico, nome_arquivo, subtitulo=None, formato=pct, destaque=None, referencia=None):
    """Barras horizontais ordenadas, com o valor escrito em cada barra.

    destaque: rótulos pintados com a cor de destaque. referencia: valor desenhado como linha tracejada.
    """
    serie = serie.sort_values()
    cores = [COR_DESTAQUE if destaque and rotulo in destaque else COR_PRINCIPAL for rotulo in serie.index]
    plt.figure(figsize=(10, max(4, 0.32 * len(serie))))
    barras = plt.barh(serie.index.astype(str), serie.values, color=cores)
    plt.bar_label(barras, labels=[formato(v) for v in serie.values], padding=3, fontsize=9)
    if referencia is not None:
        plt.axvline(referencia, color='black', ls='--', lw=1)
        plt.annotate(f'média geral: {formato(referencia)}', (referencia, len(serie) - 0.4), xytext=(4, 0),
                     textcoords='offset points', fontsize=9)
    plt.xticks([])
    sns.despine(left=True, bottom=True)
    titulo(titulo_grafico, subtitulo)
    salvar(nome_arquivo)
    plt.show()


# Estados pequenos têm o rótulo deslocado para o oceano (em graus de longitude/latitude), com uma linha-guia
DESLOCAMENTO_ROTULO = {'RN': (4, 1.2), 'PB': (5, 0), 'PE': (5.5, -1.4), 'AL': (5, -2.6), 'SE': (4.5, -3.6),
                       'ES': (4.5, -0.8), 'RJ': (4, -2.6)}


def plot_mapa_uf(mapa, coluna, titulo_grafico, nome_arquivo, subtitulo=None, formato=pct, cmap='YlOrRd'):
    """Mapa do Brasil por UF (GeoDataFrame com a coluna `uf`), com o valor escrito em cada estado."""
    fig, ax = plt.subplots(figsize=(11, 9))
    mapa.plot(column=coluna, cmap=cmap, legend=True, edgecolor='white', linewidth=0.8, ax=ax,
              legend_kwds={'shrink': 0.5, 'format': mtick.FuncFormatter(lambda v, _: formato(v))},
              missing_kwds={'color': '#EEEEEE', 'label': 'Sem eleição'})
    for _, linha in mapa.dropna(subset=[coluna]).iterrows():
        ponto = linha.geometry.representative_point()
        dx, dy = DESLOCAMENTO_ROTULO.get(linha['uf'], (0, 0))
        if dx:
            ax.annotate(f"{linha['uf']} {formato(linha[coluna])}", (ponto.x, ponto.y),
                        xytext=(ponto.x + dx, ponto.y + dy), ha='left', va='center', fontsize=9,
                        arrowprops={'arrowstyle': '-', 'color': 'gray', 'lw': 0.7})
        else:
            ax.annotate(f"{linha['uf']}\n{formato(linha[coluna])}", (ponto.x, ponto.y), ha='center', va='center',
                        fontsize=9)
    ax.set_axis_off()
    titulo(titulo_grafico, subtitulo)
    salvar(nome_arquivo)
    plt.show()


def plot_dispersao_partidos(resumo, x, y, titulo_grafico, nome_arquivo, xlabel, ylabel, subtitulo=None,
                            destaque=None, rotular=None, taxa_referencia=None, log=True):
    """Um ponto por partido (escala log para caber partidos pequenos e grandes).

    Só os partidos em `destaque` (em vermelho) e em `rotular` recebem o nome, para não poluir o gráfico.
    taxa_referencia: desenha a reta y = taxa * x. Partidos acima dela elegeram mais por candidato que a média.
    """
    destaque = destaque or []
    rotular = set(destaque) | set(rotular or [])
    dados = resumo[(resumo[x] > 0) & (resumo[y] > 0)]
    plt.figure(figsize=(12, 7))
    cores = [COR_DESTAQUE if p in destaque else COR_PRINCIPAL for p in dados.index]
    plt.scatter(dados[x], dados[y], s=70, color=cores, alpha=0.8)
    if taxa_referencia:
        eixo_x = np.geomspace(dados[x].min(), dados[x].max(), 50)
        plt.plot(eixo_x, eixo_x * taxa_referencia, color='gray', ls='--', lw=1,
                 label=f'Média geral: {pct(taxa_referencia, 1)} dos candidatos eleitos')
        plt.legend(frameon=False, loc='upper left')
    for partido, linha in dados[dados.index.isin(rotular)].iterrows():
        plt.annotate(partido, (linha[x], linha[y]), textcoords='offset points', xytext=(7, -4), fontsize=10,
                     color=COR_DESTAQUE if partido in destaque else '#444444')
    if log:
        plt.xscale('log')
        plt.yscale('log')
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    sns.despine()
    titulo(titulo_grafico, subtitulo)
    salvar(nome_arquivo)
    plt.show()
