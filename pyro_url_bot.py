import asyncio
import json
from datetime import datetime, timedelta
from pyrogram import Client, filters
from apscheduler.schedulers.background import BackgroundScheduler

class URLSummarizerBot:

    def __init__(self, session_name="my_account"):
        self.session_name = session_name
        self.summary_group_id = 123456789  # The group id where the bot should post the URLs
        self.message_storage = self._load_json("message_storage.json", [])
        self.url_storage = self._load_json("url_storage.json", {})
        self.scheduler = BackgroundScheduler()

    def _load_json(self, filename, default):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return default

    def _save_json(self, filename, data):
        with open(filename, "w") as f:
            json.dump(data, f)

    async def retrieve_summary_and_type(self, url):
        # Dummy method for retrieving summary and type
        return "", ""

    def format_output_message(self, url, url_info):
        # Dummy method for formatting output message
        return url

    async def url_listener(self, client, message):
        url = message.text
        summary, type = await self.retrieve_summary_and_type(url)
        self.message_storage.append({
            "date": str(datetime.now()),
            "messageID": message.message_id,
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
        cutoff = datetime.now() - timedelta(days=14)
        for dialog in await client.get_dialogs():
            if dialog.chat.type in ["supergroup", "group"]:
                for msg in await client.search_chat_messages(dialog.chat.id, query="http", limit=100):
                    if msg.date > cutoff and (msg.text.startswith('http://') or msg.text.startswith('https://')):
                        url = msg.text
                        summary, type = await self.retrieve_summary_and_type(url)
                        self.message_storage.append({
                            "date": str(msg.date),
                            "messageID": msg.message_id,
                            "url": url,
                        })
                        if url not in self.url_storage:
                            self.url_storage[url] = {
                                "date": str(msg.date),
                                "summary": summary,
                                "type": type,
                                "count": 1,
                            }
                        else:
                            self.url_storage[url]["count"] += 1
        self.message_storage.sort(key=lambda x: x["date"])
        await message.reply("Finished building storage.")

    async def start_summarization(self, client, message):
        await message.reply("Started listening for URLs.")

    async def post_summary(self, client, message=None):
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

    def save_storages(self):
        self._save_json("message_storage.json", self.message_storage)
        self._save_json("url_storage.json", self.url_storage)

    def run(self):
        app = Client(self.session_name)

        @app.on_message(filters.regex("(http|https)://") & filters.group)
        async def url_listener(client, message):
            await self.url_listener(client, message)

        @app.on_message(filters.command("build_storage") & filters.private)
        async def build_storage(client, message):
            await self.build_storage(client, message)

        @app.on_message(filters.command("start_summarize") & filters.private)
        async def start_summarization(client, message):
            await self.start_summarization(client, message)

        @app.on_message(filters.command("summarize") & filters.private)
        async def post_summary(client, message):
            await self.post_summary(client, message)

        self.scheduler.add_job(lambda: asyncio.run(self.post_summary(app)), 'interval', hours=24)
        self.scheduler.add_job(self.save_storages, 'interval', minutes=5)
        self.scheduler.start()

        app.run()


if __name__ == '__main__':
    bot = URLSummarizerBot()
    bot.run()
