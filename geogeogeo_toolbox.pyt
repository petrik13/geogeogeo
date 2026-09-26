# -*- coding: utf-8 -*-
"""
GeoGeoGeo — criação de File Geodatabase a partir do JSON do modelo lógico.

Esta toolbox consome o arquivo gerado pelo GeoGeoGeo em
"Migrar > Para o Físico (GDB)" (ou pelo menu do app). O JSON descreve O QUE
criar; aqui é onde isso vira geodatabase.

Escopo, conforme as decisões registradas em mapeamento-logico-para-gdb.md:
  - Cria a File GDB, domínios, feature datasets, tables/feature classes,
    campos, índices, relationship classes, topologias e attribute rules.
  - NÃO cria Network Dataset: o JSON declara a intenção de rede
    (status "declaredOnly") porque criar exigiria a extensão Network Analyst
    e a rede nasceria sem conectividade, custos nem direcionalidade. As
    feature classes participantes e o feature dataset que as agrupa são
    criados normalmente.
  - TIN e Raster Dataset vêm marcados como "placeholder": dependem de dados
    de entrada e não são criados vazios. São reportados, não criados.

Nada aqui aborta a execução inteira por causa de um item: cada passo que
falha vira aviso e o resto continua, com um resumo no fim.
"""

import io
import os
import json
import arcpy


# --------------------------------------------------------------------------
# Toolbox
# --------------------------------------------------------------------------
class Toolbox(object):
    def __init__(self):
        self.label = "GeoGeoGeo"
        self.alias = "geogeogeo"
        self.tools = [CriarGeodatabase]


