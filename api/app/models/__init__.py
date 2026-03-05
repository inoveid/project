from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.team import Team
from app.models.agent import Agent
from app.models.agent_link import AgentLink
from app.models.session import Session, Message
from app.models.oauth_token import OAuthToken

__all__ = ["Base", "Team", "Agent", "AgentLink", "Session", "Message", "OAuthToken"]
