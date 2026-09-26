# Mapeamento: Modelo Lógico → JSON de criação da File Geodatabase

Especificação do gerador (`buildGdbJson()` no `index.html`) e do contrato com a toolbox
(`geogeogeo_toolbox.pyt`). Diz o que cada elemento do modelo lógico do GeoGeoGeo vira
no GDB e por quê.

Este documento descreve o **estado atual**. As decisões numeradas (Decisão 1 a 15) são
citadas no código. O caminho até aqui, com as decisões que mudaram, está no
[histórico](#histórico-de-decisões) no fim.

## Legenda

| Marca | Significa |
| --- | --- |
| **1:1** | Correspondência direta, sem perda. |
| **Adaptado** | Existe equivalente, com outra forma. |
| **Parcial** | Parte da semântica se perde e é avisada. |
| **Combinado** | Um elemento OMT-G exige vários objetos do GDB. |
| **Regra** | Resolvido por Attribute Rule (Arcade). |
| **Sem equivalente** | Vai para `unmapped` ou `warnings` no JSON. |

## Premissa

O GDB é destino de criação, não diagrama. O JSON descreve *o que criar*, em que ordem,
e carrega junto tudo que não coube, porque o que não é representável é justamente o que
precisa ser auditado. Nada some calado: o que não tem equivalente vira `warnings`
(avisos) ou `unmapped` (perdas registradas).

O GDB cria sozinho `OBJECTID` (sempre) e `SHAPE` (em toda feature class), mais
`Shape_Length` e `Shape_Area` em linhas e polígonos. `GLOBALID` só é criado onde é
exigido (seção 8).

## Formato do JSON

```
formatVersion   1
generator       "GeoGeoGeo"
generatedAt     data ISO
source          {model, from: "logical"}
workspace       {name, type: "fileGeodatabase", spatialReference, metadata}
featureDatasets [{name, spatialReference, items[], metadata}]
domains         [{name, type: codedValue|range, fieldType, length?, values[] | min/max, omtg}]
datasets        [{name, alias, kind: table|featureClass|tinDataset|rasterDataset,
                  geometryType?, spatialReference?, hasZ?, hasM?, featureDataset?,
                  status?: "placeholder", systemFields[], fields[], indexes[],
                  attachments?, editorTracking?, notes[], omtg, metadata}]
relationshipClasses [{name, origin, destination, type: SIMPLE|COMPOSITE, cardinality,
                  forwardLabel, backwardLabel, attributed: "NONE",
                  originPrimaryKey, originForeignKey,
                  destinationPrimaryKey?, destinationForeignKey?, notes[], omtg, metadata}]
topologies      [{name, featureDataset, clusterTolerance: "default", featureClasses[], rules[]}]
networks        [{name, featureDataset, edges[], junctions[], status: "declaredOnly", notes[]}]
attributeRules  [{name, dataset, field, type: constraint|calculation|validation,
                  triggers?, arcade, description, omtg}]
unmapped        [{on, omtg, reason, classIds?, relIds?}]
warnings        [{severity, on, message, classIds?, relIds?}]
```

Todo objeto gerado leva um bloco `omtg` com os ids de origem (`classId`, `attrId`,
`relId`), para rastrear o que veio de onde. A toolbox ignora chaves que não conhece;
se uma chave que ela usa mudar, mude os dois lados (o `tests/test_toolbox.py` pega a
divergência).

---

## 1. Nomes ✅ (Decisão 1)

No Lógico, o nome de classe, atributo, relacionamento e rede é **livre**: aceita
espaço, acento e caractere especial. O nome livre vira o **alias**. O nome físico é
derivado por `gdbSanitize()`:

- acentos removidos preservando a letra base (`á` → `a`, `ç` → `c`, `ñ` → `n`);
- as palavras são unidas por `_`, cada uma com a inicial maiúscula;
- demais caracteres suprimidos; nome que começaria com dígito ganha `_` na frente;
- no máximo 30 caracteres.

Exemplos: "Lote Urbano" → `Lote_Urbano`, "Área de Preservação" → `Area_De_Preservacao`,
"VALOR_TERRITORIAL" → `VALOR_TERRITORIAL`.

**Unicidade (`gdbUnique`).** Datasets, relationship classes, feature datasets,
topologias e redes dividem o mesmo espaço de nomes. Um nome repetido ganha sufixo
(`Lote_2`) e o gerador avisa. Campos são únicos dentro da classe e não podem usar os
nomes que o ArcGIS reserva: `OBJECTID`, `SHAPE`, `GLOBALID`, `Shape_Length`,
`Shape_Area` e os campos do controle de edições. `gdbFieldNames(cls)` é a fonte única
desses nomes, usada pelo gerador e pela prévia do cálculo.

**Relacionamento sem nome.** O gerador monta o nome com as duas classes
(`Lote_Edificacao`) e avisa se precisou encurtar.

O mesmo padrão vale para os nomes que o gerador cria: domínios (`Faixa_Testada_M`),
regras (`PK_Lote`, `Unico_Proprietario_CPF`), feature datasets (`SRID_31982`), colunas
da tabela intermediária do M:N (`Proprietario_ID`) e Network Datasets (`Rede_ND`).

O painel do Lógico mostra o nome físico enquanto se digita. No canvas do Lógico, o nome
físico aparece entre parênteses quando difere do alias. A Validação acusa dois nomes que
caem no mesmo nome físico (erro), nome que precisa ser encurtado (aviso) e nome sem
nenhuma letra ou número (erro).

## 2. Metadados do modelo

Editáveis no painel da direita do Lógico, com nada selecionado.

| Elemento lógico | Vira no GDB | Status |
| --- | --- | --- |
| `meta.workspaceName` ("Nome da geodatabase") | `workspace.name`, o nome do `.gdb` | 1:1; vazio usa `meta.name` |
| `meta.name` (nome do modelo) | Título dos metadados; nome do `.gdb` se o anterior estiver vazio | Adaptado |
| `meta.srid` ("SRID padrão") | Spatial Reference padrão; vale para classe sem SRID | 1:1 |
| `meta.schema` | Só aparece em `unmapped` quando não é `public` | Sem equivalente (conceito PostGIS) |

A toolbox ainda aceita um nome de geodatabase no parâmetro dela, que tem prioridade.

## 3. Classe

| Propriedade | Vira no GDB | Status |
| --- | --- | --- |
| `id` | `omtg.classId` | 1:1 |
| `name` | Nome físico + alias | Adaptado (seção 1) |
| `kind = conventional` | **Table**, na raiz da GDB | 1:1 |
| `kind = geo` | Feature class, TIN ou Raster | Adaptado (seção 3.1) |
| `primitive` | Dataset + geometria + estrutura | Combinado |
| `srid` | Spatial Reference da feature class; vazio herda `meta.srid` | 1:1 |
| `hasZ` / `hasM` | `has_z` / `has_m` | 1:1 |
| `editTracking` ("Controle de edições") | `EnableEditorTracking`, seção 8 | 1:1 |
| `operations[]` | `unmapped` | Sem equivalente (seção 3.2) |
| `x`, `y`, `calcNote`, `listBox` | Nada | Layout do canvas |

### 3.1 Primitiva → dataset e geometria (Decisão 3)

| Primitiva OMT-G | Dataset | Geometria | Estrutura |
| --- | --- | --- | --- |
| (convencional) | Table | — | — |
| Ponto | Feature Class | `POINT` | — |
| Linha | Feature Class | `POLYLINE` | — |
| Polígono | Feature Class | `POLYGON` | — |
| Linha unidirecional | Feature Class | `POLYLINE` | Rede, um sentido |
| Linha bidirecional | Feature Class | `POLYLINE` | Rede, dois sentidos |
| Nó | Feature Class | `POINT` | Rede (junction) |
| Isolinhas | Feature Class | `POLYLINE` | — |
| **Amostragem** | Feature Class | **`MULTIPOINT`** | — |
| Subdivisão Planar | Feature Class | `POLYGON` | Topologia (seção 7) |
| TIN | TIN Dataset | — | **placeholder** |
| Tesselação | Raster Dataset | — | **placeholder** |

**Amostragem é sempre Multipoint (Decisão 3).** O LAS Dataset não mora dentro da
geodatabase: é um `.lasd` que *referencia* arquivos `.las` externos. E a conversão entre
os dois é de mão única: existe `LAS To Multipoint`, mas não o caminho inverso. Multipoint
é o formato que vive dentro do `.gdb` e para o qual sempre se pode importar LiDAR.

**TIN e Raster são placeholders.** Nascem de dados de entrada, não de criação vazia por
geoprocessamento. Vão no JSON com `status: "placeholder"` e os atributos como
documentação, mas sem regras, índices nem GLOBALID. A toolbox relata e não cria.

### 3.2 As 21 operações OMT-G

As operações do artigo (geométricas, de generalização cartográfica e de análise
espacial) **produzem uma representação nova**, com outra geometria e outra contagem de
feições: Voronoi, Delaunay, isolinhas, buffer etc. Attribute Rule calcula campos, não
cria datasets. Por isso cada operação marcada vai para `unmapped`. Esse é o material
do diagrama de transformação do OMT-G (item 5 do roteiro).

O que é valor derivado da própria feição (área, perímetro, comprimento, coordenadas do
centroide) se modela como **campo calculado** (seção 5), que vira regra de cálculo.

## 4. Campo (atributo)

| Propriedade | Vira no GDB | Status |
| --- | --- | --- |
| `name` | Nome físico + alias | Adaptado |
| `type = text` | `TEXT`, `length` (padrão 255) | 1:1 |
| `type = integer` | `SHORT` ou `LONG` pelos dígitos | Adaptado (4.1) |
| `type = double` | `DOUBLE` | 1:1 |
| `type = boolean` | `SHORT` + domínio `SimNao` | Adaptado (4.2) |
| `type = date` | `DATE` | 1:1 |
| `type = blob` | **Anexo** da classe | Adaptado (4.3) |
| `type = list` | Campo + domínio de valores codificados | Combinado (4.4) |
| `precision` / `scale` | Declarados, com aviso | **Parcial**: ignorados em File GDB, valem só em enterprise |
| `required` | `NON_NULLABLE` | 1:1 |
| `defaultValue` | `AssignDefaultToField` | 1:1 |
| `unique` | Constraint Rule `Unico_<Classe>_<Campo>` | Regra (Decisão 6) |
| `minValue` / `maxValue` | Domínio de intervalo + Constraint Rule | Regra (4.5) |
| `pk` | Campo `NON_NULLABLE` + índice + Constraint Rule `PK_<Classe>` | Adaptado (4.6) |
| `fk` | `originForeignKey` da relationship class | Adaptado (seção 6) |
| `refIntegrity` | Tipo da relationship class (+ regra) | Adaptado (6.3) |
| `calculated` + expressão | Calculation Rule `Calc_<Classe>_<Campo>` | Regra (seção 5) |

### 4.1 Inteiro: dígitos → SHORT ou LONG (Decisão 4)

| Dígitos | Tipo GDB | Faixa |
| --- | --- | --- |
| 1 a 4 | `SHORT` | −32.768 a 32.767 |
| 5 ou mais, ou sem tamanho | `LONG` | −2.147.483.648 a 2.147.483.647 |

O corte é em 4, não em 5, porque `SHORT` vai até 32.767 e não cabe todo número de
5 dígitos.

### 4.2 Booleano (Decisão 5)

File GDB não tem booleano. Vira `SHORT` com um domínio compartilhado por todo o modelo:
`SimNao` (1 = Sim, 0 = Não).

### 4.3 Blob → anexo

Um atributo Blob não vira campo BLOB: a classe recebe anexos (`EnableAttachments`,
tabela `__ATTACH`). Vários Blobs na mesma classe caem numa única tabela de anexos, e o
gerador avisa, porque o GDB não separa anexos por campo. No PostGIS o Blob continua
`bytea`.

### 4.4 Lista → domínio de valores codificados (Decisão 7)

`code` = chave e `name` = valor. O nome do domínio é o nome do campo (`Situacao`).
Domínios com conteúdo idêntico são **fundidos**, mesmo em classes diferentes. Dois campos
com o mesmo nome e conteúdos diferentes: o segundo recebe o nome da classe como prefixo
(`No_Da_Rede_Tipo`).

Se todos os códigos forem inteiros, domínio e campo saem `SHORT` (até 32.767) ou `LONG`.
Basta um código com letra para tudo ficar `TEXT`, com o tamanho do maior código.

### 4.5 Faixa de valores

Inteiros e decimais têm Mínimo e Máximo. Com os dois limites, gera um domínio de
intervalo `Faixa_<Campo>`, deduplicado pelo conteúdo. Com um ou os dois, gera uma
Constraint Rule `Faixa_<Classe>_<Campo>`, porque o domínio sozinho não impede a edição.
Mínimo maior que máximo é erro de Validação (LOG-FAIXA) e não gera nada. No PostGIS, o
equivalente previsto é um `CHECK`.

### 4.6 Chave primária

O GDB identifica a linha pelo `OBJECTID`. A PK do modelo vira:

- campo `NON_NULLABLE`;
- índice `IDX_<Classe>_<Campo>`, não único, porque File GDB não tem índice único;
- Constraint Rule `PK_<Classe>`, que recusa valor vazio e repetição (numa PK composta,
  a repetição da combinação);
- a chave de origem (`originPrimaryKey`) das relationship classes.

**Unicidade por regra (Decisão 6).** A regra vale para edições feitas através do
geodatabase: não protege contra carga que a contorne e tem custo em tabelas grandes.

**FK com tipo diferente da PK.** O ArcGIS só liga campos do mesmo tipo (ERROR 000800).
O gerador alinha o tipo da FK ao da PK referenciada e avisa, para o Lógico ser
corrigido.

## 5. Campo calculado e linguagem de cálculo

O campo calculado carrega uma expressão real, montada no **construtor de cálculo**
(nos moldes do Field Calculator), numa **sintaxe neutra**: o modelo lógico não se prende
a um software, e cada gerador traduz.

```
campos entre colchetes   [Area]
funções em MAIÚSCULAS    ARRED(AREA([SHAPE]) / 10000, 2)
textos entre aspas       CONCAT([Nome], " ", [Sobrenome])
```

Funções disponíveis:

| Grupo | Funções |
| --- | --- |
| Número | ABS, ARRED, TETO, PISO, RAIZ, POT, MIN, MAX |
| Texto | CONCAT, MAIUSC, MINUSC, APARAR, TAMANHO, EXTRAIR, SUBSTITUIR |
| Data | HOJE, AGORA, ANO, MES, DIA, DIAS_ENTRE, ANOS_ENTRE |
| Geometria | AREA, PERIMETRO, COMPRIMENTO, X, Y, VERTICES |
| Lógica | SE, VAZIO, SE_VAZIO |

No GDB vira **Calculation Rule** (`triggers` insert e update), com a expressão traduzida
para Arcade e os nomes **físicos** dos campos. O JSON guarda também a tradução SQL para o
futuro gerador PostGIS (`calculatedExpression.sql`).

**Área, perímetro e comprimento dependem do SRID da classe.** Em SRID projetado (UTM
etc.) usam `Area`/`Length` planos, e a unidade já é metro. Em 4326 e 3857 usam
`AreaGeodetic`/`LengthGeodetic`. Em outro SRID geográfico, o gerador avisa que o
resultado sairia em graus. No SQL, o cálculo é via `::geography`.

Expressão inválida ou vazia: o campo é criado sem regra, com aviso.

## 6. Relacionamentos

### 6.1 Campos comuns e rótulos

| Propriedade | Vira | Status |
| --- | --- | --- |
| `id` | `omtg.relId` | 1:1 |
| `name` | Nome da relationship class + `forwardLabel` | Adaptado (seção 1) |
| `nameInverse` ("Nome inverso") | `backwardLabel` | 1:1 (Decisão 9) |
| `sourceId` / `targetId` | `origin` / `destination`, conforme o tipo | Adaptado |
| `srcAnchor` / `dstAnchor` | Nada | Layout |

Sem nome inverso, o rótulo de volta é padrão do tipo:

- associação: "pertence a \<Origem\>";
- agregação: "faz parte de";
- generalização: "é um(a)";
- generalização cartográfica: "representa".

No relacionamento espacial, o inverso sai da regra topológica (Decisão 9):

| Regra | Ida | Volta |
| --- | --- | --- |
| toca | toca | é tocado por |
| está dentro de | está dentro de | contém |
| contém | contém | está dentro de |
| cruza | cruza | é cruzado por |
| sobrepõe | sobrepõe | é sobreposto por |
| é disjunto de / é adjacente a / coincide com / está próximo de | igual | igual *(simétricas)* |

### 6.2 Cardinalidade (associação e espacial)

| `cardSource` × `cardTarget` | GDB |
| --- | --- |
| (`1`\|`0..1`) × (`1`\|`0..1`) | `ONE_TO_ONE` |
| (`1`\|`0..1`) × (`0..*`\|`1..*`) | `ONE_TO_MANY` |
| (`0..*`\|`1..*`) × (`1`\|`0..1`) | `ONE_TO_MANY`, com origem e destino invertidos |
| (`0..*`\|`1..*`) × (`0..*`\|`1..*`) | `MANY_TO_MANY`, **não atribuível** (Decisão 10) |

**Onde fica a FK.**

- No 1:N ela é obrigatória no lado N.
- No 1:1 ela fica em uma das duas tabelas, qualquer uma. Quem tem a FK vira o
  destino. FK nos dois lados é redundante: vale a do destino do desenho, e o gerador
  avisa. Sem FK em nenhum lado, o aviso pede uma.
- No M:N não há FK direta. O ArcGIS cria a tabela intermediária, e as colunas dela
  (`<Origem>_ID`, `<Destino>_ID`) são as chaves. As duas classes precisam de PK.

Sem PK na origem (ou em qualquer lado, no M:N), a relationship class não pode ser
criada, e o aviso diz por quê. Se a FK falta e a cardinalidade no Conceitual é
diferente da do Lógico, o aviso lembra que as abas são independentes.

**M:N nunca é atribuível.** Relação com atributos próprios se modela como uma classe
intermediária com dois 1:N, o que funciona igual no GDB e no PostGIS.

**Participação mínima (`1..*`).** Vira uma Validation Rule
`Min_<Relação>_<Classe>`, que usa `FeatureSetByRelationshipName` para exigir ao menos
um registro relacionado. Ela não bloqueia a edição, porque a classe nasce antes dos
relacionados. Quem ficou sem nenhum aparece em Validate → Error Inspector. O ArcGIS só
aceita Validation Rule em tabela com Editor Tracking (ERROR 003324). Por isso o
gerador liga o controle de edições nessas tabelas e avisa; se um nome padrão da Esri
já existir na tabela, os campos de controle usam o prefixo `et_`. A regra só é criada
quando a relationship class tem as chaves necessárias.

### 6.3 Integridade referencial (Decisão 8)

A integridade é propriedade da FK do Lógico. O tipo da relationship class sai da FK que
liga o destino à origem.

| `refIntegrity` | Vira | Status |
| --- | --- | --- |
| Cascata | Relationship class `COMPOSITE` | 1:1: excluir a origem exclui os destinos |
| Nulo | `SIMPLE` | 1:1: em relação simples, excluir a origem anula a FK do destino |
| **Restringir** | `SIMPLE` + Constraint Rule `Ref_<Relação>` no delete da origem | Regra: bloqueia a exclusão enquanto houver filhos |
| **Padrão** | `SIMPLE` + registro em `unmapped` | Sem equivalente: repor o valor padrão exigiria uma regra que edita outra tabela, ainda não gerada |

Agregação e generalização são sempre `COMPOSITE`. Se a FK delas pedir "Restringir", as
duas coisas se contradizem: o gerador avisa e gera a regra de bloqueio mesmo assim.

### 6.4 Por tipo

| Tipo | Vira | Status |
| --- | --- | --- |
| **Associação** | Relationship class `SIMPLE`/`COMPOSITE` + cardinalidade | 1:1 |
| **Relacionamento espacial** | Relationship class + regra de topologia **ou** Constraint Rule | Regra (6.5) |
| **Agregação** | Relationship class `COMPOSITE` 1:N (todo → parte) | 1:1: todo-parte é a semântica de composto |
| **Agregação espacial** | O mesmo + regras de topologia | Combinado (6.6) |
| **Generalização** | Tabela por classe + relationship class 1:1 `COMPOSITE` por subclasse | Adaptado (6.7) |
| **Generalização cartográfica** | Relationship class 1:N `COMPOSITE` por representação | Adaptado (6.8) |
| **Rede** | Declarada em `networks`, não criada | Parcial (6.9) |

### 6.5 Relacionamento espacial (Decisão 13)

Além da relationship class, cada regra vira uma das duas coisas:

| Regra OMT-G | Destino | Como |
| --- | --- | --- |
| está dentro de | Topologia | *Must Be Covered By…* / *Must Be Properly Inside* / *Must Be Inside*, conforme as geometrias |
| contém | Topologia | a mesma, com os lados invertidos |
| coincide com | Topologia | *Must Be Covered By Feature Class Of* |
| é disjunto de | Topologia | *Must Not Overlap With* |
| toca | Constraint Rule | `Touches` |
| é adjacente a | Constraint Rule | `Touches` |
| cruza | Constraint Rule | `Crosses` |
| sobrepõe | Constraint Rule | `Overlaps` |
| está próximo de | Constraint Rule | `Intersects` com `Buffer($feature, distância)` |

Regra de topologia é **proibitiva** ("não pode sobrepor"), enquanto a relação OMT-G é
**afirmativa** ("sobrepõe"). A Constraint Rule (`Esp_<A>_<B>_<regra>`) resolve isso
porque afirma: exige que a relação seja verdadeira para a edição passar.

"Está próximo de" usa a distância em metros do inspetor (`nearDistance`). Sem distância,
a regra sai com 0 e o gerador avisa.

### 6.6 Agregação espacial → topologia

| `spatialAggKind` | Regras |
| --- | --- |
| Subdivisão | Partes: *Must Not Overlap* + *Must Not Have Gaps*; todo coberto pelas partes (*Must Be Covered By Feature Class Of*) |
| União | **As mesmas.** A diferença é a procedência da geometria (o todo deriva das partes, ou o contrário), que o GDB não guarda; o gerador avisa |
| Contém | A parte coberta pelo todo (*Must Be Covered By…*, conforme as geometrias) |

### 6.7 Generalização: sempre tabela por classe (Decisão 11)

Superclasse e cada subclasse viram dataset próprio, ligados por relationship class 1:1
`COMPOSITE` (superclasse → subclasse). A PK da subclasse é também a FK para a
superclasse.

Subtypes foram descartados. O ArcGIS ofereceria uma feature class só, com um campo de
categoria, mas isso só serve quando as subclasses não têm atributos próprios. Além disso,
amarra o modelo a uma otimização do ArcGIS que não existe no PostGIS; tabela por classe
é a mesma estrutura nos dois.

`total`/`parcial` e `disjunta`/`sobreposta` não são representáveis no GDB. O gerador
emite um aviso por grupo (superclasse + restrições), não um por subclasse.

### 6.8 Generalização cartográfica

No diagrama, o **destino** é a superclasse, e cada **origem** é uma representação dela
(por forma ou por escala). No GDB, cada representação ganha uma relationship class 1:N
`COMPOSITE`, com a superclasse na origem e a FK na representação. Modelos antigos, com
a FK na superclasse, continuam funcionando.

A Validação avisa (CART-GEN) quando a superclasse tem uma representação só. Nesse caso,
o certo é um relacionamento espacial entre as duas classes.

### 6.9 Rede (Decisão 12)

**A toolbox não cria o Network Dataset.** Ela cria as feature classes participantes, que
já ficam no feature dataset do SRID delas (pré-requisito da rede). A intenção de rede
vai no bloco `networks` com `status: "declaredOnly"`:

- os arcos, com a direcionalidade (`uni`/`bi`);
- as junctions (primitiva Nó);
- o feature dataset.

Motivos: criar exigiria a extensão Network Analyst, e a falta dela derrubaria a criação
inteira da geodatabase por causa de um pedaço. Mesmo criada, a rede nasceria sem
conectividade, custos nem direcionalidade, e ainda precisaria de `Build Network`. O
trabalho ficaria com o usuário de qualquer forma.

Uma rede já configurada pode ser exportada como XML e usada como template em
`Create Network Dataset From Template`. Esse é o caminho se um dia valer a pena criar a
rede.

- **Arco-arco** (a classe ligada a ela mesma): entra uma vez só, com conectividade por
  endpoint. Parcial.
- **Classes em SRIDs diferentes:** não cabem no mesmo feature dataset, e o gerador
  avisa.

## 7. Feature datasets e topologias (Decisão 15)

- **Um feature dataset por SRID** (`SRID_<código>`), com todas as feature classes
  daquele SRID. Tabelas ficam na raiz (o ArcGIS não aceita tabela em feature dataset).
  Placeholders não entram.
- **Uma topologia por feature dataset que tenha regras.** O nome é `Topologia`, com o
  SRID como sufixo quando há mais de uma.
- **Tolerância de cluster:** o padrão do Spatial Reference.
- As regras vêm dos relacionamentos espaciais (6.5), das agregações espaciais (6.6) e da
  primitiva **Subdivisão Planar**, que sozinha já gera *Must Not Overlap* e *Must Not
  Have Gaps*.
- O nome da regra no arcpy leva o par de geometrias (`Must Be Properly Inside
  (Point-Area)`) e é resolvido no gerador. Se não existe regra do ArcGIS para aquela
  combinação de geometrias, ela é omitida com aviso.
- Regra entre classes de SRIDs diferentes é ignorada com aviso: as duas não podem
  dividir o mesmo feature dataset.

## 8. GLOBALID, anexos e controle de edições

- **GLOBALID (Decisão 14):** só em dataset com attribute rule, porque o ArcGIS não
  aceita regra sem ele (ERROR 002710). Anexos e Editor Tracking não pedem GLOBALID. Com
  "Criar attribute rules" desligado na toolbox, nenhum GLOBALID é criado.
- **Anexos:** seção 4.3.
- **Controle de edições:** opção por classe no Lógico. Vira `EnableEditorTracking` com
  os campos padrão da Esri (`created_user`, `created_date`, `last_edited_user`,
  `last_edited_date`) e datas em UTC. No PostGIS, o equivalente previsto são quatro
  colunas preenchidas por um trigger `BEFORE INSERT OR UPDATE`.

## 9. Metadados

O JSON traz um bloco `metadata` (title, summary, description em HTML simples, tags,
credits) para a GDB (`workspace.metadata`) e para cada feature dataset, dataset,
relationship class e topologia. O conteúdo vem do modelo OMT-G e deste mapeamento:

- tipo OMT-G e primitiva;
- atributos com PK, FK, integridade, domínio e cálculo;
- relacionamentos, regras de topologia e a origem delas;
- attribute rules e operações OMT-G;
- os avisos do que não coube.

A toolbox grava esses metadados com `arcpy.metadata` (Item Description). Um parâmetro
desliga isso.

## 10. O que não sobrevive

Tudo abaixo fica registrado em `warnings` ou `unmapped`:

1. `total`/`parcial` e `disjunta`/`sobreposta` da generalização.
2. A diferença entre Subdivisão e União (procedência da geometria).
3. `precision`/`scale` em File Geodatabase.
4. As operações OMT-G (destino: modelo de transformação).
5. Integridade "Padrão" (SET DEFAULT).
6. Network Dataset (declarado, não criado).
7. TIN e Raster sem dados de entrada (placeholders).
8. `meta.schema` diferente de `public` (conceito PostGIS).

## 11. A toolbox

`geogeogeo_toolbox.pyt`, ferramenta **Criar Geodatabase a partir do modelo**.
Parâmetros:

- o JSON;
- a pasta de saída;
- o nome da geodatabase (opcional; vazio usa `workspace.name`);
- criar attribute rules;
- criar topologias;
- preencher metadados;
- formatos do Schema Report (vazio não gera).

Ordem dos passos: GDB → domínios → feature datasets → datasets e campos (com anexos e
Editor Tracking) → índices → relationship classes → topologias → attribute rules
(Validation Rule com `severity=3`, obrigatório) → metadados → Schema Report.

Um item que falha não aborta o resto: vira aviso, e o resumo final lista o que foi
criado, o que não foi (placeholders, regras de dataset não criado) e os avisos.

## 12. O modelo Exemplo

O botão **Exemplo** carrega "Exemplo — Teste completo GDB" no Lógico. Com uma tela que
já tem classes, é preciso confirmar. O `exemplo-gdb.json` é a saída dele e o golden dos
testes.

| Item | Quantidade |
| --- | --- |
| Datasets | 24 (22 criados + TIN e raster placeholders) |
| Relationship classes | 24 |
| Domínios | 15 |
| Attribute rules | 61 (22 PK, 15 faixa, 6 cálculo, 5 restringir, 5 espaciais, 4 único, 4 participação mínima) |
| Feature datasets | 2 (`SRID_31982`, `SRID_4674`) |
| Topologias | 1, com 12 regras |
| Redes declaradas | 2 (arco-nó e arco-arco) |
| Avisos / unmapped | 26 / 2 |

O que ele exercita:

- **PK:** texto, inteiro, e PK que é FK (generalização).
- **FK e integridade:** FK SHORT contra PK LONG (alinhamento de tipo); Cascata,
  Restringir, Nulo e Padrão.
- **Cardinalidade:** 1:1 com a FK de um lado só, 1:N, M:N, participação mínima e classe
  intermediária (Contrato de Servidão).
- **Domínios:** lista numérica, lista de texto e faixa.
- **Valores:** padrão e campo único.
- **Cálculo:** área, perímetro e comprimento (planos, em UTM), aritmético e
  condicional (SE).
- **Recursos do GDB:** anexos (2 Blobs na mesma tabela), controle de edições, Z e Z+M,
  metadados.
- **Relacionamentos:** generalização total/disjunta, generalização cartográfica (uma
  superclasse com duas representações), agregação espacial (união e subdivisão), redes
  arco-nó e arco-arco, e uma relação espacial de cada tipo.
- **Geo-campos:** isolinhas, subdivisão planar, amostragem (MULTIPOINT); TIN e raster
  como placeholders.

## Apêndice: recursos do editor ligados ao modelo

**Dicionário de dados (Word).** Menu Exportar → Documentação. O .docx é gerado no próprio
app, sem biblioteca externa, em A4 paisagem. Tem quatro seções: visão geral das classes;
cada classe com atributos, relacionamentos e operações; relacionamentos; domínios. O
modelo ainda não tem campo de descrição, então o dicionário deixa "(a preencher)".

**Organizar (layout automático).** Arruma o diagrama da aba aberta em camadas
(Sugiyama), e Ctrl+Z desfaz tudo de uma vez. Os passos:

1. Separa grupos conexos; classes soltas vão para uma grade.
2. Monta a hierarquia. Ficam em cima a superclasse, o todo da agregação, o lado 1 do
   1:N, o lado sem FK no 1:1 e a origem da generalização cartográfica. Relação
   espacial, rede e M:N só aproximam as classes.
3. Equilibra a largura das camadas.
4. Reduz cruzamentos por baricentro.
5. Posiciona com os tamanhos reais, usando regressão isotônica para nada se
   sobrepor.
6. Testa quatro variantes e fica com a de menos cruzamentos. A horizontal só vence
   se poupar dois ou mais.

Pontas arrastadas à mão voltam para o roteamento automático.

**Desenho sem sobreposição.** Listas, notas de cálculo e a linha da nota são obstáculos
para as rotas. Nome e cardinalidades procuram um lugar livre, evitando linhas, caixas e
outros rótulos. O nome da rede fica entre as paralelas quando cabe; se não cabe, fica
por fora.

---

## Histórico de decisões

As decisões 1 a 15 foram tomadas na versão 2 desta spec. O que mudou depois está
anotado.

| # | Decisão | Situação atual |
| --- | --- | --- |
| 1 | Nomes físicos sem acento, até 30 caracteres, únicos entre datasets e relationship classes, nome original no alias | Vale. O CamelCase original virou palavras unidas por `_` (padrão da ET-EDGV). O nome no Lógico chegou a ser restrito a identificador válido, e depois voltou a ser livre, com alias. |
| 3 | Amostragem é Multipoint | Vale. O gerador chegou a emitir `POINT`, o que foi corrigido para `MULTIPOINT`. |
| 4 | Inteiro: ≤4 dígitos SHORT, ≥5 LONG | Vale. |
| 5 | Booleano = SHORT + domínio SimNao | Vale. |
| 6 | Único = Constraint Rule | Vale. Estendido à PK (regra `PK_<Classe>`). |
| 7 | Lista = domínio codificado, deduplicado | Vale. Ganhou a detecção de códigos numéricos (SHORT/LONG). |
| 8 | Integridade: Cascata COMPOSITE, Nulo SIMPLE, Restringir SIMPLE + regra, Padrão SIMPLE + regra de cálculo | Vale, **menos Padrão**: a regra de cálculo nunca foi gerada, e o gerador emitia uma pseudorregra. Hoje Padrão vai para `unmapped` (pendência). |
| 9 | Rótulo inverso: de-para para espacial, campo "Nome inverso" para os demais | Vale. |
| 10 | M:N atribuído | **Substituída:** M:N é `NONE`; atributos na relação pedem classe intermediária. |
| 11 | Generalização sempre tabela por classe | Vale. |
| 12 | Rede declarada, não criada | Vale. A rede fica no feature dataset do SRID das classes. |
| 13 | Espacial: topologia quando há regra proibitiva, Constraint Rule quando não há | Vale. "Está próximo de" ganhou o campo de distância de volta. |
| 14 | GLOBALID só quando necessário | Vale: só onde há attribute rule. Anexos e Editor Tracking não pedem. Placeholders não recebem. |
| 15 | Tolerância de cluster = padrão do SR; feature dataset "Topologia" só com as classes da topologia | Tolerância vale. **O feature dataset "Topologia" foi substituído** por um feature dataset por SRID com todas as feature classes. |

Outras mudanças registradas:

- **Cálculo geodésico.** Começou com `AreaGeodetic`/`LengthGeodetic` em todo SRID. O
  ArcGIS Pro recusou em 31982 ("Projection is invalid"), e hoje o cálculo depende do SRID
  (seção 5).
- **ET-EDGV.** Uma verificação opcional de conformidade com a ET-EDGV 3.0 foi criada e
  depois retirada por completo, a pedido do autor. Dela ficou só o padrão de nomes
  com `_`.
- **Generalização cartográfica.** Passou a ter a superclasse no destino do desenho e uma
  relationship class por representação.
- **Participação mínima.** Passou a ligar o Editor Tracking, que o ArcGIS exige para
  Validation Rule.
