# Mapeamento: Modelo Lógico → JSON de criação da File Geodatabase

Especificação do gerador de JSON que alimenta a toolbox `.pyt`. Lista **todo** elemento
que existe no modelo lógico do GeoGeoGeo e o que ele vira no GDB.

**Versão 2** — incorpora as 15 decisões. As que mudaram o mapeamento de forma
relevante estão marcadas com ✅.

## Legenda

| Marca | Significa |
| --- | --- |
| **1:1** | Correspondência direta, sem perda. |
| **Adaptado** | Existe equivalente, com outra forma. |
| **Parcial** | Parte da semântica se perde. |
| **Combinado** | Um elemento OMT-G exige vários objetos do GDB. |
| **Regra** | Resolvido por Attribute Rule (Arcade). |
| **Sem equivalente** | Vira metadado/aviso no JSON. |
| 🆕 | Exige campo novo no modelo lógico. |

## Premissa

O GDB é destino de criação, não diagrama. O JSON descreve *o que criar*, em que ordem,
e carrega junto tudo que não coube — porque o que não é representável é justamente o
que precisa ser auditado.

Três coisas o GDB cria sozinho: `OBJECTID` (sempre), `SHAPE` (em toda Feature Class) e
`GLOBALID` (quando necessário — **Decisão 14**: só quando houver Attribute Rule,
replicação ou Utility Network, que são os casos que o exigem).

---

## 0. Convenção de nomes ✅ (Decisão 1)

> **Atualização (Round RR): a regra passou a valer JÁ NO LÓGICO.** Nome de
> classe e de relacionamento no modelo lógico só aceita letras, números e `_`,
> começando por letra, com no máximo 30 caracteres — o campo filtra enquanto
> se digita e resolve duplicata no blur. A unicidade vale entre classes **e**
> relacionamentos, porque no GDB os dois dividem o mesmo espaço de nomes.
> Consequência: **o gerador não sanitiza nem encurta mais o que o usuário
> nomeou** — ele usa o nome como está. Só monta nome automático (e aí sim pode
> truncar, avisando) para relacionamento deixado sem nome.
> A conversão automática acontece uma vez, na migração Conceitual → Lógico,
> onde o nome livre vira CamelCase: `Área de Preservação` → `AreaDePreservacao`.
> O Conceitual segue livre — lá o nome é linguagem de modelagem, não
> identificador de banco.

A regra abaixo é a que o gerador aplica a campos e domínios, e a que a
migração aplica ao converter um nome livre:

- **CamelCase**, iniciando em maiúscula para datasets e relacionamentos.
- Acentos removidos preservando a letra base: `á à â ã ä` → `a`, `é ê` → `e`, `í` → `i`,
  `ó ô õ` → `o`, `ú ü` → `u`.
- **`ç` → `c`**, **`ñ` → `n`**.
- Espaços suprimidos (viram a fronteira entre palavras do CamelCase).
- Demais caracteres especiais suprimidos. Se sobrar um nome começando com dígito,
  recebe prefixo (`_`).
- **Máximo 30 caracteres.** Se estourar, trunca e desambigua com sufixo numérico.
- **Únicos no conjunto classes + relacionamentos** (namespace compartilhado).
- O nome original, com acento e espaço, vai sempre para o **alias**.

`Subdivisão Planar` → `SubdivisaoPlanar` (alias `Subdivisão Planar`).
`Área de Preservação` → `AreaDePreservacao`.

---

## 1. Metadados do modelo

| Elemento lógico | Vira no GDB | Status |
| --- | --- | --- |
| `meta.name` | Nome do `.gdb` (sanitizado) | Adaptado |
| `meta.workspaceName` | Nome do workspace | 1:1 |
| `meta.srid` + `meta.srsAuthority` | Spatial Reference padrão | 1:1 |
| `meta.schema` | — | Sem equivalente (conceito PostGIS; preservado para o gerador futuro) |

---

## 2. Classe

| Propriedade | Vira no GDB | Status |
| --- | --- | --- |
| `id` | `omtgId` no JSON | 1:1 — rastreabilidade de todo objeto gerado |
| `name` | Nome CamelCase + alias | Adaptado (seção 0) |
| `kind = conventional` | **Table** | 1:1 |
| `kind = geo` | Feature Class / Raster / TIN | Adaptado (seção 2.1) |
| `geoType` | — | Metadado; só influencia a escolha do dataset |
| `primitive` | Dataset + geometria + estrutura | Combinado (seção 2.1) |
| `srid` | Spatial Reference da FC | 1:1 — vazio herda `meta.srid` |
| `operations[]` | Attribute Rules **ou** modelo de transformação | Parcial (seção 2.2) |
| `x`, `y`, `w`, `h` | — | Layout do canvas, fora do JSON |

### 2.1 Primitiva → dataset, geometria e estrutura ✅

