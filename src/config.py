# Copyright (c) Microsoft. All rights reserved.
"""
Configuration and Settings for the Agentic AI Solution

Uses Pydantic Settings for type-safe configuration management.
"""

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM provider configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # LLM Provider: "openai", "azure_openai", "anthropic"
    llm_provider: Literal["openai", "azure_openai", "anthropic"] = Field(
        default="openai",
        description="LLM provider to use",
    )
    
    # OpenAI Configuration
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model name")
    
    # Azure OpenAI Configuration
    azure_openai_endpoint: str | None = Field(default=None, description="Azure OpenAI endpoint")
    azure_openai_api_key: str | None = Field(default=None, description="Azure OpenAI API key")
    azure_openai_deployment: str | None = Field(default=None, description="Azure OpenAI deployment name")
    azure_openai_api_version: str = Field(default="2024-08-01-preview", description="Azure OpenAI API version")
    
    # Anthropic Configuration
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022", description="Anthropic model name")
    
    # LLM Parameters
    temperature: float = Field(default=0.0, description="LLM temperature")
    max_tokens: int = Field(default=4096, description="Max tokens for LLM response")


class GitHubSettings(BaseSettings):
    """GitHub API configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    github_token: str | None = Field(default=None, description="GitHub API token")
    github_api_base_url: str = Field(
        default="https://api.github.com",
        description="GitHub API base URL",
    )


class AgentSettings(BaseSettings):
    """Agent server configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    code_ingestion_agent_port: int = Field(default=5001, description="Code Ingestion Agent port")
    architect_agent_port: int = Field(default=5002, description="Architect Agent port")
    
    # LangSmith tracing (optional)
    langchain_tracing_v2: bool = Field(default=False, description="Enable LangSmith tracing")
    langchain_api_key: str | None = Field(default=None, description="LangSmith API key")
    langchain_project: str = Field(default="code-comprehension", description="LangSmith project name")


class Settings(BaseSettings):
    """Main application settings combining all configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Sub-configurations
    llm: LLMSettings = Field(default_factory=LLMSettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    
    # Checkpointing
    checkpoint_dir: str = Field(default=".checkpoints", description="Directory for state checkpoints")
    
    # Output directory for generated reports
    output_dir: str = Field(default="output", description="Directory for generated outputs")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export for convenience
settings = get_settings()
