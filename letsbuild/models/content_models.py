"""Pydantic v2 models for Layer 7: Content Factory."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ContentFormat(StrEnum):
    """Supported content output formats."""

    YOUTUBE_SCRIPT = "youtube_script"
    BLOG_POST = "blog_post"
    LINKEDIN_CAROUSEL = "linkedin_carousel"
    TWITTER_THREAD = "twitter_thread"
    PROJECT_WALKTHROUGH = "project_walkthrough"


class ContentOutput(BaseModel):
    """A single piece of generated content for a specific platform."""

    model_config = ConfigDict(strict=True)

    content_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this content piece.",
    )
    format: ContentFormat = Field(
        description="The content format / target platform type.",
    )
    title: str = Field(
        description="Title of the content piece.",
    )
    content: str = Field(
        description="Full content body (markdown or plain text).",
    )
    word_count: int = Field(
        description="Word count of the content body.",
    )
    target_platform: str = Field(
        description="Target platform name (e.g. 'YouTube', 'Medium', 'LinkedIn').",
    )
    seo_keywords: list[str] = Field(
        description="SEO keywords for discoverability.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this content was generated (UTC).",
    )