| Primitiva OMT-G | Dataset | Geometria | Estrutura |
| --- | --- | --- | --- |
| (convencional) | Table | — | — |
| Ponto | Feature Class | `POINT` | — |
| Linha | Feature Class | `POLYLINE` | — |
| Polígono | Feature Class | `POLYGON` | — |
| Linha unidirecional | Feature Class | `POLYLINE` | Network, um sentido |
| Linha bidirecional | Feature Class | `POLYLINE` | Network, dois sentidos |
| Nó | Feature Class | `POINT` | Network (junction) |
| Isolinhas | Feature Class | `POLYLINE` | — |
| TIN | TIN Dataset | — | Surface |
| Tesselação | Raster Dataset | — | — |
| **Amostragem** | Feature Class | **`MULTIPOINT`** | Sampling |
| Subdivisão Planar | Feature Class | `POLYGON` | Topology |

**Decisão 3 — Amostragem é sempre Multipoint.** Tecnicamente bem fundamentada: o LAS
Dataset não mora dentro da geodatabase (é um `.lasd` que *referencia* arquivos `.las`
externos), e a conversão entre os dois é **mão única** — existe `LAS To Multipoint`,
não existe o caminho inverso (`Convert LAS` só aceita `.las`/`.zlas`/`.laz` e LAS
datasets, nunca feature classes). Multipoint é o formato que vive dentro do `.gdb` e
para o qual sempre se pode importar LiDAR.

TIN e Raster Dataset continuam sendo **placeholders declarados**: nascem de dados de
entrada, não de criação vazia por geoprocessamento.

### 2.2 As 21 operações OMT-G ✅

Elas se dividem em dois grupos com destinos diferentes:

**Grupo A — valor derivado da própria feição.** Cabem em **Calculate Attribute Rule**
(Arcade), porque produzem um número ou ponto a partir da geometria da própria linha:
área, perímetro, comprimento, centroide (como X/Y em campos).

**Grupo B — produzem uma representação nova.** Voronoi, Delaunay, isolinhas,
esqueletização, fecho convexo, triangulação de polígonos, e os operadores de
generalização cartográfica e análise espacial. Essas **não são atributo** — elas geram
uma camada de saída, com outra geometria e outra contagem de feições. Attribute Rule
não faz isso: ela calcula campos, não cria datasets.

Esse é exatamente o recorte do **diagrama de transformação** do OMT-G (passo 5 do
roadmap). Proposta: Grupo A vira Attribute Rule agora; Grupo B vai para `unmapped` com
a ferramenta de geoprocessamento correspondente sugerida, e é o material do modelo de
transformação quando ele existir.

---

## 3. Campo (atributo)

| Propriedade | Vira no GDB | Status |
| --- | --- | --- |
| `name` | Nome CamelCase + alias | Adaptado |
| `type = text` | `TEXT` + `length` | 1:1 |
| `type = integer` | `SHORT` ou `LONG` | Adaptado ✅ — seção 3.1 🆕 |
| `type = double` | `DOUBLE` | 1:1 |
| `type = boolean` | `SHORT` + domínio Sim/Não | Adaptado ✅ — seção 3.2 |
| `type = date` | `DATE` | 1:1 |
| `type = blob` | `BLOB` | 1:1 |
| `type = list` | `TEXT` + coded value domain | Combinado — seção 3.3 |
| `length` | `field_length` | 1:1 (só `TEXT`) |
| `precision` / `scale` | `field_precision` / `field_scale` | **Parcial** — ignorados em File GDB (valem só em enterprise). Vão como intenção + aviso. |
| `required` | `NON_NULLABLE` | 1:1 |
| `defaultValue` | `AssignDefaultToField` | 1:1 |
| `unique` | **Constraint Attribute Rule** | Regra ✅ (Decisão 6) — seção 3.4 |
| `pk` | Campo + índice + `origin_primary_key` | Adaptado — o GDB identifica pelo `OBJECTID`; a PK vira campo indexado usado como chave nas relationship classes |
| `fk` | `origin_foreign_key` | Adaptado |
| `pk` **e** `fk` juntos | Chave da subclasse na herança | 1:1 |
| `refIntegrity` | Tipo da relationship class + regra | Adaptado ✅ — seção 3.5 |
| `calculated` + expressão | **Calculate Attribute Rule** | Adaptado ✅ — seção 3.6 🆕 |
| `listDomain[]` | Coded value domain | Combinado |
| `listBox` | — | Layout do canvas |

### 3.1 Inteiro: tamanho → SHORT ou LONG ✅ (Decisão 4) 🆕

Campo novo no lógico: **tamanho do inteiro** (número de dígitos).

| Dígitos | Tipo GDB | Faixa real |
| --- | --- | --- |
| 1 a 4 | `SHORT` | −32.768 a 32.767 |
| 5 ou mais | `LONG` | −2.147.483.648 a 2.147.483.647 |

**Correção ao que você escreveu:** o corte precisa ser em 4, não em 5. `SHORT` vai até
32.767, então não cabe todo número de 5 dígitos (99.999 estoura). Adotei
**≤4 → SHORT, ≥5 → LONG**; sem tamanho preenchido, `LONG`. Se algum dia precisar de
mais de 10 dígitos, aí só `DOUBLE` ou `TEXT` — vira aviso.

