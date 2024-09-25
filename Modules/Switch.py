import logging

import telethon

from .. import loader, utils

logger = logging.getLogger(__name__)


async def register(cb):
    cb(SwitchWordsMod())


@loader.tds
class SwitchWordsMod(loader.Module):
    """Заміна мови розкладки в тексті"""

    strings = {"name": "SwitchWords"}

    async def suacmd(self, message):
        """Якщо ти припустився помилки і набрав текст не змінивши розкладку клавіатури
         то повернися в його початок і допиши `.sua` і твій текст стане читабельним.
         Якщо ти все ж таки відправив повідомлення не в тій розкладці, то просто дай відповідь на нього цією командою і він змінитися.
         якщо ж твій співрозмовник припустився помилки, то просто дай відповідь на його повідомлення і повідомлення з командою змінитися.
        """
        UaKeys = """'йцукенгшщзхїфівапролджєячсмитьбю.₴"№;%:?ЙЦУКЕНГШЩЗХЇФІВАПРОЛДЖЄ/ЯЧСМИТЬБЮ,"""
        EnKeys = """`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$%^&QWERTYUIOP{}ASDFGHJKL:"|ZXCVBNM<>?"""

        if message.is_reply:
            reply = await message.get_reply_message()
            text = reply.raw_text
            if not text:
                await message.edit("Тут немає тексту...")
                return
            change = str.maketrans(UaKeys + EnKeys, EnKeys + UaKeys)
            text = str.translate(text, change)

            if message.sender_id != reply.sender_id:
                await message.edit(text)
            else:
                await message.delete()
                await reply.edit(text)
        else:
            text = utils.get_args_raw(message)
            if not text:
                await message.edit("Тут немає тексту...")
                return
            change = str.maketrans(UaKeys + EnKeys, EnKeys + UaKeys)
            text = str.translate(text, change)
            await message.edit(text)

    async def srucmd(self, message):
        """Теж саме, але на москальскій💩
        """
        RuKeys = """ёйцукенгшщзхъфывапролджэячсмитьбю.Ё"№;%:?ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭ/ЯЧСМИТЬБЮ,"""
        EnKeys = """`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$%^&QWERTYUIOP{}ASDFGHJKL:"|ZXCVBNM<>?"""

        if message.is_reply:
            reply = await message.get_reply_message()
            text = reply.raw_text
            if not text:
                await message.edit("Тут немає тексту...")
                return
            change = str.maketrans(RuKeys + EnKeys, EnKeys + RuKeys)
            text = str.translate(text, change)

            if message.sender_id != reply.sender_id:
                await message.edit(text)
            else:
                await message.delete()
                await reply.edit(text)
        else:
            text = utils.get_args_raw(message)
            if not text:
                await message.edit("Тут немає тексту...")
                return
            change = str.maketrans(RuKeys + EnKeys, EnKeys + RuKeys)
            text = str.translate(text, change)
            await message.edit(text)
