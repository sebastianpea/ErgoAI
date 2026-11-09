"""
Construye el corpus normativo del agente (config_normativo/corpus_normativo.json).

Fuentes:
  1. NOM-036-1-STPS-2018 tal como se publicó en el DOF (PDF). El texto se extrae con `pdftotext`
     (poppler) y se fragmenta por cláusula de segundo nivel (7.1, 8.3, ...) en el cuerpo de la norma
     y por página en los apéndices (son tablas).
  2. Cláusulas Jabil 16-PE30-6500-00023 ya catalogadas en config_normativo/jabil_standards_00023.json.

Se ejecuta una sola vez (o cuando cambie una fuente); el JSON resultante se versiona para que el
backend arranque sin el PDF, sin poppler y sin red.

Uso (desde la raíz del repositorio):
    .venv/bin/python scripts/construir_corpus_normativo.py --pdf ruta/23-11-2018-Matutina.pdf --paginas 21-63
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.settings import CONFIG_DIR  # noqa: E402

DOCUMENTO_NOM = "NOM-036-1-STPS-2018"
MAX_CARACTERES_FRAGMENTO = 2400

RE_ENCABEZADO_DOF = re.compile(r"DIARIO OFICIAL")
RE_INICIO_CUERPO = re.compile(r"^\s*1\.\s+Objetivo\s*$")
# El DOF pega el número de nota al pie al título ("APÉNDICE I1"), de ahí el dígito opcional.
RE_APENDICE = re.compile(r"^\s*(AP[ÉE]NDICE\s+[IVX]+|GU[ÍI]A DE REFERENCIA\s+[IVX]+)\d?\s*$")
RE_CLAUSULA = re.compile(r"^\s{0,8}(\d{1,2})\.(\d{1,2})?((?:\.\d{1,2})*)\.?\s+(\S.*)$")


def extraer_paginas(pdf: Path, primera: int, ultima: int) -> List[Tuple[int, str]]:
    """Devuelve [(número de página DOF, texto)] usando pdftotext en modo layout."""
    salida = subprocess.run(
        ["pdftotext", "-layout", "-f", str(primera), "-l", str(ultima), str(pdf), "-"],
        check=True, capture_output=True, text=True,
    ).stdout
    return [(primera + i, texto) for i, texto in enumerate(salida.split("\f")) if texto.strip()]


def _limpiar(lineas: List[str]) -> str:
    texto = " ".join(l.strip() for l in lineas if l.strip())
    texto = re.sub(r"\s{2,}", " ", texto)
    return re.sub(r"(\w)- (\w)", r"\1\2", texto).strip()


def _partir(texto: str) -> List[str]:
    """Parte un texto largo en trozos <= MAX_CARACTERES_FRAGMENTO cortando en fin de oración."""
    if len(texto) <= MAX_CARACTERES_FRAGMENTO:
        return [texto]
    partes, actual = [], ""
    for oracion in re.split(r"(?<=[.;:])\s+", texto):
        if actual and len(actual) + len(oracion) + 1 > MAX_CARACTERES_FRAGMENTO:
            partes.append(actual)
            actual = oracion
        else:
            actual = f"{actual} {oracion}".strip()
    if actual:
        partes.append(actual)
    return partes


def _nombre_apendice(titulo: str) -> str:
    """'APÉNDICE  II' -> 'Apéndice II'; 'GUÍA DE REFERENCIA I' -> 'Guía de referencia I'."""
    nombre, numeral = re.sub(r"\s+", " ", titulo).rsplit(" ", 1)
    return f"{nombre.capitalize()} {numeral.upper()}"


def _slug(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9.]+", "-", sin_acentos).strip("-")


def _lineas(paginas: List[Tuple[int, str]]) -> Iterator[Tuple[int, str]]:
    for num, texto in paginas:
        for linea in texto.splitlines():
            if not RE_ENCABEZADO_DOF.search(linea):
                yield num, linea


def fragmentar_nom(paginas: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
    lineas = list(_lineas(paginas))
    # El índice de contenido también lista "1. Objetivo": el cuerpo empieza en la última aparición
    # dentro de la primera página.
    primera_pag = lineas[0][0]
    inicios = [i for i, (p, l) in enumerate(lineas) if p == primera_pag and RE_INICIO_CUERPO.match(l)]
    if not inicios:
        raise SystemExit("No se encontró el inicio del cuerpo de la norma ('1. Objetivo').")
    lineas = lineas[inicios[-1]:]

    bloques: List[Dict[str, Any]] = []
    actual: Optional[Dict[str, Any]] = None
    seccion_principal = 0
    en_apendice: Optional[str] = None

    def cerrar() -> None:
        if actual and actual["lineas"]:
            bloques.append(actual)

    for pagina, linea in lineas:
        apendice = RE_APENDICE.match(linea)
        if apendice:
            cerrar()
            en_apendice = _nombre_apendice(apendice.group(1))
            actual = {"clave": f"{en_apendice} p{pagina}", "seccion": en_apendice, "titulo": None,
                      "pagina": pagina, "lineas": []}
            continue
        if en_apendice:
            if actual is None or actual["pagina"] != pagina:  # apéndices: un fragmento por página
                cerrar()
                actual = {"clave": f"{en_apendice} p{pagina}", "seccion": en_apendice, "titulo": None,
                          "pagina": pagina, "lineas": []}
            actual["lineas"].append(linea)
            continue

        m = RE_CLAUSULA.match(linea)
        if m:
            principal, sub = int(m.group(1)), m.group(2)
            # Solo cuenta como cláusula si respeta la numeración (descarta filas de tablas como "5.6 Registro").
            if principal in (seccion_principal, seccion_principal + 1):
                nivel2 = f"{principal}.{sub}" if sub else f"{principal}"
                if actual is None or actual["clave"] != nivel2:
                    cerrar()
                    seccion_principal = principal
                    actual = {"clave": nivel2, "seccion": f"§{nivel2}",
                              "titulo": m.group(4).strip() if not sub else None,
                              "pagina": pagina, "lineas": []}
        if actual is not None:
            actual["lineas"].append(linea)
    cerrar()

    fragmentos: List[Dict[str, Any]] = []
    for b in bloques:
        texto = _limpiar(b["lineas"])
        if len(texto) < 40:
            continue
        partes = _partir(texto)
        for n, parte in enumerate(partes, start=1):
            sufijo = f" (parte {n}/{len(partes)})" if len(partes) > 1 else ""
            fragmentos.append({
                "id": f"NOM036-{_slug(b['clave'])}" + (f"-{n}" if len(partes) > 1 else ""),
                "documento": DOCUMENTO_NOM,
                "seccion": f"{b['seccion']}{sufijo}",
                "titulo": b["titulo"] or parte[:90].rstrip(),
                "pagina": b["pagina"],
                "texto": parte,
                "metadatos": {"fuente": "DOF 23/11/2018"},
            })
    return fragmentos


def fragmentos_jabil(ruta: Path) -> List[Dict[str, Any]]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    res = []
    for c in datos.get("normative_rag_clauses", []):
        res.append({
            "id": c["id"],
            "documento": c["documento"],
            "seccion": c["seccion"],
            "titulo": c["titulo"],
            "pagina": c.get("pagina"),
            "texto": f"{c['texto_oficial']} Control recomendado: {c['control_ingenieria']}",
            "metadatos": {
                "norma_vinculada": c.get("norma_vinculada"),
                "hoja_excel_jabil": c.get("hoja_excel_jabil"),
                "layer_autocad": c.get("layer_autocad"),
                "tramite_moc": c.get("tramite_moc"),
                "palabras_clave": c.get("keywords", []),
            },
        })
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", type=Path, required=True, help="PDF del DOF con la NOM-036-1-STPS-2018")
    ap.add_argument("--paginas", default="21-63",
                    help="Rango de páginas de la norma sin el cuestionario de Kuorinka (DOF 23/11/2018: 21-63)")
    ap.add_argument("--jabil", type=Path, default=CONFIG_DIR / "jabil_standards_00023.json")
    ap.add_argument("--salida", type=Path, default=CONFIG_DIR / "corpus_normativo.json")
    args = ap.parse_args()

    primera, ultima = (int(x) for x in args.paginas.split("-"))
    nom = fragmentar_nom(extraer_paginas(args.pdf, primera, ultima))
    jabil = fragmentos_jabil(args.jabil)
    corpus = {
        "version": datetime.now(timezone.utc).strftime("%Y%m%d"),
        "fuentes": [f"{DOCUMENTO_NOM} (DOF 23/11/2018, págs. {args.paginas})", args.jabil.name],
        "fragmentos": nom + jabil,
    }
    args.salida.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(nom)} fragmentos NOM-036 + {len(jabil)} cláusulas Jabil -> {args.salida}")


if __name__ == "__main__":
    main()