### 3.2 Booleano ✅ (Decisão 5)

Não existe tipo booleano em File GDB. Vira `SHORT` com domínio de valores codificados
compartilhado por todo o modelo:

```
Domínio "SimNao" (SHORT): 1 = Sim, 0 = Não
```

Um único domínio para todos os campos booleanos, coerente com a deduplicação da
Decisão 7.

### 3.3 Lista → domínio de valores codificados ✅ (Decisão 7)

Vira três objetos: `CreateDomain`, `AddCodedValueToDomain` por par, e
`AssignDomainToField`. `code` = chave, `name` = valor.

**Nomeação e deduplicação:** o nome do domínio é o **nome do campo** apenas
(`Situacao`). Domínios com conteúdo idêntico são **fundidos em um só**, mesmo em
classes diferentes. Se dois campos tiverem o mesmo nome e conteúdos **diferentes**,
aí o segundo recebe o nome da classe como prefixo (`LoteSituacao`, `QuadraSituacao`).

### 3.4 Único → Constraint Attribute Rule ✅ (Decisão 6)

Índice único não é suportado em File GDB. Vira uma **Constraint Attribute Rule**, que
roda na inserção/atualização e rejeita a edição se o valor já existir:

```
// Regra de restrição no campo Matricula
var existentes = Filter(
  FeatureSetByName($datastore, "Lote", ["Matricula"], false),
  "Matricula = @codigo AND OBJECTID <> @oid"
);
return Count(existentes) == 0;
```

Ressalva honesta: a regra vale para edições feitas **através do geodatabase**. Não
protege contra carga bruta que a contorne, e tem custo de avaliação em tabelas grandes.
O JSON declara a regra e registra a ressalva.

### 3.5 Integridade referencial ✅ (Decisão 8)

| `refIntegrity` | Vira | Status |
| --- | --- | --- |
| Cascata | Relationship class `COMPOSITE` | 1:1 — excluir a origem exclui os destinos |
| Nulo | Relationship class `SIMPLE` | 1:1 — em relacionamento simples, excluir a origem nulifica a FK do destino |
| **Restringir** | `SIMPLE` + **Constraint Attribute Rule** | Regra ✅ — a regra bloqueia a exclusão da origem quando existem filhos |
| Padrão | `SIMPLE` + regra de cálculo | Adaptado — a regra repõe o `defaultValue` no lugar do nulo |

### 3.6 Campo calculado → Calculate Attribute Rule ✅ 🆕

Muda de natureza: o campo calculado deixa de ser texto documental e passa a carregar
**expressão real**, montada num construtor no modelo lógico (nos moldes do Field
Calculator). No GDB vira **Calculate Attribute Rule**, com a expressão traduzida para
Arcade e `triggers` de inserção e atualização.

Isso fecha o ciclo com o Grupo A das operações (2.2): "área", "perímetro" e
"centroide" deixam de ser só nome de operador e passam a ser expressões calculáveis.

⚠ **Pendente: a linguagem da expressão.** Ver a pergunta no fim do documento.

---

## 4. Relacionamentos

Campos comuns:

| Propriedade | Vira | Status |
| --- | --- | --- |
| `id` | `omtgId` | 1:1 |
| `name` | `forward_label` | 1:1 |
| **inverso** | `backward_label` | Adaptado ✅ — seção 4.1 🆕 |
| `sourceId` / `targetId` | `origin` / `destination` | 1:1 |
| `srcAnchor` / `dstAnchor` | — | Layout |

### 4.1 Rótulo invertido ✅ (Decisão 9)

O GDB pede dois rótulos, ida e volta. Para relacionamento espacial, o inverso é
derivado por de-para da regra topológica:

| Regra | Ida | Volta |
| --- | --- | --- |
| toca | toca | é tocado por |
| está dentro de | está dentro de | contém |
| cruza | cruza | é cruzado por |
| sobrepõe | sobrepõe | é sobreposto por |
| é disjunto de | é disjunto de | é disjunto de *(simétrico)* |
| é adjacente a | é adjacente a | é adjacente a *(simétrico)* |
| coincide com | coincide com | coincide com *(simétrico)* |
| contém | contém | está dentro de |
| está próximo de | está próximo de | está próximo de *(simétrico)* |

Repare que `dentro`/`contém` são inversos um do outro, e quatro regras são simétricas.

Para **associação**, o nome é livre ("possui") e o inverso não é derivável. 🆕 Proposta:
campo opcional **"nome inverso"** no inspetor; vazio, o gerador usa o nome da classe de
origem (`pertence a Proprietario`).

### 4.2 Cardinalidade → cardinality

