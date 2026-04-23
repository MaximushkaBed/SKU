from fastapi import APIRouter, Depends

from auth import DBSession, get_current_user
from models import User
from schemas import AiChatMessage, AiChatReply, ClusterInfoRead, EnhancedRecommendationRead
from services.intelligence import ai_assistant_reply, build_enhanced_recommendations, get_user_cluster


router = APIRouter(prefix="/ai", tags=["AI Module"])


@router.get("/cluster-me", response_model=ClusterInfoRead)
def cluster_me(
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> ClusterInfoRead:
    data = get_user_cluster(db, current_user.id)
    return ClusterInfoRead(**data)


@router.get("/recommendations-plus", response_model=list[EnhancedRecommendationRead])
def recommendations_plus(
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> list[EnhancedRecommendationRead]:
    return build_enhanced_recommendations(db, current_user.id)


@router.post("/assistant", response_model=AiChatReply)
def assistant_chat(
    payload: AiChatMessage,
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> AiChatReply:
    data = ai_assistant_reply(db, current_user.id, payload.message)
    return AiChatReply(**data)
