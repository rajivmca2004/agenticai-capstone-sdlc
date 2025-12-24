# Copyright (c) Microsoft. All rights reserved.
"""
Custom Exceptions Module

Provides a hierarchy of domain-specific exceptions for better error handling.
"""

from typing import Any


class CodeComprehensionError(Exception):
    """Base exception for all code comprehension errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# CONFIGURATION ERRORS
# =============================================================================

class ConfigurationError(CodeComprehensionError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, config_key: str | None = None, **kwargs):
        super().__init__(
            message=message,
            error_code="CONFIG_ERROR",
            details={"config_key": config_key} if config_key else {},
            **kwargs,
        )


class MissingAPIKeyError(ConfigurationError):
    """Raised when required API key is missing."""
    
    def __init__(self, provider: str):
        super().__init__(
            message=f"API key for {provider} is not configured",
            config_key=f"{provider.upper()}_API_KEY",
        )
        self.provider = provider


# =============================================================================
# GITHUB ERRORS
# =============================================================================

class GitHubError(CodeComprehensionError):
    """Base exception for GitHub-related errors."""
    
    def __init__(self, message: str, repo_url: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if repo_url:
            details["repo_url"] = repo_url
        super().__init__(
            message=message,
            error_code="GITHUB_ERROR",
            details=details,
            **kwargs,
        )


class RepositoryNotFoundError(GitHubError):
    """Raised when repository cannot be found."""
    
    def __init__(self, repo_url: str):
        super().__init__(
            message=f"Repository not found: {repo_url}",
            repo_url=repo_url,
        )
        self.error_code = "REPO_NOT_FOUND"


class RepositoryAccessDeniedError(GitHubError):
    """Raised when access to repository is denied."""
    
    def __init__(self, repo_url: str):
        super().__init__(
            message=f"Access denied to repository: {repo_url}. Check your GitHub token permissions.",
            repo_url=repo_url,
        )
        self.error_code = "REPO_ACCESS_DENIED"


class GitHubRateLimitError(GitHubError):
    """Raised when GitHub API rate limit is exceeded."""
    
    def __init__(self, reset_time: str | None = None):
        message = "GitHub API rate limit exceeded"
        if reset_time:
            message += f". Resets at {reset_time}"
        super().__init__(message=message)
        self.error_code = "GITHUB_RATE_LIMIT"
        self.reset_time = reset_time


class InvalidRepositoryURLError(GitHubError):
    """Raised when repository URL is invalid."""
    
    def __init__(self, repo_url: str):
        super().__init__(
            message=f"Invalid GitHub repository URL: {repo_url}",
            repo_url=repo_url,
        )
        self.error_code = "INVALID_REPO_URL"


# =============================================================================
# INGESTION ERRORS
# =============================================================================

class IngestionError(CodeComprehensionError):
    """Base exception for ingestion-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="INGESTION_ERROR",
            **kwargs,
        )


class FileProcessingError(IngestionError):
    """Raised when a file cannot be processed."""
    
    def __init__(self, file_path: str, reason: str, cause: Exception | None = None):
        super().__init__(
            message=f"Failed to process file '{file_path}': {reason}",
            details={"file_path": file_path, "reason": reason},
            cause=cause,
        )
        self.error_code = "FILE_PROCESSING_ERROR"
        self.file_path = file_path


class FileTooLargeError(IngestionError):
    """Raised when a file exceeds size limit."""
    
    def __init__(self, file_path: str, size_mb: float, max_size_mb: float):
        super().__init__(
            message=f"File '{file_path}' ({size_mb:.2f} MB) exceeds maximum size ({max_size_mb} MB)",
            details={
                "file_path": file_path,
                "size_mb": size_mb,
                "max_size_mb": max_size_mb,
            },
        )
        self.error_code = "FILE_TOO_LARGE"


class IngestionTimeoutError(IngestionError):
    """Raised when ingestion exceeds time limit."""
    
    def __init__(self, timeout_seconds: int, files_processed: int = 0):
        super().__init__(
            message=f"Ingestion timed out after {timeout_seconds} seconds",
            details={
                "timeout_seconds": timeout_seconds,
                "files_processed": files_processed,
            },
        )
        self.error_code = "INGESTION_TIMEOUT"


# =============================================================================
# LLM ERRORS
# =============================================================================

