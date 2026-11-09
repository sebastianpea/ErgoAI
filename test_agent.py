# test_agent.py
import os

from backend.app.core_agent.ergo_agent import ErgoAIAgent
from backend.app.core_agent.knowledge_retriever import InMemoryNormativeRetriever
from backend.app.core_agent.llm_factory import LLMFactory
from backend.app.settings import JABIL_REGLAS_PATH

# Simulamos la variable de entorno para usar tu Ollama (local o contenedor)
os.environ.setdefault("LLM_PROVIDER", "OLLAMA")
os.environ.setdefault("MODEL_NAME", "qwen2.5")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")

if __name__ == "__main__":
    # 1. Instanciamos el retriever (carga config_normativo/jabil_reglas.json en RAM desde settings)
    retriever = InMemoryNormativeRetriever(JABIL_REGLAS_PATH)

    # 2. Obtenemos el modelo desde nuestra fábrica (Factory)
    llm = LLMFactory.get_llm()

    # 3. Inyectamos dependencias al Agente
    agente = ErgoAIAgent(llm=llm, retriever=retriever)

    # 4. Probamos con una anomalía detectada por tu motor de visión
    resultado = agente.evaluar_caso(
        anomalia="El operador manipula cajas de 18 kg desde el suelo flexionando el tronco a 48 grados.",
        reba_score=11,
        palabras_clave=["carga", "peso", ">14kg"],  # El RAG buscará estos tags
    )

    print(resultado)
