from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class UserRoleEnum(str):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class QuestionTypeEnum(str):
    SINGLE = "single"
    MULTIPLE = "multiple"
    OPEN = "open"


class Subject(Base):
    __tablename__ = "subject"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    topics: Mapped[list["Topic"]] = relationship("Topic", back_populates="subject", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        "subjects_id", ForeignKey("subject.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    difficulty_level: Mapped[int] = mapped_column("difficullty_level", Integer, nullable=False, server_default="1")

    subject: Mapped[Subject] = relationship("Subject", back_populates="topics")
    questions: Mapped[list["Question"]] = relationship("Question", back_populates="topic", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRoleEnum.STUDENT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    tests: Mapped[list["Test"]] = relationship("Test", back_populates="user", cascade="all, delete-orphan")
    schedules: Mapped[list["Schedule"]] = relationship("Schedule", back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        "Recommendation", back_populates="user", cascade="all, delete-orphan"
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topics.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    question_text: Mapped[str] = mapped_column("questions_text", Text, nullable=False)
    question_type: Mapped[str] = mapped_column("questions_type", String(20), nullable=False, default=QuestionTypeEnum.SINGLE)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )

    topic: Mapped[Topic] = relationship("Topic", back_populates="questions")
    answers: Mapped[list["Answer"]] = relationship("Answer", back_populates="question", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")

    question: Mapped[Question] = relationship("Question", back_populates="answers")


class Test(Base):
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subject.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    test_type: Mapped[str] = mapped_column(String(10), nullable=False, default="quick")  # quick/full
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0.00")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    user: Mapped[User] = relationship("User", back_populates="tests")
    subject: Mapped[Subject] = relationship("Subject")
    results: Mapped[list["TestResult"]] = relationship(
        "TestResult", back_populates="test", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        "Recommendation", back_populates="test", cascade="all, delete-orphan"
    )


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    test_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tests.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    selected_answer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("answers.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    test: Mapped[Test] = relationship("Test", back_populates="results")
    question: Mapped[Question] = relationship("Question")
    selected_answer: Mapped[Answer | None] = relationship("Answer")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    test_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tests.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    user: Mapped[User] = relationship("User", back_populates="recommendations")
    test: Mapped[Test] = relationship("Test", back_populates="recommendations")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    topic_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topics.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    scheduled_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="planned")  # planned/completed

    user: Mapped[User] = relationship("User", back_populates="schedules")
    topic: Mapped[Topic] = relationship("Topic")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False, default="push")  # email/push
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    user: Mapped[User] = relationship("User", back_populates="notifications")

