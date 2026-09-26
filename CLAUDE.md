# Guia para continuar o GeoGeoGeo

Este arquivo é para quem vai mexer no código, pessoa ou agente (Claude Code, Claude
Cowork). Leia antes de começar. O [`README.md`](README.md) explica o que o projeto é
para quem só vai usar.

## Contexto

- O autor é geógrafo e usa o projeto como parte de um mestrado. O roteiro de longo prazo
  está em [`docs/contexto-pesquisa-mestrado.md`](docs/contexto-pesquisa-mestrado.md):
  conceitual → lógico → físico ArcGIS → físico PostGIS → diagramas de transformação e
  de representação do OMT-G. A seção "O que já existe" desse documento é antiga; o
  estado atual está aqui e no README.
- A referência da notação é o artigo do OMT-G: Borges, Davis Jr. & Laender,
  *GeoInformatica* 5(3), 2001.
- **Idioma:** interface, comentários, mensagens de commit e documentos em português do
  Brasil. Os nomes no código (funções e variáveis) são em inglês.
- O autor trabalha em rodadas curtas: manda prints e observações, e confere o resultado
  na tela. Mudanças visuais precisam ser conferidas renderizando, não só lendo o código.
- As decisões de mapeamento para o GDB estão numeradas em
  [`mapeamento-logico-para-gdb.md`](mapeamento-logico-para-gdb.md) ("Decisão 1" a
  "Decisão 15"). O código cita essas decisões nos comentários. Uma decisão nova ou
  alterada entra na spec, no histórico de decisões do fim dela.
- `annotator.html` foi abandonado de propósito: não altere.

## Arquivos

| Arquivo | Papel |
| --- | --- |
| `index.html` | O app inteiro, cerca de 9.500 linhas. Detalhes abaixo. |
| `geogeogeo_toolbox.pyt` | A toolbox ArcGIS (Python 3, arcpy). É a **fonte**. |
| `mapeamento-logico-para-gdb.md` | A spec do gerador: o que cada elemento do Lógico vira no GDB. |
| `exemplo-gdb.json` | O JSON do modelo Exemplo. É o golden dos testes. |
| `tests/run-tests.mjs` | Os testes (Playwright + Node). |
| `tests/test_toolbox.py` | A toolbox rodando com um arcpy simulado (`FakeArcpy`). |
| `tools/embed-toolbox.mjs` | Copia o `.pyt` para o `<script id="pytSource">` do `index.html`. |

## Como o `index.html` está organizado

São três blocos `<script>`:

1. `<script type="text/plain" id="pytSource">`: cópia da toolbox, baixada pelo menu.
   **Não edite aqui.** Edite o `.pyt` e rode `npm run embed-toolbox`.
2. `<script type="application/json" id="exampleModel">`: o modelo do botão Exemplo, com
   uma classe ou relação por linha.
3. `<script>`: o app. A última linha é `boot()`.

O app é dividido em seções com cabeçalho `/* ---------- nome ---------- */`. Na ordem
em que aparecem:

