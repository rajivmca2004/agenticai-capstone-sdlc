# Copyright (c) Microsoft. All rights reserved.
"""
Pytest configuration and shared fixtures.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# =============================================================================
# MOCK DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_repo_url():
    """Sample GitHub repository URL."""
    return "https://github.com/microsoft/sample-repo"


@pytest.fixture
def sample_ref():
    """Sample Git reference."""
    return "main"


@pytest.fixture
def sample_file_infos():
    """Sample file information list."""
    from src.schemas import FileInfo
    
    return [
        FileInfo(
            path="src/main.py",
            language="python",
            size_bytes=1024,
            classification="code",
            checksum="abc123",
        ),
        FileInfo(
            path="src/utils.py",
            language="python",
            size_bytes=512,
            classification="code",
            checksum="def456",
        ),
        FileInfo(
            path="requirements.txt",
            language=None,
            size_bytes=256,
            classification="config",
            checksum="ghi789",
        ),
        FileInfo(
            path="README.md",
            language=None,
            size_bytes=2048,
            classification="docs",
            checksum="jkl012",
        ),
        FileInfo(
            path="tests/test_main.py",
            language="python",
            size_bytes=768,
            classification="tests",
            checksum="mno345",
        ),
    ]


@pytest.fixture
def sample_dependencies():
    """Sample dependency information list."""
    from src.schemas import DependencyInfo
    
    return [
        DependencyInfo(name="fastapi", version="0.115.0", package_manager="pip"),
        DependencyInfo(name="pydantic", version="2.9.0", package_manager="pip"),
        DependencyInfo(name="pytest", version="8.0.0", package_manager="pip", is_dev=True),
    ]


@pytest.fixture
def sample_risks():
    """Sample risk items."""
    from src.schemas import RiskItem, RiskSeverity
    
    return [
        RiskItem(
            id="RISK-001",
            category="security",
            severity=RiskSeverity.HIGH,
            title="Outdated dependency",
            description="FastAPI version has known CVE",
            remediation="Upgrade to 0.116.0+",
        ),
        RiskItem(
            id="RISK-002",
            category="tech_debt",
            severity=RiskSeverity.MEDIUM,
            title="Missing type hints",
            description="Some modules lack type annotations",
            remediation="Add type hints using mypy",
        ),
    ]


@pytest.fixture
def sample_repo_bundle(sample_file_infos, sample_dependencies, sample_risks):
    """Sample RepoBundle for testing."""
    from datetime import datetime
    from src.schemas import IngestionPolicy, RepoBundle
    
    return RepoBundle(
        repo_url="https://github.com/microsoft/sample-repo",
        ref="main",
        timestamp=datetime.utcnow(),
        languages=["python"],
        frameworks=["FastAPI"],
        build_systems=["pip"],
        files=sample_file_infos,
        total_files=len(sample_file_infos),
        total_size_bytes=sum(f.size_bytes for f in sample_file_infos),
        dependencies=sample_dependencies,
        code_files=["src/main.py", "src/utils.py"],
        config_files=["requirements.txt"],
        doc_files=["README.md"],
        iac_files=[],
        cicd_files=[],
        test_files=["tests/test_main.py"],
        risks=sample_risks,
        files_ingested=5,
        files_excluded=0,
        secrets_redacted=0,
        ingestion_policy=IngestionPolicy(),
    )


@pytest.fixture
def sample_business_report():
    """Sample business report."""
    from src.schemas import BusinessReport, OptionItem, EffortBand, RiskSeverity
    
    return BusinessReport(
        executive_summary="This is a Python FastAPI application suitable for cloud migration.",
        current_state="Monolithic REST API with SQLite backend.",
        options=[
            OptionItem(
                id="OPT-A",
                name="Rehost",
                description="Lift and shift to Azure App Service",
                pros=["Quick", "Low risk"],
                cons=["No optimization"],
                effort=EffortBand.S,
                risk_level=RiskSeverity.LOW,
                recommended=False,
            ),
            OptionItem(
                id="OPT-B",
                name="Refactor",
                description="Containerize and deploy to AKS",
                pros=["Scalable", "Modern"],
                cons=["More effort"],
                effort=EffortBand.M,
                risk_level=RiskSeverity.MEDIUM,
                recommended=True,
            ),
        ],
        value_and_kpis="Reduce MTTR by 40%, improve uptime to 99.9%",
        adoption_plan="Phase 1: Containerize. Phase 2: Deploy to AKS.",
        diagram_mermaid="graph TD\n  A[Current] --> B[Target]",
    )


@pytest.fixture
def sample_technical_report(sample_risks):
    """Sample technical report."""
    from src.schemas import (
        TechnicalReport, MigrationWave, BacklogItem, EffortBand
    )
    
    return TechnicalReport(
        codebase_map="Python 100%: FastAPI-based REST API",
        topology="Single service with SQLite database",
        security_compliance="Basic authentication, no encryption at rest",
        nfrs="Current: 99% uptime, 200ms latency. Target: 99.9% uptime, 100ms latency",
        risk_register=sample_risks,
        target_architecture="Containerized microservice on Azure AKS",
        architecture_diagram_mermaid="graph TD\n  A[AKS] --> B[Azure SQL]",
        migration_plan=[
            MigrationWave(
                wave_number=1,
                name="Foundation",
                duration_weeks=2,
                tasks=["Containerize app", "Set up CI/CD"],
                prerequisites=[],
                rollback_plan="Revert to VM deployment",
            ),
            MigrationWave(
                wave_number=2,
                name="Migration",
                duration_weeks=4,
                tasks=["Deploy to AKS", "Migrate database"],
                prerequisites=["Wave 1 complete"],
                rollback_plan="Switch traffic back to old system",
            ),
        ],
        backlog_slice=[
            BacklogItem(
                id="STORY-001",
                title="Create Dockerfile",
                description="Containerize the FastAPI application",
                effort=EffortBand.S,
                linked_risk_id=None,
                sprint=1,
            ),
            BacklogItem(
                id="STORY-002",
                title="Set up AKS cluster",
                description="Provision Azure Kubernetes Service",
                effort=EffortBand.M,
                linked_risk_id=None,
                sprint=1,
            ),
        ],
    )


@pytest.fixture
def mock_github_service(sample_file_infos, sample_dependencies):
    """Mock GitHub service."""
    from src.services.github_service import GitHubService
    
    mock_service = MagicMock(spec=GitHubService)
    
    # Mock repository
    mock_repo = MagicMock()
    mock_repo.full_name = "microsoft/sample-repo"
    mock_service.get_repository.return_value = mock_repo
    
    # Mock list_files as async generator
    async def mock_list_files(*args, **kwargs):
        for file_info in sample_file_infos:
            yield file_info
    
    mock_service.list_files = mock_list_files
    
    # Mock discover_dependencies
    async def mock_discover_deps(*args, **kwargs):
        return sample_dependencies
    
    mock_service.discover_dependencies = mock_discover_deps
    
    return mock_service


@pytest.fixture
def mock_llm_response():
    """Mock LLM response."""
    mock_response = MagicMock()
    mock_response.content = '''{
        "languages": ["python"],
        "frameworks": ["FastAPI"],
        "build_systems": ["pip"],
        "risks": [
            {
                "id": "RISK-001",
                "category": "security",
                "severity": "high",
                "title": "Outdated dependency",
                "description": "FastAPI version has known CVE",
                "remediation": "Upgrade to latest version"
            }
        ]
    }'''
    return mock_response


@pytest.fixture
def mock_business_report_response():
    """Mock LLM response for business report."""
    mock_response = MagicMock()
    mock_response.content = '''{
        "executive_summary": "Python FastAPI application ready for cloud migration.",
        "current_state": "Monolithic REST API",
        "options": [
            {
                "id": "A",
                "name": "Rehost",
                "description": "Deploy to Azure App Service",
                "pros": ["Quick deployment"],
                "cons": ["Limited scaling"],
                "effort": "S",
                "risk_level": "low",
                "recommended": false
            },
            {
                "id": "B",
                "name": "Refactor",
                "description": "Containerize for AKS",
                "pros": ["Scalable"],
                "cons": ["More work"],
                "effort": "M",
                "risk_level": "medium",
                "recommended": true
            }
        ],
        "value_and_kpis": "Improve uptime and reduce costs",
        "adoption_plan": "Two-phase approach over 6 weeks",
        "diagram_mermaid": "graph TD\\n  A --> B"
    }'''
    return mock_response


@pytest.fixture
def mock_technical_report_response():
    """Mock LLM response for technical report."""
    mock_response = MagicMock()
    mock_response.content = '''{
        "codebase_map": "Python 100%",
        "topology": "Single service architecture",
        "security_compliance": "Basic security posture",
        "nfrs": "99% uptime target",
        "risk_register": [
            {
                "id": "RISK-001",
                "category": "security",
                "severity": "high",
                "title": "Dependency vulnerability",
                "description": "Update required",
                "remediation": "Upgrade packages",
                "effort": "S"
            }
        ],
        "target_architecture": "Containerized on AKS",
        "architecture_diagram_mermaid": "graph TD\\n  AKS --> SQL",
        "migration_plan": [
            {
                "wave_number": 1,
                "name": "Foundation",
                "duration_weeks": 2,
                "tasks": ["Setup infrastructure"],
                "prerequisites": [],
                "rollback_plan": "Revert changes"
            }
        ],
        "backlog_slice": [
            {
                "id": "STORY-001",
                "title": "Create Dockerfile",
                "description": "Containerize app",
                "effort": "S",
                "linked_risk_id": null,
                "sprint": 1
            }
        ]
    }'''
    return mock_response


# =============================================================================
# ENVIRONMENT FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def mock_environment():
    """Mock environment variables for tests."""
    env_vars = {
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test-key-for-testing",
        "GITHUB_TOKEN": "ghp_test_token_for_testing",
        "LOG_LEVEL": "WARNING",
        "LOG_FORMAT": "console",
    }
    with patch.dict(os.environ, env_vars):
        yield
