# Prancheta OMT-G

Ferramenta interativa de modelagem conceitual de bancos de dados geográficos em notação **OMT-G** (Borges, Davis & Laender). Roda inteiramente no navegador — sem backend, sem build, um único arquivo HTML.

## O que faz

- Classes convencionais e geo-referenciadas (geo-objeto e geo-campo, com as primitivas geométricas do OMT-G).
- Relacionamentos: associação, generalização/especialização, agregação (todo-parte), rede e relações espaciais/topológicas.
- Roteamento ortogonal dos conectores no diagrama, com desvio automático de obstáculos.
- Exportação para:
  - **Script Python (arcpy)** — recomendado para ArcGIS: cria o esquema chamando a API oficial do ArcGIS (`CreateFeatureclass`, `AddField`, `CreateRelationshipClass`).
  - **Esri Geodatabase XML** (XML Workspace Document) — formato interno do ArcGIS, mais frágil de importar; use o script Python acima quando possível.
  - **GeoPackage** (DDL SQL).
  - **PostGIS** (DDL SQL, com esquema opcional de topologia).

## Por que hospedar fora do Claude

A versão publicada como Claude Artifact só consegue baixar arquivos com um conjunto fixo de extensões (não inclui `.xml` nem `.sql`), então esses exports saíam renomeados para `.txt`. Hospedado como um site comum (GitHub Pages, Vercel, Netlify, ou qualquer servidor estático), o download usa o mecanismo nativo do navegador e funciona com qualquer extensão sem nenhuma mudança de código — o botão de exportar já foi escrito para isso.

## Como rodar localmente

Não precisa de nada instalado além de um navegador — é um HTML autocontido.

```bash
# qualquer servidor estático simples serve, por exemplo:
python3 -m http.server 8000
# depois abra http://localhost:8000
```

Ou simplesmente abra `index.html` direto no navegador (duplo clique).

## Como publicar no GitHub Pages

1. Suba este repositório para o GitHub (veja os comandos abaixo).
2. No GitHub, vá em **Settings → Pages**.
3. Em "Build and deployment", escolha **Deploy from a branch**, selecione a branch `main` e a pasta `/ (root)`.
4. Salve. Em alguns minutos o site fica disponível em `https://<seu-usuário>.github.io/<nome-do-repositório>/`.

Qualquer novo `git push` para `main` atualiza o site automaticamente.

## Comandos para subir este repositório

Rodando de dentro desta pasta (onde estão `index.html` e este `README.md`):

```bash
git init
git add index.html README.md
git commit -m "Prancheta OMT-G: ferramenta de modelagem conceitual geográfica"
git branch -M main
git remote add origin https://github.com/petrik13/geogeogeo.git
git push -u origin main
```

Se o repositório `petrik13/geogeogeo` já tiver conteúdo (por exemplo, um README criado pelo próprio GitHub), troque o `git push` acima por:

```bash
git pull origin main --allow-unrelated-histories
# resolva conflitos se aparecerem, depois:
git push -u origin main
```

## Estado dos dados

Tudo fica salvo no `localStorage` do navegador (autosave a cada edição). Isso é por navegador/dispositivo — não sincroniza entre máquinas. Use "Salvar .json" para exportar o modelo e "Abrir" para importar em outro lugar.
