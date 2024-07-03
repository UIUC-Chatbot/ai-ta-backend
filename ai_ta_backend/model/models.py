from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import JSON
from sqlalchemy import Text
from sqlalchemy.sql import func

from ai_ta_backend.extensions import db


class Base(db.Model):
  __abstract__ = True


class Document(Base):
  __tablename__ = 'documents'
  id = Column(BigInteger, primary_key=True, autoincrement=True)
  created_at = Column(DateTime, default=func.now())
  s3_path = Column(Text)
  readable_filename = Column(Text)
  course_name = Column(Text)
  url = Column(Text)
  contexts = Column(JSON, default=lambda: [{"text": "", "timestamp": "", "embedding": "", "pagenumber": ""}])
  base_url = Column(Text)

  __table_args__ = (
      Index('documents_course_name_idx', 'course_name', postgresql_using='hash'),
      Index('documents_created_at_idx', 'created_at', postgresql_using='btree'),
      Index('idx_doc_s3_path', 's3_path', postgresql_using='btree'),
  )


class DocumentDocGroup(Base):
  __tablename__ = 'documents_doc_groups'
  document_id = Column(BigInteger, primary_key=True)
  doc_group_id = Column(BigInteger, ForeignKey('doc_groups.id', ondelete='CASCADE'), primary_key=True)
  created_at = Column(DateTime, default=func.now())

  __table_args__ = (
      Index('documents_doc_groups_doc_group_id_idx', 'doc_group_id', postgresql_using='btree'),
      Index('documents_doc_groups_document_id_idx', 'document_id', postgresql_using='btree'),
  )


class DocGroup(Base):
  __tablename__ = 'doc_groups'
  id = Column(BigInteger, primary_key=True, autoincrement=True)
  name = Column(Text, nullable=False)
  course_name = Column(Text, nullable=False)
  created_at = Column(DateTime, default=func.now())
  enabled = Column(Boolean, default=True)
  private = Column(Boolean, default=True)
  doc_count = Column(BigInteger)

  __table_args__ = (Index('doc_groups_enabled_course_name_idx', 'enabled', 'course_name', postgresql_using='btree'),)


class Project(Base):
  __tablename__ = 'projects'
  id = Column(BigInteger, primary_key=True, autoincrement=True)
  created_at = Column(DateTime, default=func.now())
  course_name = Column(Text)
  doc_map_id = Column(Text)
  convo_map_id = Column(Text)
  n8n_api_key = Column(Text)
  last_uploaded_doc_id = Column(BigInteger)
  last_uploaded_convo_id = Column(BigInteger)
  subscribed = Column(BigInteger, ForeignKey('doc_groups.id', onupdate='CASCADE', ondelete='SET NULL'))


class N8nWorkflows(Base):
  __tablename__ = 'n8n_workflows'
  latest_workflow_id = Column(BigInteger, primary_key=True, autoincrement=True)
  is_locked = Column(Boolean, nullable=False)

  def __init__(self, is_locked: bool):
    self.is_locked = is_locked


class LlmConvoMonitor(Base):
  __tablename__ = 'llm_convo_monitor'
  id = Column(BigInteger, primary_key=True, autoincrement=True)
  created_at = Column(DateTime, default=func.now())
  convo = Column(JSON)
  convo_id = Column(Text, unique=True)
  course_name = Column(Text)
  user_email = Column(Text)

  __table_args__ = (
      Index('llm_convo_monitor_course_name_idx', 'course_name', postgresql_using='hash'),
      Index('llm_convo_monitor_convo_id_idx', 'convo_id', postgresql_using='hash'),
  )
