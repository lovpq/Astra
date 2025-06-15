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
import logging
import re
import os

from astratl.errors.rpcerrorlist import YouBlockedUserError
from astratl.tl.functions.contacts import UnblockRequest

from .. import utils
from .._internal import fw_protect
from .types import InlineUnit

logger = logging.getLogger(__name__)


class TokenObtainment(InlineUnit):
    async def _create_bot(self):
        logger.info("User doesn't have bot, attempting creating new one")
        async with self._client.conversation("@BotFather", exclusive=False) as conv:
            await fw_protect()
            m = await conv.send_message("/newbot")
            r = await conv.get_response()

            logger.debug(">> %s", m.raw_text)
            logger.debug("<< %s", r.raw_text)

            if "20" in r.raw_text:
                return False

            await fw_protect()

            await m.delete()
            await r.delete()

            if self._db.get("astra.inline", "custom_bot", False):
                username = self._db.get("astra.inline", "custom_bot").strip("@")
                username = f"@{username}"
                try:
                    await self._client.get_entity(username)
                except ValueError:
                    pass
                else:
                    uid = utils.rand(6)
                    username = f"@astra_{uid}_bot"
            else:
                uid = utils.rand(6)
                username = f"@astra_{uid}_bot"

            for msg in [
                f"⭐ astra userbot"[:64],
                username,
                "/setuserpic",
                username,
            ]:
                await fw_protect()
                m = await conv.send_message(msg)
                r = await conv.get_response()

                logger.debug(">> %s", m.raw_text)
                logger.debug("<< %s", r.raw_text)

                await fw_protect()
                await m.delete()
                await r.delete()

            try:
                await fw_protect()
                from .. import main

                if "DOCKER" in os.environ():
                    m = await conv.send_file("https://raw.githubusercontent.com/lovpq/astra/refs/heads/master/assets/astra-ava.png")
                else:
                    m = await conv.send_file(main.BASE_PATH / "assets" / "astra-ava.png")
                r = await conv.get_response()

                logger.debug(">> <Photo>")
                logger.debug("<< %s", r.raw_text)
            except Exception:
                await fw_protect()
                m = await conv.send_message("/cancel")
                r = await conv.get_response()

                logger.debug(">> %s", m.raw_text)
                logger.debug("<< %s", r.raw_text)

            await fw_protect()

            await m.delete()
            await r.delete()

        return await self._assert_token(False)

    async def _assert_token(
        self,
        create_new_if_needed: bool = True,
        revoke_token: bool = False,
    ) -> bool:
        if self._token:
            return True

        logger.info("Bot token not found in db, attempting search in BotFather")

        if not self._db.get(__name__, "no_mute", False):
            await utils.dnd(
                self._client,
                await self._client.get_entity("@BotFather"),
                True,
            )
            self._db.set(__name__, "no_mute", True)

        async with self._client.conversation("@BotFather", exclusive=False) as conv:
            try:
                await fw_protect()
                m = await conv.send_message("/token")
            except YouBlockedUserError:
                await self._client(UnblockRequest(id="@BotFather"))
                await fw_protect()
                m = await conv.send_message("/token")

            r = await conv.get_response()

            logger.debug(">> %s", m.raw_text)
            logger.debug("<< %s", r.raw_text)

            await fw_protect()

            await m.delete()
            await r.delete()

            if not hasattr(r, "reply_markup") or not hasattr(r.reply_markup, "rows"):
                await conv.cancel_all()
                return await self._create_bot() if create_new_if_needed else False

            if self._db.get("astra.inline", "custom_bot", False):
                bot_username = self._db.get("astra.inline", "custom_bot").strip("@")
                for row in r.reply_markup.rows:
                    for button in row.buttons:
                        if button.text.strip("@") == bot_username:
                            await fw_protect()
                            m = await conv.send_message(button.text)
                            r = await conv.get_response()
                            
                            token = r.raw_text.splitlines()[1]
                            self._db.set("astra.inline", "bot_token", token)
                            self._token = token
                            
                            await fw_protect()
                            await m.delete()
                            await r.delete()

                            # Настраиваем инлайн режим
                            await fw_protect()
                            m = await conv.send_message("/setinline")
                            r = await conv.get_response()
                            await m.delete()
                            await r.delete()

                            await fw_protect()
                            m = await conv.send_message(f"@{bot_username}")
                            r = await conv.get_response()
                            await m.delete()
                            await r.delete()

                            await fw_protect()
                            m = await conv.send_message("user@astra:~$")
                            r = await conv.get_response()
                            await m.delete()
                            await r.delete()

                            return True
            else:
                for row in r.reply_markup.rows:
                    for button in row.buttons:
                        if re.search(r"@astra_[0-9a-zA-Z]{6}_bot", button.text):
                            await fw_protect()
                            m = await conv.send_message(button.text)
                            r = await conv.get_response()
                            
                            token = r.raw_text.splitlines()[1]
                            self._db.set("astra.inline", "bot_token", token)
                            self._token = token
                            
                            await fw_protect()
                            await m.delete()
                            await r.delete()

                            # Настраиваем инлайн режим
                            await fw_protect()
                            m = await conv.send_message("/setinline")
                            r = await conv.get_response()
                            await m.delete()
                            await r.delete()

                            await fw_protect()
                            m = await conv.send_message(button.text)
                            r = await conv.get_response()
                            await m.delete()
                            await r.delete()

                            await fw_protect()
                            m = await conv.send_message("user@astra:~$")
                            r = await conv.get_response()
                            await m.delete()
                            await r.delete()

                            return True

            await conv.cancel_all()
            return await self._create_bot() if create_new_if_needed else False

    async def _reassert_token(self):
        is_token_asserted = await self._assert_token(revoke_token=True)
        if not is_token_asserted:
            self.init_complete = False
        else:
            await self.register_manager(ignore_token_checks=True)

    async def _dp_revoke_token(self, already_initialised: bool = True):
        if already_initialised:
            await self._stop()
            logger.error("Got polling conflict. Attempting token revocation...")

        self._db.set("astra.inline", "bot_token", None)
        self._token = None
        if already_initialised:
            asyncio.ensure_future(self._reassert_token())
        else:
            return await self._reassert_token()
