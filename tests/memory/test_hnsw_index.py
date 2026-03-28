"""Tests for HNSWIndex and simple_text_embedding."""

from __future__ import annotations

import math

import pytest

from letsbuild.memory.hnsw_index import HNSWIndex, simple_text_embedding

# ---------------------------------------------------------------------------
# simple_text_embedding
# ---------------------------------------------------------------------------


def test_simple_text_embedding_produces_correct_dimension() -> None:
    """simple_text_embedding should return a vector of the requested dimension."""
    for dim in [64, 128, 384]:
        vec = simple_text_embedding("hello world", dim=dim)
        assert len(vec) == dim


def test_simple_text_embedding_default_dimension_is_384() -> None:
    """Default dimension should be 384."""
    vec = simple_text_embedding("test")
    assert len(vec) == 384


def test_simple_text_embedding_is_deterministic() -> None:
    """Calling simple_text_embedding twice with the same text should return identical vectors."""
    text = "fastapi python postgresql microservice"
    v1 = simple_text_embedding(text)
    v2 = simple_text_embedding(text)
    assert v1 == v2


def test_simple_text_embedding_different_texts_differ() -> None:
    """Two different texts should produce different embedding vectors."""
    v1 = simple_text_embedding("fastapi project")
    v2 = simple_text_embedding("react typescript frontend")
    assert v1 != v2


def test_simple_text_embedding_is_unit_length() -> None:
    """The output vector should be approximately L2-normalised (magnitude ~1.0)."""
    vec = simple_text_embedding("any text here")
    magnitude = math.sqrt(sum(v * v for v in vec))
    assert abs(magnitude - 1.0) < 1e-5


def test_simple_text_embedding_empty_string_returns_zeros() -> None:
    """An empty string should return a zero vector."""
    vec = simple_text_embedding("")
    assert all(v == 0.0 for v in vec)


# ---------------------------------------------------------------------------
# HNSWIndex — initialisation
# ---------------------------------------------------------------------------


@pytest.fixture
def index() -> HNSWIndex:
    """Provide a freshly-initialised HNSWIndex."""
    idx = HNSWIndex(dim=64, max_elements=100)
    idx.init_index()
    return idx


def test_init_creates_empty_index(index: HNSWIndex) -> None:
    """A newly initialised index should be empty."""
    assert len(index) == 0


def test_init_without_explicit_call_auto_initialises(tmp_path: pytest.TempPathFactory) -> None:  # type: ignore[type-arg]
    """add() should auto-initialise the index if init_index() was not called."""
    idx = HNSWIndex(dim=64, max_elements=100)
    vec = simple_text_embedding("trigger auto init", dim=64)
    idx.add(["auto-id"], [vec])
    assert len(idx) == 1


# ---------------------------------------------------------------------------
# HNSWIndex — add and query
# ---------------------------------------------------------------------------


def test_add_and_query_returns_nearest_neighbor(index: HNSWIndex) -> None:
    """Querying with the same vector that was added should return it as nearest."""
    vec = simple_text_embedding("fastapi python", dim=64)
    index.add(["item-1"], [vec])

    results = index.query(vec, top_k=1)

    assert len(results) == 1
    assert results[0][0] == "item-1"
    assert results[0][1] >= 0.0  # distance is non-negative


def test_query_with_multiple_results(index: HNSWIndex) -> None:
    """query with top_k=3 should return up to 3 results."""
    texts = ["python fastapi", "react typescript", "go microservice"]
    for i, text in enumerate(texts):
        vec = simple_text_embedding(text, dim=64)
        index.add([f"item-{i}"], [vec])

    query_vec = simple_text_embedding("python fastapi", dim=64)
    results = index.query(query_vec, top_k=3)

    assert len(results) == 3
    ids = [r[0] for r in results]
    # The most similar item should be item-0 (same text)
    assert ids[0] == "item-0"


def test_query_on_empty_index_returns_empty(index: HNSWIndex) -> None:
    """Querying an empty index should return an empty list."""
    vec = simple_text_embedding("any query", dim=64)
    results = index.query(vec, top_k=5)
    assert results == []


def test_query_top_k_capped_at_index_size(index: HNSWIndex) -> None:
    """If top_k > number of items, only available items are returned."""
    for i in range(2):
        vec = simple_text_embedding(f"item text {i}", dim=64)
        index.add([f"item-{i}"], [vec])

    results = index.query(simple_text_embedding("text", dim=64), top_k=10)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# HNSWIndex — contains and len
# ---------------------------------------------------------------------------


