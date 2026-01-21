#!/usr/bin/env python3
"""CLI runner for LLM-evaluated architectural analysis benchmarks.

Usage:
    # Run single task evaluation
    python -m tests.benchmarks.run_llm_benchmarks --task sia-trace-001 --tool sia-code --judge gpt-4o

    # Run comparison across multiple tools
    python -m tests.benchmarks.run_llm_benchmarks --task sia-arch-001 --compare sia-code,grep --judge claude-opus

    # Run full benchmark suite
    python -m tests.benchmarks.run_llm_benchmarks --suite sia-code --judges gpt-4o,claude-opus --output results/
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

from .tasks.architectural_tasks import (
    get_all_tasks,
    get_tasks_by_codebase,
    ArchitecturalTask,
)
from .llm_evaluation import create_judge, save_evaluation_results, EvaluationResult


def dummy_sia_code_retriever(task: ArchitecturalTask, top_k: int = 10) -> List[str]:
    """Dummy retriever - replace with actual sia-code integration.

    Args:
        task: The architectural task
        top_k: Number of chunks to retrieve

    Returns:
        List of retrieved code chunks
    """
    # TODO: Integrate with actual sia-code backend
    # For now, return placeholder
    return [
        f"# Placeholder chunk {i + 1} for task: {task.task_id}\n"
        f"# This would be actual code retrieved by sia-code\n"
        f"# Question: {task.question}"
        for i in range(min(top_k, 3))
    ]


def dummy_grep_retriever(task: ArchitecturalTask) -> List[str]:
    """Dummy grep-based retriever - replace with actual implementation.

    Args:
        task: The architectural task

    Returns:
        List of grep results
    """
    # TODO: Implement actual grep-based retrieval
    return [
        f"# Grep result {i + 1} for task: {task.task_id}\n# Simple text search results\n"
        for i in range(2)
    ]


def generate_tool_response(task: ArchitecturalTask, tool_name: str, retriever_fn) -> str:
    """Generate a tool's response to an architectural task.

    Args:
        task: The architectural task
        tool_name: Name of the tool
        retriever_fn: Function to retrieve code chunks

    Returns:
        Tool's response to the task
    """
    # Retrieve chunks
    chunks = retriever_fn(task)

    # Format response (in real implementation, this would use the tool's actual logic)
    response = f"# {tool_name.upper()} Analysis\n\n"
    response += f"Question: {task.question}\n\n"
    response += f"Retrieved {len(chunks)} code chunks:\n\n"

    for i, chunk in enumerate(chunks, 1):
        response += f"## Chunk {i}\n{chunk}\n\n"

    response += "## Analysis\n"
    response += f"Based on the retrieved code, this is a {task.task_type} task with "
    response += f"{task.difficulty} difficulty.\n"

    # Add placeholder analysis
    response += "\n[Tool would provide detailed architectural analysis here]\n"

    return response


def run_single_evaluation(
    task_id: str, tool_name: str, judge_model: str, rubric: str = "comprehensive"
) -> EvaluationResult:
    """Run evaluation for a single task and tool.

    Args:
        task_id: ID of the task to evaluate
        tool_name: Name of the tool to evaluate
        judge_model: Model to use as judge
        rubric: Scoring rubric to use

    Returns:
        Evaluation result
    """
    # Get task
    tasks = {t.task_id: t for t in get_all_tasks()}
    if task_id not in tasks:
        raise ValueError(f"Task not found: {task_id}")

    task = tasks[task_id]

    # Select retriever
    if tool_name == "sia-code":
        retriever = dummy_sia_code_retriever
    elif tool_name == "grep":
        retriever = dummy_grep_retriever
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

    # Generate tool response
    tool_response = generate_tool_response(task, tool_name, retriever)

    # Create judge and evaluate
    judge = create_judge(judge_model, rubric)
    result = judge.evaluate(task, tool_response, tool_name)

    return result


def run_comparison(task_id: str, tool_names: List[str], judge_model: str) -> Dict[str, Any]:
    """Run side-by-side comparison of multiple tools.

    Args:
        task_id: ID of the task to evaluate
        tool_names: List of tool names to compare
        judge_model: Model to use as judge

    Returns:
        Comparison results
    """
    # Get task
    tasks = {t.task_id: t for t in get_all_tasks()}
    if task_id not in tasks:
        raise ValueError(f"Task not found: {task_id}")

    task = tasks[task_id]

    # Generate responses from all tools
    tool_responses = {}
    for tool_name in tool_names:
        if tool_name == "sia-code":
            retriever = dummy_sia_code_retriever
        elif tool_name == "grep":
            retriever = dummy_grep_retriever
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool_responses[tool_name] = generate_tool_response(task, tool_name, retriever)

    # Create judge and compare
    judge = create_judge(judge_model, "comprehensive")
    comparison = judge.compare_tools(task, tool_responses)

    return comparison


def run_benchmark_suite(
    codebase: str,
    tools: List[str],
    judges: List[str],
    output_dir: Path,
    rubric: str = "comprehensive",
) -> None:
    """Run complete benchmark suite for a codebase.

    Args:
        codebase: Name of the codebase (e.g., 'sia-code', 'flask')
        tools: List of tools to benchmark
        judges: List of judge models to use
        output_dir: Directory to save results
        rubric: Scoring rubric to use
    """
    # Get tasks for codebase
    tasks = get_tasks_by_codebase(codebase)

    if not tasks:
        print(f"No tasks found for codebase: {codebase}")
        return

    print(f"\n=== Running {len(tasks)} tasks for {codebase} ===")
    print(f"Tools: {', '.join(tools)}")
    print(f"Judges: {', '.join(judges)}")
    print(f"Rubric: {rubric}\n")

    # Run evaluations
    all_results = []

    for task in tasks:
        print(f"\nTask: {task.task_id} ({task.difficulty}, {task.task_type})")
        print(f"Question: {task.question}")

        for tool_name in tools:
            print(f"  Evaluating {tool_name}...")

            for judge_model in judges:
                try:
                    result = run_single_evaluation(task.task_id, tool_name, judge_model, rubric)
                    all_results.append(result)

                    print(f"    {judge_model}: {result.score:.1f}/100")
                    print(
                        f"      Coverage: {result.file_coverage:.1f}F {result.concept_coverage:.1f}C"
                    )
                    print(
                        f"      Quality: {result.accuracy:.1f}A {result.completeness:.1f}C {result.clarity:.1f}Cl"
                    )

                except Exception as e:
                    print(f"    {judge_model}: ERROR - {e}")

    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file = output_dir / f"{codebase}_results.json"
    save_evaluation_results(all_results, results_file)

    print(f"\n=== Results saved to {results_file} ===")

    # Print summary
    print("\n=== Summary ===")
    for tool_name in tools:
        tool_results = [r for r in all_results if r.tool_name == tool_name]
        if tool_results:
            avg_score = sum(r.score for r in tool_results) / len(tool_results)
            print(f"{tool_name}: {avg_score:.1f}/100 (avg across {len(tool_results)} evaluations)")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run LLM-evaluated architectural analysis benchmarks"
    )

    parser.add_argument("--task", help="Task ID to evaluate (e.g., sia-trace-001)")
    parser.add_argument("--tool", help="Tool to evaluate (sia-code, grep)")
    parser.add_argument(
        "--compare", help="Comma-separated list of tools to compare (e.g., sia-code,grep)"
    )
    parser.add_argument(
        "--judge",
        default="gpt-4o",
        help="Judge model (gpt-4o, claude-opus-4-20250514, gemini-2.0-flash-exp)",
    )
    parser.add_argument("--suite", help="Run full suite for codebase (sia-code, flask, fastapi)")
    parser.add_argument(
        "--judges", help="Comma-separated list of judges for suite (e.g., gpt-4o,claude-opus)"
    )
    parser.add_argument(
        "--rubric",
        default="comprehensive",
        choices=["comprehensive", "quick", "strict"],
        help="Scoring rubric to use",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark_results"),
        help="Output directory for results",
    )
    parser.add_argument("--list-tasks", action="store_true", help="List all available tasks")

    args = parser.parse_args()

    # List tasks
    if args.list_tasks:
        tasks = get_all_tasks()
        print(f"\n=== {len(tasks)} Available Tasks ===\n")
        for task in tasks:
            print(f"{task.task_id}: {task.question}")
            print(
                f"  Codebase: {task.codebase}, Difficulty: {task.difficulty}, Type: {task.task_type}"
            )
            print()
        return

    # Run benchmark suite
    if args.suite:
        tools = args.compare.split(",") if args.compare else ["sia-code"]
        judges = args.judges.split(",") if args.judges else [args.judge]

        run_benchmark_suite(args.suite, tools, judges, args.output, args.rubric)
        return

    # Run comparison
    if args.compare:
        if not args.task:
            print("Error: --task required for comparison")
            sys.exit(1)

        tools = args.compare.split(",")
        result = run_comparison(args.task, tools, args.judge)

        print("\n=== Comparison Results ===")
        print(json.dumps(result, indent=2))
        return

    # Run single evaluation
    if args.task and args.tool:
        result = run_single_evaluation(args.task, args.tool, args.judge, args.rubric)

        print("\n=== Evaluation Result ===")
        print(f"Task: {result.task_id}")
        print(f"Tool: {result.tool_name}")
        print(f"Judge: {result.judge_model}")
        print(f"\nOverall Score: {result.score}/100")
        print(f"\nBreakdown:")
        print(f"  File Coverage: {result.file_coverage}/100")
        print(f"  Concept Coverage: {result.concept_coverage}/100")
        print(f"  Accuracy: {result.accuracy}/100")
        print(f"  Completeness: {result.completeness}/100")
        print(f"  Clarity: {result.clarity}/100")
        print(f"\nReasoning:\n{result.reasoning}")

        if result.missing_elements:
            print(f"\nMissing Elements:")
            for elem in result.missing_elements:
                print(f"  - {elem}")

        if result.strengths:
            print(f"\nStrengths:")
            for strength in result.strengths:
                print(f"  + {strength}")

        if result.weaknesses:
            print(f"\nWeaknesses:")
            for weakness in result.weaknesses:
                print(f"  - {weakness}")

        return

    # No valid arguments
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
