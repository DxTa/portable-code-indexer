"""Multi-hop code research for discovering code relationships."""

from dataclasses import dataclass, field
from typing import Set

from ..core.models import Chunk
from ..core.types import ChunkId
from ..storage.backend import MemvidBackend
from .entity_extractor import EntityExtractor, Entity


@dataclass
class CodeRelationship:
    """Represents a relationship between code entities."""

    from_entity: str
    to_entity: str
    relationship_type: str  # "calls", "imports", "extends", "uses"
    from_chunk: ChunkId | None = None
    to_chunk: ChunkId | None = None


@dataclass
class ResearchResult:
    """Result of multi-hop code research."""

    question: str
    chunks: list[Chunk] = field(default_factory=list)
    relationships: list[CodeRelationship] = field(default_factory=list)
    hops_executed: int = 0
    total_entities_found: int = 0


class MultiHopSearchStrategy:
    """Implements multi-hop code research for architectural discovery."""

    def __init__(self, backend: MemvidBackend, max_hops: int = 2):
        """Initialize multi-hop search strategy.

        Args:
            backend: Storage backend for searching
            max_hops: Maximum relationship hops to follow
        """
        self.backend = backend
        self.max_hops = max_hops
        self.extractor = EntityExtractor()

    def research(
        self, question: str, max_results_per_hop: int = 5, max_total_chunks: int = 50
    ) -> ResearchResult:
        """Perform multi-hop code research.

        Automatically discovers code relationships by:
        1. Initial search for the question
        2. Extract entities (function calls, imports, classes) from results
        3. Follow entity references to discover related code
        4. Build relationship graph

        Args:
            question: Natural language question about the codebase
            max_results_per_hop: Maximum results to explore per hop
            max_total_chunks: Safety limit on total chunks

        Returns:
            Research result with chunks and relationships
        """
        visited_chunks: Set[ChunkId] = set()
        visited_entities: Set[str] = set()
        relationships: list[CodeRelationship] = []
        all_chunks: list[Chunk] = []

        # Hop 0: Initial search (lexical - no API needed)
        initial_results = self.backend.search_lexical(question, k=max_results_per_hop)

        if not initial_results:
            return ResearchResult(question=question, chunks=[], relationships=[], hops_executed=0)

        # Process initial results
        for result in initial_results:
            chunk = result.chunk
            all_chunks.append(chunk)
            if chunk.id:
                visited_chunks.add(chunk.id)

        # Multi-hop exploration
        current_hop = 0
        entities_to_explore: list[tuple[Entity, Chunk]] = []

        # Extract entities from initial chunks
        for chunk in all_chunks[:]:
            entities = self.extractor.extract_from_chunk(chunk)
            for entity in entities:
                if entity.name not in visited_entities:
                    entities_to_explore.append((entity, chunk))
                    visited_entities.add(entity.name)

        # Follow entity references
        while current_hop < self.max_hops and entities_to_explore:
            current_hop += 1
            next_entities: list[tuple[Entity, Chunk]] = []

            # Explore each entity
            for entity, source_chunk in entities_to_explore[:max_results_per_hop]:
                if len(visited_chunks) >= max_total_chunks:
                    break

                # Search for this entity
                try:
                    entity_results = self.backend.search_lexical(entity.name, k=3)
                except Exception as e:
                    # Log search failures for debugging
                    import logging

                    logging.getLogger(__name__).debug(
                        f"Entity search failed for {entity.name}: {e}"
                    )
                    continue

                # Process results
                for entity_result in entity_results:
                    target_chunk = entity_result.chunk

                    # Skip if already visited
                    if target_chunk.id and target_chunk.id in visited_chunks:
                        continue

                    # Add to results
                    all_chunks.append(target_chunk)
                    if target_chunk.id:
                        visited_chunks.add(target_chunk.id)

                    # Record relationship
                    relationships.append(
                        CodeRelationship(
                            from_entity=source_chunk.symbol,
                            to_entity=target_chunk.symbol,
                            relationship_type=entity.entity_type,
                            from_chunk=source_chunk.id,
                            to_chunk=target_chunk.id,
                        )
                    )

                    # Extract entities from this chunk for next hop
                    if current_hop < self.max_hops:
                        new_entities = self.extractor.extract_from_chunk(target_chunk)
                        for new_entity in new_entities:
                            if new_entity.name not in visited_entities:
                                next_entities.append((new_entity, target_chunk))
                                visited_entities.add(new_entity.name)

            # Prepare for next hop
            entities_to_explore = next_entities

        return ResearchResult(
            question=question,
            chunks=all_chunks,
            relationships=relationships,
            hops_executed=current_hop,
            total_entities_found=len(visited_entities),
        )

    def build_call_graph(self, relationships: list[CodeRelationship]) -> dict[str, list[dict]]:
        """Build call graph from relationships.

        Args:
            relationships: List of code relationships

        Returns:
            Call graph as adjacency list
        """
        graph: dict[str, list[dict]] = {}

        for rel in relationships:
            if rel.from_entity not in graph:
                graph[rel.from_entity] = []

            graph[rel.from_entity].append(
                {"target": rel.to_entity, "type": rel.relationship_type, "chunk_id": rel.to_chunk}
            )

        return graph

    def get_entry_points(self, relationships: list[CodeRelationship]) -> list[str]:
        """Identify entry points (entities with no incoming edges).

        Args:
            relationships: List of code relationships

        Returns:
            List of entry point entity names
        """
        all_entities = set()
        targets = set()

        for rel in relationships:
            all_entities.add(rel.from_entity)
            all_entities.add(rel.to_entity)
            targets.add(rel.to_entity)

        # Entry points are entities that are never targets
        entry_points = all_entities - targets
        return list(entry_points)
