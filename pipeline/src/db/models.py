"""
SQLAlchemy Models — Workflow Database (provenpick_workflow)

Tracks pipeline state: subscribed channels, processed videos,
pipeline jobs, and transcript cache.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Channel(Base):
    __tablename__ = "channels"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    channel_id      = Column(String(64), unique=True, nullable=False)   # YouTube channel ID e.g. "UCxxxxxx"
    channel_name    = Column(String(255))
    channel_url     = Column(String(512))
    is_active       = Column(Boolean, default=True)
    last_scanned_at = Column(DateTime(timezone=True))
    created_at      = Column(DateTime(timezone=True), default=utcnow)

    processed_videos = relationship("ProcessedVideo", back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Channel {self.channel_name} ({self.channel_id})>"


class ProcessedVideo(Base):
    __tablename__ = "processed_videos"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    video_id     = Column(String(64), unique=True, nullable=False)   # YouTube video ID
    channel_id   = Column(String(64), ForeignKey("channels.channel_id"), nullable=False)
    video_title  = Column(String(512))
    video_url    = Column(String(512))
    is_review    = Column(Boolean, nullable=False)   # True = product review, False = skipped
    skip_reason  = Column(Text)                      # Only set if is_review = False
    processed_at = Column(DateTime(timezone=True), default=utcnow)

    channel = relationship("Channel", back_populates="processed_videos")
    job     = relationship("PipelineJob", back_populates="video", uselist=False)

    def __repr__(self):
        status = "review" if self.is_review else f"skipped ({self.skip_reason})"
        return f"<ProcessedVideo {self.video_id} [{status}]>"


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    job_uuid      = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    video_id      = Column(String(64), ForeignKey("processed_videos.video_id"))
    status        = Column(String(64), default="queued")
    current_agent = Column(String(64))      # Which agent is actively working on this job
    attempt_count = Column(Integer, default=0)   # Rewrite attempts after rejection
    error_message = Column(Text)
    created_at    = Column(DateTime(timezone=True), default=utcnow)
    updated_at    = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    video = relationship("ProcessedVideo", back_populates="job")

    def __repr__(self):
        return f"<PipelineJob {self.job_uuid} [{self.status}]>"


class TranscriptCache(Base):
    __tablename__ = "transcript_cache"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    video_id          = Column(String(64), unique=True, nullable=False)
    original_language = Column(String(16))
    language          = Column(String(16))
    raw_transcript    = Column(Text, nullable=True)
    clean_transcript  = Column(Text, nullable=True)
    translated_text   = Column(Text)
    is_hindi          = Column(Boolean, default=False)
    cached_at         = Column(DateTime(timezone=True), default=utcnow)

    def __repr__(self):
        return f"<TranscriptCache {self.video_id} [{self.original_language or self.language}]>"
