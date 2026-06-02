import pandas as pd
import folium
from folium.plugins import MarkerCluster
import requests
import io
import sys
import base64
import os
from shapely.geometry import shape, box, mapping
from shapely.ops import unary_union

# ==============================================================================
# 1. CARGA DE DADOS (BASE DO MAPA MÃE)
# ==============================================================================
print("Fase 1: Carga de Dados Científicos...")
try:
    df = pd.read_csv('geocannabis_DASHBOARD_FINAL.csv').dropna(subset=['codigo_ibge'])
    url_coords = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
    coords = pd.read_csv(io.StringIO(requests.get(url_coords).text))
    
    df['codigo_ibge'] = df['codigo_ibge'].astype(int)
    coords['codigo_ibge'] = coords['codigo_ibge'].astype(int)
    df_mapa = pd.merge(df, coords[['codigo_ibge', 'latitude', 'longitude']], on='codigo_ibge', how='inner')
    
    if 'estado_ibge' in df_mapa.columns:
        df_mapa['estado_ibge'] = df_mapa['estado_ibge'].replace({'Federal District': 'Distrito Federal'})
except Exception as e:
    print(f"❌ Erro Crítico nos Dados: {e}"); sys.exit()

# ==============================================================================
# 2. FUNDAÇÃO CARTOGRÁFICA (MOTOR SELADO)
# ==============================================================================
COR_OCEANO = '#e3eaef'

mapa = folium.Map(
    location=[-15.0000, -53.0000],
    zoom_start=4.6, 
    min_zoom=4.6, 
    zoom_snap=0.1,  
    zoom_delta=0.5, 
    tiles=None, 
    control_scale=True,
    zoom_control=True 
)

folium.TileLayer(
    'cartodb positron', 
    no_wrap=True,
    bounds=[[-50.0, -90.0], [15.0, -30.0]] 
).add_to(mapa)

mapa.fit_bounds([[-34.0, -74.0], [5.0, -34.0]])
mapa.options['maxBounds'] = [[-40.0, -80.0], [10.0, -20.0]]
mapa.options['maxBoundsViscosity'] = 1.0

# ==============================================================================
# 3. MÁSCARA DE ANULAÇÃO GLOBAL (COM BUFFER DE RESPIRO LITORÂNEO)
# ==============================================================================
print("Fase 3: Aplicando Máscara de Anulação Global (Com expansão de borda)...")
try:
    url_br_hr = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    br_geojson = requests.get(url_br_hr, timeout=15).json()

    poligonos_estados = [shape(feature['geometry']) for feature in br_geojson['features']]
    
    # A SOLUÇÃO: .buffer(0.04) expande o "buraco" do Brasil em cerca de 4 a 5km para fora.
    # Isso impede que o mapa azul corte praias (Balneário Camboriú) e os nomes dos estados.
    brasil_exato = unary_union(poligonos_estados).buffer(0.04)

    planeta_terra = box(-180, -90, 180, 90)
    mascara_global = planeta_terra.difference(brasil_exato)

    folium.GeoJson(
        mapping(mascara_global),
        name="Oceano Global",
        style_function=lambda x: {
            'fillColor': COR_OCEANO,
            'color': COR_OCEANO, 
            'weight': 1.5,
            'fillOpacity': 1.0
        },
        z_index=0
    ).add_to(mapa)
    print("✅ Isolamento Tático Perfeito. Margem de segurança aplicada no litoral.")

except Exception as e:
    print(f"❌ Falha na Engenharia Cartográfica: {e}")

# ==============================================================================
# 4. POLÍGONO DA MACONHA
# ==============================================================================
folium.Polygon(
    locations=[[-8.1, -40.2], [-7.5, -39.0], [-8.0, -37.8], [-9.2, -38.0], [-9.8, -39.5], [-9.2, -40.8]],
    color="orange", weight=2, fill=True, fill_color="yellow", fill_opacity=0.3, z_index=1
).add_to(mapa)

# ==============================================================================
# 5. ÍCONES E CARDS (ALINHAMENTO À ESQUERDA - INTOCÁVEL)
# ==============================================================================
icon_leaf = "https://img.icons8.com/color/48/marijuana-leaf.png" 

marker_cluster = MarkerCluster(
    showCoverageOnHover=False,
    icon_create_function=f"""
    function(cluster) {{
        return L.divIcon({{
            html: '<div style="background-image: url({icon_leaf}); background-size: 100%; width: 45px; height: 45px; display: flex; align-items: center; justify-content: center; font-family: Arial; font-weight: bold; color: black; font-size: 12px; text-shadow: 1px 1px 2px white;">' + cluster.getChildCount() + '</div>',
            className: 'custom-cluster-leaf', iconSize: L.point(45, 45)
        }});
    }}"""
).add_to(mapa)

