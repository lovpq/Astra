"""Inline buttons, galleries and other Telegram-Bot-API stuff"""

# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ lovpq, 2025
# This file is a part of Astra Userbot
# 🌐 https://github.com/lovpq/Astra
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import contextlib
import logging
import time
import typing

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from aiogram.client.default import DefaultBotProperties
from astratl.errors.rpcerrorlist import InputUserDeactivatedError, YouBlockedUserError
from astratl.tl.functions.contacts import UnblockRequest
from astratl.tl.types import Message
from astratl.utils import get_display_name

from .. import utils
from ..database import Database
from ..tl_cache import CustomTelegramClient
from ..translations import Translator
from .bot_pm import BotPM
from .events import Events
from .form import Form
from .gallery import Gallery
from .list import List
from .query_gallery import QueryGallery
from .token_obtainment import TokenObtainment
from .utils import Utils

logger = logging.getLogger(__name__)


class InlineManager(
    Utils,
    Events,
    TokenObtainment,
    Form,
    Gallery,
    QueryGallery,
    List,
    BotPM,
):
    """
    Inline buttons, galleries and other Telegram-Bot-API stuff
    :param client: Telegram client
    :param db: Database instance
    :param allmodules: All modules
    :type client: astra.tl_cache.CustomTelegramClient
    :type db: astra.database.Database
    :type allmodules: astra.loader.Modules
    """

    def __init__(
        self,
        client: CustomTelegramClient,
        db: Database,
        allmodules: "Modules",  # type: ignore  # noqa: F821
    ):
        """Initialize InlineManager to create forms"""
        self._client = client
        self._db = db
        self._allmodules = allmodules
        self.translator: Translator = allmodules.translator

        self._units: typing.Dict[str, dict] = {}
        self._custom_map: typing.Dict[str, callable] = {}
        self.fsm: typing.Dict[str, str] = {}
        self._web_auth_tokens: typing.List[str] = []
        self._error_events: typing.Dict[str, asyncio.Event] = {}

        self._markup_ttl = 60 * 60 * 24
        self.init_complete = False

        self._token = db.get("astra.inline", "bot_token", False)

        self._me: int = None
        self._name: str = None
        self._dp: Dispatcher = None
        self._task: asyncio.Future = None
        self._cleaner_task: asyncio.Future = None
        self.bot: Bot = None
        self.bot_id: int = None
        self.bot_username: str = None

    async def _cleaner(self):
        """Cleans outdated inline units"""
        while True:
            for unit_id, unit in self._units.copy().items():
                if (unit.get("ttl") or (time.time() + self._markup_ttl)) < time.time():
                    del self._units[unit_id]

            await asyncio.sleep(5)

    async def register_manager(
        self,
        after_break: bool = False,
        ignore_token_checks: bool = False,
    ):
        """
        Register manager
        :param after_break: Loop marker
        :param ignore_token_checks: If `True`, will not check for token
        :type after_break: bool
        :type ignore_token_checks: bool
        :return: None
        :rtype: None
        """
        self._me = self._client.tg_id
        self._name = get_display_name(self._client.astra_me)

        if not ignore_token_checks:
            is_token_asserted = await self._assert_token()
            if not is_token_asserted:
                self.init_complete = False
                return

        self.init_complete = True

        self.bot = Bot(token=self._token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self._bot = self.bot
        self._dp = Dispatcher()

        try:
            bot_me = await self.bot.get_me()
            self.bot_username = bot_me.username
            self.bot_id = bot_me.id
        except TelegramUnauthorizedError:
            logger.critical("Token expired, revoking...")
            return await self._dp_revoke_token(False)

        try:
            m = await self._client.send_message(self.bot_username, "/start astra init")
        except (InputUserDeactivatedError, ValueError):
            self._db.set("astra.inline", "bot_token", None)
            self._token = False

            if not after_break:
                return await self.register_manager(True)

            self.init_complete = False
            return False
        except YouBlockedUserError:
            await self._client(UnblockRequest(id=self.bot_username))
            try:
                m = await self._client.send_message(
                    self.bot_username, "/start astra init"
                )
            except Exception:
                logger.critical("Can't unblock users bot", exc_info=True)
                return False
        except Exception:
            self.init_complete = False
            logger.critical("Initialization of inline manager failed!", exc_info=True)
            return False

        await self._client.delete_messages(self.bot_username, m)

        self._dp.inline_query.register(
            self._inline_handler,
            lambda _: True,
        )

        self._dp.callback_query.register(
            self._callback_query_handler,
            lambda _: True,
        )

        self._dp.chosen_inline_result.register(
            self._chosen_inline_handler,
            lambda _: True,
        )

        self._dp.message.register(
            self._message_handler,
            lambda *_: True,
        )

        old = self.bot.get_updates
        revoke = self._dp_revoke_token

        async def new(*args, **kwargs):
            nonlocal revoke, old
            try:
                return await old(*args, **kwargs)
            except TelegramConflictError:
                await revoke()
            except TelegramUnauthorizedError:
                logger.critical("Got Unauthorized")
                await self._stop()

        self.bot.get_updates = new

        self._task = asyncio.ensure_future(self._dp.start_polling(self._bot, handle_signals=False))
        self._cleaner_task = asyncio.ensure_future(self._cleaner())

    async def _stop(self):
        """Stop the bot"""
        self._task.cancel()
        await self._dp.stop_polling()
        self._cleaner_task.cancel()

    def pop_web_auth_token(self, token: str) -> bool:
        """
        Check if web confirmation button was pressed
        :param token: Token to check
        :type token: str
        :return: `True` if token was found, `False` otherwise
        :rtype: bool
        """
        if token not in self._web_auth_tokens:
            return False

        self._web_auth_tokens.remove(token)
        return True

    async def _invoke_unit(self, unit_id: str, message: Message) -> Message:
        if not self.init_complete:
            if isinstance(message, Message):
                return await message.respond("Inline bot is not initialized yet. Please wait...")
            else:
                return await self._client.send_message(message, "Inline bot is not initialized yet. Please wait...")

        event = asyncio.Event()
        self._error_events[unit_id] = event

        q: "InlineResults" = None  # type: ignore  # noqa: F821
        exception: Exception = None

        async def result_getter():
            nonlocal unit_id, q
            try:
                q = await self._client.inline_query(self.bot_username, unit_id)
                if q and hasattr(q, 'result') and q.result:
                    event.set()
            except Exception as e:
                logger.error(f"Error in inline query: {e}")
                event.set()

        async def event_poller():
            nonlocal exception
            try:
                await asyncio.wait_for(event.wait(), timeout=10)
                if self._error_events.get(unit_id):
                    exception = self._error_events[unit_id]
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for inline query results")

        result_getter_task = asyncio.ensure_future(result_getter())
        event_poller_task = asyncio.ensure_future(event_poller())

        _, pending = await asyncio.wait(
            [result_getter_task, event_poller_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        self._error_events.pop(unit_id, None)

        if exception and isinstance(exception, BaseException):
            raise exception  # skipcq: PYL-E0702

        if not q or not hasattr(q, 'result') or not q.result:
            # Если нет результатов, отправляем обычное сообщение
            if isinstance(message, Message):
                return await message.respond("No inline results available. Please try again in a few seconds.")
            else:
                return await self._client.send_message(message, "No inline results available. Please try again in a few seconds.")

        try:
            # Получаем первый результат из списка
            first_result = next(iter(q.result), None)
            if not first_result:
                raise Exception("No results available")

            return await first_result.click(
                utils.get_chat_id(message) if isinstance(message, Message) else message,
                reply_to=(
                    message.reply_to_msg_id if isinstance(message, Message) else None
                ),
            )
        except Exception as e:
            logger.error(f"Error clicking inline result: {e}")
            if isinstance(message, Message):
                return await message.respond("Error sending inline message. Please try again.")
            else:
                return await self._client.send_message(message, "Error sending inline message. Please try again.")
