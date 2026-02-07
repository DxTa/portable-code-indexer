"""LLM-as-judge evaluation framework for architectural analysis benchmarks.

This module implements the evaluation infrastructure for comparing code retrieval
tools using LLM judges (GPT-4o, Claude Opus, Gemini Pro).
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Protocol
from pathlib import Path

from .tasks.architectural_tasks import ArchitecturalTask
from .tasks.evaluation_prompts import (
    create_judge_prompt,
    create_comparison_prompt,
    create_retrieval_quality_prompt,
)


class LLMClient(Protocol):
    """Protocol for LLM client implementations."""

    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        """Generate a completion from the LLM.

        Args:
            prompt: The prompt to send to the LLM
            temperature: Sampling temperature (0.0 for deterministic)

        Returns:
            Generated text response
        """
        ...


@dataclass
class EvaluationResult:
    """Results from LLM judge evaluation.

    Attributes:
        task_id: Unique identifier for the task
        tool_name: Name of the tool being evaluated
        judge_model: Model used as judge (e.g., 'gpt-4o', 'claude-opus')
        score: Overall score (0-100)
        file_coverage: File coverage score (0-100)
        concept_coverage: Concept coverage score (0-100)
        accuracy: Accuracy score (0-100)
        completeness: Completeness score (0-100)
        clarity: Clarity score (0-100)
        reasoning: Detailed explanation of the score
        missing_elements: List of critical missing information
        strengths: List of response strengths
        weaknesses: List of response weaknesses
        raw_response: Raw JSON response from judge
    """

    task_id: str
    tool_name: str
    judge_model: str
    score: float
    file_coverage: float
    concept_coverage: float
    accuracy: float
    completeness: float
    clarity: float
    reasoning: str
    missing_elements: List[str]
    strengths: List[str]
    weaknesses: List[str]
    raw_response: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class OpenAIClient:
    """OpenAI API client for LLM judge evaluation."""

    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None):
        """Initialize OpenAI client.

        Args:
            model: Model name (gpt-4o, gpt-4-turbo, etc.)
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")

        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        """Generate completion using OpenAI API."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""


class AnthropicClient:
    """Anthropic API client for LLM judge evaluation."""

    def __init__(self, model: str = "claude-opus-4-20250514", api_key: Optional[str] = None):
        """Initialize Anthropic client.

        Args:
            model: Model name (claude-opus-4, claude-sonnet-4, etc.)
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "Anthropic package not installed. Install with: pip install anthropic"
            )

        self.model = model
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        """Generate completion using Anthropic API."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


class GeminiClient:
    """Google Gemini API client for LLM judge evaluation."""

    def __init__(self, model: str = "gemini-2.0-flash-exp", api_key: Optional[str] = None):
        """Initialize Gemini client.

        Args:
            model: Model name (gemini-2.0-flash-exp, etc.)
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
        """
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "Google Generative AI package not installed. "
                "Install with: pip install google-generativeai"
            )

        self.model = model
        genai.configure(api_key=api_key or os.getenv("GOOGLE_API_KEY"))
        self.client = genai.GenerativeModel(model)

    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        """Generate completion using Gemini API."""
        response = self.client.generate_content(
            prompt,
            generation_config={"temperature": temperature},
        )
        return response.text


class LLMJudge:
    """LLM-as-judge evaluator for code analysis quality."""

    def __init__(self, client: LLMClient, model_name: str, rubric: str = "comprehensive"):
        """Initialize LLM judge.

        Args:
            client: LLM client implementation
            model_name: Name of the judge model (for logging)
            rubric: Scoring rubric to use (comprehensive/quick/strict)
        """
        self.client = client
        self.model_name = model_name
        self.rubric = rubric

    def evaluate(
        self, task: ArchitecturalTask, tool_response: str, tool_name: str
    ) -> EvaluationResult:
        """Evaluate a tool's response to an architectural task.

        Args:
            task: The architectural task
            tool_response: The tool's response to evaluate
            tool_name: Name of the tool being evaluated

        Returns:
            Evaluation result with scores and detailed feedback
        """
        # Create judge prompt
        prompt = create_judge_prompt(task, tool_response, self.rubric)

        # Get judge evaluation
        raw_response = self.client.generate(prompt, temperature=0.0)

        # Parse JSON response
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in raw_response:
                json_str = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                json_str = raw_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = raw_response.strip()

            evaluation = json.loads(json_str)

            return EvaluationResult(
                task_id=task.task_id,
                tool_name=tool_name,
                judge_model=self.model_name,
                score=float(evaluation.get("score", 0)),
                file_coverage=float(evaluation.get("file_coverage", 0)),
                concept_coverage=float(evaluation.get("concept_coverage", 0)),
                accuracy=float(evaluation.get("accuracy", 0)),
                completeness=float(evaluation.get("completeness", 0)),
                clarity=float(evaluation.get("clarity", 0)),
                reasoning=evaluation.get("reasoning", ""),
                missing_elements=evaluation.get("missing_elements", []),
                strengths=evaluation.get("strengths", []),
                weaknesses=evaluation.get("weaknesses", []),
                raw_response=raw_response,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback if JSON parsing fails
            return EvaluationResult(
                task_id=task.task_id,
                tool_name=tool_name,
                judge_model=self.model_name,
                score=0.0,
                file_coverage=0.0,
                concept_coverage=0.0,
                accuracy=0.0,
                completeness=0.0,
                clarity=0.0,
                reasoning=f"Failed to parse judge response: {e}",
                missing_elements=[],
                strengths=[],
                weaknesses=[],
                raw_response=raw_response,
            )

    def compare_tools(
        self, task: ArchitecturalTask, tool_responses: Dict[str, str]
    ) -> Dict[str, Any]:
        """Compare multiple tools side-by-side on the same task.

        Args:
            task: The architectural task
            tool_responses: Dictionary mapping tool name to response

        Returns:
            Comparison results with ranking and detailed analysis
        """
        # Create comparison prompt
        prompt = create_comparison_prompt(task, tool_responses)

        # Get judge comparison
        raw_response = self.client.generate(prompt, temperature=0.0)

        # Parse JSON response
        try:
            if "```json" in raw_response:
                json_str = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                json_str = raw_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = raw_response.strip()

            comparison = json.loads(json_str)
            comparison["raw_response"] = raw_response
            comparison["judge_model"] = self.model_name
            comparison["task_id"] = task.task_id

            return comparison
        except (json.JSONDecodeError, KeyError) as e:
            return {
                "error": f"Failed to parse comparison response: {e}",
                "raw_response": raw_response,
                "judge_model": self.model_name,
                "task_id": task.task_id,
            }

    def evaluate_retrieval(
        self, task: ArchitecturalTask, retrieved_files: List[str], chunk_count: int
    ) -> Dict[str, Any]:
        """Evaluate retrieval quality before analysis.

        Args:
            task: The architectural task
            retrieved_files: List of file paths retrieved
            chunk_count: Total number of chunks retrieved

        Returns:
            Retrieval quality evaluation
        """
        # Create retrieval quality prompt
        prompt = create_retrieval_quality_prompt(task, retrieved_files, chunk_count)

        # Get judge evaluation
        raw_response = self.client.generate(prompt, temperature=0.0)

        # Parse JSON response
        try:
            if "```json" in raw_response:
                json_str = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                json_str = raw_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = raw_response.strip()

            evaluation = json.loads(json_str)
            evaluation["raw_response"] = raw_response
            evaluation["judge_model"] = self.model_name
            evaluation["task_id"] = task.task_id

            return evaluation
        except (json.JSONDecodeError, KeyError) as e:
            return {
                "error": f"Failed to parse retrieval evaluation: {e}",
                "raw_response": raw_response,
                "judge_model": self.model_name,
                "task_id": task.task_id,
            }


def create_judge(model: str = "gpt-4o", rubric: str = "comprehensive") -> LLMJudge:
    """Factory function to create an LLM judge.

    Args:
        model: Model name (gpt-4o/claude-opus/gemini-pro)
        rubric: Scoring rubric (comprehensive/quick/strict)

    Returns:
        Configured LLM judge instance
    """
    if model.startswith("gpt"):
        client = OpenAIClient(model=model)
        return LLMJudge(client, model, rubric)
    elif model.startswith("claude"):
        client = AnthropicClient(model=model)
        return LLMJudge(client, model, rubric)
    elif model.startswith("gemini"):
        client = GeminiClient(model=model)
        return LLMJudge(client, model, rubric)
    else:
        raise ValueError(
            f"Unsupported model: {model}. "
            "Use gpt-4o, claude-opus-4-20250514, or gemini-2.0-flash-exp"
        )


def save_evaluation_results(results: List[EvaluationResult], output_path: Path) -> None:
    """Save evaluation results to JSON file.

    Args:
        results: List of evaluation results
        output_path: Path to save results
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump([r.to_dict() for r in results], f, indent=2)


def load_evaluation_results(input_path: Path) -> List[EvaluationResult]:
    """Load evaluation results from JSON file.

    Args:
        input_path: Path to results file

    Returns:
        List of evaluation results
    """
    with open(input_path) as f:
        data = json.load(f)

    return [EvaluationResult(**item) for item in data]
