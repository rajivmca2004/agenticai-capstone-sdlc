# Copyright (c) Microsoft. All rights reserved.
"""
Main entry point for the Code Comprehension Agentic AI Solution.

This module provides CLI commands to run the workflow.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def setup_langsmith():
    """Configure LangSmith tracing if enabled."""
    if os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true":
        print("🔍 LangSmith tracing enabled")
        print(f"   Project: {os.getenv('LANGCHAIN_PROJECT', 'default')}")


async def run_workflow(
    repo_url: str,
    ref: str = "main",
    output_dir: str = "output",
    business_objective: str | None = None,
    target_platforms: list[str] | None = None,
    verbose: bool = False,
):
    """
    Run the full code comprehension workflow.
    
    Args:
        repo_url: GitHub repository URL
        ref: Git reference (branch, tag, commit)
        output_dir: Directory for generated reports
        business_objective: Optional business context
        target_platforms: Optional target platforms
        verbose: Enable verbose output
    """
    from src.graph import stream_comprehension_workflow
    
    print("🚀 Starting Code Comprehension Workflow")
    print(f"   Repository: {repo_url}")
    print(f"   Reference: {ref}")
    print(f"   Output: {output_dir}")
    print()
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate thread ID for this run
    thread_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    final_state = None
    
    # Stream workflow with progress updates
    async for node_name, state_update in stream_comprehension_workflow(
        repo_url=repo_url,
        ref=ref,
        thread_id=thread_id,
    ):
        if node_name == "code_ingestion":
            print("📦 Code Ingestion Agent")
            if "ingestion_status" in state_update:
                status = state_update["ingestion_status"]
                print(f"   Status: {status.value if hasattr(status, 'value') else status}")
            if "repo_bundle" in state_update and state_update["repo_bundle"]:
                bundle = state_update["repo_bundle"]
                print(f"   Files: {bundle.total_files}")
                print(f"   Languages: {', '.join(bundle.languages[:5])}")
                print(f"   Dependencies: {len(bundle.dependencies)}")
                print(f"   Risks: {len(bundle.risks)}")
            if "error" in state_update and state_update["error"]:
                print(f"   ❌ Error: {state_update['error']}")
            print()
            
        elif node_name == "architect":
            print("🏗️  Architect Agent")
            if "business_report" in state_update and state_update["business_report"]:
                report = state_update["business_report"]
                print(f"   Business Report: Generated with {len(report.options)} options")
            if "technical_report" in state_update and state_update["technical_report"]:
                report = state_update["technical_report"]
                print(f"   Technical Report: Generated")
                print(f"   Migration Waves: {len(report.migration_plan)}")
                print(f"   Backlog Items: {len(report.backlog_slice)}")
            if "error" in state_update and state_update["error"]:
                print(f"   ❌ Error: {state_update['error']}")
            print()
        
        final_state = state_update
    
    # Save outputs
    if final_state:
        print("💾 Saving Reports...")
        
        # Save business report
        if hasattr(final_state, 'business_report') and final_state.business_report:
            biz_report = final_state.business_report
            biz_path = output_path / "business_report.md"
            with open(biz_path, "w") as f:
                f.write("# Business Comprehension Report\n\n")
                f.write(f"## Executive Summary\n\n{biz_report.executive_summary}\n\n")
                f.write(f"## Current State\n\n{biz_report.current_state}\n\n")
                f.write("## Options Analysis\n\n")
                f.write("| Option | Description | Effort | Risk | Recommended |\n")
                f.write("|--------|-------------|--------|------|-------------|\n")
                for opt in biz_report.options:
                    rec = "✅" if opt.recommended else ""
                    f.write(f"| {opt.name} | {opt.description[:50]}... | {opt.effort.value} | {opt.risk_level.value} | {rec} |\n")
                f.write(f"\n## Value & KPIs\n\n{biz_report.value_and_kpis}\n\n")
                f.write(f"## Adoption Roadmap\n\n{biz_report.adoption_plan}\n\n")
                if biz_report.diagram_mermaid:
                    f.write(f"## Architecture Diagram\n\n```mermaid\n{biz_report.diagram_mermaid}\n```\n")
            print(f"   ✅ {biz_path}")
        
        # Save technical report
        if hasattr(final_state, 'technical_report') and final_state.technical_report:
            tech_report = final_state.technical_report
            tech_path = output_path / "technical_report.md"
            with open(tech_path, "w") as f:
                f.write("# Technical Comprehension Report\n\n")
                f.write(f"## 1. Codebase Map\n\n{tech_report.codebase_map}\n\n")
                f.write(f"## 2. Topology\n\n{tech_report.topology}\n\n")
                f.write(f"## 3. Security & Compliance\n\n{tech_report.security_compliance}\n\n")
                f.write(f"## 4. Non-Functional Requirements\n\n{tech_report.nfrs}\n\n")
                f.write("## 5. Risk Register\n\n")
                f.write("| ID | Category | Severity | Title |\n")
                f.write("|----|----------|----------|-------|\n")
                for risk in tech_report.risk_register:
                    f.write(f"| {risk.id} | {risk.category} | {risk.severity.value} | {risk.title} |\n")
                f.write(f"\n## 6. Target Architecture\n\n{tech_report.target_architecture}\n\n")
                if tech_report.architecture_diagram_mermaid:
                    f.write(f"```mermaid\n{tech_report.architecture_diagram_mermaid}\n```\n\n")
                f.write("## 7. Migration Playbook\n\n")
                for wave in tech_report.migration_plan:
                    f.write(f"### Wave {wave.wave_number}: {wave.name} ({wave.duration_weeks} weeks)\n\n")
                    for task in wave.tasks:
                        f.write(f"- {task}\n")
                    f.write("\n")
                f.write("## 8. Backlog Slice\n\n")
                f.write("| ID | Title | Effort | Sprint |\n")
                f.write("|----|-------|--------|--------|\n")
                for item in tech_report.backlog_slice:
                    f.write(f"| {item.id} | {item.title} | {item.effort.value} | {item.sprint} |\n")
            print(f"   ✅ {tech_path}")
        
        # Save repo bundle as JSON
        if hasattr(final_state, 'repo_bundle') and final_state.repo_bundle:
            bundle_path = output_path / "repo_bundle.json"
            with open(bundle_path, "w") as f:
                json.dump(final_state.repo_bundle.model_dump(mode="json"), f, indent=2, default=str)
            print(f"   ✅ {bundle_path}")
        
        print()
        print("✅ Workflow completed successfully!")
    else:
        print("❌ Workflow failed - no output generated")
        sys.exit(1)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Code Comprehension Agentic AI Solution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a public repository
  python -m src.main https://github.com/microsoft/vscode
  
  # Analyze a specific branch
  python -m src.main https://github.com/owner/repo --ref develop
  
  # Specify output directory
  python -m src.main https://github.com/owner/repo --output reports/
  
  # With business context
  python -m src.main https://github.com/owner/repo --objective "Migrate to Azure AKS"
        """,
    )
    
    parser.add_argument(
        "repo_url",
        help="GitHub repository URL to analyze",
    )
    parser.add_argument(
        "--ref", "-r",
        default="main",
        help="Git reference (branch, tag, or commit). Default: main",
    )
    parser.add_argument(
        "--output", "-o",
        default="output",
        help="Output directory for reports. Default: output/",
    )
    parser.add_argument(
        "--objective",
        help="Business objective for the analysis",
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        help="Target platforms (e.g., 'Azure AKS' 'Azure SQL')",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--graph",
        action="store_true",
        help="Print the workflow graph and exit",
    )
    
    args = parser.parse_args()
    
    # Print graph if requested
    if args.graph:
        from src.graph import get_graph_mermaid
        print(get_graph_mermaid())
        return
    
    # Setup tracing
    setup_langsmith()
    
    # Run workflow
    asyncio.run(run_workflow(
        repo_url=args.repo_url,
        ref=args.ref,
        output_dir=args.output,
        business_objective=args.objective,
        target_platforms=args.platforms,
        verbose=args.verbose,
    ))


if __name__ == "__main__":
    main()