| `cardSource` × `cardTarget` | GDB |
| --- | --- |
| (`1`\|`0..1`) × (`1`\|`0..1`) | `ONE_TO_ONE` |
| (`1`\|`0..1`) × (`0..*`\|`1..*`) | `ONE_TO_MANY` |
| (`0..*`\|`1..*`) × (`1`\|`0..1`) | `ONE_TO_MANY` com origem/destino invertidos |
| (`0..*`\|`1..*`) × (`0..*`\|`1..*`) | `MANY_TO_MANY` **atributado** ✅ (Decisão 10) |

**O que se perde:** a participação mínima. `1..*` e `0..*` viram a mesma coisa; a
exigência de ao menos uma instância vira aviso. (Também é candidata a Constraint Rule,
se você quiser depois.)

Em M:N, o ArcGIS cria a tabela intermediária sozinho; declarada como `ATTRIBUTED` para
aceitar atributos no relacionamento.

### 4.3 Por tipo

| Tipo | Vira | Status |
| --- | --- | --- |
| **Associação** | Relationship class `SIMPLE` + cardinalidade | 1:1 |
| **Agregação simples** | Relationship class `COMPOSITE`, 1:N | 1:1 — todo-parte é a semântica de composto |
| **Agregação espacial** | `COMPOSITE` + Topology | Combinado — 4.4 |
| **Generalização** | Tabela por classe + relationship class 1:1 `COMPOSITE` **ou Subtypes** | Adaptado — 4.5 |
| **Generalização cartográfica** | FCs separadas + relationship class | Adaptado |
| **Rede** | Feature Dataset + Network Dataset | Parcial — 4.6 |
| **Relacionamento espacial** | Topology rule **ou** Constraint Rule | Regra ✅ — 4.7 |

### 4.4 Agregação espacial → Topology

| `spatialAggKind` | Regras |
| --- | --- |
| Subdivisão | Partes: *Must Not Overlap* + *Must Not Have Gaps*; Todo: *Area Must Be Covered By Area Class Of* |
| União | **As mesmas** — a diferença é a procedência da geometria (o todo deriva das partes, ou o contrário), que o GDB não guarda. Vai como metadado. |
| Contém | *Must Be Properly Inside* / *Must Be Covered By*, conforme a geometria da parte |

Topology exige **Feature Dataset**, e todas as FCs participantes precisam estar nele e
**compartilhar o mesmo Spatial Reference**. Classes com SRIDs diferentes não podem
participar da mesma topologia — vale virar validação no app.

**Tolerância de cluster:** padrão do Spatial Reference ✅ (Decisão 15).

### 4.5 Generalização: sempre tabela por classe ✅ (Decisão 11)

**Uma tabela por classe, sempre.** Superclasse e cada subclasse viram dataset próprio,
ligados por relationship class `ONE_TO_ONE` `COMPOSITE`, com a PK da subclasse servindo
também de FK.

**Subtypes foram descartados.** O ArcGIS ofereceria o caminho de uma feature class só
com um campo de categoria, mas ele só serve quando as subclasses não têm atributos
próprios — e amarra o modelo a uma otimização do ArcGIS que não tem contrapartida no
PostGIS. Tabela por classe é a mesma estrutura nos dois destinos.

`total`/`parcial` e `disjunto`/`sobreposto` não são representáveis no GDB — viram aviso.

### 4.6 Rede ✅ (Decisão 12)

Você perguntou o que é a decisão de template. Existem dois caminhos:

**`Create Network Dataset`** — cria a rede dentro de um Feature Dataset com
"configurações padrão básicas". Não precisa de template. Mas exige a **extensão Network
Analyst** (em qualquer nível de licença), e o resultado ainda precisa que você abra as
propriedades da rede e configure conectividade, atributos de custo, restrições e
direcionalidade, além de rodar `Build Network` antes de usar.

**`Create Network Dataset From Template`** — recria uma rede a partir de um XML
exportado de outra rede já configurada. Útil para replicar uma configuração que você já
acertou, inútil para criar a primeira.

Ou seja: o template não é obrigatório — é o atalho para repetir uma configuração
existente.

**Decidido: a toolbox não tenta criar a rede.** Ela cria as feature classes
participantes e o Feature Dataset que as agrupa (pré-requisito obrigatório), e declara
a intenção de rede — quem é arco, quem é junction, qual a direcionalidade — no bloco
`networks`, com `status: "declaredOnly"`. Duas razões: criar exigiria a extensão Network
Analyst, e a falta dela derrubaria a criação inteira da geodatabase por causa de um
pedaço; e mesmo criando, a rede nasceria sem conectividade, custos nem direcionalidade
configurados, e ainda precisaria de `Build Network`. O trabalho ficaria com o usuário de
qualquer forma — melhor entregar o terreno pronto e não tropeçar numa licença.

Se um dia existir uma rede já configurada, dá para exportar o XML dela e plugar o
caminho do template no JSON, e aí a criação passa a valer a pena.

A estrutura arco-arco (auto-loop) vira conectividade por endpoint. **Parcial.**

### 4.7 Relacionamento espacial → Topology rule ou Constraint Rule ✅ (Decisão 13)