class CriarGeodatabase(object):
    def __init__(self):
        self.label = "Criar Geodatabase a partir do modelo"
        self.description = (
            u"Le o JSON exportado pelo GeoGeoGeo (modelo logico) e cria a "
            u"File Geodatabase correspondente: dominios, datasets, campos, "
            u"relationship classes, topologias e attribute rules."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        p_json = arcpy.Parameter(
            displayName=u"JSON do modelo (gerado pelo GeoGeoGeo)",
            name="in_json", datatype="DEFile", parameterType="Required", direction="Input")
        p_json.filter.list = ["json"]

        p_folder = arcpy.Parameter(
            displayName=u"Pasta de saida",
            name="out_folder", datatype="DEFolder", parameterType="Required", direction="Input")

        p_name = arcpy.Parameter(
            displayName=u"Nome da geodatabase (vazio = usa o nome do modelo)",
            name="gdb_name", datatype="GPString", parameterType="Optional", direction="Input")

        p_rules = arcpy.Parameter(
            displayName=u"Criar attribute rules (unicidade, calculo, integridade)",
            name="do_rules", datatype="GPBoolean", parameterType="Optional", direction="Input")
        p_rules.value = True

        p_topo = arcpy.Parameter(
            displayName=u"Criar topologias",
            name="do_topology", datatype="GPBoolean", parameterType="Optional", direction="Input")
        p_topo.value = True

        p_meta = arcpy.Parameter(
            displayName=u"Preencher metadados (descricao de cada item a partir do modelo OMT-G)",
            name="do_metadata", datatype="GPBoolean", parameterType="Optional", direction="Input")
        p_meta.value = True

        p_report = arcpy.Parameter(
            displayName=u"Schema Report da geodatabase criada (vazio = nao gerar)",
            name="report_formats", datatype="GPString", parameterType="Optional",
            direction="Input", multiValue=True)
        p_report.filter.type = "ValueList"
        p_report.filter.list = ["HTML", "PDF", "XLSX", "JSON"]
        p_report.value = ["HTML", "XLSX"]

        p_out = arcpy.Parameter(
            displayName=u"Geodatabase criada",
            name="out_gdb", datatype="DEWorkspace", parameterType="Derived", direction="Output")

        return [p_json, p_folder, p_name, p_rules, p_topo, p_meta, p_report, p_out]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        json_path = parameters[0].valueAsText
        out_folder = parameters[1].valueAsText
        gdb_name = parameters[2].valueAsText
        do_rules = parameters[3].value
        do_topology = parameters[4].value
        do_metadata = parameters[5].value
        fmt_text = parameters[6].valueAsText or ""
        report_formats = [f.strip().strip("'").upper() for f in fmt_text.split(";") if f.strip()]

        builder = GdbBuilder(json_path, out_folder, gdb_name, do_rules, do_topology,
                             do_metadata is not False, report_formats)
        gdb = builder.run()
        arcpy.SetParameterAsText(7, gdb)


# --------------------------------------------------------------------------
# Construcao
# --------------------------------------------------------------------------
FIELD_TYPES = set(["TEXT", "SHORT", "LONG", "FLOAT", "DOUBLE", "DATE", "BLOB", "GUID", "RASTER"])
GEOMETRY_TYPES = set(["POINT", "MULTIPOINT", "POLYLINE", "POLYGON"])
REL_TYPES = set(["SIMPLE", "COMPOSITE"])
CARDINALITIES = set(["ONE_TO_ONE", "ONE_TO_MANY", "MANY_TO_MANY"])

# Contadores do resumo final, na ordem em que aparecem.
SUMMARY_ITEMS = [
    ("domains", u"dominios"), ("featureDatasets", u"feature datasets"),
    ("datasets", u"datasets"), ("fields", u"campos"),
    ("indexes", u"indices"), ("relationshipClasses", u"relationship classes"),
    ("topologies", u"topologias"), ("rules", u"attribute rules"),
    ("attachments", u"classes com anexos"),
    ("editorTracking", u"controle de edicoes"),
    ("metadata", u"itens com metadados"),
]


class GdbBuilder(object):

    def __init__(self, json_path, out_folder, gdb_name, do_rules, do_topology, do_metadata=True,
                 report_formats=None):
        self.json_path = json_path
        self.out_folder = out_folder
        self.gdb_name = gdb_name
        self.do_rules = bool(do_rules)
        self.do_topology = bool(do_topology)
        self.do_metadata = bool(do_metadata)
        self.report_formats = [f for f in (report_formats or []) if f in ("HTML", "PDF", "XLSX", "JSON")]
        self.doc = None
        self.gdb = None
        self.created = dict((key, 0) for key, _ in SUMMARY_ITEMS)
        self.warnings = []   # tudo que foi avisado
        self.failures = []   # passos que falharam (subconjunto dos avisos)
        self.skipped = []
        self._bad_srids = set()
        # nome do dataset -> caminho completo na gdb
        self.paths = {}

    # -- utilitarios ------------------------------------------------------
    def info(self, msg):
        arcpy.AddMessage(msg)

    def warn(self, msg):
        arcpy.AddWarning(msg)
        self.warnings.append(msg)

    def field_type(self, table, field):
        try:
            for f in arcpy.ListFields(table):
                if f.name.lower() == (field or "").lower():
                    return f.type
        except Exception:
            return "?"
        return None

    def step(self, what, fn):
        """Executa um passo isolando a falha: um item quebrado nao derruba o resto."""
        try:
            fn()
            return True
        except Exception as exc:
            msg = u"%s: %s" % (what, exc)
            self.failures.append(msg)
            self.warn(msg)
            return False

    def spatial_ref(self, spec):
        if not spec:
            return None
        wkid = spec.get("wkid")
        if not wkid:
            return None
        try:
            return arcpy.SpatialReference(int(wkid))
        except Exception:
            if wkid not in self._bad_srids:
                self._bad_srids.add(wkid)
                self.warn(u"SRID %s nao existe nesta instalacao do ArcGIS; os dados foram "
                          u"criados em 4326 (WGS 84). Corrija o SRID no modelo e gere de novo." % wkid)
            return arcpy.SpatialReference(4326)

    # -- execucao ---------------------------------------------------------
    def run(self):
        self.load()
        self.create_gdb()
        self.create_domains()
        self.create_feature_datasets()
        self.create_datasets()
        self.create_indexes()
        self.create_relationship_classes()
        if self.do_topology:
            self.create_topologies()
        if self.do_rules:
            self.create_attribute_rules()
        if self.do_metadata:
            self.write_metadata()
        if self.report_formats:
            self.schema_report()
        self.report()
        return self.gdb

    def load(self):
        # utf-8 explicito: no Windows o padrao e cp1252 e os acentos do JSON
        # viravam "Ã§Ã£o" nas mensagens.
        with io.open(self.json_path, "r", encoding="utf-8-sig") as fh:
            self.doc = json.load(fh)
        version = self.doc.get("formatVersion")
        if version != 1:
            self.warn(u"formatVersion %s nao e a esperada (1). Seguindo mesmo assim." % version)
        gen = self.doc.get("generator")
        src = (self.doc.get("source") or {}).get("model")
        self.info(u"Modelo: %s (gerado por %s)" % (src, gen))

    def create_gdb(self):
        ws = self.doc.get("workspace") or {}
        name = self.gdb_name or ws.get("name") or "ModeloOMTG"
        if not name.lower().endswith(".gdb"):
            name = name + ".gdb"
        target = os.path.join(self.out_folder, name)
        if arcpy.Exists(target):
            raise arcpy.ExecuteError(
                u"Ja existe %s. Apague, renomeie, ou informe outro nome." % target)
        arcpy.management.CreateFileGDB(self.out_folder, name)
        self.gdb = target
        self.info(u"Geodatabase criada: %s" % target)

    # -- dominios ---------------------------------------------------------
    def create_domains(self):
        for dom in self.doc.get("domains") or []:
            name = dom.get("name")
            if not name:
                continue

            def make(dom=dom, name=name):
                ftype = dom.get("fieldType") or "TEXT"
                if ftype not in FIELD_TYPES:
                    ftype = "TEXT"
                arcpy.management.CreateDomain(
                    self.gdb, name, dom.get("description") or name, ftype,
                    "CODED" if (dom.get("type") or "codedValue") == "codedValue" else "RANGE")
                if (dom.get("type") or "codedValue") == "range":
                    arcpy.management.SetValueForRangeDomain(
                        self.gdb, name, dom.get("min"), dom.get("max"))
                for pair in dom.get("values") or []:
                    arcpy.management.AddCodedValueToDomain(
                        self.gdb, name, pair.get("code"), pair.get("name"))
                self.created["domains"] += 1

            self.step(u"Dominio '%s'" % name, make)

    # -- feature datasets -------------------------------------------------
    def create_feature_datasets(self):
        for fd in self.doc.get("featureDatasets") or []:
            name = fd.get("name")
            if not name:
                continue

            def make(fd=fd, name=name):
                sr = self.spatial_ref(fd.get("spatialReference")) or self.default_sr()
                arcpy.management.CreateFeatureDataset(self.gdb, name, sr)
                self.created["featureDatasets"] += 1

            self.step(u"Feature dataset '%s'" % name, make)

    def default_sr(self):
        return self.spatial_ref((self.doc.get("workspace") or {}).get("spatialReference")) \
            or arcpy.SpatialReference(4326)

    def dataset_home(self, name):
        """Se o dataset pertence a um feature dataset, e la que ele nasce."""
        for fd in self.doc.get("featureDatasets") or []:
            if name in (fd.get("items") or []):
                return os.path.join(self.gdb, fd.get("name"))
        return self.gdb

    # -- datasets e campos ------------------------------------------------
    def create_datasets(self):
        for ds in self.doc.get("datasets") or []:
            name = ds.get("name")
            kind = ds.get("kind")
            if not name:
                continue

            # TIN/Raster/LAS dependem de dados de entrada — reportar, nao criar.
            if ds.get("status") == "placeholder" or kind in ("tinDataset", "rasterDataset", "lasDataset"):
                self.skipped.append(
                    u"%s (%s): nao criado — depende de dados de entrada. %s"
                    % (name, kind, " ".join(ds.get("notes") or [])))
                continue

            home = self.dataset_home(name)

            def make(ds=ds, name=name, kind=kind, home=home):
                if kind == "featureClass":
                    geom = (ds.get("geometryType") or "POINT").upper()
                    if geom not in GEOMETRY_TYPES:
                        self.warn(u"%s: geometria '%s' desconhecida; usando POINT." % (name, geom))
                        geom = "POINT"
                    # dentro de um feature dataset o SR e o do dataset
                    sr = None if home != self.gdb else (
                        self.spatial_ref(ds.get("spatialReference")) or self.default_sr())
                    has_m = "ENABLED" if ds.get("hasM") else "DISABLED"
                    has_z = "ENABLED" if ds.get("hasZ") else "DISABLED"
                    arcpy.management.CreateFeatureclass(
                        home, name, geom, None, has_m, has_z, sr)
                else:
                    arcpy.management.CreateTable(home, name)
                self.paths[name] = os.path.join(home, name)
                self.created["datasets"] += 1
                if ds.get("alias"):
                    try:
                        arcpy.management.AlterAliasName(self.paths[name], ds.get("alias"))
                    except Exception:
                        pass

            if self.step(u"Dataset '%s'" % name, make):
                self.add_fields(ds)
                self.add_globalid(ds)
                self.add_attachments(ds)
                self.add_editor_tracking(ds)

    def add_fields(self, ds):
        name = ds.get("name")
        table = self.paths.get(name)
        if not table:
            return
        for f in ds.get("fields") or []:
            fname = f.get("name")
            if not fname:
                continue

            def make(f=f, fname=fname, table=table, name=name):
                ftype = (f.get("type") or "TEXT").upper()
                if ftype not in FIELD_TYPES:
                    self.warn(u"%s.%s: tipo '%s' desconhecido; usando TEXT." % (name, fname, ftype))
                    ftype = "TEXT"
                arcpy.management.AddField(
                    table, fname, ftype,
                    f.get("precision"), f.get("scale"), f.get("length"),
                    f.get("alias") or fname,
                    "NULLABLE" if f.get("nullable", True) else "NON_NULLABLE",
                    "NON_REQUIRED",
                    f.get("domain"))
                self.created["fields"] += 1
                default = f.get("default")
                if default not in (None, ""):
                    arcpy.management.AssignDefaultToField(table, fname, default)

            self.step(u"Campo '%s.%s'" % (name, fname), make)

    def add_globalid(self, ds):
        # GlobalID existe so para as attribute rules (exigencia do ArcGIS,
        # ERROR 002710). Sem regras, nao cria.
        if not self.do_rules:
            return
        if "GLOBALID" not in [s.upper() for s in (ds.get("systemFields") or [])]:
            return
        table = self.paths.get(ds.get("name"))
        if not table:
            return
        self.step(u"GlobalID em '%s'" % ds.get("name"),
                  lambda: arcpy.management.AddGlobalIDs(table))

    def add_attachments(self, ds):
        """Atributo Blob do modelo logico = anexos no GDB (tabela __ATTACH)."""
        att = ds.get("attachments")
        table = self.paths.get(ds.get("name"))
        if not att or not table:
            return

        def make():
            arcpy.management.EnableAttachments(table)
            self.created["attachments"] += 1
            self.info(u"  %s: anexos habilitados (%s)." % (ds.get("name"), ", ".join(att.get("fields") or [])))

        self.step(u"Anexos em '%s'" % ds.get("name"), make)

    def add_editor_tracking(self, ds):
        """Controle de edicoes do modelo logico = Editor Tracking."""
        et = ds.get("editorTracking")
        table = self.paths.get(ds.get("name"))
        if not et or not table:
            return

        def make():
            arcpy.management.EnableEditorTracking(
                table, et.get("creatorField"), et.get("creationDateField"),
                et.get("lastEditorField"), et.get("lastEditDateField"),
                "ADD_FIELDS", et.get("recordDatesIn") or "UTC")
            self.created["editorTracking"] += 1

        self.step(u"Controle de edicoes em '%s'" % ds.get("name"), make)

    def create_indexes(self):
        for ds in self.doc.get("datasets") or []:
            table = self.paths.get(ds.get("name"))
            if not table:
                continue
            for idx in ds.get("indexes") or []:
                fields = idx.get("fields") or []
                if not fields:
                    continue

                def make(idx=idx, fields=fields, table=table):
                    # Indice unico so existe em enterprise geodatabase; em File
                    # GDB a unicidade vem da attribute rule (ver create_attribute_rules).
                    arcpy.management.AddIndex(
                        table, fields, idx.get("name"), "NON_UNIQUE", "NON_ASCENDING")
                    self.created["indexes"] += 1

                self.step(u"Indice '%s'" % idx.get("name"), make)

    # -- relationship classes ---------------------------------------------
    def create_relationship_classes(self):
        for rc in self.doc.get("relationshipClasses") or []:
            name = rc.get("name")
            origin = self.paths.get(rc.get("origin"))
            dest = self.paths.get(rc.get("destination"))
            if not name:
                continue
            if not origin or not dest:
                self.warn(u"Relationship class '%s': origem ou destino nao foi criado (%s -> %s)."
                          % (name, rc.get("origin"), rc.get("destination")))
                continue
            opk = rc.get("originPrimaryKey")
            ofk = rc.get("originForeignKey")
            card = (rc.get("cardinality") or "ONE_TO_MANY").upper()
            dpk = rc.get("destinationPrimaryKey")
            dfk = rc.get("destinationForeignKey")
            if card == "MANY_TO_MANY":
                # Num M:N nao ha chave estrangeira direta: o ArcGIS cria a
                # tabela intermediaria e origin/destination foreign key sao as
                # COLUNAS DELA. O que precisa existir sao as duas PKs.
                if not opk or not dpk:
                    self.warn(u"Relationship class '%s' (M:N) nao criada: as duas classes "
                              u"precisam de PK (origem='%s', destino='%s')." % (name, opk, dpk))
                    continue
            elif not opk or not ofk:
                self.warn(u"Relationship class '%s' nao criada: falta chave (PK='%s', FK='%s'). "
                          u"Defina a PK na classe de origem e o atributo FK no destino."
                          % (name, opk, ofk))
                continue

            if card != "MANY_TO_MANY":
                # O ArcGIS so liga PK e FK do mesmo tipo; sem isso o erro e o
                # obscuro ERROR 000800 "The value is not a member of ...".
                t_pk = self.field_type(origin, opk)
                t_fk = self.field_type(dest, ofk)
                if t_pk is None or t_fk is None:
                    self.warn(u"Relationship class '%s' nao criada: campo '%s' em '%s' ou '%s' em '%s' nao existe."
                              % (name, opk, rc.get("origin"), ofk, rc.get("destination")))
                    continue
                if t_pk != t_fk:
                    self.warn(u"Relationship class '%s' nao criada: a PK %s.%s e %s e a FK %s.%s e %s — "
                              u"precisam ter o mesmo tipo." % (name, rc.get("origin"), opk, t_pk,
                                                                rc.get("destination"), ofk, t_fk))
                    continue

            def make(rc=rc, name=name, origin=origin, dest=dest,
                     opk=opk, ofk=ofk, dpk=dpk, dfk=dfk, card=card):
                rtype = (rc.get("type") or "SIMPLE").upper()
                if rtype not in REL_TYPES:
                    rtype = "SIMPLE"
                if card not in CARDINALITIES:
                    card = "ONE_TO_MANY"
                # Atribuivel so quando o JSON pede. No M:N a tabela
                # intermediaria existe de qualquer forma; atributos proprios
                # da relacao sao modelados como classe intermediaria.
                attributed = "ATTRIBUTED" if rc.get("attributed") == "ATTRIBUTED" else "NONE"
                arcpy.management.CreateRelationshipClass(
                    origin, dest, os.path.join(self.gdb, name), rtype,
                    rc.get("forwardLabel") or name,
                    rc.get("backwardLabel") or name,
                    "NONE", card, attributed, opk, ofk, dpk, dfk)
                self.created["relationshipClasses"] += 1
                for n in rc.get("notes") or []:
                    self.info(u"  %s: %s" % (name, n))

            self.step(u"Relationship class '%s'" % name, make)

    # -- topologias --------------------------------------------------------
    def create_topologies(self):
        for topo in self.doc.get("topologies") or []:
            name = topo.get("name")
            fd_name = topo.get("featureDataset")
            if not name or not fd_name:
                continue
            fd = os.path.join(self.gdb, fd_name)
            if not arcpy.Exists(fd):
                self.warn(u"Topologia '%s': feature dataset '%s' nao existe." % (name, fd_name))
                continue

            created = []

            def make(topo=topo, name=name, fd=fd, created=created):
                tol = topo.get("clusterTolerance")
                if tol in (None, "", "default"):
                    arcpy.management.CreateTopology(fd, name)
                else:
                    arcpy.management.CreateTopology(fd, name, tol)
                created.append(os.path.join(fd, name))
                self.created["topologies"] += 1

            if not self.step(u"Topologia '%s'" % name, make):
                continue
            topo_path = created[0]

            for fc_name in topo.get("featureClasses") or []:
                fc = self.paths.get(fc_name)
                if not fc:
                    self.warn(u"Topologia '%s': '%s' nao foi criada." % (name, fc_name))
                    continue
                self.step(u"Topologia '%s' + '%s'" % (name, fc_name),
                          lambda fc=fc: arcpy.management.AddFeatureClassToTopology(topo_path, fc, 1, 1))

            for rule in topo.get("rules") or []:
                rtype = rule.get("rule")
                fc1 = self.paths.get(rule.get("origin"))
                fc2 = self.paths.get(rule.get("destination"))
                if not rtype or not fc1:
                    continue

                def add_rule(rtype=rtype, fc1=fc1, fc2=fc2, rule=rule):
                    # regra de uma classe so (Must Not Overlap, Must Not Have Gaps)
                    # nao leva a segunda feature class
                    if fc2 and fc2 != fc1:
                        arcpy.management.AddRuleToTopology(topo_path, rtype, fc1, "", fc2, "")
                    else:
                        arcpy.management.AddRuleToTopology(topo_path, rtype, fc1)

                self.step(u"Regra '%s' (%s -> %s)" % (rtype, rule.get("origin"), rule.get("destination")),
                          add_rule)

            self.step(u"Validar topologia '%s'" % name,
                      lambda: arcpy.management.ValidateTopology(topo_path))

    # -- attribute rules ---------------------------------------------------
    def create_attribute_rules(self):
        for rule in self.doc.get("attributeRules") or []:
            name = rule.get("name")
            table = self.paths.get(rule.get("dataset"))
            script = rule.get("arcade")
            if not name or not script:
                continue
            if not table:
                self.skipped.append(u"Attribute rule '%s': o dataset '%s' nao foi criado."
                                    % (name, rule.get("dataset")))
                continue
            if script.strip().startswith("//"):
                # JSON de versoes antigas do gerador marcava assim um caso sem
                # equivalente executavel; hoje isso vai para "unmapped".
                self.skipped.append(u"Attribute rule '%s': %s" % (name, script.strip()))
                continue

            def make(rule=rule, name=name, table=table, script=script):
                rtype = (rule.get("type") or "CONSTRAINT").upper()
                if rtype not in ("CALCULATION", "CONSTRAINT", "VALIDATION"):
                    rtype = "CONSTRAINT"
                triggers = [t.upper() for t in (rule.get("triggers") or ["INSERT", "UPDATE"])]
                kwargs = dict(
                    in_table=table, name=name, type=rtype, script_expression=script,
                    description=rule.get("description") or name)
                # Validation roda em lote (Validate -> Error Inspector): nao tem
                # eventos de disparo.
                if rtype == "VALIDATION":
                    kwargs["batch"] = "BATCH"
                    kwargs["error_number"] = 9998
                    # obrigatorio em validation rule: 1 (mais grave) a 5
                    kwargs["severity"] = int(rule.get("severity") or 3)
                    kwargs["error_message"] = rule.get("description") or name
                else:
                    kwargs["triggering_events"] = triggers
                # So a regra de calculo aceita campo associado; em constraint
                # o ArcGIS recusa (ERROR 002543).
                if rtype == "CALCULATION" and rule.get("field"):
                    kwargs["field"] = rule.get("field")
                if rtype == "CONSTRAINT":
                    kwargs["error_number"] = 9999
                    kwargs["error_message"] = rule.get("description") or name
                elif rtype == "CALCULATION":
                    kwargs["is_editable"] = "NONEDITABLE"
                arcpy.management.AddAttributeRule(**kwargs)
                self.created["rules"] += 1

            self.step(u"Attribute rule '%s'" % name, make)

    # -- metadados -----------------------------------------------------------
    def apply_metadata(self, label, path, meta):
        """Preenche o Item Description (titulo, resumo, descricao, tags,
        creditos) de um item. Falha isolada: vira aviso e segue."""
        if not meta or not path:
            return
        if not arcpy.Exists(path):
            return

        def make():
            from arcpy import metadata as md
            m = md.Metadata(path)
            if meta.get("title"):
                m.title = meta["title"]
            if meta.get("summary"):
                m.summary = meta["summary"]
            if meta.get("description"):
                m.description = meta["description"]
            tags = meta.get("tags") or []
            if tags:
                m.tags = u", ".join([t for t in tags if t])
            if meta.get("credits"):
                m.credits = meta["credits"]
            m.save()
            self.created["metadata"] += 1

        self.step(u"Metadados de %s" % label, make)

    # -- Schema Report (a ferramenta da propria Esri, sobre a GDB criada) ----
    def schema_report(self):
        fn = getattr(arcpy.management, "GenerateSchemaReport", None)
        if fn is None:
            self.warn(u"Schema Report nao gerado: a ferramenta Generate Schema Report "
                      u"so existe a partir do ArcGIS Pro 3.1.")
            return
        base = os.path.splitext(os.path.basename(self.gdb))[0] + "_SchemaReport"

        def make():
            fn(self.gdb, self.out_folder, base, self.report_formats)
            self.info(u"Schema Report (%s): %s" % (", ".join(self.report_formats),
                                                   os.path.join(self.out_folder, base)))

        self.step(u"Schema Report", make)

    def write_metadata(self):
        self.apply_metadata(u"'%s' (geodatabase)" % os.path.basename(self.gdb), self.gdb,
                            (self.doc.get("workspace") or {}).get("metadata"))
        for fd in self.doc.get("featureDatasets") or []:
            self.apply_metadata(u"'%s'" % fd.get("name"), os.path.join(self.gdb, fd.get("name") or ""),
                                fd.get("metadata"))
        for ds in self.doc.get("datasets") or []:
            self.apply_metadata(u"'%s'" % ds.get("name"), self.paths.get(ds.get("name")), ds.get("metadata"))
        for rc in self.doc.get("relationshipClasses") or []:
            self.apply_metadata(u"'%s'" % rc.get("name"), os.path.join(self.gdb, rc.get("name") or ""),
                                rc.get("metadata"))
        for t in self.doc.get("topologies") or []:
            self.apply_metadata(u"'%s'" % t.get("name"),
                                os.path.join(self.gdb, t.get("featureDataset") or "", t.get("name") or ""),
                                t.get("metadata"))

    # -- relatorio ---------------------------------------------------------
    def report(self):
        self.info(u"")
        self.info(u"===== Resumo =====")
        for key, label in SUMMARY_ITEMS:
            self.info(u"  %-22s %d" % (label, self.created[key]))

        nets = self.doc.get("networks") or []
        if nets:
            self.info(u"")
            self.info(u"Redes declaradas (nao criadas — exigem Network Analyst e configuracao):")
            for net in nets:
                arcos = ", ".join([e.get("class", "") for e in net.get("edges") or []])
                juncs = ", ".join([j.get("class", "") for j in net.get("junctions") or []])
                self.info(u"  %s (em %s) | arcos: %s | juncoes: %s"
                          % (net.get("name"), net.get("featureDataset") or "?", arcos, juncs))

        if self.skipped:
            self.info(u"")
            self.info(u"Itens nao criados:")
            for s in self.skipped:
                self.info(u"  - %s" % s)

        warnings = self.doc.get("warnings") or []
        if warnings:
            self.info(u"")
            self.info(u"Avisos vindos do modelo (o que nao coube 1:1 no GDB):")
            for w in warnings:
                self.info(u"  - %s: %s" % (w.get("on"), w.get("message")))

        unmapped = self.doc.get("unmapped") or []
        if unmapped:
            self.info(u"")
            self.info(u"Sem equivalente no GDB:")
            for u in unmapped:
                self.info(u"  - %s (%s): %s" % (u.get("on"), u.get("omtg"), u.get("reason")))

        self.info(u"")
        if self.failures:
            self.warn(u"%d item(ns) nao foram criados — veja os avisos acima." % len(self.failures))
        elif self.warnings:
            self.info(u"Concluido com %d aviso(s) — veja acima." % len(self.warnings))
        else:
            self.info(u"Concluido sem avisos.")
