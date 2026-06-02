# 🌍 Observatório de Plantios Ilícitos no Brasil: 

> **Uma iniciativa do Núcleo de Estudos de Violência, Direitos Humanos e Políticas Públicas sobre Drogas (NEVIDH)** > *Programa de Pós-Graduação em Ciências Sociais (PPGCS) — Universidade Federal de Juiz de Fora (UFJF)*

---

## 📌 Sobre o Projeto

Este repositório sedia a infraestrutura tecnológica e metodológica do **Centro Informacional Georreferenciado**, o núcleo duro do nosso Observatório de Pesquisa. Este sistema foi desenvolvido para atuar como um **repositório científico vivo**, cujo objetivo é mapear, catalogar e espacializar o fenômeno dos plantios ilícitos no território brasileiro (com foco na cannabis), as dinâmicas de sua erradicação e a simbiose complexa com os processos institucionais de criminalização.

A plataforma rompe com a lógica de dados estáticos ou relatórios lineares em PDF. Aqui, a cartografia digital atua como a interface principal de difusão científica, integrando em um único ecossistema geoespacial:
1. **Dados Policiais Qualitativos e Quantificados:** O histórico de operações, volumes erradicados e forças envolvidas.
2. **Literatura Científica Territorializada:** Artigos, teses, dissertações e notas técnicas produzidas pelo NEVIDH/UFJF indexados diretamente nos palcos geográficos dos fenômenos.

---

## 🛠️ Engenharia de Dados & Arquitetura Cartográfica

Para modelar a complexidade do cenário de segurança pública e a geografia do crime no Brasil (especialmente os desafios logísticos da região Amazônica e do Polígono da Maconha), o script automatizado em Python processa o banco de dados através de **quatro motores especializados de renderização**:
[ Base de Dados Consolidada ]
                             │
     ┌───────────────────────┼───────────────────────┬───────────────────────┐
     ▼                       ▼                       ▼                       ▼

     [ 1. Motor de Terra ]   [ 2. Motor de TI ]     [ 3. Motor de Rios ]    [ 4. Motor de Incerteza ]
Pontos e densidades     Zonas de Proteção      Vetores de Fluxo        Zonas Limítrofes
(MarkerCluster / Terra) (Polígonos da FUNAI)   (Linhas Fluviais ANA)   (Buffers de Aproximação)

### 🧠 Os Quatro Motores do Script

1. **Motor Territorial Tradicional (Zonas de Cultivo Adensado):** Processa ocorrências com coordenadas e municípios exatos (ex: fazendas e roças tradicionais), agrupando-as em clusters dinâmicos com assinaturas visuais dedicadas.
2. **Motor de Terras Indígenas (Vulnerabilidade Territorial):** Identifica ocorrências em áreas protegidas pela União. O script calcula o centroide da área e insere o marcador do *Cocar*. Ao clique do usuário, o sistema executa um disparo de expansão espacial, **revelando o polígono oficial da FUNAI** e trazendo a literatura científica do Observatório sobre o conflito naquela TI.
3. **Motor Fluvial (Logística e Escoamento de Narcotráfico):** Trata dados complexos de apreensões móveis em embarcações e balsas submersas (comum nas calhas dos rios Solimões, Negro e Japurá). O ponto fixa-se no leito do rio correspondente ao município e, ao clique do usuário, o mapa **ilumina a hidrovia em linhas neon azul vibrante**, demonstrando o vetor de escoamento logístico.
4. **Motor de Ponto Médio e Incerteza Espacial (Rigor Metodológico):** Para notícias e registros institucionais que indicam termos vagos como "na divisa entre a cidade X e Y", o sistema aplica uma função matemática de centroide médio e desenha um **Círculo Translúcido com Borda Tracejada (Buffer)**. Isso mapeia a incerteza estatística de forma honesta, sem gerar coordenadas pontuais falsas.

---📈 Como Executar o Sistema
(As instruções de ambiente virtual e comandos de terminal serão adicionadas conforme a consolidação do script final).
# Exemplo de compilação futura do ecossistema do Observatório
python gerador_mapa.py
🎓 Contribuição Acadêmica e Créditos
Este projeto constitui parte fundamental da produção científica e infraestrutura de pesquisa do doutorado de Alessandro Carneiro, sob orientação/coordenação do Prof. Dr. Paulo Cesar Pontes Fraga.

Para citações, referências teóricas ou parcerias institucionais entre Universidades e Laboratórios de Segurança Pública, por favor entre em contato com o coordenador do núcleo ou envie um e-mail institucional via PPGCSO/UFJF.

## 💾 Estrutura do Repositório

```text
├── .gitignore               # Proteção contra arquivos temporários e GeoJSONs pesados
├── README.md                # Documentação principal da plataforma
├── gerador_mapa.py          # Script core em Python (Pandas, Folium, GeoPandas)
├── dados/
│   ├── dados_antigos.csv    # Base histórica consolidada de apreensões
│   └── dados_novos.csv       # Novas inserções de dados (importados via TSV/Clipboard do GSheets)
├── geo_shapes/
│   ├── funai_tis.geojson    # Malha vetorial oficial de Terras Indígenas do Brasil
│   └── ana_rios.geojson     # Malha vetorial oficial das principais hidrovias brasileiras
└── index.html               # O PRODUTO FINAL (Compilado automaticamente, pronto para o servidor)

Princípio de Sustentabilidade e Risco Zero
O repositório foi arquitetado seguindo padrões estritos de governança de dados:

Fusão Programática em Memória: Os arquivos originais de dados brutos (dados_antigos.csv e dados_novos.csv) permanecem intactos. A conciliação de colunas, limpeza de duplicadas e padronização textual ocorrem estritamente na memória do computador durante a execução do script.

Filtro de Arquivos Pesados: O arquivo .gitignore está configurado para omitir o upload das malhas geográficas gigantescas (.geojson), mantendo o repositório leve, rápido e focado no código-fonte e na inteligência cartográfica.
     