Você perguntou se as cinco que faltavam davam para resolver com attribute rule. **Dão.**
O Arcade tem os predicados espaciais completos — `Touches`, `Crosses`, `Overlaps`,
`Within`, `Contains`, `Disjoint`, `Intersects`, `Relate` — além de `Distance` e
`Buffer`. Então o que não vira regra de topologia vira **Constraint Attribute Rule**:

| Regra OMT-G | Destino | Como |
| --- | --- | --- |
| está dentro de | Topology rule | *Must Be Properly Inside* / *Must Be Covered By* |
| contém | Topology rule | Mesma, lados invertidos |
| coincide com | Topology rule | *Must Be Covered By Feature Class Of* |
| é disjunto de | Topology rule | *Must Not Overlap With* |
| **toca** | Constraint Rule | `Touches($feature, vizinhas)` |
| **é adjacente a** | Constraint Rule | `Touches(...)` sobre polígonos |
| **cruza** | Constraint Rule | `Crosses($feature, outras)` |
| **sobrepõe** | Constraint Rule | `Overlaps($feature, outras)` |
| **está próximo de** | Constraint Rule | `Intersects(Buffer($feature, d), outras)` 🆕 precisa da distância |

Duas observações. Primeira: regra de topologia é **proibitiva** ("não pode sobrepor"),
enquanto a relação OMT-G é **afirmativa** ("sobrepõe"). A Constraint Rule resolve isso
porque ela afirma — exige que a relação seja verdadeira para a edição passar.

Segunda: "está próximo de" precisa de uma distância, e o campo `nearDistance` existe na
estrutura mas teve a interface removida. 🆕 Precisa voltar ao inspetor do lógico para
essa regra ser gerável.

---

## 5. O que o GDB exige e o lógico não tem

| Item | Tratamento |
| --- | --- |
| `OBJECTID` | Automático. Declarado como campo de sistema. |
| `SHAPE` | Idem, em toda Feature Class. |
| `GLOBALID` | ✅ Criado **quando necessário**: há Attribute Rule, replicação ou Utility Network. |
| **Feature Dataset** | Obrigatório para topologia e rede. Gerado agrupando as classes envolvidas, que precisam compartilhar o SR. |
| Nomes válidos | Seção 0. |
| Tolerância de cluster | ✅ Padrão do SR. |

---

## 6. Campos novos no modelo lógico

O que estas decisões exigem que seja acrescentado antes do gerador existir:

1. **Tamanho do inteiro** (dígitos) no atributo — Decisão 4.
2. **Construtor de cálculo** para o campo calculado, com expressão real.
3. **Nome inverso** (opcional) no relacionamento de associação — Decisão 9.
4. **Distância** de volta ao relacionamento espacial, para a regra "está próximo de".

---

## 7. O que ainda não sobrevive

Encolheu bastante depois das decisões. Resta:

1. Participação mínima das cardinalidades (`1..*` vira `0..*`) — salvo se virar regra.
2. `total`/`parcial` e `disjunto`/`sobreposto` da generalização.
3. A diferença entre Subdivisão e União (procedência da geometria).
4. `precision`/`scale` em File Geodatabase.
5. O Grupo B das 21 operações (as que geram representação nova) — destino é o modelo de transformação.
6. `meta.schema` (conceito PostGIS).

Tudo registrado em `unmapped`/`warnings` no JSON.

---

## 8. A linguagem do construtor de cálculo ✅

**Decidido: sintaxe neutra.** O modelo lógico não se prende a software nenhum, então a
expressão é escrita numa linguagem própria e cada gerador traduz — Arcade para o ArcGIS,
SQL para o PostGIS. Campos entre colchetes, funções em maiúsculas:

```
[AreaTotal] = AREA([SHAPE]) / 10000
[NomeCompleto] = CONCAT([Nome], " ", [Sobrenome])
[Idade] = ANOS_ENTRE([DataNascimento], HOJE())
```

que vira, no ArcGIS: `Area($feature, 'hectares')`,
`$feature.Nome + " " + $feature.Sobrenome`, `DateDiff(Now(), $feature.DataNascimento, 'years')`

e no PostGIS: `ST_Area(geom)/10000`, `nome || ' ' || sobrenome`,
`EXTRACT(YEAR FROM age(data_nascimento))`.

O construtor mostra os campos da classe, os operadores e as funções por categoria
(número, texto, data, geometria, lógica), e monta a expressão por clique, como o Field
Calculator — só que na sintaxe neutra, com a tradução para os dois destinos visível ao
vivo enquanto se escreve.

## Atualização — FK em relações 1:1

Num 1:1 a FK fica em **uma** das tabelas, qualquer uma. A classe que tem a FK vira o destino da relationship class, e a outra vira a origem. Se não houver FK em nenhuma das duas, o aviso pede FK em uma delas. Se houver FK nos dois lados, o gerador usa a do destino do desenho e avisa que a outra é redundante. No 1:N a FK continua obrigatória no lado N, e no M:N ela é indireta, na tabela intermediária.

