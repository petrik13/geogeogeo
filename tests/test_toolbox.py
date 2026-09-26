# -*- coding: utf-8 -*-
"""
Roda a toolbox (geogeogeo_toolbox.pyt) sobre o exemplo-gdb.json com um arcpy
simulado, sem ArcGIS instalado.

Não valida a semântica do ArcGIS (isso só no ArcGIS Pro), mas pega o que
quebra antes de chegar lá: erro de Python, chave do JSON que a toolbox não
lê do jeito que o gerador escreve, e contagens que não batem. Cada chamada
arcpy.management.* é registrada; ListFields devolve os campos já criados, com
os nomes de tipo que o ArcGIS usa.

Uso: python3 tests/test_toolbox.py   (também roda dentro do npm test)
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARC_TYPE = {"TEXT": "String", "SHORT": "SmallInteger", "LONG": "Integer", "FLOAT": "Single",
            "DOUBLE": "Double", "DATE": "Date", "BLOB": "Blob", "GUID": "Guid"}


class FakeArcpy(types.ModuleType):
    """O mínimo de arcpy que a toolbox usa, registrando as chamadas."""

    def __init__(self):
        super(FakeArcpy, self).__init__("arcpy")
        self.calls = []
        self.messages = []
        self.warnings = []
        self.existing = set()
        self.fields = {}  # caminho da tabela -> [(nome, tipo)]
        fake = self

        class ExecuteError(Exception):
            pass
        self.ExecuteError = ExecuteError

        class SpatialReference(object):
            def __init__(self, wkid):
                self.factoryCode = int(wkid)
        self.SpatialReference = SpatialReference

        class Field(object):
            def __init__(self, name, ftype):
                self.name, self.type = name, ftype

        def record(name, create=None):
            def fn(*args, **kwargs):
                fake.calls.append((name, args, kwargs))
                if create:
                    path = create(*args, **kwargs)
                    if path:
                        fake.existing.add(path)
            return fn

        def add_field(table, name, ftype, *rest, **kw):
            fake.calls.append(("AddField", (table, name, ftype) + rest, kw))
            fake.fields.setdefault(table, []).append((name, ARC_TYPE.get(ftype, ftype)))

        mgmt = types.SimpleNamespace(
            CreateFileGDB=record("CreateFileGDB", lambda folder, name: os.path.join(folder, name)),
            CreateDomain=record("CreateDomain"),
            SetValueForRangeDomain=record("SetValueForRangeDomain"),
            AddCodedValueToDomain=record("AddCodedValueToDomain"),
            CreateFeatureDataset=record("CreateFeatureDataset", lambda gdb, name, sr: os.path.join(gdb, name)),
            CreateFeatureclass=record("CreateFeatureclass", lambda home, name, *a: os.path.join(home, name)),
            CreateTable=record("CreateTable", lambda home, name: os.path.join(home, name)),
            AlterAliasName=record("AlterAliasName"),
            AddField=add_field,
            AssignDefaultToField=record("AssignDefaultToField"),
            AddGlobalIDs=record("AddGlobalIDs"),
            EnableAttachments=record("EnableAttachments"),
            EnableEditorTracking=record("EnableEditorTracking"),
            AddIndex=record("AddIndex"),
            CreateRelationshipClass=record("CreateRelationshipClass", lambda o, d, out, *a: out),
            CreateTopology=record("CreateTopology", lambda fd, name, *a: os.path.join(fd, name)),
            AddFeatureClassToTopology=record("AddFeatureClassToTopology"),
            AddRuleToTopology=record("AddRuleToTopology"),
            ValidateTopology=record("ValidateTopology"),
            AddAttributeRule=record("AddAttributeRule"),
            GenerateSchemaReport=record("GenerateSchemaReport"),
        )
        self.management = mgmt

        class Metadata(object):
            def __init__(self, path):
                self.path = path

            def save(self):
                fake.calls.append(("Metadata.save", (self.path,), {}))
        self.metadata = types.SimpleNamespace(Metadata=Metadata)
        sys.modules["arcpy.metadata"] = self.metadata

        self.Exists = lambda path: path in fake.existing
        self.ListFields = lambda table: [Field(n, t) for n, t in fake.fields.get(table, [])]
        self.AddMessage = self.messages.append
        self.AddWarning = self.warnings.append
        self.SetParameterAsText = lambda i, v: None
        self.Parameter = object


def load_toolbox(fake):
    sys.modules["arcpy"] = fake
    path = os.path.join(ROOT, "geogeogeo_toolbox.pyt")
    loader = importlib.machinery.SourceFileLoader("geogeogeo_toolbox", path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def main():
    fake = FakeArcpy()
    toolbox = load_toolbox(fake)
    json_path = os.path.join(ROOT, "exemplo-gdb.json")
    with open(json_path, encoding="utf-8") as fh:
        doc = json.load(fh)
    out = tempfile.mkdtemp()

    builder = toolbox.GdbBuilder(json_path, out, None, True, True, True, ["HTML"])
    gdb = builder.run()

    errors = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    count = lambda name: sum(1 for c in fake.calls if c[0] == name)
    real = [d for d in doc["datasets"] if d.get("status") != "placeholder"]

    check(gdb and gdb.endswith(doc["workspace"]["name"] + ".gdb"), "caminho da gdb: %r" % gdb)
    check(not builder.failures, "passos falharam:\n    " + "\n    ".join(builder.failures))
    check(builder.created["datasets"] == len(real),
          "datasets criados: %d de %d" % (builder.created["datasets"], len(real)))
    check(builder.created["relationshipClasses"] == len(doc["relationshipClasses"]),
          "relationship classes: %d de %d" % (builder.created["relationshipClasses"], len(doc["relationshipClasses"])))
    check(builder.created["rules"] == len(doc["attributeRules"]),
          "attribute rules: %d de %d" % (builder.created["rules"], len(doc["attributeRules"])))
    check(builder.created["domains"] == len(doc["domains"]), "domínios")
    check(builder.created["featureDatasets"] == len(doc["featureDatasets"]), "feature datasets")
    check(builder.created["topologies"] == len(doc["topologies"]), "topologias")
    n_topo_rules = sum(len(t["rules"]) for t in doc["topologies"])
    check(count("AddRuleToTopology") == n_topo_rules, "regras de topologia: %d de %d" % (count("AddRuleToTopology"), n_topo_rules))
    with_globalid = [d for d in real if "GLOBALID" in d["systemFields"]]
    check(count("AddGlobalIDs") == len(with_globalid), "GLOBALID")
    placeholders = [d["name"] for d in doc["datasets"] if d.get("status") == "placeholder"]
    for name in placeholders:
        check(any(s.startswith(name + " ") for s in builder.skipped), "placeholder %s não relatado" % name)
    check(count("GenerateSchemaReport") == 1, "Schema Report não gerado")

    if errors:
        print("FALHA — toolbox com arcpy simulado:")
        for e in errors:
            print("  - " + e)
        sys.exit(1)
    print("toolbox ok: %d chamadas ao arcpy, %d aviso(s), %d item(ns) não criado(s) (placeholders)."
          % (len(fake.calls), len(fake.warnings), len(builder.skipped)))


if __name__ == "__main__":
    main()
