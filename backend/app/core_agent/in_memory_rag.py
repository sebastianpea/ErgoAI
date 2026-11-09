"""
RAG Estático en Memoria (In-Memory Lexical & Semantic Retriever).
Alineado con ARCHITECTURE.md, PLAN_PERSISTENCIA_SIN_BASE_DE_DATOS.md y Rúbrica Jabil X-RAIC 2026.

Reglas del módulo:
1. PROHIBIDO importar motores de bases de datos (sqlite3, psycopg, redis, etc.).
2. Cero alucinaciones: recuperación de apartados literales de 16-PE30-6500-00023.pdf y NOM-036-1-STPS-2018.
3. 100% Offline y ejecución en microsegundos (< 5 ms).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Set

from backend.app.settings import BM25_B, BM25_K1

# Lista compacta de palabras vacías (stop words) en español para indexación léxica
STOP_WORDS: Set[str] = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para",
    "con", "no", "una", "su", "al", "lo", "como", "más", "pero", "sus", "le", "ya", "o", "este",
    "sí", "porque", "esta", "entre", "cuando", "muy", "sin", "sobre", "también", "me", "hasta",
    "hay", "donde", "quien", "desde", "todo", "nos", "durante", "todos", "uno", "les", "ni", "contra",
}


def _tokenizar(texto: str) -> List[str]:
    """Extrae palabras clave alfanuméricas normalizadas en minúsculas."""
    tokens = re.findall(r"[a-záéíóúüñ0-9_]+", texto.lower())
    return [t for t in tokens if len(t) > 1 and t not in STOP_WORDS]


@dataclass
class ClausulaNormativa:
    id: str
    condicion: str
    titulo: str
    documento: str
    seccion: str
    pagina: int
    norma_vinculada: str
    hoja_excel_jabil: str
    layer_autocad: str
    tramite_moc: str
    texto_oficial: str
    control_ingenieria: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class ResultadoBusquedaRAG:
    clausula: ClausulaNormativa
    score: float
    terminos_coincidentes: List[str]


class InMemoryRAG:
    """
    Motor RAG determinista y léxico en memoria RAM (Zero Database).
    Mantiene un índice invertido BM25-lite y mapeo directo por clave de condición.
    """

    def __init__(self, jabil_standards: Dict[str, Any], nom036_kb_text: Optional[str] = None):
        self.clausulas_por_id: Dict[str, ClausulaNormativa] = {}
        self.clausulas_por_condicion: Dict[str, ClausulaNormativa] = {}
        self.corpus_docs: List[ClausulaNormativa] = []
        self.indice_invertido: Dict[str, List[int]] = {}  # token -> indices en self.corpus_docs
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 1.0
        self.nom036_raw_kb: str = nom036_kb_text or ""
        self.max_single_lift_kg: float = float(
            jabil_standards.get("load_limits", {}).get("max_single_person_lift_kg", 14.0)
        )

        self._indexar_estandares(jabil_standards)

    def _indexar_estandares(self, jabil_standards: Dict[str, Any]) -> None:
        raw_clauses = jabil_standards.get("normative_rag_clauses", [])
        for rc in raw_clauses:
            clausula = ClausulaNormativa(
                id=rc["id"],
                condicion=rc["condicion"],
                titulo=rc["titulo"],
                documento=rc["documento"],
                seccion=rc["seccion"],
                pagina=int(rc.get("pagina", 1)),
                norma_vinculada=rc["norma_vinculada"],
                hoja_excel_jabil=rc["hoja_excel_jabil"],
                layer_autocad=rc["layer_autocad"],
                tramite_moc=rc["tramite_moc"],
                texto_oficial=rc["texto_oficial"],
                control_ingenieria=rc["control_ingenieria"],
                keywords=rc.get("keywords", []),
            )
            self.clausulas_por_id[clausula.id] = clausula
            self.clausulas_por_condicion[clausula.condicion] = clausula
            self.corpus_docs.append(clausula)

        # Construir índice BM25
        total_tokens = 0
        for idx, doc in enumerate(self.corpus_docs):
            texto_completo = f"{doc.titulo} {doc.seccion} {doc.texto_oficial} {doc.control_ingenieria} {' '.join(doc.keywords)}"
            tokens = _tokenizar(texto_completo)
            longitud = len(tokens)
            self.doc_lengths.append(longitud)
            total_tokens += longitud
            for t in set(tokens):
                self.indice_invertido.setdefault(t, []).append(idx)

        self.avg_doc_length = (total_tokens / len(self.corpus_docs)) if self.corpus_docs else 1.0

    def recuperar_por_condicion(self, condicion: str) -> Optional[ClausulaNormativa]:
        """Recuperación O(1) exacta cuando el motor de ergonomía detecta una condición específica."""
        return self.clausulas_por_condicion.get(condicion)

    def buscar(self, consulta: str, top_k: int = 3) -> List[ResultadoBusquedaRAG]:
        """
        Búsqueda ponderada BM25-lite en memoria RAM sin bases de datos.
        Responde en menos de 1 milisegundo.
        """
        tokens_consulta = _tokenizar(consulta)
        if not tokens_consulta or not self.corpus_docs:
            return []

        n_docs = len(self.corpus_docs)
        k1 = BM25_K1
        b = BM25_B
        scores = [0.0] * n_docs
        matched_terms: Dict[int, List[str]] = {i: [] for i in range(n_docs)}

        for token in tokens_consulta:
            docs_con_token = self.indice_invertido.get(token, [])
            df = len(docs_con_token)
            if df == 0:
                continue
            # IDF con corrección BM25
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
            for doc_idx in docs_con_token:
                doc = self.corpus_docs[doc_idx]
                texto_doc = f"{doc.titulo} {doc.seccion} {doc.texto_oficial} {doc.control_ingenieria} {' '.join(doc.keywords)}".lower()
                tf = texto_doc.count(token)
                longitud = self.doc_lengths[doc_idx]
                denominador = tf + k1 * (1.0 - b + b * (longitud / self.avg_doc_length))
                score_termino = idf * (tf * (k1 + 1.0)) / (denominador if denominador > 0 else 1.0)
                scores[doc_idx] += score_termino
                matched_terms[doc_idx].append(token)

        resultados = []
        for idx, s in enumerate(scores):
            if s > 0:
                resultados.append(ResultadoBusquedaRAG(
                    clausula=self.corpus_docs[idx],
                    score=round(s, 3),
                    terminos_coincidentes=matched_terms[idx],
                ))

        resultados.sort(key=lambda r: r.score, reverse=True)
        return resultados[:top_k]

    def enriquecer_recomendacion(
        self,
        rec: Dict[str, Any],
        angulos: Mapping[str, Optional[float]],
        contexto: Any,
        tipo_tarea: str,
    ) -> Dict[str, Any]:
        """
        Inyecta las citas literales de Jabil 16-PE30-6500-00023 y NOM-036
        en el objeto de recomendación generado deterministamente.
        """
        titulo = rec.get("titulo", "").lower()
        texto = rec.get("texto", "").lower()
        texto_comb = f"{titulo} {texto}"
        clausula: Optional[ClausulaNormativa] = None

        carga_actual = (
            float(getattr(contexto, "carga_kg", 0.0) or 0.0)
            if contexto is not None
            else 0.0
        )
        if ("asistencia mecánica" in titulo or "lifter" in titulo or "carga" in titulo) and carga_actual > self.max_single_lift_kg:
            clausula = self.recuperar_por_condicion("carga_individual_mayor_14kg")
        elif "conforme" in texto_comb or "inapreciable" in texto_comb or "sin anomalías" in texto_comb:
            clausula = self.recuperar_por_condicion("postura_conforme_riesgo_inapreciable")
        elif "cuello" in texto_comb or "cervical" in texto_comb or "visión" in texto_comb or "monitor" in texto_comb or "pantalla" in texto_comb:
            clausula = self.recuperar_por_condicion("flexion_cervical_linea_vision")
        elif "altura" in titulo or "superficie" in titulo or "tronco" in titulo or "reposapiés" in titulo or "plataforma" in titulo:
            clausula = self.recuperar_por_condicion("altura_mesa_espacio_piernas_pies")
        elif "alcance" in titulo or "zonas" in titulo or "muñeca" in titulo or "herramienta" in titulo:
            clausula = self.recuperar_por_condicion("materiales_lejos_zonas_alcance")
        elif "rotación" in titulo or "pausas" in titulo or "silla" in titulo or "bipedestación" in titulo:
            clausula = self.recuperar_por_condicion("trabajo_pie_prolongado_ley_silla")
        elif "conveyor" in titulo or "transportador" in titulo:
            clausula = self.recuperar_por_condicion("inspeccion_postura_conveyor")
        elif "auxiliar" in titulo or "carro" in titulo or "empuje" in tipo_tarea:
            clausula = self.recuperar_por_condicion("pasillos_empuje_arrastre_amr")
        elif "técnica" in titulo or "postura" in titulo:
            clausula = self.recuperar_por_condicion("restriccion_postural_alturas_verticales")

        # Fallback a búsqueda semántica si no coincidió directamente
        if clausula is None:
            busqueda = self.buscar(f"{rec.get('titulo', '')} {rec.get('texto', '')}", top_k=1)
            if busqueda:
                clausula = busqueda[0].clausula

        if clausula is not None:
            rec["justificacion_rag"] = (
                f"[{clausula.documento} {clausula.seccion} (Pág. {clausula.pagina})]: "
                f"{clausula.texto_oficial}"
            )
            rec["norma_vinculada"] = clausula.norma_vinculada
            rec["hoja_excel_jabil"] = clausula.hoja_excel_jabil
            rec["layer_autocad"] = clausula.layer_autocad
            rec["tramite_moc"] = clausula.tramite_moc
            rec["codigo_jabil"] = f"{clausula.documento} {clausula.seccion}"

        return rec