class LLMError(CodeComprehensionError):
    """Base exception for LLM-related errors."""
    
    def __init__(self, message: str, provider: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if provider:
            details["provider"] = provider
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            details=details,
            **kwargs,
        )


class LLMConnectionError(LLMError):
    """Raised when connection to LLM fails."""
    
    def __init__(self, provider: str, cause: Exception | None = None):
        super().__init__(
            message=f"Failed to connect to {provider} LLM service",
            provider=provider,
            cause=cause,
        )
        self.error_code = "LLM_CONNECTION_ERROR"


class LLMRateLimitError(LLMError):
    """Raised when LLM rate limit is exceeded."""
    
    def __init__(self, provider: str, retry_after: int | None = None):
        message = f"{provider} rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message=message, provider=provider)
        self.error_code = "LLM_RATE_LIMIT"
        self.retry_after = retry_after


class LLMResponseError(LLMError):
    """Raised when LLM response is invalid or cannot be parsed."""
    
    def __init__(self, message: str, raw_response: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if raw_response:
            details["raw_response_preview"] = raw_response[:500]
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )
        self.error_code = "LLM_RESPONSE_ERROR"


class LLMTokenLimitError(LLMError):
    """Raised when input exceeds LLM token limit."""
    
    def __init__(self, tokens_used: int, max_tokens: int, provider: str | None = None):
        super().__init__(
            message=f"Input exceeds token limit: {tokens_used} tokens used, max {max_tokens}",
            provider=provider,
            details={
                "tokens_used": tokens_used,
                "max_tokens": max_tokens,
            },
        )
        self.error_code = "LLM_TOKEN_LIMIT"


# =============================================================================
# ARCHITECT ERRORS
# =============================================================================

class ArchitectError(CodeComprehensionError):
    """Base exception for Architect agent errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="ARCHITECT_ERROR",
            **kwargs,
        )


class MissingRepoBundleError(ArchitectError):
    """Raised when repo bundle is not available for analysis."""
    
    def __init__(self):
        super().__init__(
            message="Repository bundle not available. Run Code Ingestion Agent first.",
        )
        self.error_code = "MISSING_REPO_BUNDLE"


class ReportGenerationError(ArchitectError):
    """Raised when report generation fails."""
    
    def __init__(self, report_type: str, reason: str, cause: Exception | None = None):
        super().__init__(
            message=f"Failed to generate {report_type} report: {reason}",
            details={"report_type": report_type, "reason": reason},
            cause=cause,
        )
        self.error_code = "REPORT_GENERATION_ERROR"


# =============================================================================
# WORKFLOW ERRORS
# =============================================================================

class WorkflowError(CodeComprehensionError):
    """Base exception for workflow-related errors."""
    
    def __init__(self, message: str, workflow_id: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if workflow_id:
            details["workflow_id"] = workflow_id
        super().__init__(
            message=message,
            error_code="WORKFLOW_ERROR",
            details=details,
            **kwargs,
        )


class WorkflowStateError(WorkflowError):
    """Raised when workflow state is invalid."""
    
    def __init__(self, message: str, current_state: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if current_state:
            details["current_state"] = current_state
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )
        self.error_code = "WORKFLOW_STATE_ERROR"


class AgentExecutionError(WorkflowError):
    """Raised when an agent fails during execution."""
    
    def __init__(self, agent_name: str, reason: str, cause: Exception | None = None):
        super().__init__(
            message=f"Agent '{agent_name}' failed: {reason}",
            details={"agent_name": agent_name, "reason": reason},
            cause=cause,
        )
        self.error_code = "AGENT_EXECUTION_ERROR"


# =============================================================================
# JOB ERRORS
# =============================================================================

class JobError(CodeComprehensionError):
    """Base exception for job-related errors."""
    
    def __init__(self, message: str, job_id: str | None = None, **kwargs):
        details = kwargs.pop("details", {})
        if job_id:
            details["job_id"] = job_id
        super().__init__(
            message=message,
            error_code="JOB_ERROR",
            details=details,
            **kwargs,
        )


class JobNotFoundError(JobError):
    """Raised when job is not found."""
    
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Job not found: {job_id}",
            job_id=job_id,
        )
        self.error_code = "JOB_NOT_FOUND"


class JobAlreadyExistsError(JobError):
    """Raised when trying to create a job that already exists."""
    
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Job already exists: {job_id}",
            job_id=job_id,
        )
        self.error_code = "JOB_ALREADY_EXISTS"
