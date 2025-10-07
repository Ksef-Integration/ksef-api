import yaml
import os
import re

# -----------------------------
# Konfiguracja
# -----------------------------
INPUT_FILE = "./api/ksef-openapi.yaml"
OUTPUT_DIR = "openapi"
SCHEMAS_DIR = os.path.join(OUTPUT_DIR, "components", "schemas")
PATHS_DIR = os.path.join(OUTPUT_DIR, "paths")

os.makedirs(SCHEMAS_DIR, exist_ok=True)
os.makedirs(PATHS_DIR, exist_ok=True)

# -----------------------------
# Pomocnicze funkcje
# -----------------------------
def to_snake_case(name: str) -> str:
    """Konwertuje CamelCase / PascalCase na snake_case."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()

# -----------------------------
# Mapa tagów na angielski
# -----------------------------
tag_map = {
    "Uzyskiwanie dostępu": "Authentication",
    "Aktywne sesje": "ActiveSessions",
    "Certyfikaty klucza publicznego": "PublicKeyCertificates",
    "Wysyłka interaktywna": "InteractiveInvoice",
    "Wysyłka wsadowa": "BatchInvoice",
    "Status wysyłki i UPO": "InvoiceStatus",
    "Pobieranie faktur": "DownloadInvoices",
    "Nadawanie uprawnień": "GrantPermissions",
    "Odbieranie uprawnień": "RevokePermissions",
    "Wyszukiwanie nadanych uprawnień": "SearchPermissions",
    "Operacje": "Operations",
    "Certyfikaty": "Certificates",
    "Tokeny KSeF": "KSeFTokens",
    "Usługi Peppol": "PeppolServices",
    "Dane testowe": "TestData"
}

# -----------------------------
# Funkcja do zamiany $ref na relatywne pliki
# -----------------------------
def replace_schema_refs(obj, current_file_path, schema_name_map):
    """
    Rekurencyjnie zamienia $ref typu '#/components/schemas/Name'
    na relatywne '../components/schemas/name.yaml' względem current_file_path.
    """
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str) and v.startswith("#/components/schemas/"):
                schema_name = v.split("/")[-1]
                filename = schema_name_map.get(schema_name, f"{to_snake_case(schema_name)}.yaml")
                rel_path = os.path.relpath(os.path.join(SCHEMAS_DIR, filename),
                                           start=os.path.dirname(current_file_path))
                new_obj[k] = rel_path.replace("\\", "/")
            else:
                new_obj[k] = replace_schema_refs(v, current_file_path, schema_name_map)
        return new_obj
    elif isinstance(obj, list):
        return [replace_schema_refs(i, current_file_path, schema_name_map) for i in obj]
    else:
        return obj

# -----------------------------
# Wczytaj plik OpenAPI
# -----------------------------
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    spec = yaml.safe_load(f)

# -----------------------------
# Rozdziel schematy do folderu components/schemas
# -----------------------------
schemas = spec.get("components", {}).get("schemas", {})
new_schemas_ref = {}
schema_name_map = {}

for name, schema in schemas.items():
    filename = f"{to_snake_case(name)}.yaml"
    schema_name_map[name] = filename

# zapis schematów po zbudowaniu mapy nazw
for name, schema in schemas.items():
    file_path = os.path.join(SCHEMAS_DIR, schema_name_map[name])
    schema = replace_schema_refs(schema, file_path, schema_name_map)

    with open(file_path, "w", encoding="utf-8") as f_out:
        yaml.safe_dump(schema, f_out, sort_keys=False, allow_unicode=True)

    new_schemas_ref[name] = {"$ref": f"./components/schemas/{schema_name_map[name]}"}

if "components" not in spec:
    spec["components"] = {}
spec["components"]["schemas"] = new_schemas_ref

# -----------------------------
# Rozdziel paths do podfolderów + mapowanie tagów + zamiana $ref
# -----------------------------
paths = spec.get("paths", {})
new_paths_ref = {}

for path, path_value in paths.items():
    parts = path.strip("/").split("/")

    # Pomijamy /api/v2
    core_parts = parts[2:] if len(parts) > 2 else ["root"]

    # Folder = pierwszy segment po api/v2
    folder = core_parts[0]
    folder_path = os.path.join(PATHS_DIR, folder)
    os.makedirs(folder_path, exist_ok=True)

    # Nazwa pliku = reszta ścieżki po folderze (bez {})
    safe_name = "_".join(core_parts[1:]) if len(core_parts) > 1 else "root"
    safe_name = re.sub(r"\{(\w+)\}", r"by_\1", safe_name)
    filename = f"{safe_name}.yaml"
    full_path_file = os.path.join(folder_path, filename)

    # Zamiana tagów w operacjach na angielski
    for method, operation in path_value.items():
        if "tags" in operation:
            operation["tags"] = [tag_map.get(t, t) for t in operation["tags"]]

    # Zamiana $ref w pathach na relatywne pliki
    path_value = replace_schema_refs(path_value, full_path_file, schema_name_map)

    # Zapisz operacje do osobnego pliku
    with open(full_path_file, "w", encoding="utf-8") as f_out:
        yaml.safe_dump(path_value, f_out, sort_keys=False, allow_unicode=True)

    # $ref w głównym pliku
    new_paths_ref[path] = {"$ref": f"./paths/{folder}/{filename}"}

spec["paths"] = new_paths_ref

# -----------------------------
# Zapisz główny plik OpenAPI
# -----------------------------
with open(os.path.join(OUTPUT_DIR, "openapi.yaml"), "w", encoding="utf-8") as f:
    yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True)

print("✅ Rozdzielony OpenAPI zapisany w:", os.path.join(OUTPUT_DIR, "openapi.yaml"))