## Atualização — nomes livres no Lógico (alias) e metadados

**Nomes.** No Lógico, o nome de classes, relacionamentos e redes voltou a ser livre: aceita espaços, acentos e outros caracteres especiais. O nome da classe vira o **alias** do dataset. O nome físico sai das mesmas regras de antes: CamelCase, sem acento, até 30 caracteres, único entre datasets e relationship classes. O painel mostra como o nome fica no banco enquanto se digita. Relationship class não tem alias no ArcGIS, então ali o nome livre vira o rótulo da relação. A Validação acusa dois nomes diferentes que caem no mesmo nome físico (erro), nomes que precisam ser encurtados (aviso) e nomes sem nenhuma letra ou número (erro). A migração Conceitual → Lógico passa o nome como está.

**Metadados.** O JSON traz um bloco `metadata` (title, summary, description em HTML simples, tags, credits) para a própria GDB (`workspace.metadata`) e para cada feature dataset, dataset (feature class ou tabela), relationship class e topologia. O conteúdo vem do modelo OMT-G e das decisões de mapeamento: tipo OMT-G e primitiva, atributos com PK, FK, integridade, domínio e cálculo, relacionamentos, regras de topologia e sua origem, attribute rules, operações OMT-G e os avisos do que não coube 1:1. A toolbox aplica esses metadados com `arcpy.metadata` no Item Description, e isso pode ser desligado por um parâmetro.

## Atualização — PK, anexos, Z/M, feature datasets por SRID e cálculo geodésico

**PK.** Toda PK ganha uma Constraint Attribute Rule (`PK<Classe>`) que recusa valor vazio e repetição. Numa PK composta, a regra vale para a combinação dos campos. Os campos da PK passam a ser NON_NULLABLE. Como toda attribute rule exige GLOBALID, classes com PK passam a tê-lo.

**Blob → anexo.** No GDB, um atributo Blob do Lógico não vira campo BLOB: a classe recebe anexos (`EnableAttachments`, tabela `__ATTACH`), o que também exige GLOBALID. Vários Blobs na mesma classe caem numa única tabela de anexos, e o gerador avisa. No PostGIS, o Blob continua sendo `bytea`.

**Z e M.** São checkboxes na classe do Lógico, logo abaixo do SRID, e viram `has_z`/`has_m` da feature class.

**Feature datasets.** Há um feature dataset por SRID (`SRID<código>`) com todas as feature classes daquele SRID. Tabelas ficam na raiz. A topologia de cada SRID nasce dentro do feature dataset dele. Isto substitui a Decisão 15 original, que criava um feature dataset "Topologia" só com as classes da topologia.

**Cálculo geodésico.** AREA, PERIMETRO e COMPRIMENTO viram `AreaGeodetic(…, 'square-meters')` e `LengthGeodetic(…, 'meters')` no Arcade, e `ST_Area/ST_Perimeter/ST_Length(geom::geography)` no SQL. Em SRID diferente de 4326 e 3857, isso exige ArcGIS Pro 3.5 ou superior (Arcade 1.30), e o gerador avisa.

## Atualização — GLOBALID, participação mínima, controle de edições e faixa de valores

**GLOBALID.** Só é criado onde há attribute rule, porque o ArcGIS não aceita regra sem ele (ERROR 002710). Anexos e Controle de edições não pedem GLOBALID. Se a toolbox rodar com "Criar attribute rules" desligado, nenhum GLOBALID é criado.

**Participação mínima (1..\*).** Vira uma Validation Attribute Rule (`Min<Relação><Classe>`) que usa `FeatureSetByRelationshipName` para exigir pelo menos um registro relacionado. Essa regra não bloqueia a edição: a classe nasce antes dos relacionados. Quem ficou sem nenhum aparece em Validate → Error Inspector. A regra só é criada quando a relationship class tem as chaves necessárias.

**Controle de edições.** É uma opção por classe no Lógico, logo depois de Atributos. No GDB vira `EnableEditorTracking` com os campos padrão da Esri (created_user, created_date, last_edited_user, last_edited_date), com datas em UTC. No PostGIS, o equivalente previsto são quatro colunas preenchidas por um trigger BEFORE INSERT OR UPDATE.

**Faixa de valores.** Campos inteiros e decimais têm Mínimo e Máximo em Propriedades do tipo. Com os dois limites, gera um domínio de intervalo (deduplicado pelo conteúdo). Com um ou os dois, gera uma Constraint Rule `Faixa<Classe><Campo>`, porque o domínio sozinho não impede a edição. No PostGIS, o equivalente previsto é um CHECK. A Validação acusa mínimo maior que máximo e valor que não é número.

**Canvas do Lógico.** O nome no banco aparece entre parênteses ao lado do alias quando os dois são diferentes. O canto superior direito mostra SRID · ZM · ✎ (controle de edições). A faixa aparece junto do tipo, por exemplo `Decimal(5,2) [0..100]`.

