"""
Edición de una plantilla Excel (.xlsx/.xlsm) SIN reconstruirla.

openpyxl, al guardar, pierde las formas dibujadas (flechas, recuadros, textos sobre diagramas) de la
hoja oficial 16-PE80-6500-00014-H. Aquí el archivo se trata como lo que es (un ZIP de XML) y solo se
tocan las partes necesarias: valores de celdas, estado de casillas de verificación, hojas duplicadas
e imágenes nuevas. Todo lo demás (formatos, fórmulas, macros, controles, imágenes y formas) se copia
byte a byte.
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, Union
from xml.sax.saxutils import escape

Valor = Union[None, bool, int, float, str]

NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TIPO_DRAWING = NS_REL + "/drawing"
TIPO_IMAGEN = NS_REL + "/image"
TIPO_CTRLPROP = NS_REL + "/ctrlProp"
TIPO_VML = NS_REL + "/vmlDrawing"
TIPO_CALCCHAIN = NS_REL + "/calcChain"
CT_DRAWING = "application/vnd.openxmlformats-officedocument.drawing+xml"
CT_HOJA = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"

_RE_REF = re.compile(r"^([A-Z]{1,3})(\d+)$")


class ErrorPlantilla(Exception):
    pass


def col_a_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def separar_ref(ref: str) -> Tuple[str, int]:
    m = _RE_REF.match(ref.replace("$", "").upper())
    if not m:
        raise ErrorPlantilla(f"Referencia de celda inválida: {ref}")
    return m.group(1), int(m.group(2))


def _xml_celda(ref: str, valor: Valor, estilo: Optional[str]) -> str:
    s = f' s="{estilo}"' if estilo is not None else ""
    if valor is None or valor == "":
        return f'<c r="{ref}"{s}/>'
    if isinstance(valor, bool):
        return f'<c r="{ref}"{s} t="b"><v>{1 if valor else 0}</v></c>'
    if isinstance(valor, (int, float)):
        texto = repr(float(valor)) if isinstance(valor, float) and not float(valor).is_integer() else str(int(valor))
        return f'<c r="{ref}"{s}><v>{texto}</v></c>'
    return f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">{escape(str(valor))}</t></is></c>'


def _desescapar(texto: str) -> str:
    return (texto.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            .replace("&apos;", "'").replace("&amp;", "&"))


def _attr(elemento: str, nombre: str) -> Optional[str]:
    m = re.search(rf'\s{nombre}="([^"]*)"', elemento)
    return m.group(1) if m else None


@dataclass
class _Rel:
    id: str
    tipo: str
    destino: str
    modo: Optional[str] = None


def _leer_rels(xml: str) -> List[_Rel]:
    rels = []
    for m in re.finditer(r"<Relationship\b[^>]*/>", xml):
        e = m.group(0)
        rels.append(_Rel(_attr(e, "Id") or "", _attr(e, "Type") or "", _attr(e, "Target") or "", _attr(e, "TargetMode")))
    return rels


def _escribir_rels(rels: Iterable[_Rel]) -> str:
    filas = []
    for r in rels:
        modo = f' TargetMode="{r.modo}"' if r.modo else ""
        filas.append(f'<Relationship Id="{r.id}" Type="{r.tipo}" Target="{escape(r.destino)}"{modo}/>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(filas)}</Relationships>')


def _ruta_rels(parte: str) -> str:
    d, f = posixpath.split(parte)
    return posixpath.join(d, "_rels", f + ".rels")


def _resolver(base: str, destino: str) -> str:
    if destino.startswith("/"):
        return destino.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), destino))


def _relativa(desde: str, hacia: str) -> str:
    return posixpath.relpath(hacia, posixpath.dirname(desde))


class LibroPlantilla:
    """Plantilla abierta en memoria; `guardar()` devuelve el archivo resultante."""

    def __init__(self, contenido: bytes):
        self._orden: List[str] = []
        self._partes: Dict[str, bytes] = {}
        self._info: Dict[str, zipfile.ZipInfo] = {}
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            for info in z.infolist():
                self._orden.append(info.filename)
                self._partes[info.filename] = z.read(info.filename)
                self._info[info.filename] = info

    # ---------------- partes ----------------

    def _texto(self, parte: str) -> str:
        return self._partes[parte].decode("utf-8")

    def _poner(self, parte: str, texto: Union[str, bytes]) -> None:
        if parte not in self._partes:
            self._orden.append(parte)
        self._partes[parte] = texto.encode("utf-8") if isinstance(texto, str) else texto

    def _quitar(self, parte: str) -> None:
        self._partes.pop(parte, None)
        if parte in self._orden:
            self._orden.remove(parte)

    def _nombre_libre(self, patron: str) -> str:
        """patron con {n}: 'xl/drawings/drawing{n}.xml'."""
        n = 1
        while patron.format(n=n) in self._partes:
            n += 1
        return patron.format(n=n)

    def _rels_de(self, parte: str) -> List[_Rel]:
        ruta = _ruta_rels(parte)
        return _leer_rels(self._texto(ruta)) if ruta in self._partes else []

    def _id_rel_libre(self, rels: List[_Rel]) -> str:
        usados = {r.id for r in rels}
        n = 1
        while f"rId{n}" in usados:
            n += 1
        return f"rId{n}"

    def _tipo_contenido(self, parte: str, content_type: str) -> None:
        ct = self._texto("[Content_Types].xml")
        nombre = "/" + parte
        if f'PartName="{nombre}"' in ct:
            return
        ext = parte.rsplit(".", 1)[-1].lower()
        if content_type.startswith("image/") and f'Extension="{ext}"' in ct:
            return
        if content_type.startswith("image/"):
            nuevo = f'<Default Extension="{ext}" ContentType="{content_type}"/>'
            ct = ct.replace("<Override", nuevo + "<Override", 1) if "<Override" in ct else ct.replace("</Types>", nuevo + "</Types>")
        else:
            ct = ct.replace("</Types>", f'<Override PartName="{nombre}" ContentType="{content_type}"/></Types>')
        self._poner("[Content_Types].xml", ct)

    def _tipo_de(self, parte: str) -> Optional[str]:
        ct = self._texto("[Content_Types].xml")
        m = re.search(rf'<Override PartName="/{re.escape(parte)}" ContentType="([^"]+)"', ct)
        return m.group(1) if m else None

    # ---------------- hojas ----------------

    def _hojas(self) -> List[Tuple[str, str, str]]:
        """[(nombre, r:id, parte)] en el orden del libro."""
        wb = self._texto("xl/workbook.xml")
        rels = {r.id: r for r in self._rels_de("xl/workbook.xml")}
        res = []
        for m in re.finditer(r"<sheet\b[^>]*/>", wb):
            e = m.group(0)
            nombre = _attr(e, "name") or ""
            rid = _attr(e, "r:id") or ""
            res.append((nombre.replace("&amp;", "&"), rid, _resolver("xl/workbook.xml", rels[rid].destino)))
        return res

    def nombres_hojas(self) -> List[str]:
        return [n for n, _, _ in self._hojas()]

    def _parte_hoja(self, hoja: str) -> str:
        for nombre, _, parte in self._hojas():
            if nombre == hoja:
                return parte
        raise ErrorPlantilla(f"La plantilla no tiene la hoja '{hoja}'")

    # ---------------- lectura ----------------

    def _cadenas_compartidas(self) -> List[str]:
        if "xl/sharedStrings.xml" not in self._partes:
            return []
        xml = self._texto("xl/sharedStrings.xml")
        res = []
        for si in re.finditer(r"<si>(.*?)</si>", xml, re.S):
            partes = re.findall(r"<t[^>]*>(.*?)</t>", si.group(1), re.S)
            res.append(_desescapar("".join(partes)))
        return res

    def textos(self, hoja: str) -> Dict[str, str]:
        """Valor mostrado (texto o número) de cada celda con valor, sin evaluar fórmulas."""
        xml = self._texto(self._parte_hoja(hoja))
        compartidas = self._cadenas_compartidas()
        res: Dict[str, str] = {}
        for m in re.finditer(r'<c\b([^>]*?)(?<!/)>(.*?)</c>', xml, re.S):
            ref = _attr(" " + m.group(1), "r")
            tipo = _attr(" " + m.group(1), "t")
            cuerpo = m.group(2)
            if ref is None:
                continue
            if tipo == "inlineStr":
                res[ref] = _desescapar("".join(re.findall(r"<t[^>]*>(.*?)</t>", cuerpo, re.S)))
                continue
            mv = re.search(r"<v>(.*?)</v>", cuerpo, re.S)
            if mv is None:
                continue
            if tipo == "s":
                idx = int(mv.group(1))
                res[ref] = compartidas[idx] if idx < len(compartidas) else ""
            else:
                res[ref] = _desescapar(mv.group(1))
        return res

    def formulas(self, hoja: str) -> Dict[str, str]:
        xml = self._texto(self._parte_hoja(hoja))
        res = {}
        for m in re.finditer(r'<c\b([^>]*?)(?<!/)>(.*?)</c>', xml, re.S):
            ref = _attr(" " + m.group(1), "r")
            mf = re.search(r"<f\b[^>]*>(.*?)</f>", m.group(2), re.S)
            if ref and mf:
                res[ref] = _desescapar(mf.group(1))
        return res

    def rangos_validacion(self, hoja: str) -> List[str]:
        """Rangos con lista desplegable (atributo sqref), p. ej. ['E12:H12', 'E40:G40']."""
        xml = self._texto(self._parte_hoja(hoja))
        rangos: List[str] = []
        for m in re.finditer(r'<(?:x14:)?dataValidation\b[^>]*?\bsqref="([^"]+)"', xml):
            rangos.extend(m.group(1).split())
        for m in re.finditer(r"<xm:sqref>([^<]+)</xm:sqref>", xml):
            rangos.extend(m.group(1).split())
        return rangos

    # ---------------- escritura ----------------

    def escribir(self, hoja: str, valores: Dict[str, Valor]) -> None:
        """Escribe valores en celdas conservando el estilo de cada una."""
        parte = self._parte_hoja(hoja)
        xml = self._texto(parte)
        por_fila: Dict[int, Dict[str, Valor]] = {}
        for ref, v in valores.items():
            col, fila = separar_ref(ref)
            por_fila.setdefault(fila, {})[col] = v

        m = re.search(r"<sheetData\s*/>|<sheetData>(.*?)</sheetData>", xml, re.S)
        if not m:
            raise ErrorPlantilla(f"Hoja '{hoja}' sin sheetData")
        datos = m.group(1) or ""
        for fila in sorted(por_fila):
            datos = self._escribir_fila(datos, fila, por_fila[fila], hoja)
        xml = xml[:m.start()] + f"<sheetData>{datos}</sheetData>" + xml[m.end():]
        self._poner(parte, xml)

    @staticmethod
    def _escribir_fila(datos: str, fila: int, celdas: Dict[str, Valor], hoja: str) -> str:
        patron_fila = re.compile(rf'<row\b[^>]*\br="{fila}"[^>]*?(?:/>|>(.*?)</row>)', re.S)
        mf = patron_fila.search(datos)
        if mf is None:
            nueva = f'<row r="{fila}">' + "".join(
                _xml_celda(f"{c}{fila}", v, None) for c, v in sorted(celdas.items(), key=lambda kv: col_a_num(kv[0]))
            ) + "</row>"
            # insertar antes de la primera fila con número mayor
            for mr in re.finditer(r'<row\b[^>]*\br="(\d+)"', datos):
                if int(mr.group(1)) > fila:
                    return datos[:mr.start()] + nueva + datos[mr.start():]
            return datos + nueva

        etiqueta = re.match(r"<row\b[^>]*?(?=/?>)", mf.group(0)).group(0)  # type: ignore[union-attr]
        contenido = mf.group(1) or ""
        for col, valor in sorted(celdas.items(), key=lambda kv: col_a_num(kv[0])):
            ref = f"{col}{fila}"
            mc = re.search(rf'<c\b[^>]*\br="{ref}"[^>]*?(?:/>|>(.*?)</c>)', contenido, re.S)
            if mc:
                if re.search(r'<f\b[^>]*\bt="shared"[^>]*\bref=', mc.group(0)):
                    raise ErrorPlantilla(f"{hoja}!{ref} es la celda maestra de una fórmula compartida; no se sobrescribe")
                estilo = _attr(re.match(r"<c\b[^>]*", mc.group(0)).group(0), "s")  # type: ignore[union-attr]
                contenido = contenido[:mc.start()] + _xml_celda(ref, valor, estilo) + contenido[mc.end():]
                continue
            nuevo = _xml_celda(ref, valor, None)
            insertado = False
            for mx in re.finditer(r'<c\b[^>]*\br="([A-Z]+)\d+"', contenido):
                if col_a_num(mx.group(1)) > col_a_num(col):
                    contenido = contenido[:mx.start()] + nuevo + contenido[mx.start():]
                    insertado = True
                    break
            if not insertado:
                contenido += nuevo
        # 'spans' limita columnas por eficiencia; se quita para no contradecir celdas nuevas
        etiqueta = re.sub(r'\sspans="[^"]*"', "", etiqueta)
        return datos[:mf.start()] + f"{etiqueta}>{contenido}</row>" + datos[mf.end():]

    def marcar_casillas(self, hoja: str, celdas: Dict[str, bool]) -> None:
        """Escribe el valor de celdas ligadas a casillas y actualiza el estado visual de esas casillas."""
        self.escribir(hoja, dict(celdas))
        parte = self._parte_hoja(hoja)
        objetivo = {separar_ref(ref): v for ref, v in celdas.items()}

        def coincide(link: str) -> Optional[bool]:
            link = link.split("!")[-1]
            try:
                return objetivo.get(separar_ref(link))
            except ErrorPlantilla:
                return None

        for rel in self._rels_de(parte):
            destino = _resolver(parte, rel.destino)
            if rel.tipo == TIPO_CTRLPROP and destino in self._partes:
                x = self._texto(destino)
                link = _attr(x, "fmlaLink")
                if link is None or (estado := coincide(link)) is None:
                    continue
                x = re.sub(r'\schecked="[^"]*"', "", x)
                if estado:
                    x = x.replace("<formControlPr ", '<formControlPr checked="Checked" ', 1)
                self._poner(destino, x)
            elif rel.tipo == TIPO_VML and destino in self._partes:
                x = self._texto(destino)

                def cambiar(mm: "re.Match[str]") -> str:
                    bloque = mm.group(0)
                    ml = re.search(r"<x:FmlaLink>([^<]+)</x:FmlaLink>", bloque)
                    if not ml or (estado := coincide(ml.group(1))) is None:
                        return bloque
                    bloque = re.sub(r"<x:Checked>[^<]*</x:Checked>", "", bloque)
                    if estado:
                        bloque = bloque.replace("</x:ClientData>", "<x:Checked>1</x:Checked></x:ClientData>")
                    return bloque

                self._poner(destino, re.sub(r'<x:ClientData ObjectType="Checkbox">.*?</x:ClientData>', cambiar, x, flags=re.S))

    def duplicar_hoja(self, origen: str, nuevo_nombre: str) -> None:
        """Copia completa de una hoja (dibujos, controles, comentarios) al final del libro."""
        if nuevo_nombre in self.nombres_hojas():
            raise ErrorPlantilla(f"Ya existe la hoja '{nuevo_nombre}'")
        hojas = self._hojas()
        indice_origen = next(i for i, (n, _, _) in enumerate(hojas) if n == origen)
        parte_origen = hojas[indice_origen][2]
        parte_nueva = self._nombre_libre("xl/worksheets/sheet{n}.xml")

        def renombrar_refs(texto: str) -> str:
            nuevo_q = "'" + nuevo_nombre.replace("'", "''") + "'!"
            return re.sub(rf"(?<![A-Za-z0-9_])'?{re.escape(origen)}'?!", lambda _: nuevo_q, texto)

        xml_hoja = self._texto(parte_origen)
        xml_hoja = re.sub(r"<f\b([^>]*)>(.*?)</f>", lambda m: f"<f{m.group(1)}>{renombrar_refs(m.group(2))}</f>", xml_hoja, flags=re.S)
        xml_hoja = re.sub(r'\stabSelected="1"', "", xml_hoja)
        self._poner(parte_nueva, xml_hoja)
        self._tipo_contenido(parte_nueva, CT_HOJA)

        rels_nuevas = []
        for rel in self._rels_de(parte_origen):
            if rel.modo == "External":
                rels_nuevas.append(rel)
                continue
            destino = _resolver(parte_origen, rel.destino)
            directorio, archivo = posixpath.split(destino)
            base, ext = posixpath.splitext(archivo)
            base = re.sub(r"\d+$", "", base)
            copia = self._nombre_libre(posixpath.join(directorio, base + "{n}" + ext))
            contenido = self._partes[destino]
            if ext in (".xml", ".vml") and ("ctrlProp" in base or "vmlDrawing" in base):
                contenido = renombrar_refs(contenido.decode("utf-8")).encode("utf-8")
            self._poner(copia, contenido)
            if (ct := self._tipo_de(destino)) is not None:
                self._tipo_contenido(copia, ct)
            if _ruta_rels(destino) in self._partes:  # p. ej. dibujos que apuntan a imágenes (se comparten)
                sub = [_Rel(r.id, r.tipo, _relativa(copia, _resolver(destino, r.destino)) if r.modo != "External" else r.destino, r.modo)
                       for r in self._rels_de(destino)]
                self._poner(_ruta_rels(copia), _escribir_rels(sub))
            rels_nuevas.append(_Rel(rel.id, rel.tipo, _relativa(parte_nueva, copia)))
        if rels_nuevas:
            self._poner(_ruta_rels(parte_nueva), _escribir_rels(rels_nuevas))

        rels_wb = self._rels_de("xl/workbook.xml")
        rid = self._id_rel_libre(rels_wb)
        rels_wb.append(_Rel(rid, NS_REL + "/worksheet", _relativa("xl/workbook.xml", parte_nueva)))
        self._poner(_ruta_rels("xl/workbook.xml"), _escribir_rels(rels_wb))

        wb = self._texto("xl/workbook.xml")
        ids = [int(x) for x in re.findall(r'<sheet\b[^>]*\bsheetId="(\d+)"', wb)]
        nombre_xml = escape(nuevo_nombre, {'"': "&quot;"})
        wb = wb.replace("</sheets>", f'<sheet name="{nombre_xml}" sheetId="{max(ids) + 1}" r:id="{rid}"/></sheets>')
        nuevo_indice = len(hojas)

        def copiar_nombres(mm: "re.Match[str]") -> str:
            bloque = mm.group(0)
            extra = []
            for d in re.finditer(r'<definedName\b[^>]*\blocalSheetId="(\d+)"[^>]*>(.*?)</definedName>', bloque, re.S):
                if int(d.group(1)) == indice_origen:
                    copia = d.group(0).replace(f'localSheetId="{indice_origen}"', f'localSheetId="{nuevo_indice}"')
                    copia = copia.replace(d.group(2), renombrar_refs(d.group(2)))
                    extra.append(copia)
            return bloque.replace("</definedNames>", "".join(extra) + "</definedNames>")

        wb = re.sub(r"<definedNames>.*?</definedNames>", copiar_nombres, wb, flags=re.S)
        self._poner("xl/workbook.xml", wb)

    def agregar_imagenes(self, hoja: str, filas: List[List[Tuple[bytes, int, int, str]]], x_px: int = 10,
                         y_px: int = 70, separacion_px: int = 16, alto_px: int = 300) -> None:
        """
        Inserta fotos JPG (contenido, ancho, alto, descripción) en filas (p. ej. una por operador),
        con altura uniforme y sin deformarlas.
        """
        if not any(filas):
            return
        parte = self._parte_hoja(hoja)
        rels_hoja = self._rels_de(parte)
        if any(r.tipo == TIPO_DRAWING for r in rels_hoja):
            raise ErrorPlantilla(f"La hoja '{hoja}' ya tiene dibujos; no se agregan fotos para no alterarlos")
        dibujo = self._nombre_libre("xl/drawings/drawing{n}.xml")
        rels_dibujo: List[_Rel] = []
        anclas: List[str] = []
        emu = 9525
        i = 0
        for n_fila, fila in enumerate(filas):
            x, y = x_px, y_px + n_fila * (alto_px + 2 * separacion_px)
            for contenido, ancho, alto, descripcion in fila:
                i += 1
                media = self._nombre_libre("xl/media/ergoai_foto{n}.jpeg")
                self._poner(media, contenido)
                self._tipo_contenido(media, "image/jpeg")
                rid = f"rId{i}"
                rels_dibujo.append(_Rel(rid, TIPO_IMAGEN, _relativa(dibujo, media)))
                w = round(ancho * alto_px / alto)
                anclas.append(
                    f'<xdr:absoluteAnchor><xdr:pos x="{x * emu}" y="{y * emu}"/><xdr:ext cx="{w * emu}" cy="{alto_px * emu}"/>'
                    f'<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="{i + 1}" name="Foto {i}" descr="{escape(descripcion, {chr(34): "&quot;"})}"/>'
                    '<xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr></xdr:nvPicPr>'
                    f'<xdr:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
                    f'<xdr:spPr><a:xfrm><a:off x="{x * emu}" y="{y * emu}"/><a:ext cx="{w * emu}" cy="{alto_px * emu}"/></a:xfrm>'
                    '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:absoluteAnchor>'
                )
                x += w + separacion_px
        self._poner(dibujo, (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            f'xmlns:r="{NS_REL}">' + "".join(anclas) + "</xdr:wsDr>"))
        self._tipo_contenido(dibujo, CT_DRAWING)
        self._poner(_ruta_rels(dibujo), _escribir_rels(rels_dibujo))

        rid_hoja = self._id_rel_libre(rels_hoja)
        rels_hoja.append(_Rel(rid_hoja, TIPO_DRAWING, _relativa(parte, dibujo)))
        self._poner(_ruta_rels(parte), _escribir_rels(rels_hoja))

        xml = self._texto(parte)
        raiz = re.search(r"<worksheet\b[^>]*>", xml)
        if raiz is None:
            raise ErrorPlantilla(f"Hoja '{hoja}' sin elemento worksheet")
        if "xmlns:r=" not in raiz.group(0):
            xml = xml[:raiz.start()] + raiz.group(0).replace("<worksheet", f'<worksheet xmlns:r="{NS_REL}"', 1) + xml[raiz.end():]
        posicion = len(xml) - len("</worksheet>")
        for etiqueta in ("<legacyDrawing", "<legacyDrawingHF", "<drawingHF", "<picture", "<oleObjects",
                         "<controls", "<webPublishItems", "<tableParts", "<extLst"):
            i = xml.find(etiqueta)
            if i != -1:
                posicion = min(posicion, i)
        self._poner(parte, xml[:posicion] + f'<drawing r:id="{rid_hoja}"/>' + xml[posicion:])

    def preparar_recalculo(self) -> None:
        """Excel recalcula todas las fórmulas al abrir; se elimina la cadena de cálculo (se regenera sola)."""
        wb = self._texto("xl/workbook.xml")
        if "<calcPr" in wb:
            wb = re.sub(r"<calcPr\b([^>]*?)\s*/>",
                        lambda m: "<calcPr" + re.sub(r'\sfullCalcOnLoad="[^"]*"', "", m.group(1)) + ' fullCalcOnLoad="1"/>', wb, count=1)
        else:
            wb = wb.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')
        self._poner("xl/workbook.xml", wb)
        rels = self._rels_de("xl/workbook.xml")
        for r in [r for r in rels if r.tipo == TIPO_CALCCHAIN]:
            self._quitar(_resolver("xl/workbook.xml", r.destino))
            rels.remove(r)
        self._poner(_ruta_rels("xl/workbook.xml"), _escribir_rels(rels))
        ct = re.sub(r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "", self._texto("[Content_Types].xml"))
        self._poner("[Content_Types].xml", ct)

    def guardar(self) -> bytes:
        salida = io.BytesIO()
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
            for nombre in self._orden:
                if nombre not in self._partes:
                    continue
                info = self._info.get(nombre)
                if info is not None:
                    nueva = zipfile.ZipInfo(nombre, date_time=info.date_time)
                    nueva.compress_type = zipfile.ZIP_DEFLATED
                    nueva.external_attr = info.external_attr
                    z.writestr(nueva, self._partes[nombre])
                else:
                    z.writestr(nombre, self._partes[nombre])
        return salida.getvalue()
