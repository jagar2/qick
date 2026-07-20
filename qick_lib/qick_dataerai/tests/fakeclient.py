"""A recording test double for ``dataerai.DataeraiClient``.

It mirrors the SDK's ``upload`` and ``create_relationship`` signatures exactly,
records every call, and verifies the temp file existed (and had content) at
upload time — so tests can assert the provenance flow without a daemon or socket.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Optional


@dataclass
class FakeUpload:
    local_path: str
    title: str
    owner_type: str
    owner_id: str
    collection_id: Optional[str]
    description: Optional[str]
    tags: Optional[list]
    metadata: Optional[dict]
    existed: bool  # did the file exist and have content when upload was called?
    content_head: bytes  # first bytes read (proves real content was written)


@dataclass
class FakeRelationship:
    from_asset_id: str
    to_asset_id: str
    rel_type: str
    analysis_mode: Optional[str]
    qualifier_note: Optional[str]
    qualifiers: Optional[dict]


class FakeClient:
    """Records uploads/relationships; optionally fails selected calls.

    Args:
        fail_on: a set of ``{"upload", "relationship"}`` selecting calls that
            should raise ``RuntimeError`` instead of succeeding.
    """

    def __init__(self, fail_on: Optional[set] = None) -> None:
        self.uploads: list[FakeUpload] = []
        self.relationships: list[FakeRelationship] = []
        self._fail_on = set(fail_on or ())
        self._n = 0

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_: Any) -> bool:
        return False

    def auth_status(self):
        return SimpleNamespace(user_email="tester@example.com", expires_at=None)

    def upload(self, local_path, *, title, owner_type, owner_id, collection_id=None,
               description=None, alias=None, tags=None, metadata=None, on_progress=None):
        existed = os.path.exists(local_path) and os.path.getsize(local_path) > 0
        head = b""
        if existed:
            with open(local_path, "rb") as fh:
                head = fh.read(64)
        if "upload" in self._fail_on:
            raise RuntimeError("boom-upload")
        self._n += 1
        self.uploads.append(
            FakeUpload(local_path, title, owner_type, owner_id, collection_id,
                       description, tags, metadata, existed, head)
        )
        return SimpleNamespace(
            transfer_id=f"xfer-{self._n}",
            asset_id=f"asset-{self._n}",
            content_id=f"content-{self._n}",
            total_bytes=len(head),
            chunk_count=1,
        )

    def create_relationship(self, from_asset_id, to_asset_id, rel_type, *,
                            analysis_mode=None, qualifier_note=None,
                            qualifier_time=None, qualifiers=None):
        if "relationship" in self._fail_on:
            raise RuntimeError("boom-rel")
        self.relationships.append(
            FakeRelationship(from_asset_id, to_asset_id, rel_type,
                             analysis_mode, qualifier_note, qualifiers)
        )
        return SimpleNamespace(
            id=f"rel-{len(self.relationships)}",
            type=rel_type,
            direction="outgoing",
            from_asset_id=from_asset_id,
            to_asset_id=to_asset_id,
            analysis_mode=analysis_mode,
            qualifier_note=qualifier_note,
            related_asset={"id": to_asset_id, "title": "", "alias": ""},
        )
