"""Auto-detect project languages and configure search strategy.

Uses config files to detect languages (faster than counting files).
Configures search strategy based on project characteristics.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class LanguageDetection:
    """Detected language in project."""

    language: str
    confidence: float  # 0.0 to 1.0
    evidence: list[str]  # Config files that indicate this language


@dataclass
class ProjectProfile:
    """Project characteristics and recommended configuration."""

    primary_languages: list[str]
    is_multi_language: bool
    has_dependencies: bool
    has_documentation: bool
    recommended_strategy: Literal["weighted", "non-dominated"]
    tier_boost: dict[str, float]
    detections: list[LanguageDetection] = field(default_factory=list)


class ProjectAnalyzer:
    """Analyzes project to auto-configure sia-code settings.

    Uses config files to detect languages (faster than counting files).
    Determines optimal search strategy based on project characteristics.
    """

    # Language detection patterns (config files → language)
    LANGUAGE_INDICATORS = {
        # Python
        "python": [
            "requirements.txt",
            "setup.py",
            "pyproject.toml",
            "Pipfile",
            "poetry.lock",
            "setup.cfg",
            "tox.ini",
            "pytest.ini",
        ],
        # JavaScript/TypeScript
        "typescript": [
            "tsconfig.json",
            "package.json",  # Could be JS or TS
        ],
        "javascript": [
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            ".eslintrc",
            ".prettierrc",
        ],
        # Go
        "go": [
            "go.mod",
            "go.sum",
            "Gopkg.toml",
        ],
        # Rust
        "rust": [
            "Cargo.toml",
            "Cargo.lock",
        ],
        # Java
        "java": [
            "pom.xml",
            "build.gradle",
            "settings.gradle",
            "build.gradle.kts",
            "gradle.properties",
        ],
        # C/C++
        "cpp": [
            "CMakeLists.txt",
            "Makefile",
            "configure.ac",
            "meson.build",
        ],
        # C#
        "csharp": [
            "*.csproj",
            "*.sln",
            "*.fsproj",
            "paket.dependencies",
        ],
        # Ruby
        "ruby": [
            "Gemfile",
            "Gemfile.lock",
            ".ruby-version",
            "Rakefile",
        ],
        # PHP
        "php": [
            "composer.json",
            "composer.lock",
        ],
    }

    # Dependency manager indicators
    DEPENDENCY_INDICATORS = {
        "python": ["requirements.txt", "Pipfile", "poetry.lock", "pyproject.toml"],
        "typescript": ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
        "javascript": ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
        "go": ["go.sum"],
        "rust": ["Cargo.lock"],
        "java": ["pom.xml", "build.gradle"],
        "ruby": ["Gemfile.lock"],
        "php": ["composer.lock"],
    }

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def analyze(self) -> ProjectProfile:
        """Analyze project and return recommended configuration.

        Returns:
            ProjectProfile with detected characteristics
        """
        # Detect languages
        detections = self._detect_languages()

        # Determine primary languages (confidence >= 0.8)
        primary_languages = [d.language for d in detections if d.confidence >= 0.8]

        # Multi-language if >1 primary language
        is_multi_language = len(primary_languages) > 1

        # Check for dependencies
        has_dependencies = self._has_dependencies(primary_languages)

        # Check for documentation
        has_documentation = self._has_documentation()

        # Determine search strategy
        if is_multi_language:
            # Multi-language projects benefit from non-dominated ranking
            strategy = "non-dominated"
            # Boost project code over dependencies
            tier_boost = {
                "project": 1.0,
                "dependency": 0.5,  # Lower boost for multi-language
                "stdlib": 0.3,
                "documentation": 0.8,
            }
        else:
            # Single-language projects can use weighted scoring
            strategy = "weighted"
            tier_boost = {
                "project": 1.0,
                "dependency": 0.7,  # Higher boost for single-language
                "stdlib": 0.5,
                "documentation": 0.9,
            }

        return ProjectProfile(
            primary_languages=primary_languages,
            is_multi_language=is_multi_language,
            has_dependencies=has_dependencies,
            has_documentation=has_documentation,
            recommended_strategy=strategy,
            tier_boost=tier_boost,
            detections=detections,
        )

    def _detect_languages(self) -> list[LanguageDetection]:
        """Detect languages by finding config files.

        Returns:
            List of language detections with confidence
        """
        detections = []

        for language, indicators in self.LANGUAGE_INDICATORS.items():
            evidence = []
            total_indicators = len(indicators)
            found_indicators = 0

            for indicator in indicators:
                # Check if indicator contains wildcard
                if "*" in indicator:
                    # Use glob for patterns like *.csproj
                    matches = list(self.project_root.glob(indicator))
                    if matches:
                        evidence.extend(
                            [str(m.relative_to(self.project_root)) for m in matches[:3]]
                        )
                        found_indicators += len(matches)
                else:
                    # Direct file check
                    file_path = self.project_root / indicator
                    if file_path.exists():
                        evidence.append(indicator)
                        found_indicators += 1

            if evidence:
                # Confidence based on:
                # - Number of indicators found
                # - Specificity of indicators (e.g., tsconfig.json is very specific)
                base_confidence = min(1.0, found_indicators / max(1, total_indicators))

                # Boost confidence for very specific indicators
                if language == "python" and "pyproject.toml" in evidence:
                    base_confidence = max(base_confidence, 0.90)
                elif language == "python" and "setup.py" in evidence:
                    base_confidence = max(base_confidence, 0.85)
                elif language == "typescript" and "tsconfig.json" in evidence:
                    base_confidence = max(base_confidence, 0.95)
                elif language == "rust" and "Cargo.toml" in evidence:
                    base_confidence = max(base_confidence, 0.95)
                elif language == "go" and "go.mod" in evidence:
                    base_confidence = max(base_confidence, 0.95)
                elif language == "java" and "pom.xml" in evidence:
                    base_confidence = max(base_confidence, 0.90)

                detections.append(
                    LanguageDetection(
                        language=language,
                        confidence=base_confidence,
                        evidence=evidence[:5],  # Limit to 5 examples
                    )
                )

        # Sort by confidence (highest first)
        detections.sort(key=lambda d: d.confidence, reverse=True)

        return detections

    def _has_dependencies(self, languages: list[str]) -> bool:
        """Check if project has dependency management.

        Args:
            languages: Detected primary languages

        Returns:
            True if dependency management detected
        """
        for language in languages:
            if language in self.DEPENDENCY_INDICATORS:
                for indicator in self.DEPENDENCY_INDICATORS[language]:
                    file_path = self.project_root / indicator
                    if file_path.exists():
                        return True
        return False

    def _has_documentation(self) -> bool:
        """Check if project has documentation.

        Returns:
            True if documentation detected
        """
        # Check for common documentation indicators
        doc_indicators = [
            "README.md",
            "docs/",
            "doc/",
            "CONTRIBUTING.md",
        ]

        for indicator in doc_indicators:
            path = self.project_root / indicator
            if path.exists():
                return True

        return False

    def apply_to_config(self, config_path: Path, dry_run: bool = False) -> dict:
        """Analyze project and update config file with recommendations.

        Args:
            config_path: Path to .sia-code/config.json
            dry_run: If True, don't modify config, just return recommendations

        Returns:
            Dictionary with applied changes
        """
        profile = self.analyze()

        # Read existing config
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to read config: {e}")
                return {}
        else:
            config = {}

        # Prepare changes
        changes = {
            "detected_languages": profile.primary_languages,
            "is_multi_language": profile.is_multi_language,
            "recommended_strategy": profile.recommended_strategy,
            "tier_boost": profile.tier_boost,
        }

        # Apply to config (under "search" section)
        if "search" not in config:
            config["search"] = {}

        config["search"]["tier_boost"] = profile.tier_boost
        config["search"]["include_dependencies"] = profile.has_dependencies

        # Add metadata section
        if "metadata" not in config:
            config["metadata"] = {}

        config["metadata"]["auto_detected_languages"] = profile.primary_languages
        config["metadata"]["is_multi_language"] = profile.is_multi_language
        config["metadata"]["detection_confidence"] = {
            d.language: d.confidence for d in profile.detections
        }

        if not dry_run:
            # Write config
            try:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=2)
                logger.info(f"Updated config: {config_path}")
            except IOError as e:
                logger.error(f"Failed to write config: {e}")
                return {}

        return changes
