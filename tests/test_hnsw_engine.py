"""Comprehensive tests for the HNSW Vector Memory Engine.

Run with: python -m pytest tests/test_hnsw_engine.py -v
"""

from __future__ import annotations

import math
import os
import tempfile
import threading
import time

import numpy as np
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.memory.hnsw_engine import (
    HNSWConfig,
    HNSWVectorMemory,
    SearchResult,
    embed_text_simple,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _random_vector(dim: int = 384, seed: int | None = None) -> list[float]:
    """Generate a random unit vector."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


def _make_engine(
    dim: int = 128,
    space: str = 'cosine',
    **kwargs,
) -> HNSWVectorMemory:
    """Create a small HNSWVectorMemory for testing."""
    config = HNSWConfig(dim=dim, max_elements=5000, space=space, **kwargs)
    return HNSWVectorMemory(config)


# ── SearchResult Dataclass ──────────────────────────────────────────


class TestSearchResult:
    """Test the SearchResult dataclass."""

    def test_creation(self):
        r = SearchResult(id='a', distance=0.5, score=0.5, metadata={'k': 'v'})
        assert r.id == 'a'
        assert r.distance == 0.5
        assert r.score == 0.5
        assert r.metadata == {'k': 'v'}

    def test_default_metadata(self):
        r = SearchResult(id='b', distance=0.0, score=1.0, metadata={})
        assert r.metadata == {}


# ── HNSWConfig ──────────────────────────────────────────────────────


class TestHNSWConfig:
    """Test HNSWConfig validation."""

    def test_defaults(self):
        cfg = HNSWConfig()
        assert cfg.dim == 384
        assert cfg.max_elements == 100_000
        assert cfg.space == 'cosine'
        assert cfg.auto_persist is False

    def test_invalid_dim(self):
        cfg = HNSWConfig(dim=0)
        with pytest.raises(ValueError, match="dim must be >= 1"):
            cfg.validate()

    def test_invalid_space(self):
        cfg = HNSWConfig(space='manhattan')
        with pytest.raises(ValueError, match="space must be one of"):
            cfg.validate()

    def test_invalid_max_elements(self):
        cfg = HNSWConfig(max_elements=-1)
        with pytest.raises(ValueError, match="max_elements must be >= 1"):
            cfg.validate()


# ── Single Vector Operations ────────────────────────────────────────


class TestSingleVectorOperations:
    """Test add, search, delete for individual vectors."""

    def test_add_and_search_single(self):
        """Add one vector and retrieve it."""
        mem = _make_engine(dim=64)
        vec = _random_vector(64, seed=1)
        mem.add('doc1', vec, {'title': 'Hello'})
        assert mem.size == 1
        assert 'doc1' in mem.ids

        results = mem.search(vec, k=1)
        assert len(results) == 1
        assert results[0].id == 'doc1'
        assert results[0].metadata == {'title': 'Hello'}
        # Cosine distance of identical vectors should be ~0
        assert results[0].distance < 0.01
        assert results[0].score > 0.99

    def test_add_without_metadata(self):
        """Add a vector without metadata."""
        mem = _make_engine(dim=64)
        vec = _random_vector(64, seed=2)
        mem.add('no_meta', vec)
        results = mem.search(vec, k=1)
        assert len(results) == 1
        assert results[0].metadata == {}

    def test_add_updates_existing_id(self):
        """Adding the same id twice should update (not duplicate)."""
        mem = _make_engine(dim=64)
        vec1 = _random_vector(64, seed=10)
        vec2 = _random_vector(64, seed=11)
        mem.add('x', vec1, {'v': 1})
        mem.add('x', vec2, {'v': 2})
        assert mem.size == 1
        results = mem.search(vec2, k=1)
        assert results[0].metadata == {'v': 2}

    def test_delete_existing(self):
        """Delete an existing vector."""
        mem = _make_engine(dim=64)
        vec = _random_vector(64, seed=5)
        mem.add('del_me', vec)
        assert mem.size == 1
        assert mem.delete('del_me') is True
        assert mem.size == 0
        results = mem.search(vec, k=5)
        assert len(results) == 0

    def test_delete_nonexistent(self):
        """Deleting a non-existent id returns False."""
        mem = _make_engine(dim=64)
        assert mem.delete('ghost') is False

    def test_contains(self):
        mem = _make_engine(dim=64)
        vec = _random_vector(64, seed=6)
        assert mem.contains('a') is False
        mem.add('a', vec)
        assert mem.contains('a') is True

    def test_vector_dimension_mismatch(self):
        """Adding a vector with wrong dimension should raise ValueError."""
        mem = _make_engine(dim=64)
        with pytest.raises(ValueError, match="dimension mismatch"):
            mem.add('bad', [0.0] * 32)

    def test_search_with_wrong_dim_raises(self):
        mem = _make_engine(dim=64)
        mem.add('ok', _random_vector(64, seed=7))
        with pytest.raises(ValueError, match="dimension mismatch"):
            mem.search([0.0] * 32)


# ── Batch Operations ───────────────────────────────────────────────


class TestBatchOperations:
    """Test add_batch and search_batch."""

    def test_add_batch_and_search(self):
        """Add multiple vectors in batch and search."""
        mem = _make_engine(dim=64)
        ids = [f'doc{i}' for i in range(10)]
        vecs = [_random_vector(64, seed=i) for i in range(10)]
        metas = [{'idx': i} for i in range(10)]

        added = mem.add_batch(ids, vecs, metas)
        assert added == 10
        assert mem.size == 10

        # Search for the first vector
        results = mem.search(vecs[0], k=3)
        assert len(results) >= 1
        assert results[0].id == 'doc0'

    def test_add_batch_without_metadata(self):
        mem = _make_engine(dim=64)
        ids = ['a', 'b', 'c']
        vecs = [_random_vector(64, seed=i) for i in range(3)]
        mem.add_batch(ids, vecs)
        assert mem.size == 3

    def test_add_batch_length_mismatch(self):
        mem = _make_engine(dim=64)
        with pytest.raises(ValueError, match="length mismatch"):
            mem.add_batch(['a'], [_random_vector(64), _random_vector(64)])

    def test_search_batch(self):
        """search_batch returns results for each query."""
        mem = _make_engine(dim=64)
        ids = [f'd{i}' for i in range(20)]
        vecs = [_random_vector(64, seed=i) for i in range(20)]
        mem.add_batch(ids, vecs)

        queries = [vecs[0], vecs[5], vecs[10]]
        all_results = mem.search_batch(queries, k=3)
        assert len(all_results) == 3
        for results in all_results:
            assert len(results) <= 3
            assert len(results) >= 1

    def test_search_batch_empty_index(self):
        mem = _make_engine(dim=64)
        all_results = mem.search_batch([_random_vector(64)], k=5)
        assert all_results == [[]]


# ── Distance Metrics ────────────────────────────────────────────────


class TestDistanceMetrics:
    """Test cosine, L2, and inner-product distance metrics."""

    def test_cosine_metric(self):
        mem = _make_engine(dim=64, space='cosine')
        vec = _random_vector(64, seed=42)
        mem.add('c1', vec, {'type': 'test'})
        results = mem.search(vec, k=1)
        assert results[0].distance < 0.01
        assert results[0].score > 0.99

    def test_l2_metric(self):
        mem = _make_engine(dim=64, space='l2')
        vec = _random_vector(64, seed=43)
        mem.add('l1', vec)
        results = mem.search(vec, k=1)
        # L2 distance of identical vectors should be ~0
        assert results[0].distance < 0.01
        assert results[0].score > 0.99

    def test_inner_product_metric(self):
        mem = _make_engine(dim=64, space='ip')
        vec = _random_vector(64, seed=44)
        mem.add('ip1', vec)
        results = mem.search(vec, k=1)
        # Inner product of identical unit vectors ≈ 1, distance ≈ 0
        assert results[0].distance < 0.1
        assert results[0].score > 0.5

    def test_different_vectors_ranked_correctly(self):
        """More similar vectors should rank higher."""
        mem = _make_engine(dim=64, space='cosine')
        target = _random_vector(64, seed=100)
        similar = _random_vector(64, seed=101)
        different = _random_vector(64, seed=102)

        # Make 'similar' actually more similar to target
        # Blend target with noise
        rng = np.random.RandomState(200)
        similar_close = (0.9 * np.array(target) + 0.1 * rng.randn(64)).tolist()
        different_far = (0.1 * np.array(target) + 0.9 * rng.randn(64)).tolist()

        mem.add('close', similar_close)
        mem.add('far', different_far)

        results = mem.search(target, k=2)
        assert results[0].id == 'close'
        assert results[0].score >= results[1].score


# ── Filter Function ─────────────────────────────────────────────────


class TestFilterFunction:
    """Test the filter_fn parameter in search."""

    def test_filter_by_metadata(self):
        mem = _make_engine(dim=64)
        for i in range(10):
            vec = _random_vector(64, seed=i + 100)
            mem.add(f'doc{i}', vec, {'category': 'tech' if i % 2 == 0 else 'sports'})

        # Filter for 'tech' only
        query = _random_vector(64, seed=999)
        results = mem.search(
            query, k=10,
            filter_fn=lambda _id, meta: meta.get('category') == 'tech',
        )
        for r in results:
            assert r.metadata['category'] == 'tech'

    def test_filter_by_id(self):
        mem = _make_engine(dim=64)
        vecs = [_random_vector(64, seed=i + 200) for i in range(5)]
        for i, v in enumerate(vecs):
            mem.add(f'doc{i}', v)

        results = mem.search(
            _random_vector(64, seed=998), k=10,
            filter_fn=lambda id_, _m: id_ in ('doc0', 'doc2', 'doc4'),
        )
        for r in results:
            assert r.id in ('doc0', 'doc2', 'doc4')

    def test_filter_excludes_all(self):
        """If filter excludes everything, return empty."""
        mem = _make_engine(dim=64)
        mem.add('a', _random_vector(64, seed=300))
        results = mem.search(
            _random_vector(64, seed=301), k=5,
            filter_fn=lambda _id, _m: False,
        )
        assert len(results) == 0


# ── Save and Load ───────────────────────────────────────────────────


class TestPersistence:
    """Test save and load operations."""

    def test_save_and_load(self):
        """Save an index, load it, and verify data integrity."""
        mem = _make_engine(dim=64)
        vecs = [_random_vector(64, seed=i + 400) for i in range(5)]
        for i, v in enumerate(vecs):
            mem.add(f'doc{i}', v, {'idx': i, 'text': f'document {i}'})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'test_index')
            mem.save(path)

            # Verify files exist
            assert os.path.exists(f'{path}.hnsw')
            assert os.path.exists(f'{path}.meta')

            # Load into new instance
            loaded = HNSWVectorMemory.load(path)
            assert loaded.size == 5
            assert set(loaded.ids) == {f'doc{i}' for i in range(5)}

            # Search should work
            results = loaded.search(vecs[0], k=1)
            assert results[0].id == 'doc0'
            assert results[0].metadata['idx'] == 0

    def test_save_load_with_deleted_items(self):
        """Deleted items should not appear after load."""
        mem = _make_engine(dim=64)
        mem.add('keep', _random_vector(64, seed=500))
        mem.add('remove', _random_vector(64, seed=501))
        mem.delete('remove')

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'test_del')
            mem.save(path)
            loaded = HNSWVectorMemory.load(path)
            assert loaded.size == 1
            assert 'keep' in loaded.ids
            assert 'remove' not in loaded.ids

    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            HNSWVectorMemory.load('/nonexistent/path')

    def test_auto_persist(self):
        """With auto_persist=True, modifications should save automatically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'auto')
            mem = _make_engine(dim=64, auto_persist=True, persist_path=path)
            mem.add('a', _random_vector(64, seed=600))
            # Files should exist after add
            assert os.path.exists(f'{path}.hnsw')
            assert os.path.exists(f'{path}.meta')


