"""exoskeleton.genome — Knowledge Heritage layer (知识传承).

Re-exports: KnowledgeHeritage, GenomeCacheManager, EvolutionTracker
"""

from .heritage import KnowledgeHeritage
from .cache_manager import GenomeCacheManager
from .evolution_tracker import EvolutionTracker

__all__ = ["KnowledgeHeritage", "GenomeCacheManager", "EvolutionTracker"]
