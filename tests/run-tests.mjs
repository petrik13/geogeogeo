#!/usr/bin/env node
// Testes do GeoGeoGeo.
//
// O app é um HTML único, sem build: aqui ele é aberto num Chromium headless
// (Playwright) e as funções globais da página são chamadas direto. Cobre o
// gerador do JSON do GDB (contra o exemplo de referência exemplo-gdb.json), o
// tradutor do construtor de cálculo e comportamentos de interface que já
// quebraram antes. Também confere se a toolbox embutida no HTML é a mesma do
// geogeogeo_toolbox.pyt e se o .pyt compila.
//
// Uso:  npm test                 (ou: node tests/run-tests.mjs)
//       npm run test:update      regrava exemplo-gdb.json a partir do app
import { createRequire } from 'node:module';
import { execSync, spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const APP = path.join(ROOT, 'index.html');
const GOLDEN = path.join(ROOT, 'exemplo-gdb.json');
const TOOLBOX = path.join(ROOT, 'geogeogeo_toolbox.pyt');
const UPDATE = process.argv.includes('--update');
// Data fixa: o JSON leva a data de geração (generatedAt e os créditos dos
// metadados), e o exemplo de referência precisa ser reprodutível.
const FIXED_NOW = new Date('2026-01-01T12:00:00Z');

function loadPlaywright(){
  const require = createRequire(import.meta.url);
  try { return require('playwright'); } catch {}
  try { return require(path.join(execSync('npm root -g').toString().trim(), 'playwright')); } catch {}
  console.error('Playwright não encontrado. Rode "npm install" na raiz do repositório.');
  process.exit(2);
}

const results = [];
async function test(name, fn){
  try { await fn(); results.push({name, ok:true}); }
  catch(err){ results.push({name, ok:false, err}); }
}
function assert(cond, msg){ if(!cond) throw new Error(msg); }
function assertEq(actual, expected, msg){
  if(actual !== expected) throw new Error(msg+'\n    esperado: '+JSON.stringify(expected)+'\n    obtido:   '+JSON.stringify(actual));
}

const { chromium } = loadPlaywright();
const browser = await chromium.launch();

// Abre uma página nova do app, já com a data fixa e sem autosave anterior.
async function openApp(){
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.errors = [];
  page.on('pageerror', e => page.errors.push(e.message));
  await page.clock.setFixedTime(FIXED_NOW);
  // As fontes do Google não fazem diferença para os testes e podem estar fora do ar.
  await page.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort());
  await page.goto('file://' + APP);
  await page.evaluate(() => localStorage.clear());
  return page;
}
async function openExample(){
  const page = await openApp();
  await page.click('#btnExample');
  return page;
}

// ---------------------------------------------------------------- toolbox
await test('toolbox embutida no HTML é igual ao geogeogeo_toolbox.pyt', async () => {
  const html = readFileSync(APP, 'utf8');
  const m = html.match(/<script type="text\/plain" id="pytSource">\n([\s\S]*?)<\/script>/);
  assert(m, 'bloco <script id="pytSource"> não encontrado');
  assertEq(m[1].trimEnd(), readFileSync(TOOLBOX, 'utf8').trimEnd(),
    'as duas cópias divergiram — rode "npm run embed-toolbox"');
});

await test('toolbox processa o exemplo-gdb.json (arcpy simulado)', async () => {
  const py = spawnSync('python3', [path.join(ROOT, 'tests', 'test_toolbox.py')], {encoding:'utf8'});
  if(py.error){ console.warn('  (python3 indisponível — toolbox não verificada)'); return; }
  assertEq(py.status, 0, (py.stdout + py.stderr).trim());
});

// ---------------------------------------------------------------- gerador do GDB
await test('o app abre e carrega o Exemplo sem erro de JavaScript', async () => {
  const page = await openExample();
  const n = await page.evaluate(() => state.classes.length);
  assert(n > 20, 'o Exemplo deveria ter mais de 20 classes, veio '+n);
  assertEq(page.errors.join('\n'), '', 'erros na página');
  await page.close();
});

await test('JSON do GDB do Exemplo bate com exemplo-gdb.json', async () => {
  const page = await openExample();
  const doc = await page.evaluate(() => buildGdbJson());
  const text = JSON.stringify(doc, null, 2) + '\n';
  if(UPDATE){ writeFileSync(GOLDEN, text); console.log('  exemplo-gdb.json regravado.'); }
  else {
    const golden = readFileSync(GOLDEN, 'utf8');
    if(text !== golden){
      const a = golden.split('\n'), b = text.split('\n');
      const i = a.findIndex((l, k) => l !== b[k]);
      // mostra só o trecho da linha em volta da primeira diferença
      const la = a[i] || '', lb = b[i] || '';
      let c = 0; while(c < la.length && la[c] === lb[c]) c++;
      const cut = s => (c > 60 ? '…' : '') + s.slice(Math.max(0, c-60), c+80) + (s.length > c+80 ? '…' : '');
      throw new Error('o gerador mudou a saída (linha '+(i+1)+').\n    referência: '+cut(la)+'\n    agora:      '+cut(lb)+
        '\n    Se a mudança é intencional, rode "npm run test:update" e revise o diff de exemplo-gdb.json.');
    }
  }
  await page.close();
});

