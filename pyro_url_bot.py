import asyncio
import json
import configparser
from datetime import datetime, timedelta
from pyrogram import Client, filters
from apscheduler.schedulers.background import BackgroundScheduler
from utils.logger import PipelineLogger
from urllib.parse import urlsplit
from pyro_functions import *


class URLSummarizerBot:

    def __init__(self, session_name="my_account", group_id=-1001893538021):
        self.session_name = session_name
        self.group_id = group_id

        self.summary_group_id = 123456789  # The group id where the bot should post the URLs
        self.message_storage = self._load_json("message_storage.json", [])
        self.url_storage = self._load_json("url_storage.json", {})
        self.scheduler = BackgroundScheduler()
        self.sleep_threshold = 20
        self.logger = PipelineLogger(file_suffix="url_summarizer_bot", verbose=False)

    def _load_json(self, filename, default):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return default

    def _save_json(self, filename, data):
        with open(filename, "w") as f:
            json.dump(data, f)

    def format_output_message(self, url, url_info):
        # Dummy method for formatting output message
        return url

    async def url_listener(self, client, message):
        url = message.text
        summary, type = await retrieve_summary_and_type(url)
        self.message_storage.append({
            "date": str(datetime.now()),
            "messageID": message.id,
            "url": url,
        })
        self.message_storage.sort(key=lambda x: x["date"])
        if url not in self.url_storage:
            self.url_storage[url] = {
                "date": str(datetime.now()),
                "summary": summary,
                "type": type,
                "count": 1,
            }
        else:
            self.url_storage[url]["count"] += 1

    async def build_storage(self, client, message):
        print("Building storage...")
        cutoff = datetime.now() - timedelta(days=14)

        async for msg in client.search_messages(self.group_id, query="https://"):
            # print(msg.date, msg.text)
            if msg.date > cutoff:
                # 从最近14天的消息中提取URL, 添加到storage中
                await self.handle_add_msg(msg)

        self.message_storage.sort(key=lambda x: x["date"])
        self.logger.info("Finished building storage.")
        self.save_storages()

        await message.reply("Finished building storage.")

    async def handle_add_msg(self, msg: Message):
        """
        处理当前msg object, 并更新self.storage
        """
        extractions = parse_url_string(msg.text)
        url = extractions["urls"][0] if extractions["urls"] else None  # todo: handle multi urls
        description = extractions["description"]
        summary, type = await retrieve_summary_and_type(url)

        additional_info = {
            "url": url,
            "description": description,
            "summary": summary,
            "type": type
        }

        await self.update_storage(msg, additional_info)

    async def update_storage(self, msg:Message, additional_info:dict):
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

            print(f"new URL: {curr_url} | id: {msg.link.split('/')[-1]} | desc: {additional_info.get('description', None)}")

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
            message_text = "\n".join(summary_urls)
            await client.send_message(self.summary_group_id, f"URL Summary:\n{message_text}")

    def _get_app(self):
        config = configparser.ConfigParser()
        config.read("config.ini")
        api_id = config.get("pyrogram", "api_id")
        api_hash = config.get("pyrogram", "api_hash")
        return Client("my_account", api_id, api_hash, sleep_threshold=self.sleep_threshold)

    def save_storages(self):
        self._save_json("message_storage.json", self.message_storage)
        self._save_json("url_storage.json", self.url_storage)

    def run(self):
        app = self._get_app()
        def register_handler(filter, method):
            @app.on_message(filter)
            async def handler(client, message):
                await method(client, message)

        register_handler(filters.regex("(http|https)://") & filters.group, self.url_listener)
        register_handler(filters.command("build_storage") & filters.private, self.build_storage)
        register_handler(filters.command("start_summarize") & filters.private, self.start_summarization)
        register_handler(filters.command("summarize") & filters.private, self.post_summary)

        self.scheduler.add_job(lambda: asyncio.run(self.post_summary(app)), 'interval', hours=24)
        self.scheduler.add_job(self.save_storages, 'interval', minutes=5)
        self.scheduler.start()

        print("starting app...")
        app.run()


if __name__ == '__main__':
    bot = URLSummarizerBot()
    bot.run()
