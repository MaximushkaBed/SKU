from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr

from models import QuestionTypeEnum, UserRoleEnum


class UserBase(BaseModel):
    full_name: str
    email: EmailStr


class UserCreate(UserBase):
    password: str
    role: Optional[str] = UserRoleEnum.STUDENT


class UserRead(BaseModel):
    full_name: str
    email: str
    id: int
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int
    role: str


class SubjectBase(BaseModel):
    name: str
    description: Optional[str] = None


class SubjectCreate(SubjectBase):
    pass


class SubjectRead(SubjectBase):
    id: int

    class Config:
        from_attributes = True


class TopicBase(BaseModel):
    name: str
    difficulty_level: Optional[int] = None


class TopicCreate(TopicBase):
    subject_id: int


class TopicRead(TopicBase):
    id: int
    subject_id: int

    class Config:
        from_attributes = True


class AnswerBase(BaseModel):
    answer_text: str
    is_correct: bool = False


class AnswerCreate(AnswerBase):
    pass


class AnswerRead(AnswerBase):
    id: int

    class Config:
        from_attributes = True


class QuestionBase(BaseModel):
    question_text: str
    question_type: str = QuestionTypeEnum.SINGLE
    difficulty: Optional[int] = 1


class QuestionCreate(QuestionBase):
    topic_id: int
    answers: List[AnswerCreate]


class QuestionRead(QuestionBase):
    id: int
    topic_id: int
    answers: List[AnswerRead]

    class Config:
        from_attributes = True


class TestCreate(BaseModel):
    subject_id: int
    test_type: str = "quick"


class TestAnswer(BaseModel):
    question_id: int
    selected_answer_id: Optional[int] = None
    answer_text: Optional[str] = None


class TestResultRead(BaseModel):
    question_id: int
    is_correct: bool

    class Config:
        from_attributes = True


class RecommendationRead(BaseModel):
    id: int
    recommendation_text: str

    class Config:
        from_attributes = True


class TestRead(BaseModel):
    id: int
    subject_id: int
    created_at: datetime
    score: float
    test_type: str
    results: List[TestResultRead] = []
    recommendations: List[RecommendationRead] = []

    class Config:
        from_attributes = True


class TopicStatRead(BaseModel):
    topic_id: int
    topic_name: str
    mistakes: int


class WrongQuestionLinkRead(BaseModel):
    test_id: int
    question_id: int
    question_text: str
    topic_name: Optional[str] = None
    help_url: str


class TestHistoryItemRead(BaseModel):
    id: int
    subject_id: int
    subject_name: str
    created_at: datetime
    score: float
    test_type: str
    total_questions: int
    correct_answers: int
    level: str
    weak_topics: List[TopicStatRead] = []
    wrong_questions: List[WrongQuestionLinkRead] = []


class SubjectProgressRead(BaseModel):
    subject_id: int
    subject_name: str
    total_tests: int
    average_score: float
    best_score: float
    latest_score: float
    level: str
    weak_topics: List[TopicStatRead] = []


class StudentProgressRead(BaseModel):
    total_tests: int
    average_score: float
    completed_subjects: int
    latest_activity: Optional[datetime] = None
    strongest_subject: Optional[str] = None
    weakest_subject: Optional[str] = None
    subjects: List[SubjectProgressRead] = []


class StudyActionRead(BaseModel):
    title: str
    description: str
    priority: str


class ResourceLinkRead(BaseModel):
    title: str
    url: str
    resource_type: str
    description: str


class QuestionExplanationRead(BaseModel):
    test_id: int
    question_id: int
    subject_name: Optional[str] = None
    topic_name: Optional[str] = None
    question_text: str
    status: str  # "unanswered" | "incorrect" | "unknown"
    selected_answer_text: Optional[str] = None
    correct_answers: List[str] = []
    resources: List[ResourceLinkRead] = []


class StudentInsightsRead(BaseModel):
    current_level: str
    average_score: float
    trend: str
    focus_subject: Optional[str] = None
    strongest_subject: Optional[str] = None
    recommended_test_subject: Optional[str] = None
    recommended_test_type: str
    motivation_message: str
    priority_topics: List[TopicStatRead] = []
    action_plan: List[StudyActionRead] = []
    resources: List[ResourceLinkRead] = []


class StudyPlanItemRead(BaseModel):
    day_label: str
    title: str
    focus_subject: Optional[str] = None
    topic_name: Optional[str] = None
    duration_minutes: int
    item_type: str
    priority: str


class StudentStudyPlanRead(BaseModel):
    generated_at: datetime
    horizon_days: int
    overview: str
    items: List[StudyPlanItemRead] = []


class ScheduleBase(BaseModel):
    scheduled_date: datetime
    topic_id: int
    status: str = "planned"


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleRead(ScheduleBase):
    id: int

    class Config:
        from_attributes = True


class NotificationRead(BaseModel):
    id: int
    message: str
    type: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ScatterPoint(BaseModel):
    x: float          # activity index, normalized 0–1
    y: float          # performance index, normalized 0–1
    cluster_id: int
    is_self: bool


class ClusterCenterInfo(BaseModel):
    cluster_id: int
    cluster_name: str
    x: float
    y: float


class ClusterInfoRead(BaseModel):
    cluster_id: int
    cluster_name: str
    summary: str
    peers_count: int
    total_students: int
    features: dict[str, float]
    feature_labels: dict[str, str]
    scatter_points: List[ScatterPoint] = []
    cluster_centers: List[ClusterCenterInfo] = []


class EnhancedRecommendationRead(BaseModel):
    title: str
    reason: str
    actions: List[str]
    confidence: float


class AiChatMessage(BaseModel):
    message: str


class AiChatReply(BaseModel):
    reply: str
    hints: List[str] = []

