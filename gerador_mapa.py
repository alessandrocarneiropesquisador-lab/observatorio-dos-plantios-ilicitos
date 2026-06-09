#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=========================================================================================
OBSERVATÓRIO DOS PLANTIOS ILÍCITOS NO BRASIL
Pesquisador: Ms. Alessandro Carneiro | NEVIDH - UFJF 2026
Objetivo: Mapeamento Sociológico e Cartografia de Precisão
=========================================================================================
"""
from folium.plugins import MousePosition
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
# 0. CONFIGURAÇÃO DE LOGS E AMBIENTE
# =========================================================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s [ %(levelname)s ] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

ARQ_ANTIGO = 'dados_antigos.csv'
ARQ_NOVO = 'dados_novos.csv'

if not os.path.exists(ARQ_ANTIGO) or not os.path.exists(ARQ_NOVO):
    logger.error(f"FATAL: Cadeia de custódia quebrada. Exijo '{ARQ_ANTIGO}' e '{ARQ_NOVO}' na mesma pasta.")
    sys.exit(1)

# =========================================================================================
# 1. MATRIZ DE NORMALIZAÇÃO ESPACIAL
# =========================================================================================
CORRECOES_MUNICIPIOS = {
    "rio janeiro": "rio de janeiro", "nas áreas caatinga em salgueiro": "salgueiro",
    "nas regiões orocó": "orocó", "circunscrição salgueiro": "salgueiro",
    "parauaopebas": "parauapebas", "brotas macaúbas": "brotas de macaúbas",
    "encontrado no km 402 da rodovia 020 em caucaia": "caucaia",
    "distrito pedro juan caballero": "ponta porã", "belém de são francisco": "belém do são francisco",
    "cabobró": "cabrobó", "conceição do lago açu": "conceição do lago-açu",
    "muquém do são francisco": "muquém de são francisco", "droga veio belém": "belém",
    "com destino para fortaleza": "fortaleza", "região do patrocínio": "patrocínio",
    "alto turiaçu": "turiaçu", "caraúba": "caraúbas",
    "ibimirim e serra talhada": "ibimirim", "e manaíra": "manaíra"
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
# 2. CARGA DE DADOS E ENGENHARIA DE RASTREABILIDADE
# =========================================================================================
df_a = pd.read_csv(ARQ_ANTIGO, sep=',', engine='python', on_bad_lines='skip')
df_n = pd.read_csv(ARQ_NOVO, sep=',', engine='python', on_bad_lines='skip')
df_a.columns = df_a.columns.str.strip()
df_n.columns = df_n.columns.str.strip()
df_base = pd.concat([df_a, df_n], ignore_index=True)

def rotina_limpeza(texto):
    if pd.isna(texto): return ""
    t = re.sub(r'\(.*?\)', '', str(texto)) 
    t = re.sub(r'/(PE|PA|PB|MA|BA|CE|AM|DF|RJ|SP|MG|RS|PR|SC|GO|MT|MS|TO|RO|AC|RR|AP|RN|AL|SE)', '', t, flags=re.IGNORECASE)
    for ruido in [r'\bentre\b', r'\bos\b', r'\bas\b', r'\bmunicípios\b', r'\bcidades\b', r'\bde\b', r'\bpróximo\b', r'\bao\b', r'\bproximidades\b', r'\bda\b', r'\bna\b']: 
        t = re.sub(ruido, ' ', t, flags=re.IGNORECASE)
    return t.replace(" e ", ", ").replace(".", ", ")

def extrair_lista(t):
    return [c.strip() for c in t.split(",") if len(c.strip()) > 2 and c.strip().lower() not in ['brasil', 'amazonas', 'bahia', 'pernambuco', 'paraíba', 'maranhão', 'pará', 'aparato geral']]

col_alvo = next((c for c in df_base.columns if 'municipio' in c.lower() or 'município' in c.lower()), None)
df_base['municipio_lista'] = df_base[col_alvo].apply(rotina_limpeza).apply(extrair_lista)
df_base['municipios_envolvidos'] = df_base['municipio_lista'].apply(lambda x: " | ".join([str(c).upper() for c in x]))
df_base['num_cidades_operacao'] = df_base['municipio_lista'].apply(len)

df_explodido = df_base.explode('municipio_lista').dropna(subset=['municipio_lista'])
df_explodido['municipio_match'] = df_explodido['municipio_lista'].apply(lambda x: CORRECOES_MUNICIPIOS.get(str(x).lower().strip(), str(x).lower().strip()))
df_explodido['lat_especial'] = df_explodido['municipio_match'].apply(lambda x: ENTIDADES_ESPECIAIS.get(x, {}).get('lat', None))
df_explodido['lon_especial'] = df_explodido['municipio_match'].apply(lambda x: ENTIDADES_ESPECIAIS.get(x, {}).get('lon', None))
df_explodido['uf_especial'] = df_explodido['municipio_match'].apply(lambda x: ENTIDADES_ESPECIAIS.get(x, {}).get('uf', None))

logger.info("Acessando malha geodésica do IBGE...")
coords = pd.read_csv(io.StringIO(requests.get("https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv", timeout=10).text))
coords['nome_match'] = coords['nome'].astype(str).str.lower().str.strip()
coords['sigla_uf'] = coords['codigo_uf'].map(MAPA_UF)
coords = coords.drop_duplicates(subset=['nome_match'])

df_mapa = pd.merge(df_explodido, coords[['nome_match', 'latitude', 'longitude', 'sigla_uf']], left_on='municipio_match', right_on='nome_match', how='left')
df_mapa['latitude'] = df_mapa['lat_especial'].combine_first(df_mapa['latitude'])
df_mapa['longitude'] = df_mapa['lon_especial'].combine_first(df_mapa['longitude'])
df_mapa['sigla_uf'] = df_mapa['uf_especial'].combine_first(df_mapa['sigla_uf'])
df_mapa = df_mapa.dropna(subset=['latitude', 'longitude']).copy()

np.random.seed(42) 
df_mapa['latitude'] += np.random.uniform(-0.012, 0.012, len(df_mapa))
df_mapa['longitude'] += np.random.uniform(-0.012, 0.012, len(df_mapa))

# =========================================================================================
# 3. FUNDAÇÃO CARTOGRÁFICA, MÁSCARA DE ISOLAMENTO E POLÍGONOS
# =========================================================================================
COR_OCEANO = '#e3eaef'
mapa = folium.Map(
    location=[-14.235, -51.925], zoom_start=4, min_zoom=4, control_scale=True, tiles='OpenStreetMap'
)
MousePosition(
    position='bottomleft',
    separator='  |  Lat: ',
    empty_string='Fora do Perímetro',
    lng_first=False,
    num_digits=6,
    prefix='Long: '
).add_to(mapa)
mapa.get_root().html.add_child(folium.Element("<style>.leaflet-marker-pane { z-index: 600 !important; } .leaflet-tooltip-pane { z-index: 650 !important; } .leaflet-popup-pane { z-index: 700 !important; }</style>"))

logger.info("A aplicar blecaute geométrico global...")
try:
    url_br_hr = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    br_geojson = requests.get(url_br_hr, timeout=20).json()
    poligonos_estados = [shape(feature['geometry']) for feature in br_geojson['features']]
    brasil_exato = unary_union(poligonos_estados).buffer(0.04)
    mascara_global = box(-180, -90, 180, 90).difference(brasil_exato)
    
    folium.GeoJson(
        mapping(mascara_global),
        style_function=lambda x: {'fillColor': COR_OCEANO, 'color': COR_OCEANO, 'weight': 1.5, 'fillOpacity': 1.0}
    ).add_to(mapa)
except Exception as e:
    logger.error(f"Erro ao isolar o Brasil: {e}")

folium.Polygon(
    locations=[[-8.1, -40.2], [-7.5, -39.0], [-8.0, -37.8], [-9.2, -38.0], [-9.8, -39.5], [-9.2, -40.8]],
    color="#d35400", weight=2, fill=True, fill_color="#f39c12", fill_opacity=0.3,
    tooltip=folium.Tooltip("<div style='font-family: Arial; font-size: 11px;'><b>Área de Concentração Histórica</b></div>", sticky=False, direction='auto')
).add_to(mapa)

folium.Polygon(
    locations=[[-2.75, -46.70], [-2.70, -46.30], [-3.15, -46.10], [-3.25, -46.60]],
    color="#8b0000", weight=2, fill=True, fill_color="#ff4500", fill_opacity=0.15,
    tooltip=folium.Tooltip("<div style='font-family: Arial; font-size: 11px; background: #fff3cd; color: #856404; padding: 8px; border-left: 4px solid #8b0000; display: flex; align-items: center;'><img src='logo_funai.png' style='width: 35px; height: 35px; margin-right: 10px; border-radius: 3px;'><div><b>TERRA INDÍGENA ALTO RIO GUAMÁ</b><br>Território de Proteção Federal Originária<br><i>Anomalia Jurisdicional Detectada</i></div></div>", sticky=False, direction='auto')
).add_to(mapa)

# =========================================================================================
# 4. RENDERIZAÇÃO DOS DADOS E GATILHOS DE ALERTA
# =========================================================================================
ICON_LEAF = "https://img.icons8.com/color/48/marijuana-leaf.png" 
codigo_cluster_js = f"function(c) {{ return L.divIcon({{ html: '<div style=\"background-image: url({ICON_LEAF}); background-size: cover; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; font-family: Arial; font-weight: 900; color: #000; font-size: 13px; filter: drop-shadow(0px 4px 4px rgba(0,0,0,0.4));\">' + c.getChildCount() + '</div>', className: 'custom-cluster-leaf', iconSize: L.point(50, 50) }}); }}"
marker_cluster = MarkerCluster(showCoverageOnHover=False, icon_create_function=codigo_cluster_js).add_to(mapa)

for index, row in df_mapa.iterrows():
    local_base = str(row.get('municipio_lista', 'Desconhecido')).title()
    local_exato = f"{local_base} - {str(row.get('sigla_uf', '??'))}" 
    data_bruta = str(row.get('data', 'Sem data')).strip()
    data_op = f"{data_bruta.split('/')[1]}/{data_bruta.split('/')[0]}/{data_bruta.split('/')[2]}" if '/' in data_bruta and len(data_bruta.split('/')) == 3 and data_bruta.split('/')[0].isdigit() and int(data_bruta.split('/')[0]) <= 12 else data_bruta

    instituicao = str(row.get('Instituição que efetuou a apreensao', 'Não informada')).replace('nan', 'Não informada')
    qtd = str(row.get('Quantidade de pés encontrados', 'Não especificado')).replace('nan', 'Não especificado')
    prensado = str(row.get('quantidade prensada (embalada)', 'Não informada')).replace('nan', 'Não informada')
    armas = str(row.get('armas apreendidas', 'Não informada')).replace('nan', 'Não informada')
    titulo = str(row.get('Titulo da reportagem', 'Registo sem título')).replace('nan', 'Sem título')
    resumo = str(row.get('resumo', 'Resumo indisponível.')).replace('nan', 'Resumo indisponível.')
    link = str(row.get('Link de acesso', '#')).replace('nan', '#')
    num_cidades = row.get('num_cidades_operacao', 1)

    alerta_simultaneidade = f"<div style='background: #fdf5e6; color: #856404; padding: 10px; margin-bottom: 12px; border-left: 5px solid #d35400; font-family: Arial; font-size: 11px;'><b style='font-size: 12px;'>⚠️ ABRANGÊNCIA COMPARTILHADA</b><br>Operação abrangeu {num_cidades} municípios:<br><i>{str(row.get('municipios_envolvidos', ''))}</i></div>" if num_cidades > 1 else ""
    
    alerta_indigena = f"<div style='background: #ffe6e6; color: #721c24; padding: 10px; margin-bottom: 12px; border-left: 5px solid #8b0000; font-family: Arial; font-size: 11px; display: flex; align-items: center;'><img src='logo_funai.png' style='width: 45px; height: 45px; margin-right: 12px; background: white; padding: 2px; border-radius: 50%; border: 1px solid #8b0000;'><div><b style='font-size: 12px;'>ALERTA DE JURISDIÇÃO: TERRITÓRIO ORIGINÁRIO</b><br>Operação estatal em Terra Indígena demarcada.</div></div>" if "guamá" in local_base.lower() or "indígena" in local_base.lower() else ""

    if any(termo in local_base.lower() for termo in ['rio ', 'ilha', 'barco', 'japurá']):
        alerta_fluvial = "<div style='background: #e6f2ff; color: #004085; padding: 10px; margin-bottom: 12px; border-left: 5px solid #0056b3; font-family: Arial; font-size: 11px; display: flex; align-items: center;'><div style='font-size: 24px; margin-right: 12px;'>🚤</div><div><b style='font-size: 12px;'>ALERTA TÁTICO: OPERAÇÃO FLUVIAL</b><br>Intervenção em calha fluvial ou arquipélago. O isolamento geográfico potencializa a assimetria da força.</div></div>"
        tag_fluvial = "<span style='color: #0056b3; font-weight: bold;'>🌊 Zona de Intervenção Fluvial</span><br>"
    else:
        alerta_fluvial, tag_fluvial = "", ""

    html_tooltip = f"<div style='font-family: Arial; font-size: 12px; padding: 6px; min-width: 300px; max-width: 450px; white-space: normal; line-height: 1.4; white-space: normal !important; overflow-wrap: break-word; word-break: normal;'><b style='color: #1a1a1a; font-size: 13px; text-transform: uppercase;'>📍 {local_exato}</b><hr style='margin:4px 0;'><span style='color: #555;'>Data: {data_op}</span><br>{tag_fluvial}<span style='color: #1a1a1a;'><b>🌿 Erradicação Reportada:</b> {qtd}</span><br></div>"
    
    html_popup = f"<div style='font-family: Arial; width: 100%; max-width: 300px; font-size: 12px; line-height: 1.6; color: #333; overflow-wrap: break-word;'><h4 style='color: #1a1a1a; margin-bottom: 8px; font-size: 13px; text-transform: uppercase; font-weight: 900;'>{titulo}</h4>{alerta_simultaneidade}{alerta_indigena}{alerta_fluvial}<div style='border-top: 2px solid #1a1a1a; border-bottom: 1px solid #ddd; padding: 10px 0; margin-bottom: 10px; font-size: 12px;'><div style='margin-bottom: 4px;'>📍 <b>Local:</b> {local_exato}</div><div style='margin-bottom: 4px;'>📅 <b>Data:</b> {data_op}</div><div style='margin-bottom: 4px;'>🚓 <b>Agência:</b> {instituicao}</div><div style='margin-bottom: 4px;'>🌿 <b>Pés Erradicados:</b> {qtd}</div><div style='margin-bottom: 4px;'>📦 <b>Maconha Prensada:</b> {prensado}</div><div style='margin-bottom: 4px;'><img src='pistola.png' style='width: 16px; height: auto; vertical-align: middle; margin-right: 4px; padding-bottom: 2px;'> <b>Armamento:</b> {armas}</div></div><div style='background: #f8f9fa; padding: 12px; margin: 10px 0; border-left: 4px solid #27ae60; max-height: 140px; overflow-y: auto; text-align: justify; font-size: 11px;'>{resumo}</div><a href='{link}' target='_blank' style='display: block; text-align: center; background: #1a1a1a; color: white; padding: 10px; text-decoration: none; font-weight: bold; border-radius: 4px; border: 1px solid #000;'>🔗 ACESSAR FONTE DOCUMENTAL</a></div>"

    folium.Marker(
        location=[row['latitude'], row['longitude']], 
        icon=folium.CustomIcon(ICON_LEAF, icon_size=(35, 35)), 
        tooltip=folium.Tooltip(html_tooltip, sticky=False, direction='auto'), 
        popup=folium.Popup(html_popup, max_width=350)
    ).add_to(marker_cluster)
# 5. UI ESTÁTICA, CO-BRANDING INSTITUCIONAL E ACABAMENTO DE ALTO PADRÃO
# =========================================================================================
elementos_interface = f"""
    <style>
        .map-title {{
            position: fixed; top: 15px; left: 50%; transform: translateX(-50%); z-index: 1000;
            font-family: Arial, sans-serif; font-size: 15px; font-weight: 900; background: rgba(255, 255, 255, 0.98);
            padding: 10px 22px; border: 2px solid #1a1a1a; box-shadow: 0 4px 15px rgba(0,0,0,0.25);
            text-transform: uppercase; white-space: nowrap;
            
            /* Engenharia Flexbox para Alinhamento Euro-Science */
            display: flex; align-items: center; justify-content: center; gap: 18px;
            min-width: 620px; border-radius: 2px;
        }}
        .logo-nevidh {{
            height: 38px; width: auto; display: block;
        }}
        .logo-brasil {{
            height: 24px; width: auto; display: block; border: 1px solid #eaeaea;
            /* Compensação óptica: a bandeira é horizontal, então uma altura menor equilibra a massa visual */
        }}
        .rosa-ventos {{ 
            position: fixed; top: 20px; right: 20px; z-index: 1000; 
            background: rgba(255,255,255,0.8); border-radius: 50%; box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            padding: 5px;
        }}
        .legend-box {{ 
            position: fixed; bottom: 215px; right: 20px; z-index: 1000; 
            background: rgba(255, 255, 255, 0.95); padding: 12px; border: 2px solid #1a1a1a; 
            font-family: Arial, sans-serif; font-size: 11px; width: 230px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            transition: opacity 0.4s ease-in-out;
        }}
        .legend-box:hover {{
            opacity: 0.10;
        }}
        .credits-box {{ 
            position: fixed; bottom: 20px; right: 20px; z-index: 1000; 
            background: rgba(255, 255, 255, 0.95); padding: 12px; border: 2px solid #1a1a1a; 
            font-family: Arial, sans-serif; font-size: 10px; width: 230px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            line-height: 1.5;
            transition: opacity 0.4s ease-in-out;
        }}
        .credits-box:hover {{
            opacity: 0.10;
        }}
    </style>

    <div class="map-title">
        <img src="nevidh_logo.png" alt="NEVIDH" class="logo-nevidh">
        
        <span style="letter-spacing: 0.5px; color: #1a1a1a;">ATLAS DA ERRADICAÇÃO DA CANNABIS NO BRASIL</span>
        
        <img src="brasil_flag.png" alt="Brasil" class="logo-brasil">
    </div>
    
    <div class="rosa-ventos">
        <svg width="45" height="45" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="42" fill="none" stroke="#1a1a1a" stroke-width="2"/>
            <polygon points="50,10 58,42 50,50 42,42" fill="#1a1a1a"/>
            <polygon points="50,90 58,58 50,50 42,58" fill="#555"/>
            <polygon points="10,50 42,42 50,50 42,58" fill="#888"/>
            <polygon points="90,50 58,42 50,50 58,58" fill="#ccc"/>
            <circle cx="50" cy="50" r="4" fill="white" stroke="#1a1a1a" stroke-width="1"/>
        </svg>
    </div>

    <div class="legend-box">
        <b style="display:block; margin-bottom:6px; border-bottom:1px solid #1a1a1a; padding-bottom:4px; font-size:12px;">TIPOLOGIA TERRITORIAL</b>
        <table style="width:100%; border-collapse:collapse;">
            <tr><td style="padding:4px 0;">Área de Concentração</td><td style="text-align:right;"><i style="background:rgba(255, 165, 0, 0.5); width:14px; height:14px; display:inline-block; border:1px solid #d35400;"></i></td></tr>
            <tr><td style="padding:4px 0;">Território Indígena</td><td style="text-align:right;"><i style="background:rgba(255, 69, 0, 0.2); width:14px; height:14px; display:inline-block; border:1px solid #8b0000;"></i></td></tr>
            <tr><td style="padding:4px 0;">Intervenção Hídrica</td><td style="text-align:right; font-size:14px;">🚤</td></tr>
            <tr><td style="padding:4px 0;">Ponto de Intervenção</td><td style="text-align:right;"><img src="{ICON_LEAF}" width="16"></td></tr>
        </table>
    </div>

    <div class="credits-box">
        <b>Coordenação:</b> Prof. Dr. Paulo Fraga<br>
        <b>Desenvolvimento:</b> Ms. Alessandro Carneiro<br>
        <b>Dados:</b> Maria Alice Vallo<br>
        <b>Parceiro:</b> Canabis Monitor<br>
        <hr style="margin:6px 0; border:0; border-top:1px solid #1a1a1a;">
        <div style="text-align:center; font-weight:900;">NEVIDH - UFJF 2026</div>
    </div>
"""
mapa.get_root().html.add_child(folium.Element(elementos_interface))

nome_mapa = mapa.get_name()
trava_centro_js = f"""
<script>
    document.addEventListener("DOMContentLoaded", function() {{
        var map_instance = {nome_mapa};
        var limites_territorio = L.latLngBounds(L.latLng(-35.0, -75.0), L.latLng(6.0, -34.0));
        map_instance.setMaxBounds(limites_territorio);
        map_instance.options.worldCopyJump = false;

        function gerenciar_trava_centro() {{
            if (map_instance.getZoom() <= 4) {{
                map_instance.dragging.disable();
                map_instance.setView([-14.235, -51.925], 4, {{animate: false}});
            }} else {{
                map_instance.dragging.enable();
            }}
        }}
        map_instance.on('zoomend', gerenciar_trava_centro);
        gerenciar_trava_centro();
    }});
</script>
"""
mapa.get_root().html.add_child(folium.Element(trava_centro_js))

mapa.save('index.html')
logger.info("Isolamento geométrico total estabelecido. Arquivo gerado: index.html")