# ── Edge Cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    """Test empty index, k > size, etc."""

    def test_search_empty_index(self):
        """Searching an empty index should return empty list."""
        mem = _make_engine(dim=64)
        results = mem.search(_random_vector(64), k=5)
        assert results == []

    def test_search_k_larger_than_size(self):
        """k > size should return at most size results."""
        mem = _make_engine(dim=64)
        mem.add('only', _random_vector(64, seed=700))
        results = mem.search(_random_vector(64), k=100)
        assert len(results) == 1

    def test_empty_ids_list(self):
        mem = _make_engine(dim=64)
        assert mem.ids == []
        assert mem.size == 0

    def test_repr(self):
        mem = _make_engine(dim=64)
        r = repr(mem)
        assert 'HNSWVectorMemory' in r
        assert 'dim=64' in r
        assert 'size=0' in r

    def test_clear(self):
        """clear() should remove all vectors."""
        mem = _make_engine(dim=64)
        for i in range(5):
            mem.add(f'd{i}', _random_vector(64, seed=800 + i))
        assert mem.size == 5
        mem.clear()
        assert mem.size == 0
        assert mem.ids == []

    def test_rebuild(self):
        """rebuild() should purge deleted entries."""
        mem = _make_engine(dim=64)
        for i in range(5):
            mem.add(f'd{i}', _random_vector(64, seed=900 + i))
        mem.delete('d0')
        mem.delete('d1')
        assert mem.size == 3
        mem.rebuild()
        assert mem.size == 3
        assert set(mem.ids) == {'d2', 'd3', 'd4'}