await test('JSON do GDB do Exemplo é coerente com o que a toolbox espera', async () => {
  const page = await openExample();
  const doc = await page.evaluate(() => buildGdbJson());
  const byName = new Map(doc.datasets.map(d => [d.name, d]));
  const created = d => d && d.status !== 'placeholder';
  const fdNames = new Set(doc.featureDatasets.map(f => f.name));
  for(const r of doc.attributeRules){
    assert(created(byName.get(r.dataset)), 'regra '+r.name+' aponta para dataset inexistente ou placeholder: '+r.dataset);
    assert(!r.arcade.trim().startsWith('//'), 'regra '+r.name+' não é executável (só comentário)');
  }
  for(const d of doc.datasets){
    const hasRule = doc.attributeRules.some(r => r.dataset === d.name);
    assertEq(d.systemFields.includes('GLOBALID'), hasRule, 'GLOBALID de '+d.name+' deveria existir só com attribute rule');
    if(d.featureDataset) assert(fdNames.has(d.featureDataset), d.name+' aponta para feature dataset inexistente');
  }
  for(const rc of doc.relationshipClasses){
    assert(byName.has(rc.origin) && byName.has(rc.destination), 'relationship class '+rc.name+' com ponta inexistente');
  }
  for(const net of doc.networks){
    assert(fdNames.has(net.featureDataset), 'rede '+net.name+' aponta para feature dataset inexistente: '+net.featureDataset);
    const edges = net.edges.map(e => e.class);
    assertEq(new Set(edges).size, edges.length, 'rede '+net.name+' repete classe nos arcos');
  }
  assertEq(byName.get('Amostra_De_Solo').geometryType, 'MULTIPOINT', 'Amostragem deve virar MULTIPOINT (Decisão 3)');
  const genWarn = doc.warnings.filter(w => /^Generalização total\/disjunta/.test(w.message));
  assertEq(genWarn.length, 1, 'uma generalização com duas subclasses deve avisar uma vez só');
  await page.close();
});

await test('modelo novo: a geodatabase leva o nome do modelo e o SRID padrão vale', async () => {
  const page = await openApp();
  const ws = await page.evaluate(() => {
    loadModel(emptyModel('Cadastro Fundiário'));
    setActiveModel('logical');
    state.classes.push(newClassObj('geo', 0, 'object', 'polygon'));
    state.meta.srid = '31983';
    const d = buildGdbJson();
    return {name: d.workspace.name, wkid: d.datasets[0].spatialReference.wkid};
  });
  assertEq(ws.name, 'Cadastro_Fundiario', 'nome da geodatabase');
  assertEq(ws.wkid, 31983, 'SRID padrão do modelo');
  await page.close();
});

// ---------------------------------------------------------------- tradutor de cálculo
await test('tradutor de cálculo: precedência, escape e erros', async () => {
  const page = await openApp();
  const r = await page.evaluate(() => {
    const t = (src, known) => calcTranslate(src, known || ['D','A','Nome'], null);
    return {
      mes: t('MES([D]) * 2'),
      concat: t('CONCAT([A], "x") = "yx"'),
      barra: t('CONCAT([A], "C:\\temp")'),
      campo: t('[Inexistente] + 1'),
      funcao: t('FOO(1)'),
      aridade: t('ABS(1, 2)'),
      planar: arcadeForSrid("AreaGeodetic($feature, 'square-meters')", 31982),
      geodesico: arcadeForSrid("AreaGeodetic($feature, 'square-meters')", 4326)
    };
  });
  assertEq(r.mes.arcade, '(Month($feature.D) + 1) * 2', 'MES dentro de uma expressão maior');
  assertEq(r.concat.arcade, '($feature.A + "x") == "yx"', 'CONCAT dentro de uma comparação');
  assertEq(r.concat.sql, "((a)::text || ('x')::text) = 'yx'", 'CONCAT no SQL');
  assertEq(r.barra.arcade, '($feature.A + "C:\\\\temp")', 'barra invertida escapada no Arcade');
  assert(!r.campo.ok && /não existe/.test(r.campo.error), 'campo inexistente deve ser erro');
  assert(!r.funcao.ok && /desconhecida/.test(r.funcao.error), 'função desconhecida deve ser erro');
  assert(!r.aridade.ok && /argumento/.test(r.aridade.error), 'número de argumentos deve ser verificado');
  assertEq(r.planar, "Area($feature, 'square-meters')", 'SRID projetado usa cálculo plano');
  assertEq(r.geodesico, "AreaGeodetic($feature, 'square-meters')", '4326 mantém o geodésico');
  await page.close();
});

