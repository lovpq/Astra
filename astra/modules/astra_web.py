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

import logging
import os
import random

import astratl
from astratl.tl.functions.messages import (
    GetDialogFiltersRequest,
    UpdateDialogFilterRequest,
)
from astratl.tl.types import Message
from astratl.utils import get_display_name

from .. import loader, log, main, utils
from .._internal import fw_protect, restart
from ..inline.types import InlineCall
from ..web import core

logger = logging.getLogger(__name__)


@loader.tds
class astraWebMod(loader.Module):
    """Web mode add account"""

    strings = {"name": "astraWeb"}


    @loader.command()
    async def weburl(self, message: Message, force: bool = False):
        if "LAVHOST" in os.environ:
            form = await self.inline.form(
                self.strings("lavhost_web"),
                message=message,
                reply_markup={
                    "text": self.strings("web_btn"),
                    "url": await main.astra.web.get_url(proxy_pass=False),
                },
                photo="https://i.imgur.com/CdNZRAi.jpeg",
            )
            return

        if (
            not force
            and not message.is_private
            and "force_insecure" not in message.raw_text.lower()
        ):
            try:
                if not await self.inline.form(
                    self.strings("privacy_leak_nowarn").format(self._client.tg_id),
                    message=message,
                    reply_markup=[
                        {
                            "text": self.strings("btn_yes"),
                            "callback": self.weburl,
                            "args": (True,),
                        },
                        {"text": self.strings("btn_no"), "action": "close"},
                    ],
                    photo="https://i.imgur.com/CdNZRAi.jpeg",
                ):
                    raise Exception
            except Exception:
                await utils.answer(
                    message,
                    self.strings("privacy_leak").format(
                        self._client.tg_id,
                        utils.escape_html(self.get_prefix()),
                    ),
                )

            return

        if not main.astra.web:
            main.astra.web = core.Web(
                data_root=main.BASE_DIR,
                api_token=main.astra.api_token,
                proxy=main.astra.proxy,
                connection=main.astra.conn,
            )
            await main.astra.web.add_loader(self._client, self.allmodules, self._db)
            await main.astra.web.start_if_ready(
                len(self.allclients),
                main.astra.arguments.port,
                proxy_pass=main.astra.arguments.proxy_pass,
            )

        if force:
            form = message
            await form.edit(
                self.strings("opening_tunnel"),
                reply_markup={"text": "🕔 Wait...", "data": "empty"},
                photo=(
                    "https://i.imgur.com/SIJVx8r.jpeg"
                ),
            )
        else:
            form = await self.inline.form(
                self.strings("opening_tunnel"),
                message=message,
                reply_markup={"text": "🕔 Wait...", "data": "empty"},
                photo=(
                    "https://i.imgur.com/SIJVx8r.jpeg"
                ),
            )

        url = await main.astra.web.get_url(proxy_pass=True)

        await form.edit(
            self.strings("tunnel_opened"),
            reply_markup={"text": self.strings("web_btn"), "url": url},
            photo="https://i.imgur.com/Vxj660D.jpeg",
        )
