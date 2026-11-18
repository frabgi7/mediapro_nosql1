from bson.json_util import dumps
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db_name = "mediapro_nosql"
db = client[db_name]

colecciones = [
    "equipo_tecnico",
    "localizaciones",
    "personal",
    "producciones",
    "talento",
]

for col_name in colecciones:
  try:
    coleccion = db[col_name]
    documentos = list(coleccion.find())
    nombre_archivo = f"{db_name}.{col_name}.json"

    with open(nombre_archivo, "w", encoding="utf-8") as f:
      f.write(dumps(documentos, indent=4, ensure_ascii=False))

    print(f"Exportado: {nombre_archivo}")
  except Exception as e:
    print(f"Error en {col_name}: {e}")

print("\n¡Listo! Archivos generados con éxito.")