# ── Metadata Retrieval ──────────────────────────────────────────────


class TestMetadataRetrieval:
    """Test get_metadata and metadata in search results."""

    def test_get_metadata_existing(self):
        mem = _make_engine(dim=64)
        mem.add('m1', _random_vector(64, seed=1000), {'key': 'value', 'num': 42})
        meta = mem.get_metadata('m1')
        assert meta == {'key': 'value', 'num': 42}

    def test_get_metadata_nonexistent(self):
        mem = _make_engine(dim=64)
        assert mem.get_metadata('nope') is None

    def test_metadata_in_search_results(self):
        mem = _make_engine(dim=64)
        vec = _random_vector(64, seed=1010)
        mem.add('r1', vec, {'tags': ['a', 'b'], 'score': 0.9})
        results = mem.search(vec, k=1)
        assert results[0].metadata['tags'] == ['a', 'b']
        assert results[0].metadata['score'] == 0.9

    def test_metadata_isolation(self):
        """Modifying returned metadata should not affect stored metadata."""
        mem = _make_engine(dim=64)
        mem.add('iso', _random_vector(64, seed=1020), {'x': 1})
        meta = mem.get_metadata('iso')
        meta['x'] = 999
        assert mem.get_metadata('iso')['x'] == 1


# ── Thread Safety ───────────────────────────────────────────────────


