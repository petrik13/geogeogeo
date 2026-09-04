# -*- coding: utf-8 -*-
"""
GeoGeoGeo — ArcGIS Python Toolbox
==================================

Ferramenta para o ArcGIS Pro que lê um modelo OMT-G exportado do GeoGeoGeo
(o arquivo .json que o botão "Exportar para > JSON" da aplicação gera) e cria
o esquema correspondente em uma File Geodatabase: feature dataset, classes/
tabelas com seus campos, classes de relacionamento e — quando o modelo tem
relações "dentro" ou agregações espaciais — um dataset de Topologia com as
regras de cobertura correspondentes.

Diferente de um script avulso, esta é uma ferramenta de geoprocessamento de
verdade: adicione este arquivo uma vez ao ArcGIS Pro (Catalog > Toolboxes >
Add Toolbox, escolha este .pyt) e ela passa a aparecer na caixa de
ferramentas, com uma interface de parâmetros nativa, pronta para reusar em
qualquer modelo novo — sem precisar gerar/colar um script a cada vez.

Como usar no ArcGIS Pro:
  1. Painel Catalog > botão direito em "Toolboxes" > Add Toolbox > selecione
     este arquivo (geogeogeo_toolbox.pyt).
  2. Abra a ferramenta "Criar Geodatabase (OMT-G)" dentro dela.
  3. Informe o arquivo .json do modelo, a pasta de destino e o nome da
     geodatabase a criar (ou reaproveitar, se já existir). Execute.

Formato de entrada esperado (mesmo formato do botão "Exportar para > JSON"
do GeoGeoGeo, ou seja, o objeto "state" interno da aplicação):
    {
      "meta": {"name": str, "srid": int, "workspaceName": str, ...},
      "classes": [
        {"id": str, "name": str, "kind": "geo"|"conventional",
         "primitive": "point"|"node"|"line"|"arc"|"polygon"|"isoline"|
                      "tin"|"tessellation"|"sample"|"partition"|"complex"|null,
         "complexKind": "multipoint"|"multiline"|"multipolygon"|"collection"|null,
         "attributes": [{"name": str, "type": "text"|"integer"|"double"|
                          "date"|"datetime"|"boolean"|"blob", "pk": bool,
                          "nullable": bool}, ...]},
        ...
      ],
      "relationships": [
        {"id": str, "type": "association"|"generalization"|"aggregation"|
                     "network"|"spatial", "sourceId": str, "targetId": str,
         "name": str,
         # association:
         "cardSource": "1"|"0..1"|"0..*"|"1..*", "cardTarget": same,
         # generalization:
         "total": bool, "disjoint": bool,
         # aggregation:
         "cardSource": ..., "cardTarget": ..., "spatialControl": bool,
         # network:
         "directed": bool,
         # spatial:
         "topoRule": "touches"|"dentro"|"disjunto"|"em_frente"|"proximo"|
                      "sobrepoe"|"cruza"},
        ...
      ]
    }

Limitações conhecidas (as mesmas do exportador de script arcpy do
GeoGeoGeo, documentadas ali com a mesma justificativa): o vocabulário de
regras de topologia do ArcGIS é construído quase todo em torno de PROIBIR
sobreposição/interseção ou EXIGIR cobertura — não existe regra para "deve
tocar", "deve sobrepor" ou "deve cruzar". Por isso só os predicados OMT-G
"dentro" (nas combinações área-área, linha-área e ponto-área) e "disjunto"
(área-área) geram uma regra real de topologia; os demais entram apenas como
mensagem informativa na execução, não como regra criada. Regras gerais de
qualidade geométrica (uma classe não sobrepor a si mesma etc.) também não
são aplicadas automaticamente — dependem de decisão de negócio por classe —
e só aparecem como sugestão nas mensagens da ferramenta.
"""

import arcpy
import json
import os
import re
import unicodedata


# ============================================================
# Helpers de identificador — replicam sqlIdent()/pascalIdent() do app.js
# ============================================================

def sql_ident(s):
    s = (s or '').strip().lower()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r'[^a-z0-9_]+', '_', s)
    s = s.strip('_')
    s = re.sub(r'^(\d)', r'c\1', s)
    return s or 'sem_nome'


