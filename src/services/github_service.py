# Copyright (c) Microsoft. All rights reserved.
"""
GitHub Service

Provides GitHub API operations for the Code Ingestion Agent.
Implements read-only operations: file reading, search, dependency discovery.
"""

import base64
import fnmatch
import hashlib
import re
from datetime import datetime
from typing import AsyncIterator

from github import Github
from github.ContentFile import ContentFile
from github.Repository import Repository

from src.config import get_settings
from src.schemas import DependencyInfo, FileInfo, IngestionPolicy


class GitHubService:
    """
    GitHub API service for code ingestion.
    
    Provides read-only operations:
    - File listing and content retrieval
    - Dependency file discovery
    - Content classification
    - Secret detection and redaction
    """
    
    # File classification patterns
    FILE_CLASSIFICATIONS = {
        "code": [
            "*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.java", "*.cs", "*.go",
            "*.rs", "*.cpp", "*.c", "*.h", "*.hpp", "*.rb", "*.php", "*.swift",
            "*.kt", "*.scala", "*.clj", "*.ex", "*.exs",
        ],
        "config": [
            "*.json", "*.yaml", "*.yml", "*.toml", "*.ini", "*.cfg", "*.conf",
            "*.properties", "*.xml", ".env*", "*.config",
        ],
        "docs": [
            "*.md", "*.rst", "*.txt", "*.adoc", "*.asciidoc",
            "README*", "CHANGELOG*", "CONTRIBUTING*", "LICENSE*",
        ],
        "iac": [
            "*.tf", "*.tfvars", "*.bicep", "*.arm.json",
            "*cloudformation*.json", "*cloudformation*.yaml",
            "*.pulumi.*", "Pulumi.yaml", "cdk.json",
        ],
        "cicd": [
            ".github/workflows/*.yml", ".github/workflows/*.yaml",
            ".gitlab-ci.yml", "Jenkinsfile*", "azure-pipelines*.yml",
            ".circleci/*", ".travis.yml", "bitbucket-pipelines.yml",
            "*.Dockerfile", "Dockerfile*", "docker-compose*.yml",
        ],
        "tests": [
            "*test*.py", "*_test.py", "test_*.py", "*_test.go",
            "*Test.java", "*_test.ts", "*.spec.ts", "*.test.ts",
            "*.spec.js", "*.test.js", "*_spec.rb",
        ],
    }
    
    # Dependency file patterns
    DEPENDENCY_FILES = {
        "npm": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
        "pip": ["requirements.txt", "requirements*.txt", "Pipfile", "Pipfile.lock", "pyproject.toml", "setup.py"],
        "maven": ["pom.xml"],
        "gradle": ["build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"],
        "cargo": ["Cargo.toml", "Cargo.lock"],
        "go": ["go.mod", "go.sum"],
        "dotnet": ["*.csproj", "*.fsproj", "*.vbproj", "packages.config", "*.sln"],
        "bundler": ["Gemfile", "Gemfile.lock"],
        "composer": ["composer.json", "composer.lock"],
    }
    
    # Secret patterns for redaction
    SECRET_PATTERNS = [
        # API Keys
        (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', "API_KEY"),
        # Passwords
        (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{8,})["\']?', "PASSWORD"),
        # Tokens
        (r'(?i)(token|bearer|auth)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?', "TOKEN"),
        # AWS
        (r'AKIA[0-9A-Z]{16}', "AWS_ACCESS_KEY"),
        (r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?', "AWS_SECRET"),
        # Azure
        (r'(?i)(azure|az)[_-]?(client|tenant|subscription)[_-]?(id|secret)\s*[:=]\s*["\']?([a-zA-Z0-9\-]{36})["\']?', "AZURE_CREDENTIAL"),
        # Connection strings
        (r'(?i)connection[_-]?string\s*[:=]\s*["\']?([^"\']+)["\']?', "CONNECTION_STRING"),
        # Private keys
        (r'-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----', "PRIVATE_KEY"),
        # GitHub tokens
        (r'ghp_[a-zA-Z0-9]{36}', "GITHUB_PAT"),
        (r'github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}', "GITHUB_PAT"),
    ]
    
    def __init__(self):
        settings = get_settings()
        self.github = Github(settings.github.github_token)
        self._compiled_patterns = [
            (re.compile(pattern), replacement)
            for pattern, replacement in self.SECRET_PATTERNS
        ]
    
    def get_repository(self, repo_url: str) -> Repository:
        """Get repository object from URL."""
        # Extract owner/repo from URL
        # Supports: https://github.com/owner/repo, git@github.com:owner/repo.git
        if "github.com" in repo_url:
            parts = repo_url.rstrip("/").rstrip(".git").split("github.com")[-1]
            parts = parts.lstrip("/:").split("/")
            owner, repo = parts[0], parts[1]
            return self.github.get_repo(f"{owner}/{repo}")
        raise ValueError(f"Invalid GitHub URL: {repo_url}")
    
    def classify_file(self, path: str) -> str | None:
        """Classify a file based on its path/name."""
        for classification, patterns in self.FILE_CLASSIFICATIONS.items():
            for pattern in patterns:
                if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.split("/")[-1], pattern):
                    return classification
        return None
    
    def should_exclude(self, path: str, policy: IngestionPolicy) -> bool:
        """Check if a file should be excluded based on policy."""
        for pattern in policy.exclude_globs:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False
    
    def redact_secrets(self, content: str) -> tuple[str, int]:
        """
        Redact secrets from content.
        
        Returns:
            Tuple of (redacted_content, count_of_redactions)
        """
        redaction_count = 0
        result = content
        
        for pattern, replacement in self._compiled_patterns:
            matches = pattern.findall(result)
            if matches:
                redaction_count += len(matches)
                result = pattern.sub(f"[REDACTED_{replacement}]", result)
        
        return result, redaction_count
    
    async def list_files(
        self,
        repo: Repository,
        ref: str = "main",
        path: str = "",
        policy: IngestionPolicy | None = None,
    ) -> AsyncIterator[FileInfo]:
        """
        List all files in the repository.
        
        Args:
            repo: GitHub repository object
            ref: Git reference (branch, tag, commit)
            path: Starting path
            policy: Ingestion policy for filtering
            
        Yields:
            FileInfo objects for each file
        """
        policy = policy or IngestionPolicy()
        
        try:
            contents = repo.get_contents(path, ref=ref)
        except Exception:
            return
        
        if not isinstance(contents, list):
            contents = [contents]
        
        for content in contents:
            if content.type == "dir":
                async for file_info in self.list_files(repo, ref, content.path, policy):
                    yield file_info
            else:
                # Check exclusions
                if self.should_exclude(content.path, policy):
                    continue
                
                # Check file size
                if content.size > policy.max_file_mb * 1024 * 1024:
                    continue
                
                # Skip test files if configured
                classification = self.classify_file(content.path)
                if classification == "tests" and not policy.include_tests:
                    continue
                
                yield FileInfo(
                    path=content.path,
                    language=self._detect_language(content.path),
                    size_bytes=content.size,
                    classification=classification,
                    checksum=content.sha,
                )
    
    def get_file_content(
        self,
        repo: Repository,
        path: str,
        ref: str = "main",
        redact: bool = True,
    ) -> tuple[str, int]:
        """
        Get file content, optionally redacting secrets.
        
        Returns:
            Tuple of (content, secrets_redacted_count)
        """
        content_file = repo.get_contents(path, ref=ref)
        
        if isinstance(content_file, list):
            raise ValueError(f"Path {path} is a directory")
        
        # Decode content
        if content_file.encoding == "base64":
            content = base64.b64decode(content_file.content).decode("utf-8", errors="replace")
        else:
            content = content_file.content or ""
        
        if redact:
            return self.redact_secrets(content)
        
        return content, 0
    
    async def discover_dependencies(
        self,
        repo: Repository,
        ref: str = "main",
    ) -> list[DependencyInfo]:
        """
        Discover dependencies from common dependency files.
        
        Returns:
            List of discovered dependencies
        """
        dependencies = []
        
        for pkg_manager, patterns in self.DEPENDENCY_FILES.items():
            for pattern in patterns:
                try:
                    # Handle glob patterns
                    if "*" in pattern:
                        continue  # Skip globs for now, would need directory listing
                    
                    content_file = repo.get_contents(pattern, ref=ref)
                    if isinstance(content_file, list):
                        continue
                    
                    content = base64.b64decode(content_file.content).decode("utf-8")
                    deps = self._parse_dependencies(content, pkg_manager, pattern)
                    dependencies.extend(deps)
                    
                except Exception:
                    continue  # File doesn't exist
        
        return dependencies
    
    def _detect_language(self, path: str) -> str | None:
        """Detect programming language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".cs": "csharp",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
        }
        
        for ext, lang in ext_map.items():
            if path.endswith(ext):
                return lang
        return None
    
    def _parse_dependencies(
        self,
        content: str,
        pkg_manager: str,
        filename: str,
    ) -> list[DependencyInfo]:
        """Parse dependencies from file content."""
        dependencies = []
        
        if pkg_manager == "pip" and filename == "requirements.txt":
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    # Parse: package==version, package>=version, package
                    match = re.match(r'^([a-zA-Z0-9_-]+)([<>=!~]+)?(.+)?$', line)
                    if match:
                        dependencies.append(DependencyInfo(
                            name=match.group(1),
                            version=match.group(3) if match.group(3) else None,
                            package_manager="pip",
                        ))
        
        elif pkg_manager == "npm" and filename == "package.json":
            import json
            try:
                data = json.loads(content)
                for name, version in data.get("dependencies", {}).items():
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=version.lstrip("^~>=<"),
                        package_manager="npm",
                    ))
                for name, version in data.get("devDependencies", {}).items():
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=version.lstrip("^~>=<"),
                        package_manager="npm",
                        is_dev=True,
                    ))
            except json.JSONDecodeError:
                pass
        
        # Add more parsers as needed...
        
        return dependencies


# Singleton instance
_github_service: GitHubService | None = None


def get_github_service() -> GitHubService:
    """Get or create GitHub service instance."""
    global _github_service
    if _github_service is None:
        _github_service = GitHubService()
    return _github_service
