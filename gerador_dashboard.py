#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=========================================================================================
OBSERVATÓRIO DOS PLANTIOS ILÍCITOS NO BRASIL
Gerador do dashboard estatístico (dashboard.html)
Pesquisador: Me. Alessandro Carneiro | NEVIDH - UFJF 2026
=========================================================================================
Lê as mesmas bases do Atlas (dados_antigos.csv, dados_novos.csv, dados_complementares.csv),
monta a lista de eventos com quantidade de pés, calcula as estatísticas e regrava o bloco
de dados dentro de dashboard.html. O restante da página (layout, gráficos, textos) não muda.

Uso:  python gerador_dashboard.py
Saídas: dashboard.html (atualizado) e eventos_dashboard.csv (auditoria, um evento por linha).

REGRAS DE CONSTRUÇÃO DO EVENTO
1. Duplicatas: mesma chave do Atlas (data, município, instituição, título); depois, a mesma
   notícia repetida nos dois arquivos de origem (mesmo link, data e quantidade); por fim, a
   lista curada de eventos_repetidos.csv (mesmo fato noticiado por dois veículos).
2. Ficam fora os balanços agregados: data com "mensuração" ou município "Aparato geral".
   Exceção: operação nomeada, com período e locais definidos, conta como um evento e entra
   por ajustes_dashboard.csv (regra 6).
3. UF: o campo Estado precisa citar exatamente uma UF ("Norte da Bahia." vale Bahia;
   "Pernambuco e Paraíba" fica fora).
4. Ano: o da data; em data parcial, o único ano citado no campo. Entram só eventos a partir
   de ANO_INICIAL (2017); os anteriores ficam registrados na auditoria como fora do recorte.
5. Pés: só quantidade expressa em pés. "Cerca de" vale como ponto, "mais de" como piso,
   "entre A e B" como ponto médio, "mil" sem número como 1.000. Quando a célula traz pés e
   mudas, contam só os pés. Ficam fora: só mudas, toneladas, quilos, hectares, áreas,
   "milhares", "dezenas" e "Sem informações".
6. Ajustes manuais: ajustes_dashboard.csv força a entrada de um registro (pelo link) com a
   quantidade de pés indicada, passando por cima das regras 2 e 5. Cada linha traz o motivo.