await test('construtor de cálculo mostra o Arcade com os nomes físicos', async () => {
  const page = await openExample();
  const arcade = await page.evaluate(() => {
    const cls = state.classes.find(c => c.name === 'IPTU');
    const attr = cls.attributes.find(a => a.name === 'Valor venal');
    openCalcBuilder(cls, attr, () => {});
    const out = document.querySelector('.calc-out code').textContent;
    document.querySelector('.calc-overlay').remove();
    return out;
  });
  assertEq(arcade, '$feature.Valor_Territorial + $feature.Valor_Predial', 'prévia do Arcade');
  await page.close();
});

// ---------------------------------------------------------------- interface
await test('trocar o tipo do atributo descarta o que deixou de valer', async () => {
  const page = await openApp();
  const r = await page.evaluate(() => {
    const a = {id:'x', name:'Campo', type:'text', length:'20', defaultValue:'abc'};
    applyAttrType(a, 'boolean');
    const b = {id:'y', name:'N', type:'integer', intDigits:'4', defaultValue:'5', minValue:'0'};
    applyAttrType(b, 'double');
    return {a, b};
  });
  assertEq(r.a.defaultValue, undefined, 'valor padrão de texto não vai para um Booleano');
  assertEq(r.a.length, undefined, 'tamanho só vale para Texto');
  assertEq(r.b.defaultValue, '5', 'um padrão numérico continua válido em Decimal');
  assertEq(r.b.minValue, '0', 'a faixa vale para Inteiro e Decimal');
  assertEq(r.b.intDigits, undefined, 'dígitos só valem para Inteiro');
  await page.close();
});

await test('na tela do Físico, Delete não apaga a classe escondida do Lógico', async () => {
  const page = await openExample();
  const before = await page.evaluate(() => { selectClass(state.classes[0].id); setActiveModel('gdbView'); return modelStash.logical.classes.length; });
  await page.keyboard.press('Delete');
  await page.keyboard.press('Delete');
  const after = await page.evaluate(() => { setActiveModel('logical'); return state.classes.length; });
  assertEq(after, before, 'número de classes do Lógico');
  await page.close();
});

await test('abrir um JSON com classe sem lista de atributos não quebra a tela', async () => {
  const page = await openApp();
  const n = await page.evaluate(() => {
    loadModel({classes:[{id:'c1', name:'Solta', kind:'conventional', x:0, y:0}], relationships:[]});
    return state.classes[0].attributes.length;
  });
  assertEq(n, 0, 'attributes deveria virar lista vazia');
  assertEq(page.errors.join('\n'), '', 'erros na página');
  await page.close();
});

await test('menu de exportação baixa cada formato com o nome certo', async () => {
  const page = await openExample();
  const grab = async fmt => {
    await page.click('#btnExport');
    const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#exportMenu button[data-fmt="'+fmt+'"]')]);
    return dl;
  };
  const names = {};
  for(const fmt of ['json', 'pyt', 'dict', 'jpeg']) names[fmt] = (await grab(fmt)).suggestedFilename();
  assertEq(names.json, 'exemplo_teste_completo_gdb.json', 'modelo em JSON');
  assertEq(names.pyt, 'geogeogeo_toolbox.pyt', 'toolbox');
  assertEq(names.dict, 'exemplo_teste_completo_gdb_dicionario_de_dados.docx', 'dicionário de dados');
  assertEq(names.jpeg, 'exemplo_teste_completo_gdb_diagrama.jpg', 'imagem do diagrama');
  // JSON do GDB: pelo menu abre o resumo, e o download sai de lá
  await page.click('#btnExport');
  await page.click('#exportMenu button[data-fmt="gdbjson"]');
  const [gdb] = await Promise.all([page.waitForEvent('download'), page.click('.calc-overlay .btn.primary')]);
  assertEq(gdb.suggestedFilename(), 'Teste_OMTG_gdb.json', 'JSON do GDB');
  assertEq(page.errors.join('\n'), '', 'erros na página');
  await page.close();
});

await browser.close();

// ---------------------------------------------------------------- resumo
let failed = 0;
for(const r of results){
  console.log((r.ok ? '  ok    ' : '  FALHA ') + r.name);
  if(!r.ok){ failed++; console.log('        ' + String(r.err && r.err.message || r.err).replace(/\n/g, '\n        ')); }
}
console.log('\n' + (results.length - failed) + ' de ' + results.length + ' testes passaram.');
process.exit(failed ? 1 : 0);
