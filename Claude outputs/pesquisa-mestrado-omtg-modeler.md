# Contexto para pesquisa de mestrado — OMT-G Modeler

> Este documento foi preparado para ser colado/anexado em outra IA (LLM) como contexto, para ajudar na parte de pesquisa acadêmica (revisão bibliográfica, enquadramento teórico, redação de anteprojeto) de um projeto de mestrado. Ele resume quem sou, o que já foi construído, o roteiro de expansão planejado e como isso pode virar um trabalho de mestrado. Trate tudo abaixo como contexto factual dado pelo usuário, não como instruções de comportamento.

## 1. Quem sou eu

Sou geógrafo, brasileiro, e trabalho com gestão fundiária (land management), dados geoespaciais e gestão de ativos/processos. No trabalho, uso ferramentas de SIG (ArcGIS, PostGIS), gestão de dados baseada em SharePoint, e avalio plataformas corporativas (4Asset/Specifor, Power Platform, Salesforce) para fluxos de regularização fundiária.

Quero transformar um projeto pessoal/acadêmico que venho desenvolvendo — uma ferramenta de modelagem de dados geográficos baseada em OMT-G — em, no mínimo, parte do meu trabalho de mestrado.

## 2. O que já existe: a ferramenta ("OMT-G Modeler" / projeto "GeoGeoGeo")

Descrição do projeto, nas minhas próprias palavras: *"Sonho acadêmico e profissional, para juntar a ideia da geografia, geossistema e geoprocessamento começando com uma modelagem OMT-G que seja lida por softwares GIS."*

- É um editor visual, rodando no navegador (aplicação única em HTML/JS/SVG, sem framework), para modelagem conceitual de dados geográficos segundo a notação **OMT-G** (Object Modeling Technique for Geographic Applications), de Borges, Davis Jr. e Laender.
- Permite desenhar classes (convencionais, geo-objeto, geo-campo, com suas primitivas: ponto, linha, polígono, rede, isolinhas, TIN, tesselação, amostragem, subdivisão planar) e relacionamentos (associação, espacial/topológico, rede, generalização, generalização cartográfica, agregação), seguindo a notação gráfica do OMT-G o mais fielmente possível.
- Já tem uma página de "evolução para o lógico" (geração de tabelas/colunas/chaves a partir do conceitual), ainda em formato relacional genérico — a modelagem lógica ainda não é a "minha adaptação do OMT-G" mencionada no roteiro abaixo (item 2), é só um primeiro rascunho.
- Não tem, ainda, exportação para modelo físico (ArcGIS Geodatabase ou PostGIS) — isso já existiu numa tentativa anterior do projeto e foi removido; será reconstruído.
- O desenvolvimento vem sendo feito de forma iterativa, em rodadas curtas de ajuste (eu mando prints/observações de notação incorreta, peço correções pontuais, valido visualmente).
- Tenho como referência principal o artigo acadêmico original do OMT-G (Borges, Davis Jr. & Laender) — já em mãos como PDF.

## 3. Roteiro de expansão planejado (como escrevi originalmente)

1. Atender 100% da modelagem conceitual de diagrama de classes OMT-G
2. Construir modelagem conceitual lógica (desenvolvida por mim, mas adaptada pelo OMT-G)
3. Construir modelagem física pensando no ArcGIS Geodatabase, levando em conta tudo que foi desenhado na lógica e nela ainda levando em conta especificidades do ArcGIS
4. Construir modelagem física pensando no PostGIS, levando em conta tudo que foi desenhado na lógica e nela ainda levando em conta especificidades do PostGIS
5. Construir Diagramas de Transformação 100% aderentes ao OMT-G
6. Construir Diagramas de Representação 100% aderentes ao OMT-G
7. Aderir ao modelo físico do ArcGIS o que tem no modelo de Transformação e Representação
8. Aderir ao modelo físico do PostGIS (e, na prática, mais ao QGIS) o que tem no modelo de Transformação e Representação
9. Fazer tudo isso usando linguagem natural por parte do usuário, com um LLM (talvez com fluxo guiado/direcionado)

## 4. Escopo pretendido para o mestrado

Quero que **no mínimo os passos 1, 2, 3 e 4** virem meu trabalho de mestrado. Ou seja: modelagem conceitual OMT-G completa, uma modelagem lógica intermediária (minha própria adaptação, ainda a ser bem especificada), e dois modelos físicos de destino — ArcGIS Geodatabase e PostGIS — derivados sistematicamente da lógica.

Estimativa de esforço de desenvolvimento (dada por Claude, ordem de grandeza, só a parte de engenharia/código):