def pascal_ident(s):
    s = re.sub(r'[^a-zA-Z0-9]+', ' ', (s or '').strip())
    words = [w for w in s.split(' ') if w]
    return ''.join(w[0].upper() + w[1:] for w in words) or 'SemNome'


# ============================================================
# Geometria — replicam geomKind()/geomCategory()/arcpyFieldType()/
# arcpyGeomType() do app.js
# ============================================================

GEOM_MAP = {
    'point':        {'esri': 'esriGeometryPoint',    'approx': False},
    'node':         {'esri': 'esriGeometryPoint',    'approx': False},
    'line':         {'esri': 'esriGeometryPolyline', 'approx': False},
    'arc':          {'esri': 'esriGeometryPolyline', 'approx': False},
    'polygon':      {'esri': 'esriGeometryPolygon',  'approx': False},
    'isoline':      {'esri': 'esriGeometryPolyline', 'approx': True},
    'tin':          {'esri': 'esriGeometryPolygon',  'approx': True},
    'tessellation': {'esri': 'esriGeometryPolygon',  'approx': True},
    'sample':       {'esri': 'esriGeometryPoint',    'approx': True},
    'partition':    {'esri': 'esriGeometryPolygon',  'approx': True},
}
COMPLEX_MAP = {
    'multipoint':   {'esri': 'esriGeometryMultipoint', 'approx': False},
    'multiline':    {'esri': 'esriGeometryPolyline',   'approx': False},
    'multipolygon': {'esri': 'esriGeometryPolygon',    'approx': False},
    'collection':   {'esri': 'esriGeometryBag',        'approx': False},
}
ARCPY_FIELD_TYPE = {'text': 'TEXT', 'integer': 'LONG', 'double': 'DOUBLE', 'date': 'DATE',
                     'datetime': 'DATE', 'boolean': 'SHORT', 'blob': 'BLOB'}
ARCPY_GEOM_TYPE = {'esriGeometryPoint': 'POINT', 'esriGeometryMultipoint': 'MULTIPOINT',
                    'esriGeometryPolyline': 'POLYLINE', 'esriGeometryPolygon': 'POLYGON'}

TOPO_RULE_LABEL = {
    'touches': 'toca (touches)',
    'dentro': 'está dentro de (dentro)',
    'disjunto': 'é disjunto de (disjunto)',
    'em_frente': 'está em frente a (em frente)',
    'proximo': 'está próximo de (próximo)',
    'sobrepoe': 'sobrepõe (sobrepõe)',
    'cruza': 'cruza (cruza)',
}


def geom_kind(c):
    if c.get('kind') != 'geo' or not c.get('primitive'):
        return None
    if c.get('primitive') == 'complex':
        return COMPLEX_MAP.get(c.get('complexKind') or 'multipolygon')
    return GEOM_MAP.get(c.get('primitive'))


def geom_category(c):
    gk = geom_kind(c)
    if not gk:
        return None
    if gk['esri'] == 'esriGeometryPolygon':
        return 'area'
    if gk['esri'] == 'esriGeometryPolyline':
        return 'line'
    if gk['esri'] in ('esriGeometryPoint', 'esriGeometryMultipoint'):
        return 'point'
    return None


def arcpy_field_type(t):
    return ARCPY_FIELD_TYPE.get(t, 'TEXT')


def arcpy_geom_type(gk):
    if not gk:
        return None
    return ARCPY_GEOM_TYPE.get(gk['esri'])


def topology_rule_for(predicate, cat_a, cat_b):
    """Mesma tabela, com a mesma justificativa, de topologyRuleFor() no
    app.js — só 'dentro' e 'disjunto' têm regra real de ArcGIS mapeada,
    verificada contra a referência oficial da ferramenta Add Rule To
    Topology, não adivinhada."""
    if predicate == 'dentro':
        if cat_a == 'area' and cat_b == 'area':
            return {'rule': 'Must Be Covered By Feature Class Of (Area-Area)'}
        if cat_a == 'line' and cat_b == 'area':
            return {'rule': 'Must Be Inside (Line-Area)'}
        if cat_a == 'point' and cat_b == 'area':
            return {'rule': 'Must Be Properly Inside (Point-Area)'}
        return None
    if predicate == 'disjunto':
        if cat_a == 'area' and cat_b == 'area':
            return {'rule': 'Must Not Overlap With (Area-Area)',
                    'caveat': 'permite fronteiras se tocando — não é disjunção estrita'}
        return None
    return None