"""
import json
import logging
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy import stats

logging.basicConfig(level=logging.INFO, format='%(asctime)s [ %(levelname)s ] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

ARQ_ANTIGO = 'dados_antigos.csv'
ARQ_NOVO = 'dados_novos.csv'
ARQ_COMPLEMENTAR = 'dados_complementares.csv'
ARQ_EVENTOS_REPETIDOS = 'eventos_repetidos.csv'
ARQ_AJUSTES = 'ajustes_dashboard.csv'
ARQ_DASHBOARD = 'dashboard.html'
ARQ_AUDITORIA = 'eventos_dashboard.csv'

# Recorte cronológico da análise (decisão de 17/11/2026). A série regular de registros começa
# em 2017; antes disso há só dois eventos isolados (RJ 2011, 2 pés; RO 2014, 31 pés), separados
# do restante por anos sem registro. O Atlas continua mostrando todos os pontos.
ANO_INICIAL = 2017

# População residente por UF: IBGE, Censo Demográfico 2022
POPULACAO = {
    'São Paulo': 44411238, 'Minas Gerais': 20539989, 'Rio de Janeiro': 16055174, 'Bahia': 14141626,
    'Paraná': 11444380, 'Rio Grande do Sul': 10882965, 'Pernambuco': 9058931, 'Ceará': 8794957,
    'Pará': 8121025, 'Santa Catarina': 7610361, 'Goiás': 7056495, 'Maranhão': 6775805,
    'Paraíba': 3974687, 'Amazonas': 3941613, 'Espírito Santo': 3833486, 'Mato Grosso': 3658649,
    'Rio Grande do Norte': 3302729, 'Piauí': 3272199, 'Alagoas': 3127683, 'Distrito Federal': 2817381,
    'Mato Grosso do Sul': 2756700, 'Sergipe': 2209558, 'Rondônia': 1581196, 'Tocantins': 1511459,
    'Acre': 830018, 'Amapá': 733759, 'Roraima': 636303,
}
REGIAO = {
    'Acre': 'Norte', 'Amapá': 'Norte', 'Amazonas': 'Norte', 'Pará': 'Norte', 'Rondônia': 'Norte',
    'Roraima': 'Norte', 'Tocantins': 'Norte',
    'Alagoas': 'Nordeste', 'Bahia': 'Nordeste', 'Ceará': 'Nordeste', 'Maranhão': 'Nordeste',
    'Paraíba': 'Nordeste', 'Pernambuco': 'Nordeste', 'Piauí': 'Nordeste',
    'Rio Grande do Norte': 'Nordeste', 'Sergipe': 'Nordeste',
    'Espírito Santo': 'Sudeste', 'Minas Gerais': 'Sudeste', 'Rio de Janeiro': 'Sudeste', 'São Paulo': 'Sudeste',
    'Paraná': 'Sul', 'Rio Grande do Sul': 'Sul', 'Santa Catarina': 'Sul',
    'Distrito Federal': 'Centro-Oeste', 'Goiás': 'Centro-Oeste', 'Mato Grosso': 'Centro-Oeste',
    'Mato Grosso do Sul': 'Centro-Oeste',
}

# =========================================================================================
# 1. LEITURA DE CAMPOS LIVRES
# =========================================================================================
_NUM = r'\d+(?:[.,]\d+)*'
_MULT = {'mil': 1e3, 'milhão': 1e6, 'milhões': 1e6, 'milhoes': 1e6}
_NAO_PES = r'(?:muda|tonelada|kg\b|quilo|hectare|ha\b|metro|m²|m2\b|campo|cova|mes\b|mês|meses|ano\b|anos\b)'


def _valor(numero, mult):
    """'12.020' -> 12020 | '146,3' + mil -> 146300 | '1.6' + mil -> 1600 | '2,5' + milhões -> 2500000"""
    if mult:
        v = float(numero.replace(',', '.')) if numero.count('.') + numero.count(',') == 1 and not re.search(r'\.\d{3}$', numero) \
            else float(numero.replace('.', '').replace(',', '.'))
        return v * _MULT[mult]
    return float(numero.replace('.', '').replace(',', '.'))


def ler_pes(texto):
    """Devolve (pés, regra) ou (None, motivo)."""
    if pd.isna(texto):
        return None, 'vazio'
    t = re.sub(r'\s+', ' ', str(texto)).strip().lower()
    if not t or t == 'x' or t.startswith('sem informa'):
        return None, 'sem informação'
    quant = r'(' + _NUM + r')\s*(milhões|milhoes|milhão|mil)?\b'
    # "entre 10 mil e 15 mil": ponto médio
    m = re.search(r'entre\s+' + quant + r'\s+e\s+' + quant, t)
    if m:
        return (_valor(m.group(1), m.group(2)) + _valor(m.group(3), m.group(4))) / 2, 'ponto médio'
    # número seguido de "pés" tem prioridade: "200 covas (cerca de 800 pés)"
    m = re.search(quant + r'\s*pés', t)
    if m:
        return _valor(m.group(1), m.group(2)), 'pés explícitos'
    m = re.search(quant + r'\s*(\S*)', t)
    if m:
        if re.match(_NAO_PES, m.group(3)) or (not m.group(2) and re.match(r'(?:mes|mês|meses|ano|anos)\b', m.group(3))):
            return None, 'unidade que não é pé: ' + m.group(3)
        return _valor(m.group(1), m.group(2)), 'mais de (piso)' if 'mais de' in t else 'número'
    if re.search(r'\bmil pés\b|\bmil\b(?!\w)', t) and 'milhares' not in t:
        return 1000.0, 'mil sem número'
    return None, 'sem número'


def ler_uf(estado):
    if pd.isna(estado):
        return None
    t = str(estado)
    achadas = [uf for uf in POPULACAO if re.search(r'(?<![\w])' + re.escape(uf) + r'(?![\w])', t)]
    # "Mato Grosso do Sul" contém "Mato Grosso"; "Rio Grande do ..." não colide
    if 'Mato Grosso do Sul' in achadas and 'Mato Grosso' in achadas and not re.search(r'Mato Grosso(?! do Sul)', t):
        achadas.remove('Mato Grosso')
    if 'Pará' in achadas and not re.search(r'Pará(?!íba)', t):
        achadas.remove('Pará')
    return achadas[0] if len(achadas) == 1 else None


def ler_ano(data, base_original):
    if pd.isna(data):
        return None
    d = str(data).strip()
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})\b', d)
    if m:
        return int(m.group(3))
    anos = set(re.findall(r'\b(19\d{2}|20\d{2})\b', d))
    return int(anos.pop()) if len(anos) == 1 else None


_txt = lambda col: col.astype(str).str.strip().str.lower().str.replace(r'\s+', ' ', regex=True)
_link = lambda col: _txt(col).str.replace(r'#.*$', '', regex=True).str.rstrip('/')

# =========================================================================================
# 2. MONTAGEM DOS EVENTOS
# =========================================================================================
def montar_eventos():
    if not os.path.exists(ARQ_ANTIGO) or not os.path.exists(ARQ_NOVO):
        logger.error(f"Faltam '{ARQ_ANTIGO}' e '{ARQ_NOVO}' na pasta.")
        sys.exit(1)
    df_a = pd.read_csv(ARQ_ANTIGO, sep=',', engine='python', on_bad_lines='skip')
    df_n = pd.read_csv(ARQ_NOVO, sep=',', engine='python', on_bad_lines='skip')
    df_a.columns = df_a.columns.str.strip()
    df_n.columns = df_n.columns.str.strip()
    base = pd.concat([df_a, df_n], ignore_index=True)
    n0 = len(base)
    base = base.drop_duplicates(subset=['data', 'município', 'Instituição que efetuou a apreensao', 'Titulo da reportagem'], keep='first')
    base['origem'] = 'Base do Observatório'
    if os.path.exists(ARQ_COMPLEMENTAR):
        comp = pd.read_csv(ARQ_COMPLEMENTAR, dtype=str)
        comp.columns = comp.columns.str.strip()
        comp['origem'] = 'Busca complementar'
        base = pd.concat([base, comp], ignore_index=True)
    logger.info(f"Registros lidos: {n0} linhas brutas, {len(base)} depois da chave de duplicatas do Atlas.")

    chave = pd.DataFrame({'link': _link(base['Link de acesso']), 'data': _txt(base['data']),
                          'qtd': _txt(base['Quantidade de pés encontrados'])})
    repetida = chave.duplicated(keep='first')
    base = base[~repetida].copy()
    logger.info(f"Mesma notícia nos dois arquivos de origem: {int(repetida.sum())} registros retirados.")

    if os.path.exists(ARQ_EVENTOS_REPETIDOS):
        fora = set(_link(pd.read_csv(ARQ_EVENTOS_REPETIDOS, dtype=str)['link_descartado']))
        marca = _link(base['Link de acesso']).isin(fora)
        base = base[~marca].copy()
        logger.info(f"Mesmo fato em dois veículos ('{ARQ_EVENTOS_REPETIDOS}'): {int(marca.sum())} registros retirados.")

    base['uf'] = base['Estado'].apply(ler_uf)
    base['ano'] = [ler_ano(d, o == 'Base do Observatório') for d, o in zip(base['data'], base['origem'])]
    lidos = base['Quantidade de pés encontrados'].apply(ler_pes)
    base['pes'] = [p for p, _ in lidos]
    base['regra_pes'] = [r for _, r in lidos]
    agregado = base['data'].astype(str).str.contains('mensura', case=False) | \
        base['município'].astype(str).str.contains('aparato geral', case=False)
    base['situacao'] = np.select(
        [agregado, base['uf'].isna(), base['ano'].isna(), base['pes'].isna()],
        ['fora: balanço agregado', 'fora: sem UF única', 'fora: sem ano', 'fora: sem quantidade em pés'], 'evento')
    base['situacao'] = base['situacao'].astype(object)
    if os.path.exists(ARQ_AJUSTES):
        aj = pd.read_csv(ARQ_AJUSTES, dtype=str)
        forcado = dict(zip(_link(aj['link']), aj['pes'].astype(float)))
        marca = _link(base['Link de acesso']).isin(forcado) & base['uf'].notna() & base['ano'].notna()
        base.loc[marca, 'pes'] = _link(base.loc[marca, 'Link de acesso']).map(forcado)
        base.loc[marca, 'regra_pes'] = 'ajuste manual'
        base.loc[marca, 'situacao'] = 'evento'
        logger.info(f"Ajustes manuais ('{ARQ_AJUSTES}'): {int(marca.sum())} registros.")
    antes = (base['situacao'] == 'evento') & (base['ano'] < ANO_INICIAL)
    base.loc[antes, 'situacao'] = f'fora: antes de {ANO_INICIAL}'
    logger.info(f"Recorte cronológico: {int(antes.sum())} eventos anteriores a {ANO_INICIAL} retirados da análise.")
    base['regiao'] = base['uf'].map(REGIAO)
    colunas = ['situacao', 'uf', 'regiao', 'ano', 'pes', 'regra_pes', 'origem', 'data', 'município', 'Estado',
               'Quantidade de pés encontrados', 'Titulo da reportagem', 'Link de acesso']
    base[colunas].to_csv(ARQ_AUDITORIA, index=False, encoding='utf-8-sig')
    for s, q in base['situacao'].value_counts().items():
        logger.info(f"   {s}: {q}")
    ev = base[base['situacao'] == 'evento'][['uf', 'regiao', 'ano', 'pes']].copy()
    ev['ano'] = ev['ano'].astype(int)
    return ev.sort_values('uf', kind='stable').reset_index(drop=True)

# =========================================================================================
# 3. ESTATÍSTICA
# =========================================================================================
def _quartis(v):
    """Q1 e Q3 como medianas das metades inferior e superior (dobradiças de Tukey, sem a mediana quando n é ímpar)."""
    v = np.sort(np.asarray(v, dtype=float))
    n = len(v)
    if n == 1:
        return float(v[0]), float(v[0])
    return float(np.median(v[:n // 2])), float(np.median(v[(n + 1) // 2:]))


def _descritiva(chave, v):
    v = np.asarray(v, dtype=float)
    q1, q3 = _quartis(v)
    return {'chave': chave, 'n': int(len(v)), 'soma': float(v.sum()), 'media': float(v.mean()),
            'dp': float(v.std(ddof=1)) if len(v) > 1 else None, 'mediana': float(np.median(v)),
            'q1': q1, 'q3': q3, 'min': float(v.min()), 'max': float(v.max())}


def _ols(x, y):
    r = stats.linregress(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return {'n': int(len(x)), 'slope': float(r.slope), 'intercept': float(r.intercept), 'r2': float(r.rvalue ** 2),
            'se_slope': float(r.stderr), 't': float(r.slope / r.stderr), 'p': float(r.pvalue)}


def _welch(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    t, p = stats.ttest_ind(a, b, equal_var=False)
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    gl = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
    return {'n1': int(len(a)), 'n2': int(len(b)), 'media1': float(a.mean()), 'media2': float(b.mean()),
            't': float(t), 'df': float(gl), 'p': float(p)}


def calcular(ev):
    ev = ev.copy()
    ev['lg'] = np.log10(ev['pes'])
    desc_uf = []
    for uf, g in ev.groupby('uf'):
        d = _descritiva(uf, g['pes'])
        d.update({'pop': POPULACAO[uf], 'pes_100k': d['soma'] / POPULACAO[uf] * 1e5, 'ocor_100k': d['n'] / POPULACAO[uf] * 1e5})
        desc_uf.append(d)
    desc_uf.sort(key=lambda d: -d['soma'])
    desc_regiao = sorted((_descritiva(r, g['pes']) for r, g in ev.groupby('regiao')), key=lambda d: -d['soma'])
    serie = [{'ano': int(a), 'regiao': r, 'n': int(len(g)), 'soma': float(g['pes'].sum()), 'media': float(g['pes'].mean()),
              'dp': float(g['pes'].std(ddof=1)) if len(g) > 1 else None}
             for (a, r), g in ev.groupby(['ano', 'regiao'])]

    rec = ev[ev['ano'].between(2017, 2026)]
    tend = {}
    for r in ['Norte', 'Nordeste', 'Sudeste', 'Sul', 'Centro-Oeste']:
        g = rec[rec['regiao'] == r]
        if len(g) >= 3 and g['ano'].nunique() >= 2:
            tend[r] = _ols(g['ano'], g['lg'])
    anual = ev[ev['ano'].between(2017, 2025)].groupby('ano')['pes'].sum()
    ne = ev.loc[ev['regiao'] == 'Nordeste', 'lg']
    por_uf = pd.DataFrame(desc_uf)
    x, y = np.log10(por_uf['pop']), np.log10(por_uf['soma'])
    r, p = stats.pearsonr(x, y)
    inferencia = {
        'tendencia_log10_pes_ano_por_regiao': tend,
        'tendencia_log10_soma_anual_2017_2025': _ols(anual.index, np.log10(anual.values)),
        'welch_log10_nordeste_vs_sudeste_sul': _welch(ne, ev.loc[ev['regiao'].isin(['Sudeste', 'Sul']), 'lg']),
        'welch_log10_nordeste_vs_norte': _welch(ne, ev.loc[ev['regiao'] == 'Norte', 'lg']),
        'pearson_log_pop_vs_log_pes_uf': {'n': int(len(x)), 'r': float(r), 't': float(r * np.sqrt((len(x) - 2) / (1 - r ** 2))), 'p': float(p)},
        'ols_log_pop_vs_log_pes_uf': _ols(x, y),
        'ols_ano_log10_pes_pooled': _ols(rec['ano'], rec['lg']),
    }
    eventos = [{'uf': u, 'regiao': r, 'ano': int(a), 'pes': float(p)} for u, r, a, p in zip(ev['uf'], ev['regiao'], ev['ano'], ev['pes'])]
    return {'desc_uf': desc_uf, 'desc_regiao': desc_regiao, 'serie_regiao': serie, 'eventos': eventos,
            'inferencia': inferencia, 'populacao': POPULACAO}

# =========================================================================================
# 4. GRAVAÇÃO NO DASHBOARD
# =========================================================================================
_BLOCO = re.compile(r'^const D = \{.*\};$', re.M)


def gravar(dados):
    if not os.path.exists(ARQ_DASHBOARD):
        logger.error(f"'{ARQ_DASHBOARD}' não encontrado: o gerador atualiza os dados de uma página que já existe.")
        sys.exit(1)
    with open(ARQ_DASHBOARD, encoding='utf-8', newline='') as f:
        html = f.read()
    if len(_BLOCO.findall(html)) != 1:
        logger.error("Bloco 'const D = {...};' não localizado em dashboard.html.")
        sys.exit(1)
    novo = 'const D = ' + json.dumps(dados, ensure_ascii=False, allow_nan=False) + ';'
    with open(ARQ_DASHBOARD, 'w', encoding='utf-8', newline='') as f:
        f.write(_BLOCO.sub(lambda _: novo, html))
    logger.info(f"'{ARQ_DASHBOARD}' atualizado.")


if __name__ == '__main__':
    eventos = montar_eventos()
    dados = calcular(eventos)
    logger.info(f"Eventos com quantidade de pés: {len(eventos)} | total de pés: {eventos['pes'].sum():,.0f}".replace(',', '.'))
    gravar(dados)