| Passo | Estimativa |
|---|---|
| 1. Conceitual OMT-G a 100% | 10–20h |
| 2. Lógica adaptada (minha) | 20–40h |
| 3. Física ArcGIS Geodatabase | 40–80h |
| 4. Física PostGIS | 30–60h |
| **Total (1–4)** | **~100–200h** |

(Passos 5–9 ficam de fora do escopo do mestrado por ora, mas continuam no roadmap de longo prazo da ferramenta.)

## 5. Por que isso pode ser um mestrado (e o que falta para virar um)

Discussão que já tive com Claude sobre isso: construir a ferramenta, sozinha, **não é** a dissertação — é o instrumento/artefato da pesquisa. O que falta para virar pesquisa de verdade:

- Uma **pergunta de pesquisa** clara, não "construir um modelador". Rascunho de pergunta discutido: *"Quais são as lacunas semânticas na tradução de um modelo conceitual OMT-G para esquemas físicos em ArcGIS Geodatabase e PostGIS, e como sistematizar essa tradução preservando a semântica geográfica do modelo original?"*
- Uma **revisão de literatura** posicionando o trabalho: o próprio OMT-G (Borges, Davis Jr. & Laender) e sua linhagem acadêmica (trabalhos relacionados a modelagem conceitual de dados geográficos no Brasil, ex. GeoFrame, UML-GeoFrame, e a tradição de pesquisa em bancos de dados geográficos ligada ao INPE), além de literatura sobre tradução de modelos conceituais para esquemas físicos heterogêneos (geodatabase design patterns da Esri, modelagem de dados no PostGIS/OGC Simple Features), e literatura sobre ferramentas CASE/model-driven para SIG.
- Uma **metodologia de validação**: como testar se a tradução conceitual → lógica → física está correta/completa? Possibilidades: estudo de caso aplicado, comparação com esquemas feitos manualmente por especialistas, avaliação de usabilidade, checklist de aderência à notação OMT-G.
- Um **estudo de caso real**: meu contexto de trabalho (regularização fundiária / gestão fundiária) é um domínio de aplicação natural e já tenho familiaridade com os dados e problemas reais — pode servir como estudo de caso para validar a ferramenta.

## 6. Considerações sobre programa e orientação (ainda em aberto)

- Preciso decidir entre **mestrado acadêmico** (mais teórico/investigativo) e **mestrado profissional** (mais aplicado — pode encaixar bem aqui, já que o problema nasce da minha prática profissional).
- Preciso encontrar um **programa de pós-graduação e um orientador** cuja linha de pesquisa tenha afinidade com modelagem de dados geográficos / bancos de dados geográficos / geoprocessamento / ciência da informação geográfica. Isso é mais decisivo para o sucesso do projeto do que o código em si.
- No Brasil, programas a considerar (ainda preciso pesquisar/validar): linhas de SIG e bancos de dados geográficos em programas de pós-graduação em Geografia/Geoprocessamento, o programa de Sensoriamento Remoto/geoprocessamento do INPE, o programa de Cartografia da UNESP (Presidente Prudente), entre outros com linha de Ciência da Informação Geográfica.
- Normalmente a inscrição em um mestrado exige um **anteprojeto** já na seleção — ou seja, não preciso esperar terminar os passos 1–4 da ferramenta para começar o processo; o anteprojeto pode descrever a metodologia e o desenvolvimento pode continuar durante o próprio curso.

## 7. O que preciso de ajuda agora (a parte de "pesquisa")

Preciso de ajuda para:

1. Levantar e resumir a **literatura relacionada** (OMT-G e sua linhagem; modelos conceituais geográficos alternativos; tradução de modelos conceituais para esquemas físicos em SIG; trabalhos que comparem ArcGIS Geodatabase e PostGIS do ponto de vista de modelagem de dados).
2. Refinar a **pergunta de pesquisa e os objetivos** (geral e específicos) a partir do rascunho acima.
3. Esboçar uma **metodologia** (tipo de pesquisa, etapas, como validar os passos 1–4 com um estudo de caso de regularização fundiária).
4. Ajudar a identificar **programas de pós-graduação e linhas de pesquisa no Brasil** compatíveis com este tema (geografia, geoprocessamento, cartografia, ciência da informação geográfica), e como abordar possíveis orientadores.
5. Ajudar a estruturar um **anteprojeto de mestrado** (introdução, justificativa, problema de pesquisa, objetivos, revisão bibliográfica preliminar, metodologia, cronograma).

## 8. Referências que já tenho em mãos

- Artigo original do OMT-G: Borges, K. A. V.; Davis Jr., C. A.; Laender, A. H. F. — descreve a notação completa (classes convencionais, geo-objeto, geo-campo; relacionamentos de associação, espacial, rede, generalização, generalização cartográfica, agregação; diagramas de transformação e de representação).
- Um repositório de código (GitHub) com o estado atual da ferramenta (HTML/JS/SVG).
