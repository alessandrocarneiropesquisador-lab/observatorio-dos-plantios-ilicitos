#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import re
import logging

# Configuração tática do terminal
logging.basicConfig(level=logging.INFO, format='%(asctime)s [ %(levelname)s ] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

ARQ_ANTIGO = 'dados_antigos.csv'
ARQ_NOVO = 'dados_novos.csv'

logger.info("Iniciando extração e consolidação da matriz empírica...")

try:
    df_a = pd.read_csv(ARQ_ANTIGO, sep=',', engine='python', on_bad_lines='skip')
    df_n = pd.read_csv(ARQ_NOVO, sep=',', engine='python', on_bad_lines='skip')
    
    # Padronização de cabeçalhos para evitar atrito
    df_a.columns = df_a.columns.str.strip()
    df_n.columns = df_n.columns.str.strip()
    
    df_base = pd.concat([df_a, df_n], ignore_index=True)
    logger.info(f"Fusão concluída. Total de registros brutos: {len(df_base)}")
except Exception as e:
    logger.error(f"Falha crítica na leitura dos arquivos: {e}")
    exit()

# =========================================================================================
# 1. ENGENHARIA DE ATRIBUTOS (LIMPEZA LETAL)
# =========================================================================================
COL_INSTITUICAO = 'Instituição que efetuou a apreensao'
COL_QTD_PES = 'Quantidade de pés encontrados'

# Padronizando o nome das instituições (Caixa alta e remoção de ruídos)
df_base['Agencia_Policial'] = df_base[COL_INSTITUICAO].astype(str).str.upper().str.strip()
df_base['Agencia_Policial'] = df_base['Agencia_Policial'].replace({'NAN': 'NÃO INFORMADA', 'NONE': 'NÃO INFORMADA'})

# Função rigorosa para extrair apenas os números da quantidade de pés
def extrair_numerico(valor):
    if pd.isna(valor) or str(valor).strip().upper() in ['NAN', 'NÃO INFORMADO', 'NI', '-']:
        return np.nan
    
    texto = str(valor).lower()
    # Remove pontos de milhar, mas mantém vírgulas (caso alguém tenha usado para decimais incorretos)
    texto = texto.replace('.', '')
    # Extrai a primeira sequência puramente numérica
    numeros = re.findall(r'\d+', texto)
    if numeros:
        return float(numeros[0])
    return np.nan

logger.info("Aplicando sanitização na coluna de erradicação...")
df_base['Pes_Erradicados_Numerico'] = df_base[COL_QTD_PES].apply(extrair_numerico)

# =========================================================================================
# 2. CÁLCULO DE ASSIMETRIA E LETALIDADE INSTITUCIONAL
# =========================================================================================
logger.info("Calculando o monopólio da força por agência...\n")

# Agrupando os dados pela Agência Policial
assimetria = df_base.groupby('Agencia_Policial').agg(
    Total_Operacoes=('Agencia_Policial', 'count'),
    Total_Pes_Destruidos=('Pes_Erradicados_Numerico', 'sum'),
    Media_Pes_por_Operacao=('Pes_Erradicados_Numerico', 'mean')
).reset_index()

# Ordenando pelo maior volume de operações
assimetria = assimetria.sort_values(by='Total_Operacoes', ascending=False)

# Arredondando a média para ficar legível
assimetria['Media_Pes_por_Operacao'] = assimetria['Media_Pes_por_Operacao'].round(2)

print("-" * 90)
print(f"{'AGÊNCIA DE SEGURANÇA':<40} | {'OPERAÇÕES':<10} | {'PÉS DESTRUÍDOS':<15} | {'MÉDIA/OPERAÇÃO':<15}")
print("-" * 90)

for index, row in assimetria.iterrows():
    print(f"{row['Agencia_Policial']:<40} | {row['Total_Operacoes']:<10} | {row['Total_Pes_Destruidos']:<15} | {row['Media_Pes_por_Operacao']:<15}")

print("-" * 90)
import pandas as pd
df = pd.read_csv('dados_novos.csv', sep=',', engine='python', on_bad_lines='skip')
for col in df.columns.tolist(): print(f"-> '{col}'")