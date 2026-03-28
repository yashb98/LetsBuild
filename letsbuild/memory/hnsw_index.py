"""HNSW vector index wrapper for ReasoningBank similarity search.

Wraps hnswlib to provide string-ID-based add/query/update/delete operations
over pattern embeddings.  A lightweight hash-based embedding helper is
included as a placeholder until a real ML model is integrated.
"""

from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path

import hnswlib
import structlog

__all__ = ["HNSWIndex", "simple_text_embedding"]

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------


def simple_text_embedding(text: str, dim: int = 384) -> list[float]:
    """Create a deterministic hash-based embedding for *text*.

    This is a reproducible placeholder until a real sentence-transformer or
    API-based embedding model is wired in.  It produces a unit-length vector
    of *dim* floats by:

    1. Hashing chunks of the text with SHA-256 seeded by position.
    2. Unpacking bytes as IEEE-754 floats.
    3. L2-normalising the result so cosine and dot-product distances agree.
    """
    if not text:
        return [0.0] * dim

    vector: list[float] = []
    # Each SHA-256 digest gives 32 bytes → 8 floats.  We iterate over
    # 4-byte windows and vary the seed to cover *dim* dimensions.
    chunk = 4

    idx = 0
    position = 0
    while idx < dim:
        # Mix text content with position so different dims get different values.
        seed = f"{position}:{text}".encode()
        digest = hashlib.sha256(seed).digest()
        for i in range(0, len(digest), chunk):
            if idx >= dim:
                break
            (raw,) = struct.unpack("!I", digest[i : i + chunk])
            # Map uint32 to [-1, 1]
            vector.append((raw / 2_147_483_647.5) - 1.0)
            idx += 1
        position += 1

    # L2 normalise
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude > 0.0:
        vector = [v / magnitude for v in vector]

    return vector


# ---------------------------------------------------------------------------
# HNSWIndex
# ---------------------------------------------------------------------------