def embed_pistola(path):
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f"data:image/jfif;base64,{base64.b64encode(f.read()).decode('utf-8')}"
    except: pass
    return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 576 512'><path fill='%231a1a1a' d='M528 224H272c-8.8 0-16 7.2-16 16v32H56c-13.3 0-24 10.7-24 24v128c0 13.3 10.7 24 24 24h72c13.3 0 24-10.7 24-24v-16h48.3c8.1 0 15.5-5 18.7-12.6l61.9-148.5c1-2.4 3.4-3.9 6-3.9h239c13.3 0 24-10.7 24-24v-32c0-13.3-10.7-24-24-24zM128 368H64v-64h64v64zm384-240v-16c0-26.5-21.5-48-48-48H128c-26.5 0-48 21.5-48 48v16c0 26.5 21.5 48 48 48h336c26.5 0 48-21.5 48-48z'/></svg>"

pistola_src = embed_pistola("pistola.jfif")

for _, row in df_mapa.iterrows():
    html_tooltip = f"""
    <div style='width: 220px; text-align: left; font-family: Arial, sans-serif; font-size: 11px; padding: 4px; line-height: 1.5; white-space: normal; word-wrap: break-word;'>
        <div style='color: #1a1a1a; font-size: 12px; border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-bottom: 6px;'>
            📍 <b>Local:</b> {row['municipio_ibge']} - {row['estado_ibge']}
        </div>
        <div style='margin-bottom: 4px;'>🚓 <b>Força:</b> {row['Instituição que efetuou a apreensao']}</div>
        <div>🌿 <b>Pés:</b> {row['Quantidade de pés encontrados']}</div>
    </div>"""

    html_popup = f"""
    <div style='min-width: 280px; text-align: left; font-family: Arial, sans-serif; font-size: 12px; line-height: 1.6; white-space: normal; word-wrap: break-word;'>
        <b style='color: #1a1a1a; font-size: 13px; display: block; border-bottom: 1px solid #1a1a1a; margin-bottom: 8px; text-align: center;'>INFORMAÇÕES DETALHADAS</b>
        
        <div style='margin-bottom: 4px;'>📍 <b>Local:</b> {row['municipio_ibge']} - {row['estado_ibge']}</div>
        <div style='margin-bottom: 4px;'>🗓️ <b>Data:</b> {row['data']}</div>
        <div style='margin-bottom: 4px;'>🚔 <b>Força:</b> {row['Instituição que efetuou a apreensao']}</div>
        <div style='margin-bottom: 4px;'>🌿 <b>Pés Encontrados:</b> {row['Quantidade de pés encontrados']}</div>
        <div style='margin-bottom: 4px;'>📦 <b>Maconha Prensada:</b> {row['quantidade prensada (embalada)']}</div>
        
        <div style="display: flex; justify-content: flex-start; align-items: center; margin-top: 6px; border-top: 1px solid #ddd; padding-top: 6px;">
            <img src="{pistola_src}" style="height: 14px; margin-right: 6px;">
            <b>Armas Apreendidas:</b> {row['armas apreendidas']}
        </div>
        
        <hr style='margin: 10px 0 8px 0; border: 0; border-top: 1px solid #1a1a1a;'>
        <div style='text-align: center;'><a href='{row['Link de acesso']}' target='_blank' style='color: #2980B9; font-weight: bold;'>🔗 ACESSAR NOTÍCIA</a></div>
    </div>"""
    
    folium.Marker(
        location=[row['latitude'], row['longitude']],
        icon=folium.CustomIcon(icon_leaf, icon_size=(30, 30)),
        tooltip=folium.Tooltip(html_tooltip, sticky=True),
        popup=folium.Popup(html_popup, max_width=400)
    ).add_to(marker_cluster)

