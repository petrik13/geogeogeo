#!/usr/bin/env node
// Copia geogeogeo_toolbox.pyt para dentro do index.html.
//
// O app oferece a toolbox para download a partir de uma cópia embutida na
// própria página (<script type="text/plain" id="pytSource">), para funcionar
// offline e sem arquivo externo. A fonte da verdade é o .pyt: edite-o e rode
//   npm run embed-toolbox
// O teste "toolbox embutida no HTML é igual ao geogeogeo_toolbox.pyt" acusa
// quando as duas cópias divergem.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const htmlPath = path.join(ROOT, 'index.html');
const pyt = readFileSync(path.join(ROOT, 'geogeogeo_toolbox.pyt'), 'utf8').trimEnd();
if(/<\/script/i.test(pyt)){
  console.error('O .pyt contém "</script" — isso fecharia o bloco no HTML. Reescreva esse trecho.');
  process.exit(1);
}
const html = readFileSync(htmlPath, 'utf8');
const re = /(<script type="text\/plain" id="pytSource">\n)[\s\S]*?(<\/script>)/;
if(!re.test(html)){
  console.error('Bloco <script type="text/plain" id="pytSource"> não encontrado no index.html.');
  process.exit(1);
}
const out = html.replace(re, (_, open, close) => open + pyt + '\n' + close);
if(out === html){ console.log('index.html já estava com a toolbox atual.'); }
else { writeFileSync(htmlPath, out); console.log('Toolbox atualizada dentro do index.html.'); }