def general_topology_suggestion(cat):
    if cat == 'area':
        return 'Must Not Overlap (Area)'
    if cat == 'line':
        return 'Must Not Self-Intersect (Line) / Must Not Self-Overlap (Line)'
    return None


def pk_field_name(c):
    """Nome do campo a usar como origin_primary_key de uma classe de
    relacionamento — o atributo marcado como PK no modelo (normalmente
    "id"), não o OBJECTID interno do arcpy. O OBJECTID só é atribuído pelo
    banco na hora da inserção, então não dá pra popular o campo de FK da
    classe dependente com ele antes de carregar os dados; a chave definida
    no modelo é estável e é o que já vem preenchido nos seus dados."""
    pk = next((a for a in (c.get('attributes') or []) if a.get('pk')), None)
    return sql_ident(pk['name']) if pk else 'id'


# ============================================================
# Campos derivados de relacionamentos — replicam computeExportFields()/
# associationPlan() do app.js
# ============================================================

def association_plan(r):
    def many(v):
        return v in ('0..*', '1..*')

    def one(v):
        return v in ('1', '0..1')

    cs, ct = r.get('cardSource'), r.get('cardTarget')
    if many(cs) and one(ct):
        return {'mode': 'fk', 'fkOn': r.get('sourceId'), 'refTo': r.get('targetId')}
    if one(cs) and many(ct):
        return {'mode': 'fk', 'fkOn': r.get('targetId'), 'refTo': r.get('sourceId')}
    if one(cs) and one(ct):
        return {'mode': 'fk', 'fkOn': r.get('sourceId'), 'refTo': r.get('targetId')}
    return {'mode': 'junction'}


def compute_export_fields(c, class_by_id, relationships):
    fields = []
    for a in c.get('attributes') or []:
        fields.append({'name': sql_ident(a.get('name')), 'type': a.get('type'),
                        'nullable': a.get('nullable'), 'fkTable': None})
    for r in relationships:
        rtype = r.get('type')
        if rtype == 'generalization' and r.get('sourceId') == c['id']:
            sup = class_by_id.get(r.get('targetId'))
            if sup:
                fields.append({'name': sql_ident(sup['name']) + '_id', 'type': 'integer',
                                'nullable': False, 'fkTable': sql_ident(sup['name'])})
        if rtype == 'aggregation' and r.get('targetId') == c['id']:
            whole = class_by_id.get(r.get('sourceId'))
            if whole:
                nullable = r.get('cardTarget') in ('0..*', '0..1')
                fields.append({'name': sql_ident(whole['name']) + '_id', 'type': 'integer',
                                'nullable': nullable, 'fkTable': sql_ident(whole['name'])})
        if rtype == 'network' and r.get('targetId') == c['id']:
            node = class_by_id.get(r.get('sourceId'))
            if node:
                base = sql_ident(node['name'])
                fields.append({'name': base + '_no_origem_id', 'type': 'integer',
                                'nullable': True, 'fkTable': base})
                fields.append({'name': base + '_no_destino_id', 'type': 'integer',
                                'nullable': True, 'fkTable': base})
        if rtype == 'association':
            plan = association_plan(r)
            if plan['mode'] == 'fk' and plan['fkOn'] == c['id']:
                ref_class = class_by_id.get(plan['refTo'])
                if ref_class:
                    own_card = r.get('cardSource') if plan['fkOn'] == r.get('sourceId') else r.get('cardTarget')
                    nullable = own_card in ('0..*', '0..1')
                    fields.append({'name': sql_ident(ref_class['name']) + '_id', 'type': 'integer',
                                    'nullable': nullable, 'fkTable': sql_ident(ref_class['name'])})
    return fields


# ============================================================
# Toolbox
# ============================================================

class Toolbox:
    def __init__(self):
        self.label = 'GeoGeoGeo'
        self.alias = 'geogeogeo'
        self.tools = [CriarGeodatabaseOMTG]


