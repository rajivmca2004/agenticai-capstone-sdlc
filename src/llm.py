# Copyright (c) Microsoft. All rights reserved.
"""
LLM Factory

Creates LLM instances based on configuration.
Supports OpenAI, Azure OpenAI, and Anthropic.
"""

from langchain_core.language_models import BaseChatModel
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from src.config import get_settings
from src.observability import get_logger, MissingAPIKeyError

# Initialize logger
logger = get_logger(__name__)


def get_llm(
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """
    Create an LLM instance based on settings.
    
    Args:
        temperature: Override default temperature
        max_tokens: Override default max tokens
        
    Returns:
        LLM instance configured for the selected provider
    """
    settings = get_settings()
    llm_settings = settings.llm
    
    temp = temperature if temperature is not None else llm_settings.temperature
    tokens = max_tokens if max_tokens is not None else llm_settings.max_tokens
    
    provider = llm_settings.llm_provider
    logger.info("creating_llm", provider=provider, temperature=temp, max_tokens=tokens)
    
    try:
        if provider == "azure_openai":
            if not llm_settings.azure_openai_api_key:
                raise MissingAPIKeyError("Azure OpenAI")
            
            llm = AzureChatOpenAI(
                azure_endpoint=llm_settings.azure_openai_endpoint,
                api_key=llm_settings.azure_openai_api_key,
                azure_deployment=llm_settings.azure_openai_deployment,
                api_version=llm_settings.azure_openai_api_version,
                temperature=temp,
                max_tokens=tokens,
            )
            logger.debug("azure_openai_configured", deployment=llm_settings.azure_openai_deployment)
            return llm
        
        elif provider == "anthropic":
            if not llm_settings.anthropic_api_key:
                raise MissingAPIKeyError("Anthropic")
            
            # Lazy import to avoid requiring anthropic if not used
            from langchain_anthropic import ChatAnthropic
            
            llm = ChatAnthropic(
                api_key=llm_settings.anthropic_api_key,
                model=llm_settings.anthropic_model,
                temperature=temp,
                max_tokens=tokens,
            )
            logger.debug("anthropic_configured", model=llm_settings.anthropic_model)
            return llm
        
        else:  # Default to OpenAI
            if not llm_settings.openai_api_key:
                raise MissingAPIKeyError("OpenAI")
            
            llm = ChatOpenAI(
                api_key=llm_settings.openai_api_key,
                model=llm_settings.openai_model,
                temperature=temp,
                max_tokens=tokens,
            )
            logger.debug("openai_configured", model=llm_settings.openai_model)
            return llm
            
    except MissingAPIKeyError:
        raise
    except Exception as e:
        logger.error("llm_creation_failed", provider=provider, error=str(e))
        raise


def get_code_ingestion_llm() -> BaseChatModel:
    """Get LLM configured for code ingestion tasks."""
    logger.debug("creating_code_ingestion_llm")
    return get_llm(temperature=0.0, max_tokens=4096)


def get_architect_llm() -> BaseChatModel:
    """Get LLM configured for architecture analysis tasks."""
    logger.debug("creating_architect_llm")
    return get_llm(temperature=0.1, max_tokens=8192)
