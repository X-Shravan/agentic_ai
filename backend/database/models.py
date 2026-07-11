"""
Database Schema Initialization
Creates all necessary tables for surveillance system
"""

import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Text, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os

logger = logging.getLogger(__name__)

Base = declarative_base()


# ==================== MODELS ====================

class Student(Base):
    """Student information"""
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True)
    student_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    roll_number = Column(String(50))
    email = Column(String(255))
    camera_id = Column(String(50), nullable=False)
    seat_x = Column(Float)
    seat_y = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    alerts = relationship("Alert", back_populates="student")
    tracking_logs = relationship("TrackingLog", back_populates="student")
    risk_scores = relationship("RiskScore", back_populates="student")
    behavior_history = relationship("BehaviorHistory", back_populates="student")
    
    __table_args__ = (
        Index('idx_student_id_camera', 'student_id', 'camera_id'),
    )


class Alert(Base):
    """Alert records"""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True)
    alert_id = Column(String(50), unique=True, nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    camera_id = Column(String(50), nullable=False)
    alert_type = Column(String(100))  # leaning, phone, gaze, etc.
    severity = Column(String(20))  # low, medium, high, critical
    risk_score = Column(Float)
    behaviors = Column(JSON)  # Array of detected behaviors
    component_scores = Column(JSON)  # {gaze, pose, phone, etc.}
    reason = Column(Text)
    gemini_explanation = Column(Text)
    evidence_captured = Column(Boolean, default=False)
    evidence_path = Column(String(500))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    student = relationship("Student", back_populates="alerts")
    evidence_images = relationship("EvidenceImage", back_populates="alert", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_alert_student_timestamp', 'student_id', 'timestamp'),
        Index('idx_alert_severity', 'severity'),
    )


class TrackingLog(Base):
    """Student tracking logs"""
    __tablename__ = "tracking_logs"
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    camera_id = Column(String(50), nullable=False, index=True)
    track_id = Column(Integer)  # DeepSORT track ID
    bbox = Column(JSON)  # [x1, y1, x2, y2]
    confidence = Column(Float)
    detection_class = Column(String(50))  # person, phone, book
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    student = relationship("Student", back_populates="tracking_logs")
    
    __table_args__ = (
        Index('idx_tracking_camera_timestamp', 'camera_id', 'timestamp'),
    )


class RiskScore(Base):
    """Risk score history"""
    __tablename__ = "risk_scores"
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    camera_id = Column(String(50), nullable=False)
    score = Column(Float, nullable=False)  # 0-100
    risk_level = Column(String(20))  # low, medium, high, critical
    components = Column(JSON)  # {gaze: 0.3, pose: 0.25, phone: 0.2, etc.}
    behaviors = Column(JSON)  # Detected behaviors
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    student = relationship("Student", back_populates="risk_scores")
    
    __table_args__ = (
        Index('idx_risk_student_timestamp', 'student_id', 'timestamp'),
        Index('idx_risk_level', 'risk_level'),
    )


class BehaviorHistory(Base):
    """Behavior event history"""
    __tablename__ = "behavior_history"
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    camera_id = Column(String(50), nullable=False)
    behavior_type = Column(String(100), nullable=False)  # leaning, phone, gaze, etc.
    severity = Column(Float)  # 0-1
    confidence = Column(Float)
    duration_ms = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    student = relationship("Student", back_populates="behavior_history")
    
    __table_args__ = (
        Index('idx_behavior_student_timestamp', 'student_id', 'timestamp'),
        Index('idx_behavior_type', 'behavior_type'),
    )


class CameraStream(Base):
    """Camera stream information"""
    __tablename__ = "camera_streams"
    
    id = Column(Integer, primary_key=True)
    camera_id = Column(String(50), unique=True, nullable=False, index=True)
    rtsp_url = Column(String(500), nullable=False)
    location = Column(String(255))
    resolution = Column(JSON)  # [width, height]
    fps = Column(Integer, default=30)
    status = Column(String(50))  # active, inactive, error
    last_frame_time = Column(DateTime)
    connected_peers = Column(Integer, default=0)
    health_score = Column(Float, default=1.0)  # 0-1
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EvidenceImage(Base):
    """Evidence snapshots"""
    __tablename__ = "evidence_images"
    
    id = Column(Integer, primary_key=True)
    evidence_id = Column(String(50), unique=True, nullable=False, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    camera_id = Column(String(50), nullable=False)
    image_path = Column(String(500), nullable=False)
    image_base64 = Column(Text)  # For small images
    features = Column(JSON)  # Detected features in image
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    alert = relationship("Alert", back_populates="evidence_images")


class Report(Base):
    """Exam session reports"""
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True)
    report_id = Column(String(50), unique=True, nullable=False, index=True)
    exam_id = Column(String(100), nullable=False, index=True)
    exam_name = Column(String(255))
    subject = Column(String(255))
    duration_minutes = Column(Integer)
    generated_at = Column(DateTime, default=datetime.utcnow)
    pdf_path = Column(String(500))
    
    # Summary statistics
    total_students = Column(Integer)
    students_flagged = Column(Integer)
    total_alerts = Column(Integer)
    critical_alerts = Column(Integer)
    high_alerts = Column(Integer)
    
    summary = Column(JSON)  # {high_risk_students: [], key_incidents: [], etc.}
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_report_exam', 'exam_id'),
    )


class SessionMetadata(Base):
    """Session-level metadata"""
    __tablename__ = "session_metadata"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), unique=True, nullable=False, index=True)
    exam_id = Column(String(100), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    total_frames_processed = Column(Integer, default=0)
    total_alerts = Column(Integer, default=0)
    avg_detection_latency_ms = Column(Float)
    avg_fps = Column(Float)
    system_status = Column(JSON)  # {cpu, memory, gpu_memory, bandwidth}
    
    __table_args__ = (
        Index('idx_session_exam', 'exam_id'),
    )


# ==================== INITIALIZATION ====================

def init_database(database_url: str):
    """Initialize database and create all tables"""
    
    logger.info(f"🗄️ Initializing database: {database_url}")
    
    try:
        # Create engine
        engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )
        
        # Create all tables
        Base.metadata.create_all(engine)
        logger.info("✅ Database tables created successfully")
        
        # Create session factory
        Session = sessionmaker(bind=engine)
        return Session
    
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


def get_database_session(database_url: str):
    """Get database session"""
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == "__main__":
    # Example usage
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/surveillance"
    )
    
    Session = init_database(database_url)
    logger.info("✅ Database ready")