class CriarGeodatabaseOMTG:
    def __init__(self):
        self.label = 'Criar Geodatabase (OMT-G)'
        self.description = (
            'Lê um modelo OMT-G exportado do GeoGeoGeo (.json) e cria o esquema '
            'correspondente — feature dataset, classes/tabelas, classes de '
            'relacionamento e topologia (quando aplicável) — em uma File Geodatabase.'
        )
        self.category = 'GeoGeoGeo'

    def getParameterInfo(self):
        p_json = arcpy.Parameter(
            displayName='Modelo OMT-G (.json exportado do GeoGeoGeo)',
            name='in_json',
            datatype='DEFile',
            parameterType='Required',
            direction='Input')
        p_json.filter.list = ['json']

        p_folder = arcpy.Parameter(
            displayName='Pasta de destino',
            name='out_folder',
            datatype='DEFolder',
            parameterType='Required',
            direction='Input')

        p_name = arcpy.Parameter(
            displayName='Nome da geodatabase (sem .gdb)',
            name='out_name',
            datatype='GPString',
            parameterType='Required',
            direction='Input')
        p_name.value = 'ModeloOMTG'

        p_out_gdb = arcpy.Parameter(
            displayName='Geodatabase criada',
            name='out_gdb',
            datatype='DEWorkspace',
            parameterType='Derived',
            direction='Output')

        return [p_json, p_folder, p_name, p_out_gdb]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        in_json = parameters[0].valueAsText
        out_folder = parameters[1].valueAsText
        out_name = parameters[2].valueAsText

        with open(in_json, 'r', encoding='utf-8') as f:
            model = json.load(f)

        classes = model.get('classes')
        relationships = model.get('relationships')
        if classes is None or relationships is None:
            raise arcpy.ExecuteError(
                "O arquivo JSON não parece ser um modelo exportado do GeoGeoGeo "
                "(faltam as chaves 'classes' e/ou 'relationships').")

        meta = model.get('meta') or {}
        class_by_id = {c['id']: c for c in classes}

        ws_name = pascal_ident(meta.get('workspaceName') or meta.get('name') or 'ModeloOMTG')
        fds_name = ws_name + '_FD'
        try:
            srid = int(meta.get('srid') or 4326)
        except (TypeError, ValueError):
            arcpy.AddWarning('SRID do modelo inválido ("%s"); usando 4326 (WGS 84).' % meta.get('srid'))
            srid = 4326

        gdb_name = out_name if out_name.lower().endswith('.gdb') else out_name + '.gdb'
        gdb_path = os.path.join(out_folder, gdb_name)

        if not arcpy.Exists(gdb_path):
            arcpy.management.CreateFileGDB(out_folder, gdb_name)
            arcpy.AddMessage('Geodatabase criada em: ' + gdb_path)
        else:
            arcpy.AddMessage('Geodatabase já existente — reaproveitando: ' + gdb_path)

        try:
            sr = arcpy.SpatialReference(srid)
        except Exception as e:
            arcpy.AddWarning('Não foi possível criar a referência espacial para o SRID %s (%s); '
                              'usando WGS 84 (4326).' % (srid, e))
            sr = arcpy.SpatialReference(4326)

        geo_classes = [c for c in classes if c.get('kind') == 'geo']
        flat_classes = [c for c in classes if c.get('kind') != 'geo']

        fds_path = None
        if geo_classes:
            fds_path = os.path.join(gdb_path, fds_name)
            if not arcpy.Exists(fds_path):
                arcpy.management.CreateFeatureDataset(gdb_path, fds_name, sr)

        def class_path(c):
            gt = arcpy_geom_type(geom_kind(c))
            name = pascal_ident(c['name'])
            if gt and fds_path:
                return os.path.join(fds_path, name)
            return os.path.join(gdb_path, name)

        # ---- Classes e tabelas ----
        arcpy.AddMessage('---- Classes e tabelas ----')
        for c in list(geo_classes) + list(flat_classes):
            gk = geom_kind(c)
            gt = arcpy_geom_type(gk)
            name = pascal_ident(c['name'])
            if gt:
                if gk.get('approx'):
                    arcpy.AddWarning(
                        '%s: primitiva conceitual "%s" não tem equivalente vetorial direto no '
                        'geodatabase; criada como %s (revise o armazenamento).'
                        % (c['name'], c.get('primitive'), gt))
                arcpy.management.CreateFeatureclass(fds_path, name, gt, spatial_reference=sr)
                target = os.path.join(fds_path, name)
            else:
                if c.get('kind') == 'geo':
                    arcpy.AddWarning(
                        '%s: primitiva "%s" não tem equivalente direto de geometria no arcpy; '
                        'criada como tabela — adicione a geometria manualmente se necessário.'
                        % (c['name'], c.get('primitive')))
                arcpy.management.CreateTable(gdb_path, name)
                target = os.path.join(gdb_path, name)
            for fdef in compute_export_fields(c, class_by_id, relationships):
                t = arcpy_field_type(fdef['type'])
                kwargs = {}
                if t == 'TEXT':
                    kwargs['field_length'] = 255
                if fdef.get('nullable') is False:
                    kwargs['field_is_nullable'] = 'NON_NULLABLE'
                arcpy.management.AddField(target, fdef['name'], t, **kwargs)
            arcpy.AddMessage('  ' + c['name'] + ' -> ' + target)

        # ---- Classes de relacionamento ----
        arcpy.AddMessage('---- Classes de relacionamento ----')

        def create_rel_class(origin, dest, out_rel_name, cardinality, is_composite,
                              fwd_label, bwd_label, fk_field):
            kwargs = dict(
                relationship_type='COMPOSITE' if is_composite else 'SIMPLE',
                forward_label=fwd_label,
                backward_label=bwd_label,
                message_direction='NONE',
                cardinality=cardinality,
                attributed='NONE',
                # com FK explícito, usa a chave definida no modelo (ex.: "id"),
                # não o OBJECTID interno do arcpy — ele só existe depois da
                # inserção, então não dá pra preencher a FK com ele antes de
                # carregar os dados. Sem FK (associação N:N / tabela de
                # junção), o arcpy gerencia tudo internamente por OBJECTID.
                origin_primary_key=(pk_field_name(origin) if fk_field else 'OBJECTID'))
            if fk_field:
                kwargs['origin_foreign_key'] = fk_field
            arcpy.management.CreateRelationshipClass(
                class_path(origin), class_path(dest),
                os.path.join(gdb_path, out_rel_name), **kwargs)
            arcpy.AddMessage('  ' + out_rel_name)

        # candidatos de cobertura para a Topologia: relação espacial "dentro"
        # OU agregação entre duas classes que têm geometria (agregação
        # espacial) — mesma lógica de buildArcpyScript()/buildEsriXML().
        coverage_candidates = []
        for r in relationships:
            a = class_by_id.get(r.get('sourceId'))
            b = class_by_id.get(r.get('targetId'))
            if not a or not b:
                continue
            rtype = r.get('type')
            if rtype == 'generalization':
                create_rel_class(b, a, pascal_ident(a['name']) + '_Generaliza_' + pascal_ident(b['name']),
                                  'ONE_TO_ONE', True, 'é especializada por', 'especializa',
                                  sql_ident(b['name']) + '_id')
            elif rtype == 'aggregation':
                create_rel_class(a, b, pascal_ident(a['name']) + '_Agrega_' + pascal_ident(b['name']),
                                  'ONE_TO_MANY', True, 'agrega', 'é parte de',
                                  sql_ident(a['name']) + '_id')
                if geom_kind(a) and geom_kind(b):
                    coverage_candidates.append({
                        'origin': b, 'dest': a, 'predicate': 'dentro',
                        'label': b['name'] + ' contido em ' + a['name'] + ' (agregação espacial)'})
            elif rtype == 'network':
                create_rel_class(a, b, pascal_ident(a['name']) + '_ConectaOrigem_' + pascal_ident(b['name']),
                                  'ONE_TO_MANY', False, 'é origem de', 'parte de (nó origem)',
                                  sql_ident(a['name']) + '_no_origem_id')
                create_rel_class(a, b, pascal_ident(a['name']) + '_ConectaDestino_' + pascal_ident(b['name']),
                                  'ONE_TO_MANY', False, 'é destino de', 'parte de (nó destino)',
                                  sql_ident(a['name']) + '_no_destino_id')
            elif rtype == 'association':
                plan = association_plan(r)
                if plan['mode'] == 'junction':
                    create_rel_class(a, b, pascal_ident(a['name']) + '_' + pascal_ident(b['name']),
                                      'MANY_TO_MANY', False,
                                      r.get('name') or 'relaciona-se com',
                                      r.get('name') or 'relaciona-se com', None)
                else:
                    fk_class = class_by_id.get(plan['fkOn'])
                    ref_class = class_by_id.get(plan['refTo'])
                    if fk_class and ref_class:
                        create_rel_class(ref_class, fk_class,
                                          pascal_ident(ref_class['name']) + '_' + pascal_ident(fk_class['name']),
                                          'ONE_TO_MANY', False,
                                          r.get('name') or 'relaciona-se com',
                                          r.get('name') or 'relaciona-se com',
                                          sql_ident(ref_class['name']) + '_id')
            elif rtype == 'spatial':
                topo_rule = r.get('topoRule')
                label = a['name'] + ' ' + TOPO_RULE_LABEL.get(topo_rule, topo_rule or '') + ' ' + b['name']
                if geom_kind(a) and geom_kind(b):
                    coverage_candidates.append({'origin': a, 'dest': b, 'predicate': topo_rule, 'label': label})
                else:
                    coverage_candidates.append({'origin': a, 'dest': b, 'predicate': topo_rule,
                                                 'label': label, 'noGeom': True})

        # ---- Topologia ----
        if fds_path and coverage_candidates:
            arcpy.AddMessage('---- Topologia ----')
            arcpy.AddMessage(
                'O vocabulário de regras do ArcGIS é quase todo negativo/de cobertura '
                '("não pode sobrepor", "deve estar coberto por/dentro de"); não existe regra '
                'para "deve tocar", "deve sobrepor" ou "deve cruzar" — esses predicados aparecem '
                'só como aviso abaixo, não como regra criada.')
            topo_name = fds_name + '_Topology'
            topo_path = os.path.join(fds_path, topo_name)
            arcpy.management.CreateTopology(fds_path, topo_name)
            added = set()

            def add_fc(c):
                nm = pascal_ident(c['name'])
                if nm not in added:
                    added.add(nm)
                    arcpy.management.AddFeatureClassToTopology(topo_path, os.path.join(fds_path, nm), 1, 1)

            for cand in coverage_candidates:
                if not cand.get('noGeom'):
                    add_fc(cand['origin'])
                    add_fc(cand['dest'])

            for cand in coverage_candidates:
                if cand.get('noGeom'):
                    arcpy.AddWarning(cand['label'] + ' — uma das classes não tem geometria; sem regra de topologia.')
                    continue
                cat_a = geom_category(cand['origin'])
                cat_b = geom_category(cand['dest'])
                mapped = topology_rule_for(cand['predicate'], cat_a, cat_b)
                if mapped:
                    arcpy.management.AddRuleToTopology(
                        topo_path, mapped['rule'],
                        os.path.join(fds_path, pascal_ident(cand['origin']['name'])), '',
                        os.path.join(fds_path, pascal_ident(cand['dest']['name'])), '')
                    msg = 'Regra de topologia: ' + cand['label']
                    if mapped.get('caveat'):
                        msg += ' (' + mapped['caveat'] + ')'
                    arcpy.AddMessage(msg)
                else:
                    arcpy.AddWarning(cand['label'] + ' — predicado sem regra de topologia equivalente no ArcGIS.')

            arcpy.management.ValidateTopology(topo_path, 'Full_Extent')

            # sugestões de qualidade geométrica — nunca aplicadas automaticamente,
            # é decisão de negócio por classe (mesmo raciocínio de
            # generalTopologyRules() no app.js)
            area_line = [c for c in geo_classes if geom_category(c) in ('area', 'line')]
            if area_line:
                arcpy.AddMessage(
                    'Sugestão (não aplicada automaticamente — avalie caso a caso na aba '
                    'Topologia do ArcGIS Pro): ' + ', '.join(
                        c['name'] + ' (' + general_topology_suggestion(geom_category(c)) + ')'
                        for c in area_line))

        parameters[3].value = gdb_path
        arcpy.AddMessage('Esquema criado com sucesso em: ' + gdb_path)