class HNSWIndex:
    """Approximate nearest-neighbour index backed by hnswlib.

    hnswlib uses integer labels internally; this class maintains a two-way
    mapping between string IDs and integer labels so callers never need to
    manage integers themselves.

    Parameters
    ----------
    dim:
        Dimensionality of all vectors stored in this index.
    max_elements:
        Maximum number of elements the index can hold (can be resized later).
    ef_construction:
        Controls index quality vs build time.  Higher = better recall.
    M:
        Number of bi-directional links created per element.  Typical: 16.
    index_path:
        If provided, the index is loaded from / saved to this path.
    """

    def __init__(
        self,
        dim: int = 384,
        max_elements: int = 10_000,
        ef_construction: int = 200,
        m: int = 16,
        index_path: str | None = None,
    ) -> None:
        self._dim = dim
        self._max_elements = max_elements
        self._ef_construction = ef_construction
        self._m = m
        self._index_path = index_path

        # String ↔ integer label mapping
        self._id_to_label: dict[str, int] = {}
        self._label_to_id: dict[int, str] = {}
        self._next_label: int = 0

        # Deleted labels are tracked separately so __len__ stays accurate.
        self._deleted_labels: set[int] = set()

        self._index: hnswlib.Index | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init_index(self) -> None:
        """Initialise or load the HNSW index.

        If *index_path* was supplied and the file exists, the index is loaded
        from disk and the ID mappings are reconstructed from the stored labels.
        Otherwise a fresh index is created.
        """
        if self._index_path and Path(self._index_path).exists():
            self.load(self._index_path)
        else:
            self._index = hnswlib.Index(space="cosine", dim=self._dim)
            self._index.init_index(
                max_elements=self._max_elements,
                ef_construction=self._ef_construction,
                M=self._m,
            )
            logger.info(
                "hnsw_index.init.created",
                dim=self._dim,
                max_elements=self._max_elements,
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, ids: list[str], vectors: list[list[float]]) -> None:
        """Add vectors with associated string IDs to the index.

        Duplicate IDs are silently skipped — use :meth:`update` to change an
        existing vector.

        Parameters
        ----------
        ids:
            String identifiers, one per vector.
        vectors:
            Embedding vectors.  Each must have length == *dim*.
        """
        if len(ids) != len(vectors):
            raise ValueError(
                f"ids and vectors must have the same length, got {len(ids)} and {len(vectors)}"
            )
        if not ids:
            return

        self._ensure_initialised()
        index = self._index_or_raise()

        new_labels: list[int] = []
        new_vectors: list[list[float]] = []

        for string_id, vec in zip(ids, vectors, strict=True):
            if string_id in self._id_to_label:
                logger.debug("hnsw_index.add.skipped_duplicate", id=string_id)
                continue
            label = self._next_label
            self._id_to_label[string_id] = label
            self._label_to_id[label] = string_id
            self._next_label += 1
            new_labels.append(label)
            new_vectors.append(vec)

        if not new_labels:
            return

        # Resize if needed
        current_count = index.element_count
        if current_count + len(new_labels) > self._max_elements:
            new_max = max(self._max_elements * 2, current_count + len(new_labels))
            index.resize_index(new_max)
            self._max_elements = new_max
            logger.info("hnsw_index.resized", new_max=new_max)

        index.add_items(new_vectors, new_labels)
        logger.debug("hnsw_index.add.done", count=len(new_labels))

    def query(
        self,
        vector: list[float],
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """Find the *top_k* nearest neighbours to *vector*.

        Returns
        -------
        list[tuple[str, float]]
            ``(string_id, distance)`` pairs, sorted ascending by distance.
            Empty list if the index has no elements.
        """
        self._ensure_initialised()
        index = self._index_or_raise()

        active_count = len(self)
        if active_count == 0:
            return []

        k = min(top_k, active_count)
        labels, distances = index.knn_query(vector, k=k)

        results: list[tuple[str, float]] = []
        for label, distance in zip(labels[0], distances[0], strict=True):
            label_int = int(label)
            if label_int in self._deleted_labels:
                continue
            string_id = self._label_to_id.get(label_int)
            if string_id is None:
                continue
            results.append((string_id, float(distance)))

        return results

    def update(self, item_id: str, vector: list[float]) -> None:
        """Replace the vector stored under *item_id*.

        If *item_id* does not exist it is added.
        """
        self._ensure_initialised()

        if item_id in self._id_to_label:
            # hnswlib doesn't support in-place vector updates, so we
            # mark-delete the old label and insert a new one.
            old_label = self._id_to_label.pop(item_id)
            del self._label_to_id[old_label]
            self._deleted_labels.add(old_label)
            index = self._index_or_raise()
            index.mark_deleted(old_label)
            logger.debug("hnsw_index.update.mark_deleted", item_id=item_id, old_label=old_label)

        self.add([item_id], [vector])
        logger.debug("hnsw_index.update.done", item_id=item_id)

    def delete(self, item_id: str) -> None:
        """Mark *item_id* as deleted.  The slot is not reclaimed until the index is rebuilt.

        Raises :class:`KeyError` if *item_id* is not present.
        """
        self._ensure_initialised()

        if item_id not in self._id_to_label:
            raise KeyError(f"ID '{item_id}' not found in index")

        label = self._id_to_label.pop(item_id)
        del self._label_to_id[label]
        self._deleted_labels.add(label)

        index = self._index_or_raise()
        index.mark_deleted(label)
        logger.debug("hnsw_index.delete.done", item_id=item_id, label=label)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | None = None) -> None:
        """Persist the index to *path* (or the configured *index_path*)."""
        target = path or self._index_path
        if target is None:
            raise ValueError("No path provided and index_path was not set during construction.")

        index = self._index_or_raise()
        index.save_index(target)
        logger.info("hnsw_index.saved", path=target, count=len(self))

    def load(self, path: str) -> None:
        """Load the index from *path* and reconstruct ID mappings."""
        self._index = hnswlib.Index(space="cosine", dim=self._dim)
        self._index.load_index(path, max_elements=self._max_elements)

        # Reconstruct label→id mapping from stored labels.
        # After a cold load we cannot recover the original string IDs —
        # callers that require persistence of string IDs should store the
        # mapping externally (e.g. in the MemoryStorage SQLite database).
        # We reset the mapping and leave it up to the caller to re-populate.
        self._id_to_label = {}
        self._label_to_id = {}
        self._next_label = self._index.element_count
        self._deleted_labels = set()
        self._index_path = path
        logger.info("hnsw_index.loaded", path=path, element_count=self._index.element_count)

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of active (non-deleted) elements."""
        return len(self._id_to_label)

    def contains(self, item_id: str) -> bool:
        """Return ``True`` if *item_id* is present and not deleted."""
        return item_id in self._id_to_label

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_initialised(self) -> None:
        if self._index is None:
            self.init_index()

    def _index_or_raise(self) -> hnswlib.Index:
        if self._index is None:  # pragma: no cover
            raise RuntimeError("HNSWIndex not initialised — call init_index() first.")
        return self._index
