from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from loguru import logger

class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get('event_from_user')
        if user:
            logger.info(f"Сообщение от {user.id} (@{user.username}): {event.text if hasattr(event, 'text') else 'не текст'}")
        return await handler(event, data)