class TestThreadSafety:
    """Concurrent operations should not crash or corrupt data."""

    def test_concurrent_adds(self):
        """Multiple threads adding vectors concurrently."""
        mem = _make_engine(dim=64)
        errors = []

        def add_vectors(start: int, count: int):
            try:
                for i in range(count):
                    idx = start + i
                    mem.add(f't{idx}', _random_vector(64, seed=idx + 2000), {'idx': idx})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_vectors, args=(i * 100, 100)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert mem.size == 400

    def test_concurrent_add_and_search(self):
        """Concurrent adds and searches should not crash."""
        mem = _make_engine(dim=64)
        # Pre-populate some data
        for i in range(50):
            mem.add(f'pre{i}', _random_vector(64, seed=i + 3000))

        errors = []
        stop = threading.Event()

        def searcher():
            try:
                while not stop.is_set():
                    results = mem.search(_random_vector(64, seed=9999), k=5)
                    assert isinstance(results, list)
            except Exception as e:
                errors.append(e)

        def adder():
            try:
                for i in range(50, 100):
                    mem.add(f'new{i}', _random_vector(64, seed=i + 3000), {'new': True})
            except Exception as e:
                errors.append(e)

        searchers = [threading.Thread(target=searcher) for _ in range(3)]
        adder_thread = threading.Thread(target=adder)

        for t in searchers:
            t.start()
        adder_thread.start()
        adder_thread.join()
        stop.set()
        for t in searchers:
            t.join()

        assert len(errors) == 0
        assert mem.size == 100

    def test_concurrent_batch_ops(self):
        """Concurrent batch add and batch search."""
        mem = _make_engine(dim=64)
        errors = []

        def batch_add(start: int):
            try:
                ids = [f'b{i}' for i in range(start, start + 50)]
                vecs = [_random_vector(64, seed=i + 4000) for i in range(start, start + 50)]
                mem.add_batch(ids, vecs)
            except Exception as e:
                errors.append(e)

        def batch_search():
            try:
                queries = [_random_vector(64, seed=i + 5000) for i in range(10)]
                results = mem.search_batch(queries, k=3)
                assert len(results) == 10
            except Exception as e:
                errors.append(e)

        # Pre-add some data
        for i in range(10):
            mem.add(f'base{i}', _random_vector(64, seed=i + 4500))

        threads = [
            threading.Thread(target=batch_add, args=(0,)),
            threading.Thread(target=batch_add, args=(50,)),
            threading.Thread(target=batch_search),
            threading.Thread(target=batch_search),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ── Text Embedding ──────────────────────────────────────────────────


class TestEmbedTextSimple:
    """Test the hash-based text embedding function."""

    def test_basic_embedding(self):
        vec = embed_text_simple("hello world", dim=64)
        assert len(vec) == 64
        assert isinstance(vec[0], float)

    def test_normalized(self):
        """Output should be L2-normalized."""
        vec = embed_text_simple("some test text here", dim=128)
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-5

    def test_deterministic(self):
        """Same input should always produce the same vector."""
        v1 = embed_text_simple("deterministic test", dim=64)
        v2 = embed_text_simple("deterministic test", dim=64)
        assert v1 == v2

    def test_different_texts_different_vectors(self):
        v1 = embed_text_simple("cats are great", dim=64)
        v2 = embed_text_simple("dogs are amazing", dim=64)
        assert v1 != v2

    def test_empty_text(self):
        """Empty string should produce a zero-vector (normalized to zero)."""
        vec = embed_text_simple("", dim=64)
        assert all(v == 0.0 for v in vec)

    def test_different_dims(self):
        """Should work with various dimensions."""
        for dim in [32, 64, 128, 384]:
            vec = embed_text_simple("test", dim=dim)
            assert len(vec) == dim

    def test_works_with_hnsw_engine(self):
        """Embeddings should be usable directly with HNSWVectorMemory."""
        mem = HNSWVectorMemory(HNSWConfig(dim=64, space='cosine'))
        texts = ["machine learning", "deep learning", "cooking recipes", "data science"]
        for i, txt in enumerate(texts):
            vec = embed_text_simple(txt, dim=64)
            mem.add(f'txt{i}', vec, {'text': txt})

        query = embed_text_simple("neural networks", dim=64)
        results = mem.search(query, k=2)
        assert len(results) == 2
        # ML-related texts should rank higher
        result_ids = [r.id for r in results]
        assert len(result_ids) == 2


# ── Integration ─────────────────────────────────────────────────────


class TestIntegration:
    """End-to-end integration scenarios."""

    def test_full_lifecycle(self):
        """Create, populate, search, delete, save, load, search again."""
        dim = 64
        mem = _make_engine(dim=dim)

        # Populate
        docs = {
            'intro': ('Introduction to AI', _random_vector(dim, seed=1)),
            'methods': ('Research Methods', _random_vector(dim, seed=2)),
            'results': ('Experimental Results', _random_vector(dim, seed=3)),
            'conclusion': ('Conclusion', _random_vector(dim, seed=4)),
            'refs': ('References', _random_vector(dim, seed=5)),
        }
        for doc_id, (title, vec) in docs.items():
            mem.add(doc_id, vec, {'title': title})

        assert mem.size == 5

        # Search
        results = mem.search(docs['intro'][1], k=3)
        assert results[0].id == 'intro'

        # Delete
        mem.delete('refs')
        assert mem.size == 4

        # Save and reload
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'lifecycle')
            mem.save(path)
            loaded = HNSWVectorMemory.load(path)

            assert loaded.size == 4
            assert 'refs' not in loaded.ids

            # Search on loaded instance
            results = loaded.search(docs['results'][1], k=2)
            assert results[0].id == 'results'
            assert results[0].metadata['title'] == 'Experimental Results'

    def test_multiple_metrics_same_data(self):
        """Same data indexed under different metrics."""
        dim = 64
        vecs = [_random_vector(dim, seed=i + 6000) for i in range(5)]
        query = _random_vector(dim, seed=6999)

        for space in ('cosine', 'l2', 'ip'):
            mem = _make_engine(dim=dim, space=space)
            for i, v in enumerate(vecs):
                mem.add(f'd{i}', v)
            results = mem.search(query, k=3)
            assert len(results) == 3
            for r in results:
                assert 0.0 <= r.score <= 1.0
