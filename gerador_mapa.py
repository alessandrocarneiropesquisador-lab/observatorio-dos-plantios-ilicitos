#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=========================================================================================
OBSERVATÓRIO DOS PLANTIOS ILÍCITOS NO BRASIL
Pesquisador: Ms. Alessandro Carneiro | NEVIDH - UFJF 2026
Objetivo: Mapeamento Sociológico e Cartografia de Precisão
=========================================================================================
"""

import pandas as pd
import folium
from folium.plugins import MarkerCluster
import requests
import io
import sys
import os
import re
import numpy as np
import logging
from shapely.geometry import shape, box, mapping
from shapely.ops import unary_union

# =========================================================================================
# 0. CONFIGURAÇÃO DE LOGS
# =========================================================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s [ %(levelname)s ] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

# =========================================================================================
# 1. MATRIZ DE NORMALIZAÇÃO ESPACIAL
# =========================================================================================
CORRECOES_MUNICIPIOS = {
    "rio janeiro": "rio de janeiro",
    "nas áreas caatinga em salgueiro": "salgueiro",
    "nas regiões orocó": "orocó",
    "circunscrição salgueiro": "salgueiro",
    "parauaopebas": "parauapebas",
    "brotas macaúbas": "brotas de macaúbas",
    "encontrado no km 402 da rodovia 020 em caucaia": "caucaia",
    "distrito pedro juan caballero": "ponta porã", 
    "belém de são francisco": "belém do são francisco",
    "cabobró": "cabrobó",
    "conceição do lago açu": "conceição do lago-açu",
    "muquém do são francisco": "muquém de são francisco",
    "droga veio belém": "belém",
    "com destino para fortaleza": "fortaleza",
    "região do patrocínio": "patrocínio",
    "alto turiaçu": "turiaçu",
    "caraúba": "caraúbas",
    "ibimirim e serra talhada": "ibimirim",
    "e manaíra": "manaíra"
}

ENTIDADES_ESPECIAIS = {
    "alto turiaçu": {"lat": -2.8569, "lon": -46.0354, "uf": "MA"},
    "alto rio guamá": {"lat": -2.9667, "lon": -46.5000, "uf": "PA"},
    "terra indígena alto rio guamá": {"lat": -2.9667, "lon": -46.5000, "uf": "PA"},
    "complexo da maré": {"lat": -22.8596, "lon": -43.2428, "uf": "RJ"},
    "ilhas do rio são francisco": {"lat": -8.7619, "lon": -39.6000, "uf": "PE"}, 
    "rio japurá": {"lat": -1.8900, "lon": -66.6000, "uf": "AM"},
    "região do cariri": {"lat": -7.2333, "lon": -39.4167, "uf": "CE"}, 
    "barco município novo airão": {"lat": -2.6200, "lon": -60.9430, "uf": "AM"},
    "nova friburgo": {"lat": -22.2885, "lon": -42.5332, "uf": "RJ"} 
}

MAPA_UF = {
    11: 'RO', 12: 'AC', 13: 'AM', 14: 'RR', 15: 'PA', 16: 'AP', 17: 'TO',
    21: 'MA', 22: 'PI', 23: 'CE', 24: 'RN', 25: 'PB', 26: 'PE', 27: 'AL', 28: 'SE', 29: 'BA',
    31: 'MG', 32: 'ES', 33: 'RJ', 35: 'SP',
    41: 'PR', 42: 'SC', 43: 'RS',
    50: 'MS', 51: 'MT', 52: 'GO', 53: 'DF'
}

# =========================================================================================
# 2. CARGA DE DADOS
# =========================================================================================
ARQ_ANTIGO = 'dados_antigos.csv'
ARQ_NOVO = 'dados_novos.csv'

if not os.path.exists(ARQ_ANTIGO) or not os.path.exists(ARQ_NOVO):
    logger.error(f"FATAL: Cadeia de custódia quebrada. Exijo '{ARQ_ANTIGO}' e '{ARQ_NOVO}' na mesma pasta.")
    sys.exit(1)

df_a = pd.read_csv(ARQ_ANTIGO, sep=',', engine='python', on_bad_lines='skip')
df_n = pd.read_csv(ARQ_NOVO, sep=',', engine='python', on_bad_lines='skip')
df_a.columns = df_a.columns.str.strip()
df_n.columns = df_n.columns.str.strip()

df_base = pd.concat([df_a, df_n], ignore_index=True)

# =========================================================================================
# 3. ENGENHARIA DE RASTREABILIDADE
# =========================================================================================
def rotina_limpeza_pre_explode(texto):
    if pd.isna(texto): return ""
    t = str(texto)
    t = re.sub(r'\(.*?\)', '', t) 
    t = re.sub(r'/(PE|PA|PB|MA|BA|CE|AM|DF|RJ|SP|MG|RS|PR|SC|GO|MT|MS|TO|RO|AC|RR|AP|RN|AL|SE)', '', t, flags=re.IGNORECASE)
    palavras_ruido = [r'\bentre\b', r'\bos\b', r'\bas\b', r'\bmunicípios\b', r'\bcidades\b', r'\bde\b', r'\bpróximo\b', r'\bao\b', r'\bproximidades\b', r'\bda\b', r'\bna\b']
    for ruido in palavras_ruido: t = re.sub(ruido, ' ', t, flags=re.IGNORECASE)
    return t.replace(" e ", ", ").replace(".", ", ")

def extrair_lista_limpa(texto_limpo):
    return [c.strip() for c in texto_limpo.split(",") if len(c.strip()) > 2 and c.strip().lower() not in ['brasil', 'amazonas', 'bahia', 'pernambuco', 'paraíba', 'maranhão', 'pará', 'aparato geral']]

coluna_alvo = next((c for c in df_base.columns if 'municipio' in c.lower() or 'município' in c.lower()), None)
df_base['texto_geografico_limpo'] = df_base[coluna_alvo].apply(rotina_limpeza_pre_explode)
df_base['municipio_lista'] = df_base['texto_geografico_limpo'].apply(extrair_lista_limpa)

df_base['municipios_envolvidos'] = df_base['municipio_lista'].apply(lambda x: " | ".join([str(c).upper() for c in x]))
df_base['num_cidades_operacao'] = df_base['municipio_lista'].apply(len)

df_explodido = df_base.explode('municipio_lista').dropna(subset=['municipio_lista'])

# =========================================================================================
# 4. NORMALIZAÇÃO E CRUZAMENTO ESPACIAL
# =========================================================================================
df_explodido['municipio_match'] = df_explodido['municipio_lista'].apply(lambda x: CORRECOES_MUNICIPIOS.get(str(x).lower().strip(), str(x).lower().strip()))

df_explodido['lat_especial'] = df_explodido['municipio_match'].apply(lambda x: ENTIDADES_ESPECIAIS.get(x, {}).get('lat', None))
df_explodido['lon_especial'] = df_explodido['municipio_match'].apply(lambda x: ENTIDADES_ESPECIAIS.get(x, {}).get('lon', None))
df_explodido['uf_especial'] = df_explodido['municipio_match'].apply(lambda x: ENTIDADES_ESPECIAIS.get(x, {}).get('uf', None))

logger.info("Acessando malha geodésica do IBGE...")
url_coords = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
coords = pd.read_csv(io.StringIO(requests.get(url_coords, timeout=10).text))
coords['nome_match'] = coords['nome'].astype(str).str.lower().str.strip()
coords['sigla_uf'] = coords['codigo_uf'].map(MAPA_UF)

coords = coords.drop_duplicates(subset=['nome_match'])

df_mapa_completo = pd.merge(df_explodido, coords[['nome_match', 'latitude', 'longitude', 'sigla_uf']], left_on='municipio_match', right_on='nome_match', how='left')

df_mapa_completo['latitude'] = df_mapa_completo['lat_especial'].combine_first(df_mapa_completo['latitude'])
df_mapa_completo['longitude'] = df_mapa_completo['lon_especial'].combine_first(df_mapa_completo['longitude'])
df_mapa_completo['sigla_uf'] = df_mapa_completo['uf_especial'].combine_first(df_mapa_completo['sigla_uf'])

# =========================================================================================
# 5. DISPERSÃO TÁTICA (JITTERING)
# =========================================================================================
df_mapa = df_mapa_completo.dropna(subset=['latitude', 'longitude']).copy()
np.random.seed(42) 
df_mapa['latitude'] = df_mapa['latitude'] + np.random.uniform(-0.012, 0.012, len(df_mapa))
df_mapa['longitude'] = df_mapa['longitude'] + np.random.uniform(-0.012, 0.012, len(df_mapa))

# =========================================================================================
# 6. INFRAESTRUTURA CARTOGRÁFICA DE ISOLAMENTO E TRAVA ABSOLUTA
# =========================================================================================
COR_OCEANO = '#e3eaef'

# Limites com uma folga matemática segura para evitar o colapso da tela
bounds_brasil = [[-34.0, -74.0], [12.0, -28.0]]

mapa = folium.Map(
    location=[-12.0000, -51.0000], # Continua deslocado para baixo e esquerda
    zoom_start=4,     # Retornamos ao zoom inteiro estável
    min_zoom=4,       # Permite que monitores menores consigam enquadrar o Brasil
    max_zoom=12,
    tiles='cartodb positron',
    control_scale=True,
    max_bounds=True 
)

# A Viscosidade: Trava a tela, mas sem asfixiar o motor de zoom
mapa.options['maxBounds'] = bounds_brasil
mapa.options['maxBoundsViscosity'] = 1.0 

mapa.fit_bounds(bounds_brasil)

logger.info("Aplicando máscara geométrica de isolamento nacional (Ocultação Global)...")
try:
    url_br_hr = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    br_geojson = requests.get(url_br_hr, timeout=20).json()
    poligonos_estados = [shape(feature['geometry']) for feature in br_geojson['features']]
    brasil_exato = unary_union(poligonos_estados).buffer(0.04)
    mascara_global = box(-180, -90, 180, 90).difference(brasil_exato)
    
    folium.GeoJson(
        mapping(mascara_global),
        style_function=lambda x: {'fillColor': COR_OCEANO, 'color': COR_OCEANO, 'weight': 1.5, 'fillOpacity': 1.0},
        z_index=0
    ).add_to(mapa)
except Exception as e:
    logger.error(f"Máscara nacional falhou: {e}")

folium.Polygon(
    locations=[[-8.1, -40.2], [-7.5, -39.0], [-8.0, -37.8], [-9.2, -38.0], [-9.8, -39.5], [-9.2, -40.8]],
    color="#d35400", weight=2, fill=True, fill_color="#f39c12", fill_opacity=0.3,
    tooltip="<div style='font-family: Arial; font-size: 11px;'><b>Área de Concentração de Lavouras Ilícitas</b><br>Região Histórica do Fenômeno</div>"
).add_to(mapa)

# =========================================================================================
# 7. RENDERIZAÇÃO DOS DADOS: O CLUSTER E OS MARCADORES
# =========================================================================================
ICON_LEAF = "https://img.icons8.com/color/48/marijuana-leaf.png" 

# O Cluster agora possui fonte menor (13px), sem aura branca, com texto em preto puro.
codigo_cluster_js = f"""
function(cluster) {{
    var markers = cluster.getChildCount();
    return L.divIcon({{
        html: '<div style="background-image: url({ICON_LEAF}); background-size: cover; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; font-family: Arial; font-weight: 900; color: #000000; font-size: 13px; filter: drop-shadow(0px 4px 4px rgba(0,0,0,0.4));">' + markers + '</div>',
        className: 'custom-cluster-leaf',
        iconSize: L.point(50, 50)
    }});
}}"""

marker_cluster = MarkerCluster(showCoverageOnHover=False, icon_create_function=codigo_cluster_js).add_to(mapa)

for index, row in df_mapa.iterrows():
    local_base = str(row.get('municipio_lista', 'Desconhecido')).title()
    sigla_estado = str(row.get('sigla_uf', '??'))
    local_exato = f"{local_base} - {sigla_estado}" 
    
    data_op = str(row.get('data', 'Sem data')).replace('nan', 'Não datado')
    instituicao = str(row.get('Instituição que efetuou a apreensao', 'Não informada')).replace('nan', 'Não informada')
    qtd = str(row.get('Quantidade de pés encontrados', 'Não especificado')).replace('nan', 'Não especificado')
    prensado = str(row.get('quantidade prensada (embalada)', 'Não informada')).replace('nan', 'Não informada')
    armas = str(row.get('armas apreendidas', 'Não informada')).replace('nan', 'Não informada')
    
    titulo = str(row.get('Titulo da reportagem', 'Registro sem título')).replace('nan', 'Sem título')
    resumo = str(row.get('resumo', 'Resumo indisponível.')).replace('nan', 'Resumo indisponível.')
    link = str(row.get('Link de acesso', '#')).replace('nan', '#')
    
    cidades_rede = str(row.get('municipios_envolvidos', ''))
    num_cidades = row.get('num_cidades_operacao', 1)

    if num_cidades > 1:
        alerta_simultaneidade = f"""
        <div style='background: #fdf5e6; color: #856404; padding: 10px; margin-bottom: 12px; border-left: 5px solid #d35400; font-family: Arial; font-size: 11px; border-radius: 3px;'>
            <b style='font-size: 12px;'>⚠️ ABRANGÊNCIA TERRITORIAL COMPARTILHADA</b><br>
            A estimativa quantitativa reflete uma ação institucional simultânea que abrangeu {num_cidades} municípios:<br>
            <i style='display: block; margin-top: 5px; color: #555;'>{cidades_rede}</i>
        </div>
        """
    else:
        alerta_simultaneidade = ""

    # HOVER ESTRANGULADO: Text-wrap forçado e cor da Erradicação em preto puro (#1a1a1a)
    html_tooltip = f"""
    <div style='font-family: Arial; font-size: 12px; padding: 6px; width: 260px; line-height: 1.4; white-space: normal; word-wrap: break-word;'>
        <b style='color: #1a1a1a; font-size: 13px; text-transform: uppercase;'>📍 {local_exato}</b><hr style='margin:4px 0;'>
        <span style='color: #555;'>Data: {data_op}</span><br>
        <span style='color: #1a1a1a;'><b>🌿 Erradicação Reportada:</b> {qtd}</span><br>
        {f"<span style='color: #d35400; font-size: 10px;'><i>⚡ Região de Atuação Limítrofe</i></span><br>" if num_cidades > 1 else ""}
        <i style='font-size: 10px; color: #888; margin-top: 4px; display: block;'>Clique para análise da ocorrência</i>
    </div>
    """

    # POPUP (Card) elegante, com limite estrito de overflow
    html_popup = f"""
    <div style='font-family: Arial; width: 330px; font-size: 12px; line-height: 1.6; color: #333; overflow-wrap: break-word;'>
        <h4 style='color: #1a1a1a; margin-bottom: 8px; font-size: 13px; text-transform: uppercase; font-weight: 900;'>{titulo}</h4>
        {alerta_simultaneidade}
        <div style='border-top: 2px solid #1a1a1a; border-bottom: 1px solid #ddd; padding: 10px 0; margin-bottom: 10px; font-size: 12px;'>
            <div style='margin-bottom: 4px;'>📍 <b>Local:</b> <span style='color: #d32f2f; font-weight: bold;'>{local_exato}</span></div>
            <div style='margin-bottom: 4px;'>📅 <b>Data:</b> {data_op}</div>
            <div style='margin-bottom: 4px;'>🚓 <b>Agência Institucional:</b> {instituicao}</div>
            <div style='margin-bottom: 4px;'>🌿 <b>Pés Erradicados:</b> {qtd}</div>
            <div style='margin-bottom: 4px;'>📦 <b>Maconha Prensada:</b> {prensado}</div>
            <div style='margin-bottom: 4px;'>🔫 <b>Armamento Apreendido:</b> {armas}</div>
        </div>
        <div style='background: #f8f9fa; padding: 12px; margin: 10px 0; border-left: 4px solid #27ae60; max-height: 140px; overflow-y: auto; text-align: justify; font-size: 11px;'>
            {resumo}
        </div>
        <a href='{link}' target='_blank' style='display: block; text-align: center; background: #1a1a1a; color: white; padding: 10px; text-decoration: none; font-weight: bold; border-radius: 4px; border: 1px solid #000; transition: background 0.3s;'>
            🔗 ACESSAR FONTE DOCUMENTAL
        </a>
    </div>
    """

    folium.Marker(
        location=[row['latitude'], row['longitude']],
        icon=folium.CustomIcon(ICON_LEAF, icon_size=(35, 35)),
        tooltip=folium.Tooltip(html_tooltip, sticky=True),
        popup=folium.Popup(html_popup, max_width=350)
    ).add_to(marker_cluster)

# =========================================================================================
# 8. ELEMENTOS DE UI PROPORCIONAIS E ACADÊMICOS
# =========================================================================================
elementos_interface = f"""
    <style>
        html, body, .leaflet-container {{ background-color: {COR_OCEANO} !important; }}
        .map-title {{
            position: fixed; top: 15px; left: 50%; transform: translateX(-50%); z-index: 9999;
            font-family: Arial, sans-serif; font-size: 15px; font-weight: 900; 
            background: rgba(255, 255, 255, 0.95); color: #1a1a1a; 
            padding: 10px 25px; border: 2px solid #1a1a1a; border-radius: 4px;
            text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            text-transform: uppercase; letter-spacing: 0.5px;
        }}
        .rosa-ventos {{ 
            position: fixed; top: 20px; right: 20px; z-index: 9999; 
            background: rgba(255, 255, 255, 0.95); padding: 8px; 
            border-radius: 50%; border: 2px solid #1a1a1a; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }}
        .legend-box {{ 
            position: fixed; bottom: 260px; right: 20px; z-index: 9999; 
            background: rgba(255, 255, 255, 0.95); padding: 15px; border: 2px solid #1a1a1a; 
            border-radius: 4px; font-family: Arial, sans-serif; font-size: 11px; 
            box-shadow: 0 4px 10px rgba(0,0,0,0.3); width: 280px;
        }}
        .credits-box {{ 
            position: fixed; bottom: 20px; right: 20px; z-index: 9999; 
            background: rgba(255, 255, 255, 0.95); color: #1a1a1a; padding: 15px 20px; 
            border-radius: 4px; font-family: Arial, sans-serif; font-size: 11px; 
            text-align: left; box-shadow: 0 4px 10px rgba(0,0,0,0.3); border: 2px solid #1a1a1a;
            width: 200px; line-height: 1.4;
        }}
    </style>

    <div class="map-title">Mapeamento Espacial da Erradicação de Cannabis no Brasil</div>
    
    <div class="rosa-ventos">
        <svg viewBox="0 0 100 100" width="45" height="45" xmlns="http://www.w3.org/2000/svg">
            <text x="50" y="15" font-family="Arial" font-size="14" font-weight="bold" text-anchor="middle" fill="#1a1a1a">N</text>
            <text x="50" y="96" font-family="Arial" font-size="12" font-weight="bold" text-anchor="middle" fill="#1a1a1a">S</text>
            <text x="94" y="54" font-family="Arial" font-size="12" font-weight="bold" text-anchor="middle" fill="#1a1a1a">L</text>
            <text x="6" y="54" font-family="Arial" font-size="12" font-weight="bold" text-anchor="middle" fill="#1a1a1a">O</text>
            <polygon points="50,18 60,50 50,82 40,50" fill="#1a1a1a"/>
            <polygon points="50,18 50,82 40,50" fill="#555"/>
            <polygon points="18,50 50,60 82,50 50,40" fill="#888"/>
            <polygon points="18,50 82,50 50,40" fill="#aaa"/>
        </svg>
    </div>

    <div class="legend-box">
        <b style="font-size: 13px; color: #1a1a1a; display: block; margin-bottom: 8px; border-bottom: 2px solid #1a1a1a; padding-bottom: 4px;">TIPOLOGIA TERRITORIAL</b>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 5px 10px 5px 0; color: #1a1a1a; font-weight: bold;">Área de Concentração de Lavouras Ilícitas</td>
                <td style="padding: 5px 0; text-align: center;"><i style="background:rgba(255, 165, 0, 0.3); width:14px; height:14px; display:inline-block; border:1px solid orange; vertical-align: middle;"></i></td>
            </tr>
            <tr>
                <td style="padding: 5px 10px 5px 0; color: #1a1a1a; font-weight: bold;">Localidade de Erradicação / Intervenção</td>
                <td style="padding: 5px 0; text-align: center;"><img src="{ICON_LEAF}" width="20" style="vertical-align: middle;"></td>
            </tr>
        </table>
    </div>

    <div class="credits-box">
        <div style="margin-bottom: 6px;">
            <b>Coordenação:</b><br>
            Prof. Dr. Paulo Fraga
        </div>
        <div style="margin-bottom: 6px;">
            <b>Desenvolvimento:</b><br>
            Ms. Alessandro Carneiro
        </div>
        <div style="margin-bottom: 6px;">
            <b>Dados:</b><br>
            Maria Alice Vallo
        </div>
        <div style="margin-bottom: 8px;">
            <b>Parceiro:</b><br>
            Canabis Monitor
        </div>
        <hr style="border: 0; border-top: 1px solid #1a1a1a; margin: 8px 0;">
        <div style="text-align: center; font-weight: 900; font-size: 11px; color: #1a1a1a;">
            NEVIDH - UFJF 2026
        </div>
    </div>
"""
mapa.get_root().html.add_child(folium.Element(elementos_interface))

# =========================================================================================
# 9. COMPILAÇÃO FINAL
# =========================================================================================
mapa.save('mapa_definitivo_geocannabis.html')
logger.info(f"Métrica Final: {len(df_mapa)} marcações táticas estabelecidas no território brasileiro.")