| Seção | O que tem |
| --- | --- |
| helpers de DOM, arquivos | `E()`/`S()` criam elementos HTML/SVG; `saveFile()`, `copyToClipboard()`, `escapeHtml()`. |
| constantes de domínio | `ATTR_TYPES`, primitivas, operações etc. |
| **Gerador do JSON do GDB** | `buildGdbJson()` e seus auxiliares. Ver "Gerador" abaixo. |
| resumo do JSON | `gdbCountsGrid()`, `gdbIssueSections()`, `openGdbResult()`, `renderGdbScreen()` (a tela do Físico). |
| Dicionário de dados | O .docx é montado à mão: um ZIP sem compressão, com CRC32 próprio. |
| Construtor de cálculo | `CALC_FUNCTIONS`, `calcParse()`, `calcEmit()`, `calcTranslate()`, `calcContext()`, `openCalcBuilder()`. |
| estado da aplicação | `state`, `selection`, `view`, `MODEL_TABS`, `modelStash`, `activeModel`, `logicalMode`. |
| migração entre modelos | `mergeModels()`, `migrateModel()`, `setActiveModel()`, `isViewActive()`. |
| undo/redo | `commitHistory()`, `undo()`, `redo()`. O histórico é do modelo na tela. |
| orquestração | `touch()` redesenha tudo e agenda o autosave. |
| motor de validação | `computeConceptualValidation()` (desenho, semântica e físico) e `renderValidationPanel()`. |
| canvas | `buildNode()` (o card da classe), caixas de lista e notas de cálculo. |
| roteamento | `assignPorts()`, `routeEdge()`/`routeOrthogonal()` (BFS numa grade), separação de segmentos coincidentes, laços de auto-relacionamento, posição dos rótulos. |
| desenho das relações | `buildEdgeDom()`, `computeConceptualLayout()`, `renderConceptualCanvas()`, marcadores (`initDefs`). |
| pan/zoom/arraste | Eventos do canvas e alças das pontas. |
| inspetor | `buildClassInspector()`, `buildRelInspector()`, `buildModelInspector()` (sem seleção), tabela de atributos. |
| persistência | `persistableState()`, `normalizeState()`/`normalizeDiagram()`, `loadModel()`, autosave. |
| legenda, topbar, exportação de imagem, `boot()`, Organizar | `runAutoLayout()` faz o layout em camadas (Sugiyama). |

### Estado e modelos

- `state = {meta, classes, relationships}` é o modelo **que está na tela**. Desenho,
  inspetor e validação só leem `state` e não sabem de qual modelo se trata.
- O Conceitual e o Lógico são independentes, ligados pelo mesmo `id` de classe e de
  relação. O modelo fora da tela fica em `modelStash`; `setActiveModel()` troca os
  arrays.
- **Físico (GDB) é uma vista** (`view:true` em `MODEL_TABS`), não um modelo. Atalhos de
  diagrama (Delete, Ctrl+V, Ctrl+Z...) ficam desligados nela
  (`diagramShortcutsActive()`), para não mexerem no Lógico escondido.
- Propriedades só do Lógico estão em `CLASS_LOGICAL_ONLY_FIELDS` e
  `ATTR_LOGICAL_ONLY_FIELDS`. `mergeModels()` usa essas listas para decidir o que a
  migração leva e o que ela descarta.
- Trocar o tipo de um atributo passa por `applyAttrType()`, que limpa as propriedades
  que deixaram de valer (`ATTR_PROPS_BY_TYPE`).
- O documento salvo tem o Conceitual no topo e o Lógico na chave `logical`. Todo JSON
  aberto passa por `normalizeState()`, que tolera arquivo antigo ou incompleto.

### Gerador (`buildGdbJson`)

- Lê sempre o Lógico (`logicalModel()`), esteja ele na tela ou não.
- Nomes físicos:
  - `gdbSanitize()` sem acento, palavras com inicial maiúscula unidas por `_`,
    até 30 caracteres;
  - `gdbUnique()` resolve duplicatas no espaço de nomes compartilhado por datasets e
    relationship classes;
  - `gdbFieldNames(cls)` é a **fonte única** dos nomes de campo, usada pelo gerador e
    pela prévia do cálculo.
- `gdbDatasetOf(c)` diz o dataset e a geometria de cada primitiva
  (`GDB_DATASET_BY_PRIMITIVE`).
- O que não tem equivalente vai para `warn()` (lista `warnings`) ou `note()` (lista
  `unmapped`). Nada some calado.
- **O JSON é um contrato com a toolbox.** Mudou uma chave ou um formato? Mude os dois
  lados, rode `npm test` (o `test_toolbox.py` pega chave que a toolbox não lê) e
  atualize a spec.

### Toolbox

A classe `GdbBuilder` executa os passos em ordem:

1. GDB;
2. domínios;
3. feature datasets;
4. datasets e campos;
5. índices;
6. relationship classes;
7. topologias;
8. attribute rules;
9. metadados;
10. Schema Report.

