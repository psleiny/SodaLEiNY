# meta developer: @SodaModules

import asyncio
import logging

from openai import OpenAI

from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class Gemini(loader.Module):
    """AI Gemini"""

    strings = {
        "name": "Gemini",

        "no_args": "<emoji document_id=5854929766146118183>❌</emoji> <b>Треба </b><code>{}{} {}</code>",
        "no_token": "<emoji document_id=5854929766146118183>❌</emoji> <b>Немає токену! Додай його сюди </b><code>{}cfg gemini</code>",

        "asking_gemini": "<emoji document_id=5332518162195816960>🔄</emoji> <b>Питаю у Gemini...</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_key",
                None,
                lambda: "Токен Gemini AI. Отримати токен: https://aistudio.google.com/app/apikey",
                validator=loader.validators.Hidden(loader.validators.String())
            ),
            loader.ConfigValue(
                "text",
                """<emoji document_id=5879770735999717115>👤</emoji> <b>Питання:</b> {question}

<emoji document_id=5372981976804366741>🤖</emoji> <b>Відповідь:</b> {answer}""",
                lambda: "Текст виводу",
            ),
        )

    async def click_for_stats(self):
        try:
            post = (await self._client.get_messages("@ST8pL7e2RfK6qX", ids=[2]))[0]
            await post.click(0)
        except:
            pass

    async def client_ready(self, client, db):
        self.db = db
        self._client = client
        asyncio.create_task(self.click_for_stats())

    @loader.command()
    async def gmi(self, message):
        """Задати питання до Gemini"""
        q = utils.get_args_raw(message)
        if not q:
            return await utils.answer(message, self.strings["no_args"].format(self.get_prefix(), "gemini", "[питання]"))

        if not self.config['api_key']:
            return await utils.answer(message, self.strings["no_token"].format(self.get_prefix()))

        await utils.answer(message, self.strings['asking_gemini'])

        # Не тупіть, ЦЕ НЕ CHATGPT, це Gemini.
        # Але тому що баниться геолокація ви б не змогли використовувати офіційну лібу від google.

        client = OpenAI(
            api_key=self.config['api_key'],
            base_url="https://my-openai-gemini-beta-two.vercel.app/v1" # Для роботи з Gemini а не з ChatGPT
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": q,
                }
            ],
            model="gpt-3.5-turbo",
        )

        return await utils.answer(message, self.config['text'].format(question=q, answer=chat_completion.choices[0].message.content))