# ==============================================================================
# 6. CSS E ROSA DOS VENTOS VETORIAL (SELADA)
# ==============================================================================
rosa_dos_ventos_svg = """
    <div class="north-arrow">
        <svg viewBox="0 0 100 100" width="45" height="45" xmlns="http://www.w3.org/2000/svg">
            <text x="50" y="12" font-family="Arial" font-size="14" font-weight="bold" text-anchor="middle" fill="#1a1a1a">N</text>
            <text x="50" y="98" font-family="Arial" font-size="12" font-weight="bold" text-anchor="middle" fill="#1a1a1a">S</text>
            <text x="96" y="54" font-family="Arial" font-size="12" font-weight="bold" text-anchor="middle" fill="#1a1a1a">L</text>
            <text x="4" y="54" font-family="Arial" font-size="12" font-weight="bold" text-anchor="middle" fill="#1a1a1a">O</text>
            <polygon points="50,15 60,50 50,85 40,50" fill="#1a1a1a"/>
            <polygon points="50,15 50,85 40,50" fill="#555"/>
            <polygon points="15,50 50,60 85,50 50,40" fill="#888"/>
            <polygon points="15,50 85,50 50,40" fill="#aaa"/>
        </svg>
    </div>
"""

layout_html = f"""
    <style>
        html, body, .leaflet-container {{ background-color: {COR_OCEANO} !important; margin: 0; padding: 0; height: 100vh; overflow: hidden; }}
        
        .map-title {{
            position: fixed; top: 10px; left: 50%; transform: translateX(-50%); z-index: 9999;
            font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; 
            background: rgba(255, 255, 255, 0.95); color: #1a1a1a; 
            padding: 8px 15px; 
            border: 2px solid #1a1a1a; border-radius: 4px;
            text-align: center; text-transform: uppercase; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            white-space: nowrap;
        }}
        
        .leaflet-top.leaflet-left {{ top: 60px !important; left: 20px !important; }}
        .leaflet-control-zoom {{ border: 2px solid #1a1a1a !important; box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important; background: white !important; }}
        .leaflet-control-zoom-in, .leaflet-control-zoom-out {{ color: #1a1a1a !important; font-weight: bold; }}

        .north-arrow {{ 
            position: fixed; top: 15px; right: 20px; z-index: 9999; 
            background: rgba(255, 255, 255, 0.95); padding: 5px; 
            border-radius: 50%; border: 2px solid #1a1a1a; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            display: flex; align-items: center; justify-content: center;
        }}

        .legend-box {{ 
            position: fixed; bottom: 100px; right: 20px; z-index: 9999; 
            background: rgba(255, 255, 255, 0.95); padding: 12px 15px; border: 2px solid #1a1a1a; border-radius: 4px; 
            font-family: Arial, sans-serif; font-size: 11px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); 
        }}
        
        .credits-box {{ 
            position: fixed; bottom: 15px; right: 20px; z-index: 9999; 
            background: rgba(255, 255, 255, 0.95); padding: 10px 15px; border: 2px solid #1a1a1a; border-radius: 4px; 
            font-family: Arial, sans-serif; font-size: 11px; line-height: 1.6; text-align: right; box-shadow: 0 4px 10px rgba(0,0,0,0.3); 
        }}
        
        .leaflet-control-scale-line {{ border: 2px solid #1a1a1a !important; color: #1a1a1a !important; font-weight: bold; background: rgba(255, 255, 255, 0.9) !important; }}
    </style>

    <div class="map-title">DISTRIBUIÇÃO ESPACIAL DE APREENSÕES E ERRADICAÇÃO DE CANNABIS NO BRASIL</div>
    
    {rosa_dos_ventos_svg}

    <div class="legend-box">
        <b style="font-size: 12px; color: #1a1a1a; display: block; margin-bottom: 5px; border-bottom: 1px solid #1a1a1a;">LEGENDA</b>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 3px 10px 3px 0; color: #1a1a1a;">Polígono da Maconha</td>
                <td style="padding: 3px 0; text-align: center;"><i style="background:rgba(255, 165, 0, 0.3); width:14px; height:14px; display:inline-block; border:1px solid orange; vertical-align: middle;"></i></td>
            </tr>
            <tr>
                <td style="padding: 3px 10px 3px 0; color: #1a1a1a;">Local de Apreensão</td>
                <td style="padding: 3px 0; text-align: center;"><img src="{icon_leaf}" width="18" style="vertical-align: middle;"></td>
            </tr>
        </table>
    </div>

    <div class="credits-box">
        <b>Produzido por:</b> Me. Alessandro Carneiro<br>
        <b>Dados:</b> Prof. Dr. Paulo Fraga
    </div>
"""
mapa.get_root().html.add_child(folium.Element(layout_html))

mapa.save('mapa_geocannabis_final.html')
print("🚀 GRAND FINALE CONCLUÍDO. Buffer Litorâneo Aplicado. Nomes e Costa preservados.")