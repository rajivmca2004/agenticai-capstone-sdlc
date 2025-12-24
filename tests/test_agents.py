# Copyright (c) Microsoft. All rights reserved.
"""
Unit tests for Code Ingestion and Architect agents.

Tests the full agent pipeline: Ingestion → Architect
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# =============================================================================
# CODE INGESTION AGENT TESTS
# =============================================================================

class TestCodeIngestionAgent:
    """Tests for the Code Ingestion Agent node."""
    
    @pytest.mark.asyncio
    async def test_ingestion_success(
        self,
        sample_repo_url,
        sample_ref,
        mock_github_service,
        mock_llm_response,
    ):
        """Test successful repository ingestion."""
        from src.schemas import AgentState, IngestionPolicy, IngestionStatus
        from src.agents.code_ingestion_node import code_ingestion_node
        
        # Create initial state
        initial_state = AgentState(
            repo_url=sample_repo_url,
            ref=sample_ref,
            ingestion_policy=IngestionPolicy(),
        )
        
        # Mock dependencies
        with patch("src.agents.code_ingestion_node.get_github_service") as mock_gh:
            with patch("src.agents.code_ingestion_node.get_code_ingestion_llm") as mock_llm:
                mock_gh.return_value = mock_github_service
                
                mock_llm_instance = AsyncMock()
                mock_llm_instance.ainvoke.return_value = mock_llm_response
                mock_llm.return_value = mock_llm_instance
                
                # Execute node
                result = await code_ingestion_node(initial_state)
        
        # Assertions
        assert result["ingestion_status"] == IngestionStatus.COMPLETED
        assert result["repo_bundle"] is not None
        assert result["error"] is None
        
        bundle = result["repo_bundle"]
        assert bundle.repo_url == sample_repo_url
        assert bundle.ref == sample_ref
        assert bundle.total_files == 5
        assert "python" in bundle.languages
        assert len(bundle.code_files) == 2
        assert len(bundle.test_files) == 1
    
    @pytest.mark.asyncio
    async def test_ingestion_missing_repo_url(self):
        """Test ingestion fails when repo_url is missing."""
        from src.schemas import AgentState, IngestionStatus
        from src.agents.code_ingestion_node import code_ingestion_node
        
        # Create state without repo_url
        initial_state = AgentState(
            repo_url="",  # Empty URL
            ref="main",
        )
        
        # Execute node
        result = await code_ingestion_node(initial_state)
        
        # Assertions
        assert result["ingestion_status"] == IngestionStatus.FAILED
        assert "repo_url is required" in result["error"]
    
    @pytest.mark.asyncio
    async def test_ingestion_github_error(self, sample_repo_url):
        """Test ingestion handles GitHub errors gracefully."""
        from src.schemas import AgentState, IngestionStatus
        from src.agents.code_ingestion_node import code_ingestion_node
        from src.observability import RepositoryNotFoundError
        
        initial_state = AgentState(
            repo_url=sample_repo_url,
            ref="main",
        )
        
        with patch("src.agents.code_ingestion_node.get_github_service") as mock_gh:
            mock_service = MagicMock()
            mock_service.get_repository.side_effect = RepositoryNotFoundError(sample_repo_url)
            mock_gh.return_value = mock_service
            
            result = await code_ingestion_node(initial_state)
        
        assert result["ingestion_status"] == IngestionStatus.FAILED
        assert result["error"] is not None
        assert "failed" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_ingestion_llm_error(self, sample_repo_url, mock_github_service):
        """Test ingestion handles LLM errors gracefully."""
        from src.schemas import AgentState, IngestionStatus
        from src.agents.code_ingestion_node import code_ingestion_node
        
        initial_state = AgentState(
            repo_url=sample_repo_url,
            ref="main",
        )
        
        with patch("src.agents.code_ingestion_node.get_github_service") as mock_gh:
            with patch("src.agents.code_ingestion_node.get_code_ingestion_llm") as mock_llm:
                mock_gh.return_value = mock_github_service
                
                mock_llm_instance = AsyncMock()
                mock_llm_instance.ainvoke.side_effect = Exception("LLM API error")
                mock_llm.return_value = mock_llm_instance
                
                result = await code_ingestion_node(initial_state)
        
        assert result["ingestion_status"] == IngestionStatus.FAILED
        assert "failed" in result["error"].lower()


# =============================================================================
# ARCHITECT AGENT TESTS
# =============================================================================

class TestArchitectAgent:
    """Tests for the Architect Agent node."""
    
    @pytest.mark.asyncio
    async def test_architect_success(
        self,
        sample_repo_bundle,
        mock_business_report_response,
        mock_technical_report_response,
    ):
        """Test successful architecture analysis."""
        from src.schemas import AgentState
        from src.agents.architect_node import architect_node
        
        # Create state with repo bundle
        initial_state = AgentState(
            repo_url=sample_repo_bundle.repo_url,
            ref=sample_repo_bundle.ref,
            repo_bundle=sample_repo_bundle,
        )
        
        with patch("src.agents.architect_node.get_architect_llm") as mock_llm:
            mock_llm_instance = AsyncMock()
            # First call returns business report, second returns technical
            mock_llm_instance.ainvoke.side_effect = [
                mock_business_report_response,
                mock_technical_report_response,
            ]
            mock_llm.return_value = mock_llm_instance
            
            result = await architect_node(initial_state)
        
        # Assertions
        assert result["error"] is None
        assert result["business_report"] is not None
        assert result["technical_report"] is not None
        assert result["completed"] is True
        
        # Check business report
        biz = result["business_report"]
        assert biz.executive_summary is not None
        assert len(biz.options) >= 1
        
        # Check technical report
        tech = result["technical_report"]
        assert tech.codebase_map is not None
        assert len(tech.migration_plan) >= 1
        assert len(tech.backlog_slice) >= 1
    
    @pytest.mark.asyncio
    async def test_architect_missing_repo_bundle(self):
        """Test architect fails without repo bundle."""
        from src.schemas import AgentState
        from src.agents.architect_node import architect_node
        
        # Create state without repo bundle
        initial_state = AgentState(
            repo_url="https://github.com/owner/repo",
            ref="main",
            repo_bundle=None,
        )
        
        result = await architect_node(initial_state)
        
        assert result["error"] is not None
        assert "repo_bundle" in result["error"].lower() or "bundle" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_architect_llm_error(self, sample_repo_bundle):
        """Test architect handles LLM errors gracefully."""
        from src.schemas import AgentState
        from src.agents.architect_node import architect_node
        
        initial_state = AgentState(
            repo_url=sample_repo_bundle.repo_url,
            ref=sample_repo_bundle.ref,
            repo_bundle=sample_repo_bundle,
        )
        
        with patch("src.agents.architect_node.get_architect_llm") as mock_llm:
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke.side_effect = Exception("LLM error")
            mock_llm.return_value = mock_llm_instance
            
            result = await architect_node(initial_state)
        
        assert result["error"] is not None


# =============================================================================
# FULL PIPELINE TESTS (Ingestion → Architect)
# =============================================================================

class TestAgentPipeline:
    """Tests for the full agent pipeline."""
    
    @pytest.mark.asyncio
    async def test_full_pipeline_success(
        self,
        sample_repo_url,
        mock_github_service,
        mock_llm_response,
        mock_business_report_response,
        mock_technical_report_response,
    ):
        """Test full pipeline: Ingestion → Architect."""
        from src.schemas import AgentState, IngestionPolicy, IngestionStatus
        from src.agents.code_ingestion_node import code_ingestion_node
        from src.agents.architect_node import architect_node
        
        # STEP 1: Run Code Ingestion Agent
        initial_state = AgentState(
            repo_url=sample_repo_url,
            ref="main",
            ingestion_policy=IngestionPolicy(),
        )
        
        with patch("src.agents.code_ingestion_node.get_github_service") as mock_gh:
            with patch("src.agents.code_ingestion_node.get_code_ingestion_llm") as mock_llm:
                mock_gh.return_value = mock_github_service
                
                mock_llm_instance = AsyncMock()
                mock_llm_instance.ainvoke.return_value = mock_llm_response
                mock_llm.return_value = mock_llm_instance
                
                ingestion_result = await code_ingestion_node(initial_state)
        
        # Verify ingestion succeeded
        assert ingestion_result["ingestion_status"] == IngestionStatus.COMPLETED
        assert ingestion_result["repo_bundle"] is not None
        
        # STEP 2: Run Architect Agent with ingestion output
        # Create new state with repo bundle from ingestion
        architect_state = AgentState(
            repo_url=sample_repo_url,
            ref="main",
            repo_bundle=ingestion_result["repo_bundle"],
            ingestion_status=ingestion_result["ingestion_status"],
            messages=ingestion_result["messages"],
        )
        
        with patch("src.agents.architect_node.get_architect_llm") as mock_llm:
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke.side_effect = [
                mock_business_report_response,
                mock_technical_report_response,
            ]
            mock_llm.return_value = mock_llm_instance
            
            architect_result = await architect_node(architect_state)
        
        # Verify architect succeeded
        assert architect_result["error"] is None
        assert architect_result["business_report"] is not None
        assert architect_result["technical_report"] is not None
        
        # Verify outputs are meaningful
        assert architect_result["business_report"].executive_summary
        assert len(architect_result["business_report"].options) > 0
        assert len(architect_result["technical_report"].migration_plan) > 0
    
    @pytest.mark.asyncio
    async def test_pipeline_stops_on_ingestion_failure(self, sample_repo_url):
        """Test pipeline stops when ingestion fails."""
        from src.schemas import AgentState, IngestionStatus
        from src.agents.code_ingestion_node import code_ingestion_node
        from src.graph import should_continue_to_architect
        
        # Create state with empty URL to trigger failure
        initial_state = AgentState(
            repo_url="",
            ref="main",
        )
        
        ingestion_result = await code_ingestion_node(initial_state)
        
        # Verify ingestion failed
        assert ingestion_result["ingestion_status"] == IngestionStatus.FAILED
        
        # Create state for routing decision
        failed_state = AgentState(
            repo_url="",
            ref="main",
            ingestion_status=ingestion_result["ingestion_status"],
            repo_bundle=None,
        )
        
        # Verify routing goes to end, not architect
        routing = should_continue_to_architect(failed_state)
        assert routing == "end"
    
    @pytest.mark.asyncio
    async def test_pipeline_routes_to_architect_on_success(
        self,
        sample_repo_bundle,
    ):
        """Test pipeline routes to architect after successful ingestion."""
        from src.schemas import AgentState, IngestionStatus
        from src.graph import should_continue_to_architect
        
        # Create successful state
        success_state = AgentState(
            repo_url=sample_repo_bundle.repo_url,
            ref=sample_repo_bundle.ref,
            ingestion_status=IngestionStatus.COMPLETED,
            repo_bundle=sample_repo_bundle,
        )
        
        # Verify routing goes to architect
        routing = should_continue_to_architect(success_state)
        assert routing == "architect"


# =============================================================================
# GRAPH INTEGRATION TESTS
# =============================================================================

class TestGraphIntegration:
    """Tests for the LangGraph orchestration."""
    
    @pytest.mark.asyncio
    async def test_graph_creation(self):
        """Test graph can be created."""
        from src.graph import create_comprehension_graph
        
        graph = create_comprehension_graph()
        
        assert graph is not None
    
    @pytest.mark.asyncio
    async def test_graph_execution_full_workflow(
        self,
        sample_repo_url,
        mock_github_service,
        mock_llm_response,
        mock_business_report_response,
        mock_technical_report_response,
    ):
        """Test full graph execution."""
        from src.schemas import AgentState, IngestionPolicy
        from src.graph import create_comprehension_graph
        
        # Create graph
        graph = create_comprehension_graph()
        
        # Create initial state
        initial_state = AgentState(
            repo_url=sample_repo_url,
            ref="main",
            ingestion_policy=IngestionPolicy(),
        )
        
        # Mock all external dependencies
        with patch("src.agents.code_ingestion_node.get_github_service") as mock_gh:
            with patch("src.agents.code_ingestion_node.get_code_ingestion_llm") as mock_ing_llm:
                with patch("src.agents.architect_node.get_architect_llm") as mock_arch_llm:
                    # Setup ingestion mocks
                    mock_gh.return_value = mock_github_service
                    
                    mock_ing_llm_instance = AsyncMock()
                    mock_ing_llm_instance.ainvoke.return_value = mock_llm_response
                    mock_ing_llm.return_value = mock_ing_llm_instance
                    
                    # Setup architect mocks
                    mock_arch_llm_instance = AsyncMock()
                    mock_arch_llm_instance.ainvoke.side_effect = [
                        mock_business_report_response,
                        mock_technical_report_response,
                    ]
                    mock_arch_llm.return_value = mock_arch_llm_instance
                    
                    # Run graph
                    config = {"configurable": {"thread_id": "test-thread"}}
                    
                    final_state = None
                    async for event in graph.astream(initial_state, config):
                        for node_name, state_update in event.items():
                            final_state = state_update
        
        # Assertions
        assert final_state is not None


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in agents."""
    
    @pytest.mark.asyncio
    async def test_ingestion_handles_invalid_json_response(
        self,
        sample_repo_url,
        mock_github_service,
    ):
        """Test ingestion handles invalid JSON from LLM."""
        from src.schemas import AgentState, IngestionStatus
        from src.agents.code_ingestion_node import code_ingestion_node
        
        initial_state = AgentState(
            repo_url=sample_repo_url,
            ref="main",
        )
        
        # Mock LLM returning invalid JSON
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON at all"
        
        with patch("src.agents.code_ingestion_node.get_github_service") as mock_gh:
            with patch("src.agents.code_ingestion_node.get_code_ingestion_llm") as mock_llm:
                mock_gh.return_value = mock_github_service
                
                mock_llm_instance = AsyncMock()
                mock_llm_instance.ainvoke.return_value = mock_response
                mock_llm.return_value = mock_llm_instance
                
                result = await code_ingestion_node(initial_state)
        
        # Should still complete (with empty analysis)
        assert result["ingestion_status"] == IngestionStatus.COMPLETED
        assert result["repo_bundle"] is not None
    
    @pytest.mark.asyncio
    async def test_architect_handles_invalid_json_response(
        self,
        sample_repo_bundle,
    ):
        """Test architect handles invalid JSON from LLM."""
        from src.schemas import AgentState
        from src.agents.architect_node import architect_node
        
        initial_state = AgentState(
            repo_url=sample_repo_bundle.repo_url,
            ref=sample_repo_bundle.ref,
            repo_bundle=sample_repo_bundle,
        )
        
        # Mock LLM returning invalid JSON
        mock_response = MagicMock()
        mock_response.content = "Not valid JSON"
        
        with patch("src.agents.architect_node.get_architect_llm") as mock_llm:
            mock_llm_instance = AsyncMock()
            mock_llm_instance.ainvoke.return_value = mock_response
            mock_llm.return_value = mock_llm_instance
            
            result = await architect_node(initial_state)
        
        # Should still complete (with empty reports)
        assert result["error"] is None
        assert result["business_report"] is not None
        assert result["technical_report"] is not None