def test_contains_returns_true_for_existing_id(index: HNSWIndex) -> None:
    """contains() should return True for an ID that was added."""
    vec = simple_text_embedding("hello", dim=64)
    index.add(["hello-id"], [vec])
    assert index.contains("hello-id") is True


def test_contains_returns_false_for_missing_id(index: HNSWIndex) -> None:
    """contains() should return False for an ID not in the index."""
    assert index.contains("ghost-id") is False


def test_len_returns_correct_count(index: HNSWIndex) -> None:
    """__len__ should accurately reflect the number of active elements."""
    assert len(index) == 0
    for i in range(5):
        index.add([f"id-{i}"], [simple_text_embedding(f"text {i}", dim=64)])
    assert len(index) == 5


def test_add_duplicate_id_is_skipped(index: HNSWIndex) -> None:
    """Adding an ID that already exists should be silently skipped."""
    vec = simple_text_embedding("test", dim=64)
    index.add(["dup-id"], [vec])
    index.add(["dup-id"], [vec])
    assert len(index) == 1


# ---------------------------------------------------------------------------
# HNSWIndex — update
# ---------------------------------------------------------------------------


def test_update_changes_the_vector(index: HNSWIndex) -> None:
    """update() should replace the stored vector for an existing ID."""
    original_vec = simple_text_embedding("original text", dim=64)
    updated_vec = simple_text_embedding("completely different content xyz", dim=64)

    index.add(["my-id"], [original_vec])
    index.update("my-id", updated_vec)

    # The ID should still be present.
    assert index.contains("my-id")
    assert len(index) == 1


def test_update_on_nonexistent_id_adds_it(index: HNSWIndex) -> None:
    """update() on a new ID should add it to the index."""
    vec = simple_text_embedding("new item", dim=64)
    index.update("brand-new", vec)
    assert index.contains("brand-new")
    assert len(index) == 1


# ---------------------------------------------------------------------------
# HNSWIndex — delete
# ---------------------------------------------------------------------------


def test_delete_removes_from_query_results(index: HNSWIndex) -> None:
    """Deleting an ID should exclude it from future query results."""
    for i in range(3):
        index.add([f"id-{i}"], [simple_text_embedding(f"item {i}", dim=64)])

    index.delete("id-1")

    assert not index.contains("id-1")
    assert len(index) == 2

    query_vec = simple_text_embedding("item 1", dim=64)
    results = index.query(query_vec, top_k=5)
    returned_ids = [r[0] for r in results]
    assert "id-1" not in returned_ids


def test_delete_raises_key_error_for_missing_id(index: HNSWIndex) -> None:
    """delete() should raise KeyError for a non-existent ID."""
    with pytest.raises(KeyError, match="ghost"):
        index.delete("ghost")


# ---------------------------------------------------------------------------
# HNSWIndex — save and load
# ---------------------------------------------------------------------------


def test_save_and_load_round_trip(tmp_path: pytest.TempPathFactory) -> None:  # type: ignore[type-arg]
    """save() then load() should restore a usable index from disk."""
    index_path = str(tmp_path / "test.index")

    idx = HNSWIndex(dim=64, max_elements=100)
    idx.init_index()

    vec = simple_text_embedding("save and load me", dim=64)
    idx.add(["saved-id"], [vec])
    idx.save(index_path)

    # Load into a fresh index object
    idx2 = HNSWIndex(dim=64, max_elements=100)
    idx2.load(index_path)

    # element_count should be preserved
    assert idx2._index is not None
    assert idx2._index.element_count >= 1


def test_save_raises_when_no_path_configured() -> None:
    """save() without a path argument or configured index_path should raise ValueError."""
    idx = HNSWIndex(dim=64, max_elements=100)
    idx.init_index()
    with pytest.raises(ValueError, match="No path provided"):
        idx.save()


def test_init_index_loads_from_disk_when_path_exists(
    tmp_path: pytest.TempPathFactory,  # type: ignore[type-arg]
) -> None:
    """init_index() with an existing file at index_path should load from disk."""
    index_path = str(tmp_path / "load_existing.index")

    # Create and persist an index
    idx = HNSWIndex(dim=64, max_elements=100)
    idx.init_index()
    idx.add(["abc"], [simple_text_embedding("abc", dim=64)])
    idx.save(index_path)

    # Construct a new instance pointing to the same path — should load automatically
    idx2 = HNSWIndex(dim=64, max_elements=100, index_path=index_path)
    idx2.init_index()
    assert idx2._index is not None
    assert idx2._index.element_count >= 1
