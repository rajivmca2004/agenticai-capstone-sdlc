# Copyright (c) Microsoft. All rights reserved.
"""
Unit tests for the REST API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# API CLIENT FIXTURE
# =============================================================================

@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    from fastapi.testclient import TestClient
    from src.api import app
    
    return TestClient(app)


# =============================================================================
# HEALTH ENDPOINT TESTS
# =============================================================================

class TestHealthEndpoint:
    """Tests for the /health endpoint."""
    
    def test_health_check(self, test_client):
        """Test health endpoint returns healthy status."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.2.0"
        assert "code_ingestion" in data["agents"]
        assert "architect" in data["agents"]


# =============================================================================
# METRICS ENDPOINT TESTS
# =============================================================================

class TestMetricsEndpoint:
    """Tests for the /metrics endpoint."""
    
    def test_metrics_endpoint(self, test_client):
        """Test metrics endpoint returns metrics."""
        response = test_client.get("/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "counters" in data
        assert "gauges" in data
        assert "histograms" in data


# =============================================================================
# ANALYSIS ENDPOINT TESTS
# =============================================================================

class TestAnalysisEndpoints:
    """Tests for the /analyze endpoints."""
    
    def test_start_analysis_returns_job_id(self, test_client):
        """Test POST /analyze returns job ID."""
        response = test_client.post(
            "/analyze",
            json={
                "repo_url": "https://github.com/microsoft/vscode",
                "ref": "main",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "message" in data
    
    def test_start_analysis_with_full_options(self, test_client):
        """Test POST /analyze with all options."""
        response = test_client.post(
            "/analyze",
            json={
                "repo_url": "https://github.com/owner/repo",
                "ref": "develop",
                "business_objective": "Migrate to Azure",
                "constraints": ["Budget < $100k"],
                "kpis": ["99.9% uptime"],
                "compliance": ["SOC2"],
                "target_platforms": ["Azure AKS"],
                "target_patterns": ["Microservices"],
                "include_tests": True,
                "max_file_mb": 1.5,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
    
    def test_get_nonexistent_job(self, test_client):
        """Test GET /analyze/{job_id} for nonexistent job."""
        response = test_client.get("/analyze/nonexistent-job-id")
        
        assert response.status_code == 404
    
    def test_get_job_status(self, test_client):
        """Test GET /analyze/{job_id} for existing job."""
        # First create a job
        create_response = test_client.post(
            "/analyze",
            json={
                "repo_url": "https://github.com/owner/repo",
                "ref": "main",
            },
        )
        job_id = create_response.json()["job_id"]
        
        # Then get its status
        response = test_client.get(f"/analyze/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert "status" in data
        assert "created_at" in data
    
    def test_list_jobs(self, test_client):
        """Test GET /jobs lists all jobs."""
        # Create a job first
        test_client.post(
            "/analyze",
            json={
                "repo_url": "https://github.com/owner/repo",
                "ref": "main",
            },
        )
        
        # List jobs
        response = test_client.get("/jobs")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_delete_job(self, test_client):
        """Test DELETE /analyze/{job_id}."""
        # Create a job
        create_response = test_client.post(
            "/analyze",
            json={
                "repo_url": "https://github.com/owner/repo",
                "ref": "main",
            },
        )
        job_id = create_response.json()["job_id"]
        
        # Delete it
        response = test_client.delete(f"/analyze/{job_id}")
        
        assert response.status_code == 200
        
        # Verify it's gone
        get_response = test_client.get(f"/analyze/{job_id}")
        assert get_response.status_code == 404
    
    def test_delete_nonexistent_job(self, test_client):
        """Test DELETE /analyze/{job_id} for nonexistent job."""
        response = test_client.delete("/analyze/nonexistent-id")
        
        assert response.status_code == 404


# =============================================================================
# SYNC ANALYSIS TESTS
# =============================================================================

class TestSyncAnalysis:
    """Tests for synchronous analysis endpoint."""
    
    @pytest.mark.asyncio
    async def test_sync_analysis_success(
        self,
        test_client,
        mock_github_service,
        mock_llm_response,
        mock_business_report_response,
        mock_technical_report_response,
    ):
        """Test POST /analyze/sync returns results."""
        with patch("src.agents.code_ingestion_node.get_github_service") as mock_gh:
            with patch("src.agents.code_ingestion_node.get_code_ingestion_llm") as mock_ing_llm:
                with patch("src.agents.architect_node.get_architect_llm") as mock_arch_llm:
                    mock_gh.return_value = mock_github_service
                    
                    mock_ing_llm_instance = AsyncMock()
                    mock_ing_llm_instance.ainvoke.return_value = mock_llm_response
                    mock_ing_llm.return_value = mock_ing_llm_instance
                    
                    mock_arch_llm_instance = AsyncMock()
                    mock_arch_llm_instance.ainvoke.side_effect = [
                        mock_business_report_response,
                        mock_technical_report_response,
                    ]
                    mock_arch_llm.return_value = mock_arch_llm_instance
                    
                    response = test_client.post(
                        "/analyze/sync",
                        json={
                            "repo_url": "https://github.com/microsoft/test",
                            "ref": "main",
                        },
                    )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "result" in data


# =============================================================================
# CORRELATION ID TESTS
# =============================================================================

class TestCorrelationId:
    """Tests for correlation ID handling."""
    
    def test_custom_correlation_id(self, test_client):
        """Test custom X-Correlation-ID is used."""
        custom_id = "my-custom-trace-id-123"
        
        response = test_client.get(
            "/health",
            headers={"X-Correlation-ID": custom_id},
        )
        
        assert response.status_code == 200
        assert response.headers.get("X-Correlation-ID") == custom_id
    
    def test_generated_correlation_id(self, test_client):
        """Test correlation ID is generated if not provided."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None
        assert len(correlation_id) > 0


# =============================================================================
# VALIDATION TESTS
# =============================================================================

class TestRequestValidation:
    """Tests for request validation."""
    
    def test_missing_repo_url(self, test_client):
        """Test POST /analyze fails without repo_url."""
        response = test_client.post(
            "/analyze",
            json={
                "ref": "main",
            },
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_invalid_json(self, test_client):
        """Test POST /analyze fails with invalid JSON."""
        response = test_client.post(
            "/analyze",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        
        assert response.status_code == 422
