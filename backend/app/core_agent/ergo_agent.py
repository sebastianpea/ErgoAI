# backend/app/core_agent/ergo_agent.py
from __future__ import annotations

import inspect
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from .models import RecomendacionErgonomica


class ErgoAIAgent:
    def __init__(self, llm, retriever):
        self.llm = llm
        self.retriever = retriever
        self.parser = JsonOutputParser(pydantic_object=RecomendacionErgonomica)

        # Prompt inflexible: el LLM es exclusivamente redactor, jamás calculador
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres ErgoAI, el copiloto auditor experto en ergonomía de Jabil.
El sistema determinista ya calculó el riesgo. Tu única tarea es redactar la recomendación de ingeniería basándote EXCLUSIVAMENTE en el texto normativo adjunto. No asumas ni agregues datos que no estén presentes.

REGLAS ARQUITECTÓNICAS ESTRICTAS:
1. El LLM NO es calculador, es redactor: Tienes estrictamente prohibido calcular o modificar el puntaje REBA o el Nivel de Riesgo NOM-036.
2. Ceguera Inducida: Redacta únicamente para el tipo de prueba y anomalía indicados, usando EXCLUSIVAMENTE el texto normativo adjunto. No mezcles REBA con EAWS ni menciones equipos o pesos que no aparezcan en los datos del caso.
3. Si el texto normativo adjunto NO menciona asistencia mecánica ni lifters, QUEDA ESTRICTAMENTE PROHIBIDO mencionarlos en tu respuesta.
4. Si la anomalía indicada es exclusivamente de cuello/cervical, enfócate ÚNICAMENTE en elevar/inclinar la pieza o monitor a la línea de visión (0°-15° bajo la horizontal); NO menciones rediseño general de la mesa, grosor de borde, espacio de piernas ni reposapiés.
5. Si la postura está en rangos neutros o REBA es Inapreciable (puntaje 1), redacta que la postura cumple los estándares y no requiere intervención física.
6. Prioriza controles de Ingeniería pertinentes solo si existe riesgo real o desviación biomecánica detectada.
7. Responde ÚNICAMENTE con el JSON válido en el formato exacto solicitado.

TEXTO NORMATIVO ADJUNTO (FILTRADO POR TIPO DE PRUEBA EN RAM):
{knowledge_base_text}

INSTRUCCIONES DE FORMATO JSON:
{format_instructions}
"""),
            ("human", """DATOS INMUTABLES CALCULADOS POR EL MOTOR DETERMINISTA:
- Tipo de Operación / Prueba: {tipo_prueba}
- Dictamen Matemático Inmutable: {riesgo_determinista}
- Puntaje REBA Inicial: {reba_score}
- Anomalía Detectada: {anomalia}

Redacta la recomendación de ingeniería ciñéndote exclusivamente al texto normativo adjunto.
""")
        ])

        self.chain = self.prompt | self.llm | self.parser

    def evaluar_caso(
        self,
        anomalia: str,
        reba_score: int,
        palabras_clave: list[str],
        tipo_prueba: str | None = None,
        riesgo_determinista: str | None = None,
    ) -> dict:
        # 1. Recuperar el fragmento normativo aplicando Ceguera Inducida por tipo_prueba
        sig = inspect.signature(self.retriever.search)
        if "tipo_prueba" in sig.parameters:
            texto_normativo = self.retriever.search(palabras_clave, tipo_prueba=tipo_prueba)
        else:
            texto_normativo = self.retriever.search(palabras_clave)

        dictamen_inmutable = riesgo_determinista or f"Puntaje REBA {reba_score}"
        prueba_activa = tipo_prueba or "General"

        # 2. Ejecutar la cadena de LangChain con el dictamen matemático inmutable
        resultado_json = self.chain.invoke({
            "knowledge_base_text": texto_normativo,
            "format_instructions": self.parser.get_format_instructions(),
            "tipo_prueba": prueba_activa,
            "riesgo_determinista": dictamen_inmutable,
            "anomalia": anomalia,
            "reba_score": reba_score,
        })

        return resultado_json


# Alias de compatibilidad
ErgoAgent = ErgoAIAgent
