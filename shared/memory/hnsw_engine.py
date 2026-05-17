"""HNSW Vector Memory Engine for ClawShell v2.1.

Provides high-performance approximate nearest neighbor search using the
Hierarchical Navigable Small World (HNSW) algorithm via ``hnswlib``.

Features:
    - Cosine, Euclidean (L2), and Inner Product distance metrics
    - Thread-safe operations with ``threading.Lock``
    - Metadata storage alongside vectors
    - Batch add/search operations
    - Configurable auto-persistence on modification
    - Simple hash-based text embedding (no external model deps)
    - Save/load index to/from disk

Typical usage::

    from shared.memory import HNSWVectorMemory, HNSWConfig

    config = HNSWConfig(dim=128, space='cosine')
    mem = HNSWVectorMemory(config)
    mem.add('doc1', [0.1, 0.2, ...], {'title': 'Hello'})
    results = mem.search([0.1, 0.2, ...], k=5)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import hnswlib
import numpy as np


# ── Data Types ──────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """A single result from a vector similarity search."""

    id: str
    distance: float  # Raw distance from the index
    score: float     # Normalised similarity score (0-1, higher is better)
    metadata: dict   # Metadata associated with the vector


@dataclass
class HNSWConfig:
    """Configuration for an HNSW vector memory instance."""

    dim: int = 384                          # Vector dimensionality
    max_elements: int = 100_000             # Maximum capacity
    ef_construction: int = 200              # Build-time accuracy parameter
    M: int = 16                             # Max bi-directional links per node
    space: str = 'cosine'                   # cosine | l2 | ip
    auto_persist: bool = False              # Auto-save after every modification
    persist_path: Optional[str] = None      # Filesystem path for auto-persist

    def validate(self) -> None:
        """Raise ``ValueError`` for invalid configuration."""
        if self.dim < 1:
            raise ValueError(f"dim must be >= 1, got {self.dim}")
        if self.max_elements < 1:
            raise ValueError(f"max_elements must be >= 1, got {self.max_elements}")
        if self.space not in ('cosine', 'l2', 'ip'):
            raise ValueError(f"space must be one of 'cosine', 'l2', 'ip', got '{self.space}'")
        if self.M < 1:
            raise ValueError(f"M must be >= 1, got {self.M}")
        if self.ef_construction < 1:
            raise ValueError(f"ef_construction must be >= 1, got {self.ef_construction}")


# ── Text Embedding (hash-based TF-IDF-like) ────────────────────────


def embed_text_simple(
    text: str,
    dim: int = 384,
    normalize: bool = True,
) -> List[float]:
    """Convert *text* to a fixed-dimensional vector using a deterministic
    hash-based approach (no external model dependencies).

    The algorithm:
        1. Tokenise on whitespace and lower-case.
        2. For each token, compute a deterministic hash that maps it to a
           position in ``[0, dim)`` and a sign (+1 or −1).
        3. Accumulate token contributions (simulating TF-IDF-style
           feature hashing).
        4. L2-normalise the result.

    This is *not* a semantic embedding — it's a simple, reproducible
    bag-of-words representation useful for basic deduplication / recall
    scenarios.
    """
    tokens = text.lower().split()
    vec = np.zeros(dim, dtype=np.float32)

    # Term frequency map
    tf: Dict[str, int] = {}
    for tok in tokens:
        tf[tok] = tf.get(tok, 0) + 1

    for tok, count in tf.items():
        # Hash the token to get a deterministic position and sign
        h = hashlib.sha256(tok.encode('utf-8')).digest()
        # First 4 bytes -> index
        idx = int.from_bytes(h[:4], 'little') % dim
        # Next byte -> sign: even = +1, odd = -1
        sign = 1.0 if h[4] & 1 == 0 else -1.0
        # Log-frequency weighting (TF-IDF-like)
        weight = sign * (1.0 + math.log(count))
        vec[idx] += weight

    if normalize:
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

    return vec.tolist()


# ── HNSW Vector Memory Engine ──────────────────────────────────────


class HNSWVectorMemory:
    """Thread-safe HNSW-backed vector memory store.

    Stores vectors indexed by string *id* with associated *metadata*.
    Supports cosine, L2, and inner-product similarity.
    """

    # hnswlib space name mapping
    _SPACE_MAP = {
        'cosine': 'cosine',
        'l2': 'l2',
        'ip': 'ip',
    }

    def __init__(self, config: Optional[HNSWConfig] = None) -> None:
        self.config = config or HNSWConfig()
        self.config.validate()

        self._lock = threading.Lock()
        self._metadata: Dict[str, dict] = {}          # id -> metadata
        self._id_to_label: Dict[str, int] = {}        # id -> internal label
        self._label_to_id: Dict[int, str] = {}        # internal label -> id
        self._next_label: int = 0
        self._deleted_labels: set = set()              # Recyclable labels

        # Initialise the hnswlib index
        self._index = hnswlib.Index(
            space=self._SPACE_MAP[self.config.space],
            dim=self.config.dim,
        )
        self._index.init_index(
            max_elements=self.config.max_elements,
            ef_construction=self.config.ef_construction,
            M=self.config.M,
        )
        # Default ef for search (trade-off between speed and accuracy)
        self._index.set_ef(max(50, self.config.ef_construction // 2))

    # ── Properties ──────────────────────────────────────────────────

    @property
    def size(self) -> int:
        """Number of vectors currently stored."""
        with self._lock:
            return len(self._metadata)

    @property
    def ids(self) -> List[str]:
        """List of all stored vector IDs."""
        with self._lock:
            return list(self._metadata.keys())

    # ── Single-vector operations ────────────────────────────────────

    def add(
        self,
        id: str,
        vector: Sequence[float],
        metadata: Optional[dict] = None,
    ) -> None:
        """Add a single vector with optional metadata."""
        vec = self._validate_vector(vector)
        with self._lock:
            if id in self._id_to_label:
                # Update existing: delete then re-add
                self._mark_deleted(id)

            label = self._allocate_label()
            self._index.add_items([vec], [label])
            self._id_to_label[id] = label
            self._label_to_id[label] = id
            self._metadata[id] = metadata or {}

        self._maybe_persist()

    def search(
        self,
        query: Sequence[float],
        k: int = 5,
        filter_fn: Optional[Callable[[str, dict], bool]] = None,
    ) -> List[SearchResult]:
        """Search for the *k* nearest neighbours of *query*.

        Args:
            query: The query vector.
            k: Number of results to return.
            filter_fn: Optional ``(id, metadata) -> bool`` predicate. Only
                results for which the predicate returns ``True`` are included.

        Returns:
            List of ``SearchResult`` ordered by ascending distance (most
            similar first).
        """
        vec = self._validate_vector(query)

        with self._lock:
            n = len(self._metadata)
            if n == 0:
                return []
            k = min(k, n)
            # Request more than k to account for filtering
            fetch_k = min(k * 3 + 10, n) if filter_fn else k
            labels, distances = self._index.knn_query([vec], k=fetch_k)

        results: List[SearchResult] = []
        for label, dist in zip(labels[0], distances[0]):
            label = int(label)
            if label in self._deleted_labels:
                continue
            vid = self._label_to_id.get(label)
            if vid is None:
                continue
            meta = self._metadata.get(vid, {})
            if filter_fn and not filter_fn(vid, meta):
                continue
            score = self._distance_to_score(float(dist))
            results.append(SearchResult(
                id=vid,
                distance=float(dist),
                score=score,
                metadata=meta,
            ))
            if len(results) >= k:
                break

        return results

    def delete(self, id: str) -> bool:
        """Delete a vector by *id*.

        Returns ``True`` if the id existed, ``False`` otherwise.

        Note: hnswlib does not support true deletion. The label is marked
        as deleted and filtered out of search results. The underlying
        capacity is reclaimed only when the index is rebuilt via
        ``save``/``load``.
        """
        with self._lock:
            if id not in self._id_to_label:
                return False
            self._mark_deleted(id)
        self._maybe_persist()
        return True

    def get_metadata(self, id: str) -> Optional[dict]:
        """Retrieve metadata for a given *id*, or ``None`` if not found."""
        with self._lock:
            if id in self._metadata and id not in [
                self._label_to_id[l] for l in self._deleted_labels if l in self._label_to_id
            ]:
                return dict(self._metadata[id])
            return None

    def contains(self, id: str) -> bool:
        """Check whether *id* is present in the index."""
        with self._lock:
            return id in self._id_to_label

    # ── Batch operations ────────────────────────────────────────────

    def add_batch(
        self,
        ids: List[str],
        vectors: List[Sequence[float]],
        metadata_list: Optional[List[dict]] = None,
    ) -> int:
        """Add multiple vectors in a single call.

        Args:
            ids: List of string IDs.
            vectors: List of vectors (each a sequence of floats).
            metadata_list: Optional list of metadata dicts (same length).

        Returns:
            Number of vectors successfully added.

        Raises:
            ValueError: If list lengths don't match.
        """
        n = len(ids)
        if len(vectors) != n:
            raise ValueError(f"ids ({n}) and vectors ({len(vectors)}) length mismatch")
        if metadata_list and len(metadata_list) != n:
            raise ValueError(f"ids ({n}) and metadata_list ({len(metadata_list)}) length mismatch")
        if metadata_list is None:
            metadata_list = [{}] * n

        batch_labels: List[int] = []
        batch_vecs: List[List[float]] = []

        with self._lock:
            for i, (vid, vec) in enumerate(zip(ids, vectors)):
                v = self._validate_vector(vec)
                if vid in self._id_to_label:
                    self._mark_deleted(vid)

                label = self._allocate_label()
                batch_labels.append(label)
                batch_vecs.append(v)
                self._id_to_label[vid] = label
                self._label_to_id[label] = vid
                self._metadata[vid] = metadata_list[i]

            # hnswlib batch add
            self._index.add_items(np.array(batch_vecs, dtype=np.float32), batch_labels)

        self._maybe_persist()
        return n

    def search_batch(
        self,
        queries: List[Sequence[float]],
        k: int = 5,
        filter_fn: Optional[Callable[[str, dict], bool]] = None,
    ) -> List[List[SearchResult]]:
        """Search for multiple query vectors in one call.

        Args:
            queries: List of query vectors.
            k: Number of results per query.
            filter_fn: Optional filter predicate.

        Returns:
            List of result lists (one per query).
        """
        if self.size == 0:
            return [[] for _ in queries]

        if filter_fn is None:
            vecs = [self._validate_vector(q) for q in queries]
            with self._lock:
                n = len(self._metadata)
                if n == 0:
                    return [[] for _ in queries]
                k = min(k, n)
                all_labels, all_distances = self._index.knn_query(
                    np.array(vecs, dtype=np.float32), k=k
                )
            all_results: List[List[SearchResult]] = []
            for labels, distances in zip(all_labels, all_distances):
                results: List[SearchResult] = []
                for label, dist in zip(labels, distances):
                    label = int(label)
                    if label in self._deleted_labels:
                        continue
                    vid = self._label_to_id.get(label)
                    if vid is None:
                        continue
                    meta = self._metadata.get(vid, {})
                    score = self._distance_to_score(float(dist))
                    results.append(SearchResult(
                        id=vid,
                        distance=float(dist),
                        score=score,
                        metadata=meta,
                    ))
                    if len(results) >= k:
                        break
                all_results.append(results)
            return all_results
        else:
            # With filter: must build results under lock
            vecs = [self._validate_vector(q) for q in queries]
            with self._lock:
                n = len(self._metadata)
                if n == 0:
                    return [[] for _ in queries]
                k = min(k, n)
                fetch_k = min(k * 3 + 10, n)
                all_labels, all_distances = self._index.knn_query(
                    np.array(vecs, dtype=np.float32), k=fetch_k
                )
                all_results = []
                for labels, distances in zip(all_labels, all_distances):
                    results: List[SearchResult] = []
                    for label, dist in zip(labels, distances):
                        label = int(label)
                        if label in self._deleted_labels:
                            continue
                        vid = self._label_to_id.get(label)
                        if vid is None:
                            continue
                        meta = self._metadata.get(vid, {})
                        if not filter_fn(vid, meta):
                            continue
                        score = self._distance_to_score(float(dist))
                        results.append(SearchResult(
                            id=vid,
                            distance=float(dist),
                            score=score,
                            metadata=meta,
                        ))
                        if len(results) >= k:
                            break
                    all_results.append(results)
            return all_results

    # ── Persistence ─────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Save the index and metadata to disk.

        Creates two files:
            - ``<path>.hnsw`` — the hnswlib index
            - ``<path>.meta`` — JSON-encoded metadata + id mappings
        """
        with self._lock:
            index_path = f"{path}.hnsw"
            meta_path = f"{path}.meta"

            # Ensure parent directory exists
            os.makedirs(os.path.dirname(os.path.abspath(index_path)), exist_ok=True)

            self._index.save_index(index_path)

            meta_payload = {
                'metadata': self._metadata,
                'id_to_label': self._id_to_label,
                'label_to_id': {str(k): v for k, v in self._label_to_id.items()},
                'next_label': self._next_label,
                'deleted_labels': list(self._deleted_labels),
                'config': {
                    'dim': self.config.dim,
                    'max_elements': self.config.max_elements,
                    'ef_construction': self.config.ef_construction,
                    'M': self.config.M,
                    'space': self.config.space,
                },
            }
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_payload, f, ensure_ascii=False)

    @classmethod
    def load(cls, path: str, auto_persist: bool = False) -> 'HNSWVectorMemory':
        """Load a previously saved index from *path*.

        Args:
            path: Base path (without extension) used during ``save()``.
            auto_persist: Whether to enable auto-persist on the loaded instance.

        Returns:
            A fully restored ``HNSWVectorMemory`` instance.
        """
        index_path = f"{path}.hnsw"
        meta_path = f"{path}.meta"

        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Index file not found: {index_path}")
        if not os.path.exists(meta_path):
            raise FileNotFoundError(f"Metadata file not found: {meta_path}")

        with open(meta_path, 'r', encoding='utf-8') as f:
            meta_payload = json.load(f)

        cfg_data = meta_payload['config']
        config = HNSWConfig(
            dim=cfg_data['dim'],
            max_elements=cfg_data['max_elements'],
            ef_construction=cfg_data['ef_construction'],
            M=cfg_data['M'],
            space=cfg_data['space'],
            auto_persist=auto_persist,
            persist_path=path if auto_persist else None,
        )

        instance = cls.__new__(cls)
        instance.config = config
        instance._lock = threading.Lock()
        instance._metadata = meta_payload['metadata']
        instance._id_to_label = meta_payload['id_to_label']
        instance._label_to_id = {int(k): v for k, v in meta_payload['label_to_id'].items()}
        instance._next_label = meta_payload['next_label']
        instance._deleted_labels = set(meta_payload.get('deleted_labels', []))

        instance._index = hnswlib.Index(
            space=cls._SPACE_MAP[config.space],
            dim=config.dim,
        )
        instance._index.load_index(index_path, max_elements=config.max_elements)
        instance._index.set_ef(max(50, config.ef_construction // 2))

        return instance

    # ── Utility / Rebuild ───────────────────────────────────────────

    def rebuild(self) -> None:
        """Rebuild the index, purging deleted entries and reclaiming capacity.

        This is expensive — it re-inserts all live vectors into a fresh index.
        """
        with self._lock:
            live_items: List[Tuple[str, List[float], dict]] = []
            for vid, label in self._id_to_label.items():
                if label in self._deleted_labels:
                    continue
                # Retrieve the vector from the index
                vec = self._index.get_items([label])[0]
                live_items.append((vid, vec.tolist(), self._metadata.get(vid, {})))

            # Re-init index
            self._index = hnswlib.Index(
                space=self._SPACE_MAP[self.config.space],
                dim=self.config.dim,
            )
            self._index.init_index(
                max_elements=self.config.max_elements,
                ef_construction=self.config.ef_construction,
                M=self.config.M,
            )
            self._index.set_ef(max(50, self.config.ef_construction // 2))

            self._metadata.clear()
            self._id_to_label.clear()
            self._label_to_id.clear()
            self._deleted_labels.clear()
            self._next_label = 0

            if live_items:
                vecs = []
                labels = []
                for vid, vec, meta in live_items:
                    label = self._allocate_label()
                    vecs.append(vec)
                    labels.append(label)
                    self._id_to_label[vid] = label
                    self._label_to_id[label] = vid
                    self._metadata[vid] = meta
                self._index.add_items(np.array(vecs, dtype=np.float32), labels)

        self._maybe_persist()

    def clear(self) -> None:
        """Remove all vectors and reset the index."""
        with self._lock:
            self._index = hnswlib.Index(
                space=self._SPACE_MAP[self.config.space],
                dim=self.config.dim,
            )
            self._index.init_index(
                max_elements=self.config.max_elements,
                ef_construction=self.config.ef_construction,
                M=self.config.M,
            )
            self._index.set_ef(max(50, self.config.ef_construction // 2))
            self._metadata.clear()
            self._id_to_label.clear()
            self._label_to_id.clear()
            self._deleted_labels.clear()
            self._next_label = 0

        self._maybe_persist()

    # ── Private helpers ─────────────────────────────────────────────

    def _validate_vector(self, vector: Sequence[float]) -> np.ndarray:
        """Convert and validate a vector to the expected numpy shape/dtype."""
        vec = np.asarray(vector, dtype=np.float32).flatten()
        if vec.shape[0] != self.config.dim:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.config.dim}, got {vec.shape[0]}"
            )
        return vec

    def _allocate_label(self) -> int:
        """Allocate the next internal label (recycles deleted labels)."""
        if self._deleted_labels:
            return self._deleted_labels.pop()
        label = self._next_label
        self._next_label += 1
        return label

    def _mark_deleted(self, id: str) -> None:
        """Mark an id as deleted (internal bookkeeping only)."""
        label = self._id_to_label.pop(id, None)
        if label is not None:
            self._label_to_id.pop(label, None)
            self._deleted_labels.add(label)
        self._metadata.pop(id, None)

    def _distance_to_score(self, distance: float) -> float:
        """Convert a raw distance to a normalised 0-1 similarity score.

        - cosine: score = 1 - distance  (distance is in [0, 2])
        - l2:     score = 1 / (1 + distance)
        - ip:     score = 1 / (1 + distance)  (inner product distance is 1 - dot)
        """
        if self.config.space == 'cosine':
            return max(0.0, min(1.0, 1.0 - distance))
        else:
            return max(0.0, min(1.0, 1.0 / (1.0 + abs(distance))))

    def _maybe_persist(self) -> None:
        """Auto-persist if configured."""
        if self.config.auto_persist and self.config.persist_path:
            try:
                self.save(self.config.persist_path)
            except Exception:
                pass  # Best-effort; don't raise on auto-persist failures

    def __repr__(self) -> str:
        return (
            f"HNSWVectorMemory(dim={self.config.dim}, space={self.config.space!r}, "
            f"size={self.size}, max={self.config.max_elements})"
        )
