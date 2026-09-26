# GeoGeoGeo

Editor de modelos de dados geográficos na notação **OMT-G** (Borges, Davis Jr. & Laender).
Roda inteiro no navegador: um único `index.html`, sem backend e sem build.

O objetivo é levar um modelo do desenho conceitual até a geodatabase pronta no ArcGIS:

```
Conceitual  ──migrar──▶  Lógico  ──gerar──▶  Físico (GDB): JSON  ──toolbox .pyt──▶  File Geodatabase
```

- **Conceitual.** O diagrama de classes OMT-G: classes convencionais, geo-objeto e
  geo-campo com suas primitivas, e os relacionamentos (associação, espacial, rede,
  generalização, generalização cartográfica e agregação).
- **Lógico.** O mesmo diagrama com o que o banco precisa:
  - tipos, PK/FK, obrigatório, único, faixa de valores, listas (domínios) e campos
    calculados;
  - SRID, Z/M e controle de edições por classe;
  - integridade referencial e operações OMT-G.

  O Conceitual e o Lógico são modelos independentes. "Migrar" copia um para o outro
  sem apagar o que só existe no destino.
- **Físico (GDB).** Uma vista, não um modelo editável. Mostra o JSON de criação da
  geodatabase gerado a partir do Lógico, com contagens, avisos e o que não tem
  equivalente no GDB.
- **Toolbox `geogeogeo_toolbox.pyt`.** Uma Python Toolbox do ArcGIS Pro que lê esse JSON
  e cria a File Geodatabase: domínios, feature datasets, tabelas e feature classes,
  relationship classes, topologias, attribute rules (Arcade) e metadados.

## Arquivos

| Arquivo | O que é |
| --- | --- |
| `index.html` | O aplicativo inteiro (HTML + CSS + JS). Também traz o modelo Exemplo e uma cópia da toolbox, que se baixa pelo menu. |
| `geogeogeo_toolbox.pyt` | A toolbox ArcGIS. É a fonte; a cópia dentro do `index.html` é sincronizada por script. |
| `mapeamento-logico-para-gdb.md` | Especificação: o que cada elemento do Lógico vira no GDB, e por quê. |
| `exemplo-gdb.json` | JSON gerado a partir do modelo Exemplo. Serve de referência (golden) para os testes. |
| `tests/` | Testes automáticos do app (Playwright) e da toolbox (arcpy simulado). |
| `tools/embed-toolbox.mjs` | Copia o `.pyt` para dentro do `index.html`. |
| `docs/contexto-pesquisa-mestrado.md` | Contexto acadêmico do projeto (mestrado) e o roteiro de longo prazo. |
| `annotator.html` | Ferramenta antiga de revisão visual, usada numa fase do projeto. Não é mantida. |
| `CLAUDE.md` | Guia para quem for continuar o desenvolvimento, seja pessoa ou agente. |

## Como usar

Abra o `index.html` no navegador (duplo clique serve) ou sirva a pasta:

```bash
python3 -m http.server 8000   # e abra http://localhost:8000
```

Fluxo típico:

1. Desenhe o modelo na aba **Conceitual**, arrastando os botões de classe e de
   relacionamento para o canvas.
2. **Migrar → Para o Lógico** e complete tipos, chaves, SRID etc. No Lógico, sem nada
   selecionado, o painel da direita mostra o SRID padrão e o nome da geodatabase.
3. **Validação** aponta problemas de desenho, de regra OMT-G e o que não vai caber no
   GDB.
4. **Migrar → Para o Físico (GDB)** gera o JSON. Baixe o JSON e a toolbox nessa tela ou
   no menu **Exportar**.
5. No ArcGIS Pro, adicione a toolbox, rode **Criar Geodatabase a partir do modelo** e
   aponte para o JSON.

O botão **Exemplo** carrega um modelo que exercita todas as transformações
(24 classes, 24 relationship classes, 61 attribute rules, topologia e redes).
Ele serve para conferir tudo no ArcGIS Pro.

**Exportar** também gera a imagem do diagrama (JPEG/PDF), o JSON do modelo e o
dicionário de dados em Word (.docx).

### Onde os dados ficam

O modelo é salvo automaticamente no `localStorage` do navegador (chave
`omtg-prancheta-model-v2`). Esse armazenamento é por navegador e por máquina. Para
levar o modelo a outro lugar, use **Exportar → JSON do modelo** e depois **Abrir**. O
JSON guarda o Conceitual e o Lógico juntos.

## Desenvolvimento

Não há build. Edite o `index.html` e recarregue a página.

Para os testes, você precisa de Node 18+ e Python 3; o Playwright é baixado pelo
`npm install`.

```bash
npm install            # só na primeira vez
npm test               # roda todos os testes
npm run test:update    # regrava exemplo-gdb.json depois de uma mudança INTENCIONAL no gerador
npm run embed-toolbox  # depois de editar geogeogeo_toolbox.pyt
```

Os testes cobrem:
- o gerador, comparado com o `exemplo-gdb.json` e com as invariantes do formato;
- a toolbox rodando sobre esse JSON com um arcpy simulado;
- o tradutor de cálculo;
- o CSS (nenhuma regra descartada);
- vários comportamentos de interface, como atalhos, troca de tipo e downloads.

Os detalhes para quem vai mexer no código estão no [`CLAUDE.md`](CLAUDE.md).

## Publicar

É um site estático. No GitHub Pages: **Settings → Pages → Deploy from a branch**,
branch `main` e pasta `/ (root)`. Os downloads usam o mecanismo normal do navegador, e
qualquer extensão funciona.
