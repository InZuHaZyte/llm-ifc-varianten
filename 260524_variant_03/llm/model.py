import logging
from langchain_ollama import ChatOllama
from config import AppConfig

logger = logging.getLogger(__name__)


def get_llm(config: AppConfig):
    if config.openai.api_key.strip():
        from langchain_openai import ChatOpenAI
        logger.info("OpenAI LLM: model=%s", config.openai.model)
        return ChatOpenAI(
            api_key=config.openai.api_key,
            model=config.openai.model,
            temperature=0,
        )
    logger.info("Ollama LLM: model=%s url=%s", config.ollama.model, config.ollama.base_url)
    return ChatOllama(
        model=config.ollama.model,
        base_url=config.ollama.base_url,
        temperature=0,
        num_predict=512,
    )