Cada passo passa por `step()`: uma falha vira aviso (`failures`) e o resto continua.
O `report()` resume o que foi criado, o que não foi (`skipped`) e os avisos.

## Convenções

- **Comentários explicam o porquê, em português.** Não conte o histórico ("na rodada X
  o usuário pediu..."): isso fica no git. Quando mexer num trecho com comentário
  antigo em inglês, reescreva-o.
- **Nunca escreva a sequência asterisco-barra dentro de um comentário de CSS ou JS.**
  Ela fecha o comentário. Já aconteceu com as marcas `*`/`U` do atributo: a regra CSS
  seguinte virou lixo e deixou de valer. O teste de CSS pega esse caso no CSS; no JS o
  sintoma é erro de sintaxe.
- Texto vindo do usuário (nomes de classe, atributo etc.) que entra em HTML passa por
  `escapeHtml()`; em XML (docx, SVG exportado), por `escapeXml()`.
- Downloads passam por `saveFile(base, ext, data)`.
- Sem dependências externas em tempo de execução, além das fontes do Google Fonts. O app
  precisa funcionar abrindo o arquivo direto (`file://`).
- Visual: sempre confira renderizando. Alguns valores foram escolhidos pelo autor
  olhando a tela, contra a conta analítica. Um exemplo é o `refX` do triângulo da
  generalização, e o comentário dele avisa. Não "corrija" esses valores sem conferir.

## Testes

```bash
npm install     # uma vez; o run-tests.mjs cai no Playwright global se não houver local
npm test
```

- O teste do golden compara o JSON do Exemplo (com o relógio fixo) com o
  `exemplo-gdb.json`. Se a mudança no gerador foi **intencional**, rode
  `npm run test:update`, **revise o diff** do `exemplo-gdb.json` e faça o commit dele
  junto.
- Mudou o `.pyt`? Rode `npm run embed-toolbox`, senão o primeiro teste falha.
- Para mudanças só de refatoração ou de comentários, uma boa prova é comparar o SVG do
  canvas (`#canvasSvg`) com o Exemplo carregado, antes e depois. O resultado tem de ser
  idêntico.
- O ArcGIS de verdade só existe na máquina do autor. O `test_toolbox.py` pega erro de
  Python e de contrato, mas não a semântica do ArcGIS. Mudanças na toolbox precisam de
  um teste no ArcGIS Pro com o Exemplo, feito pelo autor.

## Pendências e ideias

Coisas conhecidas que ainda não foram feitas, em ordem aproximada de valor:

1. **Integridade "Padrão" (SET DEFAULT) no GDB.** Hoje vai para `unmapped`. Daria para
   gerar uma regra de cálculo no `delete` da origem que edita a tabela filha (Arcade
   com `edit`).
2. **Físico PostGIS.** O `MODEL_TABS` e o tradutor de cálculo (`sql`) já preveem esse
   físico. A spec registra o equivalente PostGIS de várias decisões (CHECK, trigger de
   controle de edições, `bytea`).
3. **Comentários em inglês.** Ainda há muitos, sobretudo em roteamento, rótulos e
   inspetor. Não narram histórico, mas vale traduzir quando se mexer no trecho.
4. **Aviso duplicado.** A checagem LOG-NEAR da Validação e o aviso do gerador para
   "está próximo de" sem distância dizem a mesma coisa em lugares diferentes.
5. **Tema escuro.** O CSS tem `:root[data-theme="dark"]` pronto, mas não há seletor na
   interface.
6. **Catálogo das regras de validação.** O cabeçalho do motor de validação cita um
   catálogo externo que não está no repositório. Vale documentar as regras (ids
   G-00x, SP-00x, CART-GEN, LOG-* e GDB-*) na spec ou num arquivo próprio.
7. **Roteiro do mestrado.** Diagramas de transformação e de representação (itens 5 e 6
   do roteiro). As operações OMT-G do "Grupo B" já vão para `unmapped` à espera deles.
