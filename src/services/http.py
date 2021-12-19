import aiohttp
import os
import re
import traceback
from asyncio.exceptions import CancelledError
from typing import List

from aiodav.client import Client as DavClient
from async_executor.task import TaskState
from modules.service import Service
from pyrogram import emoji
from pyrogram.types import Message

from services.extractors.animeflv import AnimeFLVExtractor
from services.extractors.extractor import Extractor
from services.extractors.mediafire import MediafireExtractor
from services.extractors.zippyshare import ZippyshareExtractor


class HttpService(Service):
    """
    Download web file and upload to webdav
    """

    EXTRACTORS: List[Extractor] = [
        AnimeFLVExtractor,
        ZippyshareExtractor,
        MediafireExtractor,
    ]

    def __init__(
        self, id: int, user: int, file_message: Message, *args, **kwargs
    ) -> None:
        super().__init__(id, user, file_message, *args, **kwargs)

    @staticmethod
    def check(m: Message) -> bool:
        return bool(m.text) and bool(
            re.fullmatch(
                r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)",
                m.text,
            )
        )

    async def start(self) -> None:
        self._set_state(TaskState.STARTING)

        async with DavClient(
            hostname=self.webdav_hostname,
            login=self.webdav_username,
            password=self.webdav_password,
            timeout=self.timeout,
            chunk_size=2097152,
        ) as dav:
            async with aiohttp.ClientSession() as session:
                url = self.file_message.text

                for e in HttpService.EXTRACTORS:
                    if e.check(url):
                        url = await e.get_url(session, url)
                        break

                async with session.get(url) as response:
                    try:
                        d = response.headers["content-disposition"]
                        filename = re.findall("filename=(.+)", d)[0]
                    except Exception:
                        filename = os.path.basename(url)

                    gen = response.content.iter_chunked(2097152)
                    await self.upload(
                        dav,
                        filename,
                        response.content_length,
                        gen,
                    )

        return None