## Atualização — M:N sem atributos, listas numéricas, dicionário de dados e ET-EDGV

**M:N.** A relationship class M:N deixa de ser atribuível (`attributed: NONE`). Quando a relação tem atributos próprios, modela-se uma classe intermediária com dois 1:N, que é portável para GDB e PostGIS.

**Listas com códigos numéricos.** Se todos os códigos de uma Lista forem inteiros, o domínio e o campo saem SHORT (até 32.767) ou LONG. Basta um código com letra para tudo continuar TEXT. É detectado automaticamente, sem configuração.

**Dicionário de dados (Word).** Menu → Documentação → Dicionário de dados. O .docx é gerado no próprio app, sem biblioteca externa, em A4 paisagem, com quatro seções:
1. Visão geral: classes, nome no banco, tipo OMT-G, primitiva, SRID e tipo de dataset.
2. Classes: dados gerais, espaço para descrição, tabela de atributos (nome no banco, tipo, restrições, domínio/faixa, padrão, descrição), relacionamentos e operações.
3. Relacionamentos.
4. Domínios, com os valores de cada lista.

O modelo ainda não tem campo de descrição; o dicionário deixa o espaço "(a preencher)".

**Conformidade com a ET-EDGV 3.0 (CONCAR, 2017) e a ET-EDGV SPU 1.5.2.** É opcional: liga-se no painel de Validação do Lógico, e a escolha fica salva no modelo. As regras vêm das convenções que as normas explicitam:
- `EDGV-CLASSE`: o nome da classe usa palavras iniciadas em maiúscula separadas por "_", sem acento (ex.: `Trecho_Drenagem`).
- `EDGV-CATALOGO`: a classe corresponde a uma classe da norma, mas com outra grafia. O catálogo tem as classes do Cap. III da ET-EDGV 3.0, com código e categoria, e as classes da extensão SPU.
- `EDGV-ABSTRATA`: a classe é marcada NI (não instanciável) na norma.
- `EDGV-PRIMITIVA`: TIN e tesselação estão fora do escopo vetorial, e a norma não usa primitivas de rede.
- `EDGV-GEOM-APROX`: toda classe georreferenciada tem `geometriaAproximada` (Booleano, obrigatório).
- `EDGV-ATRIBUTO`: o nome do atributo é camelCase começando em minúscula.
- `EDGV-NOME`: `nome` é Alfanumérico(80).
- `EDGV-BOOLEANO`: um booleano opcional deveria ser uma lista Booleano_Estendido (1 Desconhecido, 2 Sim, 3 Não).
- `EDGV-LISTA`: as codeLists usam códigos inteiros.

Não verificado: a primitiva esperada de cada classe do catálogo (está nos diagramas do Anexo A, que não vieram no documento) e as regras de escala de aquisição.

## Atualização — nomes no banco com "_" (substitui o CamelCase da Decisão 1)

Os nomes físicos agora unem as palavras com "_" em vez de CamelCase. Continuam valendo as outras regras: sem acento, cada palavra com inicial maiúscula, até 30 caracteres, únicos entre datasets e relationship classes.

Exemplos:
- "Lote Urbano" → `Lote_Urbano`
- "VALOR_TERRITORIAL" → `VALOR_TERRITORIAL`
- "Área de Preservação" → `Area_De_Preservacao`

O mesmo padrão vale para:
- domínios (`Faixa_Nota`);
- regras (`PK_Lote`, `Unico_Proprietario_CPF`);
- feature datasets (`SRID_31982`) e topologias;
- colunas da tabela intermediária do M:N (`Proprietario_ID`);
- sufixos de desambiguação (`Lote_2`) e o Network Dataset (`Rede_ND`).

É o padrão de nomes da ET-EDGV.

## Atualização — ET-EDGV: só verificação de classes, com os Anexos

A verificação de conformidade deixou de olhar atributos. As regras `EDGV-ATRIBUTO`, `EDGV-NOME`, `EDGV-BOOLEANO`, `EDGV-LISTA` e `EDGV-GEOM-APROX` foram retiradas.

O catálogo passou a usar o Anexo A da ET-EDGV 3.0: 215 classes, com código, descrição, superclasses e, quando legível no PDF, a geometria (linha ou complexa).

As verificações que ficaram são todas de classe:
- `EDGV-CLASSE`: padrão do nome.
- `EDGV-CATALOGO`: classe da norma escrita com outra grafia.
- `EDGV-ABSTRATA`: classe NI (não instanciável).
- `EDGV-PRIMITIVA`: TIN, tesselação e primitivas de rede.
- `EDGV-GEOMETRIA` (nova): a classe é linha na norma e outra coisa no modelo; ou é Complexa na norma e não tem agregações no modelo.
- `EDGV-HERANCA` (nova): a superclasse da norma está no modelo sem a generalização; ou a classe especializa outra classe da norma que não é a superclasse prevista.

Com a verificação ligada, o dicionário de dados preenche a "Descrição" das classes reconhecidas com a definição da norma, citando código e fonte.

