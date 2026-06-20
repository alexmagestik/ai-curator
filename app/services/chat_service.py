from __future__ import annotations

from dataclasses import dataclass, replace

from app.analytics.logger import RequestLogger, Timer
from app.database.models import ChatSession, Message, UserProfile
from app.database.repository import ChatRepository, UserRepository
from app.lms.handler import LMSHandler
from app.rag.context import format_sources_for_display
from app.rag.pipeline import RAGPipeline, RAGResponse
from app.services.level_detector import (
    LevelDetectionResult,
    LevelDetector,
    classify_intent,
    update_user_level,
)
from app.utils.config import Settings, get_settings


@dataclass(frozen=True)
class ChatTurnResult:
    answer: str
    response_type: str
    session: ChatSession
    user_message: Message
    assistant_message: Message
    sources_text: str
    fragments_text: str
    detected_level: LevelDetectionResult
    user_profile: UserProfile
    response_time: float
    question_category: str
    sources_count: int
    answer_found: bool
    module: str | None
    rag_response: RAGResponse | None = None


class ChatService:
    def __init__(
        self,
        pipeline: RAGPipeline | None = None,
        chat_repository: ChatRepository | None = None,
        user_repository: UserRepository | None = None,
        level_detector: LevelDetector | None = None,
        lms_handler: LMSHandler | None = None,
        request_logger: RequestLogger | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.pipeline = pipeline or RAGPipeline(self.settings)
        self.chats = chat_repository or ChatRepository(self.settings)
        self.users = user_repository or UserRepository(self.settings)
        self.level_detector = level_detector or LevelDetector(self.settings)
        self.lms_handler = lms_handler or LMSHandler(self.settings)
        self.request_logger = request_logger or RequestLogger()

    def get_or_create_session(
        self,
        user_id: int,
        session_id: int | None,
    ) -> ChatSession:
        if session_id is not None:
            session = self.chats.get_session(session_id, user_id)
            if session is not None:
                return session
        return self.chats.create_session(user_id)

    def load_session_messages(self, session_id: int, user_id: int) -> list[dict]:
        session = self.chats.get_session(session_id, user_id)
        if session is None:
            return []

        messages = self.chats.get_messages(session_id)
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def _resolve_user_level(self, user_id: int) -> str:
        profile = self.users.get_profile(user_id)
        return profile.current_level if profile else "intermediate"

    def send_message(
        self,
        *,
        user_id: int,
        session_id: int | None,
        question: str,
        filters: dict[str, str] | None = None,
    ) -> ChatTurnResult:
        session = self.get_or_create_session(user_id, session_id)
        history = self.load_session_messages(session.id, user_id)
        user_level = self._resolve_user_level(user_id)

        intent = classify_intent(question)
        rag_response: RAGResponse | None = None
        retrieved_documents = []

        with Timer() as timer:
            if intent == "organizational":
                answer = self.lms_handler.answer(
                    question,
                    user_level=user_level,
                    chat_history=history,
                )
                response_type = "lms"
                sources_text = "**Источник:** LMS API (расписание, задания, информация о курсе)"
                fragments_text = "Организационный вопрос — поиск по базе знаний не выполнялся."
            else:
                rag_response = self.pipeline.ask(
                    question,
                    user_level=user_level,
                    filters=filters,
                    chat_history=history,
                    max_history_messages=self.settings.max_history_messages,
                )
                answer = rag_response.answer
                response_type = "rag"
                retrieved_documents = rag_response.retrieved_documents
                sources_text = format_sources_for_display(rag_response.sources)
                fragments = []
                for index, item in enumerate(rag_response.retrieved_documents, start=1):
                    meta = item.document.metadata
                    fragments.append(
                        f"**{index}. {meta.get('file_name')}** "
                        f"(`{meta.get('module')}`, score={item.score:.3f}, "
                        f"source={item.source})\n\n"
                        f"{item.document.page_content[:400]}..."
                    )
                fragments_text = "\n\n".join(fragments) if fragments else "Фрагменты не найдены."

        metrics = self.request_logger.build_metrics(
            question=question,
            answer=answer,
            response_time=timer.elapsed,
            response_type=response_type,
            retrieved_documents=retrieved_documents,
            prompt_text=question,
        )
        if rag_response:
            metrics = replace(
                metrics,
                tokens_input=rag_response.tokens_input or metrics.tokens_input,
                tokens_output=rag_response.tokens_output or metrics.tokens_output,
            )

        self.request_logger.log(
            user_id=user_id,
            question=question,
            answer=answer,
            metrics=metrics,
            response_type=response_type,
        )

        user_message = self.chats.add_message(session.id, "user", question)
        assistant_message = self.chats.add_message(session.id, "assistant", answer)

        if session.message_count == 0:
            title = question.strip()[:80] or "Новый диалог"
            self.chats.update_session_title(session.id, title)
            session = self.chats.get_session(session.id, user_id) or session

        detection = self.level_detector.detect(question, history)
        user_profile = update_user_level(self.users, user_id, detection)

        return ChatTurnResult(
            answer=answer,
            response_type=response_type,
            session=session,
            user_message=user_message,
            assistant_message=assistant_message,
            sources_text=sources_text,
            fragments_text=fragments_text,
            detected_level=detection,
            user_profile=user_profile,
            response_time=metrics.response_time,
            question_category=metrics.question_category,
            sources_count=metrics.sources_count,
            answer_found=metrics.answer_found,
            module=metrics.module,
            rag_response=rag_response,
        )

    def list_sessions(self, user_id: int) -> list[ChatSession]:
        return self.chats.list_sessions(user_id)

    def search_sessions(self, user_id: int, query: str) -> list[ChatSession]:
        if not query.strip():
            return self.list_sessions(user_id)
        return self.chats.search_sessions(user_id, query)
