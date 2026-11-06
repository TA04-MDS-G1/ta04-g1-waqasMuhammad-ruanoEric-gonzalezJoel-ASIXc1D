import csv
import xml.etree.ElementTree as ET

def csv_a_xml(archivo_csv, archivo_xml, delimitador=",", encoding="utf-8"):
    raiz = ET.Element("registros")

    with open(archivo_csv, newline="", encoding=encoding) as f:
        lector = csv.DictReader(f, delimiter=delimitador)
        for fila in lector:
            registro = ET.SubElement(raiz, "registro")
            for columna, valor in fila.items():
                # Los nombres de etiqueta XML no pueden tener espacios
                etiqueta = columna.strip().replace(" ", "_")
                ET.SubElement(registro, etiqueta).text = valor

    arbol = ET.ElementTree(raiz)
    ET.indent(arbol, space="  ")
    arbol.write(archivo_xml, encoding="utf-8", xml_declaration=True)

csv_a_xml("incidencias.csv", "incidencias.xml")