Limitação: os ícones de ponto e polígono do Anexo A não sobrevivem à extração de texto do PDF. Por isso só são verificadas as classes marcadas como linha (─) ou complexas (C).

## Atualização — verificação ET-EDGV removida

A verificação de conformidade com a ET-EDGV foi retirada por completo, a pedido do usuário. Isso inclui o catálogo de classes, as regras, a opção no painel de Validação e a descrição automática no dicionário de dados. A ferramenta não usa conceitos nem classes da norma. Do que veio junto com ela, fica só a decisão independente de nomear o banco com "_".

## Atualização — modelo "Exemplo" (teste massivo no ArcGIS Pro)

O botão **Exemplo**, ao lado de **Grid**, carrega o modelo "Exemplo — Teste completo GDB" direto no Lógico. Se já houver classes na tela, é preciso clicar duas vezes para confirmar. O modelo tem 23 classes e gera:

- 23 datasets;
- 23 relationship classes;
- 15 domínios;
- 63 attribute rules;
- uma topologia com 12 regras;
- 2 Feature Datasets: SRID_31982 e SRID_4674;
- 2 redes.

Ele cobre todas as transformações implementadas, e cada uma pode ser conferida no ArcGIS Pro:

- **PK:** simples de texto e de inteiro; também PK que é FK, na generalização.
- **FK:** do tipo SHORT contra uma PK LONG (Bairro.Município), para testar o alinhamento de tipo.
- **Integridade referencial:** Cascata, Restringir, Anular e Padrão.
- **Cardinalidades:** 1:1 com a FK de um lado só, 1:N, M:N sem atributo, participação mínima 1..* e classe intermediária (Contrato de Servidão).
- **Domínios:** lista numérica (SHORT), lista de texto e faixa (min/max).
- **Valores:** valor padrão e campo único.
- **Cálculos:** geodésicos (área, perímetro, comprimento), aritméticos e condicionais (SE).
- **Recursos do GDB:** anexos (2 Blobs na mesma tabela), controle de edições, Z e Z+M, e metadados.
- **Generalizações:** convencional total/disjunta e cartográfica.
- **Agregações espaciais:** união e subdivisão.
- **Redes:** arco-nó e arco-arco.
- **Relações espaciais:** uma de cada tipo.
  - Dentro, contém, coincide e disjunto viram topologia.
  - Toca, adjacente, cruza, sobrepõe e próximo (50 m) viram regra Arcade.
- **Geo-campos:** isolinhas, subdivisão planar e amostragem; TIN e raster ficam como placeholders.

## Atualização — botão "Organizar" (layout automático)

O botão **Organizar**, ao lado de Grid, arruma o diagrama da aba aberta, e cada aba guarda o próprio arranjo. Ctrl+Z desfaz a organização inteira de uma vez.

O layout é feito em camadas (Sugiyama), em seis passos:

1. **Grupos.** Separa os grupos de classes ligadas entre si. As classes soltas vão para uma grade embaixo.
2. **Hierarquia.** Define quem fica em cima:
   - na generalização, a superclasse;
   - na agregação, o todo;
   - na associação 1:N e 1 × 0..1, o lado 1;
   - no 1:1, o lado sem FK;
   - na generalização cartográfica, a origem.

   Relações espaciais, redes e M:N não criam hierarquia: só aproximam as classes, que podem ficar lado a lado.
3. **Largura das camadas.** Uma camada larga demais passa para a vizinha as classes que têm folga.
4. **Cruzamentos.** Reordena as classes de cada camada pelo baricentro, com várias passadas e trocas entre vizinhas.
5. **Posições.** Usa o tamanho real de cada caixa, e as listas e a nota de cálculo ficam numa coluna à direita da classe. O alinhamento com os vizinhos é feito por regressão isotônica, que garante que nada se sobreponha. O espaçamento é folgado.
6. **Variantes.** Testa quatro: vertical ou horizontal, com camadas alinhadas ao topo ou à base. Fica com a de menos cruzamentos, com preferência pela vertical com o pai em cima.

Ao organizar, as pontas de relacionamento arrastadas à mão voltam para o roteamento automático.

## Atualização — correções do teste no ArcGIS Pro

**AREA, PERIMETRO e COMPRIMENTO.** O Arcade do ArcGIS Pro recusou `AreaGeodetic` e `LengthGeodetic` em 31982, com o erro "Projection is invalid". Agora esses cálculos seguem o SRID da classe:

- em SRID projetado (UTM etc.), usam `Area` e `Length` planos, e a unidade já é metro;
- em 4326 e 3857, continuam geodésicos;
- em outro SRID geográfico, o gerador avisa que o resultado sairia em graus.

O aviso "exige Pro 3.5" foi removido. No PostGIS, o cálculo continua via `::geography`.

**Validation rules.** Agora a toolbox passa `severity=3`, que é obrigatório (de 1 a 5); faltava e causava o ERROR 002709.
