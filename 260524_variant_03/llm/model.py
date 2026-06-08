import logging
from langchain_ollama import ChatOllama
from config import OllamaConfig

logger = logging.getLogger(__name__)


def get_llm(config: OllamaConfig) -> ChatOllama:
    logger.info("Ollama LLM: model=%s url=%s", config.model, config.base_url)
    return ChatOllama(
        model=config.model,
        base_url=config.base_url,
        temperature=0,        # Deterministisch voor Cypher-generatie
        num_predict=512,
    )
