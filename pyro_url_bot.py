import asyncio
import json
import configparser
import time
import csv
from datetime import datetime, timedelta
from pyrogram import Client, filters
from apscheduler.schedulers.background import BackgroundScheduler
from utils.logger import PipelineLogger
from pyro_functions import *
from typing import Dict, Any


class URLSummarizerBot:

    def __init__(self, session_name="my_account", group_id=-1001893538021):
        self.session_name = session_name
        self.group_id = group_id
        self.summary_group_id = 123456789  # The group id where the bot should post the URLs

        self.message_storage = self._load_csv("message_storage.csv", [])
        self.url_storage: Dict[str, Any] = self._load_csv("url_storage.csv", {})

        self.scheduler = BackgroundScheduler()

        self.sleep_threshold = 20
        self.logger = PipelineLogger(file_suffix="url_summarizer_bot", verbose=False)

    def _load_csv(self, filename, default):
        try:
            with open(filename, "r") as f:
                return list(csv.DictReader(f))
        except FileNotFoundError:
            return default

    def _save_csv(self, filename, data):
        if not data:
            return

        keys = data[0].keys()
        with open(filename, 'w', newline='') as f:
            dict_writer = csv.DictWriter(f, keys)
            dict_writer.writeheader()
            dict_writer.writerows(data)

    def format_output_message(self, url, url_info):
        # Dummy method for formatting output message
        return url

    async def url_listener(self, client, message):

        if message.chat.id != self.group_id:
            return

        await self.handle_add_msg(message)
        self.message_storage.sort(key=lambda x: x["date"])

    async def build_storage(self, client, message):
        print("Building storage...")
        cutoff = datetime.now() - timedelta(days=14)

        # 更新信息
        async for msg in client.search_messages(self.group_id, query="https://"):
            # print(msg.date, msg.text)
            if msg.date > cutoff:
                # 从最近14天的消息中提取URL, 添加到storage中
                await self.handle_add_msg(msg)
                time.sleep(0.3)

        # 排序
        self.message_storage.sort(key=lambda x: x["date"])
        self.logger.info("Finished building storage.")

        # 保存storage
        self.save_storages()

        await message.reply("Finished building storage.")

    async def handle_add_msg(self, msg: Message):
        """
        处理当前msg object, 并更新self.storage
        """
        print(f"handling: {msg.text} || {msg.link}")

        if msg.link == "https://t.me/StableDiffusion_CN/1117330":
            print("STOP")

        # extractions: {[urls], [other_texts], "original_text"}
        extractions = parse_url_string(msg.text)
        url_str = extractions["urls"][0] if extractions["urls"] else None  # todo: handle multi urls
        description = extractions["description"]

        # 文档总结
        summary, type = retrieve_summary_and_type(url_str)

        additional_info = {
            "url": url_str,
            "description": description,
            "summary": summary,
            "type": type
        }

        if url_str is not None:
            self.update_storage(msg, additional_info)
        else:
            # todo: handle forwarded messages
            self.logger.error(f"URL not found from message: {msg.text}, link: {msg.link}")
            return

    def update_storage(self, msg: Message, additional_info: dict):
        """
        输入msg object和相关新信息, 更新self.storage信息
        message_storage: sorted list of dict
        url_storage: dict of URL and info
        """
        curr_url = additional_info.get("url", None)

        if curr_url is None:
            self.logger.error(f"URL not found from message: {msg.text}, link: {msg.link}")
            return

        self.message_storage.append({
            "date": str(msg.date),
            "url": additional_info["url"],  # primary key for url_storage
            "chat_link": msg.link,
        })

        if curr_url not in self.url_storage:

            # print(f"new URL: {curr_url} | id: {msg.link.split('/')[-1]} | desc: {additional_info.get('description', None)}")

            self.url_storage[curr_url] = {
                "description": additional_info["description"],
                "summary": additional_info["summary"],
                "type": additional_info["type"],
                "chat_links": [msg.link],
                "count": 1,
            }
        else:
            self.url_storage[curr_url]["count"] += 1
            self.url_storage[curr_url]["chat_links"].append(msg.link)

    async def start_summarization(self, client, message):

        print("Started summarization.")
        self.logger.info("Started listening for URLs.")
        cutoff = datetime.now() - timedelta(days=14)
        async for dialog in client.get_dialogs():
            if dialog.chat.type in ["supergroup", "group"]:
                async for msg in client.search_chat_messages(dialog.chat.id, query="http", limit=100):
                    if msg.date > cutoff and (msg.text.startswith('http://') or msg.text.startswith('https://')):
                        await self.url_listener(client, msg)
        await message.reply("Started listening for URLs.")

    async def post_summary(self, client, message=None):
        self.logger.info("Posting summary...")
        # Get messages from the last 24 hours
        cutoff = datetime.now() - timedelta(days=1)
        summary_urls = []
        for msg in self.message_storage:
            url_date = datetime.fromisoformat(msg["date"])
            if url_date > cutoff:
                url = msg["url"]
                url_info = self.url_storage[url]
                output_message = self.format_output_message(url, url_info)
                summary_urls.append(output_message)
        if summary_urls:
            message_text = "\n".join(summary_urls[:10])
            await message.reply(f"URL Summary:\n{message_text}")
            # await client.send_message(self.summary_group_id, f"URL Summary:\n{message_text}")

    async def diagnose(self, client, message):
        msg_storage_len = len(self.message_storage)
        url_storage_len = len(self.url_storage)
        await message.reply(f"message_storage: {msg_storage_len}\nurl_storage: {url_storage_len}")

    async def test(self, client, message):
        await self.post_summary(client, message)
        # await message.reply("test")

    def _get_app(self):
        config = configparser.ConfigParser()
        config.read("config.ini")
        api_id = config.get("pyrogram", "api_id")
        api_hash = config.get("pyrogram", "api_hash")
        return Client("my_account", api_id, api_hash, sleep_threshold=self.sleep_threshold)

    def save_storages(self):
        self._save_csv("message_storage.csv", self.message_storage)
        self._save_csv("url_storage.csv", self.url_storage)

    def run(self):
        app = self._get_app()

        def register_handler(filter, method):
            @app.on_message(filter)
            async def handler(client, message):
                await method(client, message)

        register_handler(filters.regex("(http|https)://") & filters.group, self.url_listener)
        register_handler(filters.command("build_storage") & filters.private, self.build_storage)
        register_handler(filters.command("start") & filters.private, self.start_summarization)
        register_handler(filters.command("summary") & filters.private, self.post_summary)
        register_handler(filters.command("diagnose") & filters.private, self.diagnose)
        register_handler(filters.command("test") & filters.group, self.test)

        self.scheduler.add_job(lambda: asyncio.run(self.post_summary(app)), 'interval', hours=24)
        self.scheduler.add_job(self.save_storages, 'interval', minutes=5)
        self.scheduler.start()

        print("starting app...")
        app.run()


if __name__ == '__main__':
    bot = URLSummarizerBot()
    bot.run()
