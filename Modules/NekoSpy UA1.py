__version__ = (1, 0, 28)

import contextlib
import io
import logging
import time
import typing

from telethon.tl.types import (
    DocumentAttributeFilename,
    Message,
    PeerChat,
    UpdateDeleteChannelMessages,
    UpdateDeleteMessages,
    UpdateEditChannelMessage,
    UpdateEditMessage,
)
from telethon.utils import get_display_name

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class NekoSpy(loader.Module):
    """Sends you deleted and / or edited messages from selected users"""

    rei = "<emoji document_id=5350606391193124570>👌</emoji>"
    groups = "<emoji document_id=6037355667365300960>👥</emoji>"
    pm = "<emoji document_id=6048540195995782913>👤</emoji>"

    strings_ua = {
        "on": "Працює",
        "off": "Не працює",
        "state": f"{rei} <b>Режим стеження тепер {{}}</b>",
        "spybl": f"{rei} <b>Цей чат додан у чорний список для стеження</b>",
        "spybl_removed": (
            f"{rei} <b>Цей чат видален із чорного списка для стеження</b>"
        ),
        "spybl_clear": f"{rei} <b>Чорний список для стеження очищений</b>",
        "spywl": f"{rei} <b>Цей чат додан у білий список для стеження</b>",
        "spywl_removed": (
            f"{rei} <b>Цей чат видален із білого списка для стеження</b>"
        ),
        "spywl_clear": f"{rei} <b>Білий список для стеження очищений</b>",
        "whitelist": (
            f"\n{rei} <b>Стежу тільки"
            " за повідомленнями від людей / груп:</b>\n{}"
        ),
        "always_track": (
            f"\n{rei} <b>Завжди стежу за повідомленнями від людей /"
            " груп:</b>\n{}"
        ),
        "blacklist": (
            f"\n{rei} <b>Ігнорю повідомлення від людей / груп:</b>\n{{}}"
        ),
        "chat": f"{groups} <b>Стежу за повідомленнями у групах</b>\n",
        "pm": f"{pm} <b>Стежу за повідомленнями у ПП</b>\n",
        "deleted_pm": (
            '🗑 <b><a href="{}">{}</a> видалив <a href="{message_url}">повідомлення</a> в'
            " ПП. у повідомленні:</b>\n{}"
        ),
        "deleted_chat": (
            '🗑 <b><a href="{message_url}">Повідомлення</a> у чаті <a href="{}">{}</a> від'
            ' <a href="{}">{}</a> було видаленно. У ньому:</b>\n{}'
        ),
        "edited_pm": (
            '🔏 <b><a href="{}">{}</a> Відредачив <a'
            ' href="{message_url}">повідомлення</a> у ПП. Старий вміст:</b>\n{}'
        ),
        "edited_chat": (
            '🔏 <b><a href="{message_url}">Повідомлення</a> у чаті <a href="{}">{}</a> від'
            ' <a href="{}">{}</a> було відредачено. Старий вміст:</b>\n{}'
        ),
        "mode_off": f"{pm} <b>Не відстежую повідомлення </b><code>{{}}spymode</code>\n",
        "cfg_enable_pm": "Увімкнути режим шпигуна у ПП",
        "cfg_enable_groups": "Увімкнути режим шпигуна у групах",
        "cfg_whitelist": "Список чатів, від яких треба зберігати повідомлення",
        "cfg_blacklist": "Список чатів, від яких треба ігнорувати повідмолення",
        "cfg_always_track": (
            "Список чатів, від яких завжди треба стежити за повідомленнями,"
            " не дивлячись ні на що"
        ),
        "cfg_log_edits": "Зберігати відредачені повідомлення",
        "cfg_ignore_inline": "Ігнорити інлайн повідомлення",
        "cfg_fw_protect": "Захист від FloodWait при пересилці",
        "_cls_doc": (
            "Зберігає видаленні і/чи відредачені повідомлення від обраних"
            " юзерів"
        ),
        "sd_media": (
            "🔥 <b><a href='tg://user?id={}'>{}</a> відправив вам самознищувальне"
            " медіа</b>"
        ),
        "save_sd": (
            "<emoji document_id=5420315771991497307>🔥</emoji> <b>Зберігаю"
            " самознищувальне медіа</b>\n"
        ),
        "cfg_save_sd": "Зберігати самознищувальне медіа",
    }

    def __init__(self):
        self._tl_channel = None
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "enable_pm",
                True,
                lambda: self.strings("cfg_enable_pm"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "enable_groups",
                False,
                lambda: self.strings("cfg_enable_groups"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "whitelist",
                [],
                lambda: self.strings("cfg_whitelist"),
                validator=loader.validators.Series(),
            ),
            loader.ConfigValue(
                "blacklist",
                [],
                lambda: self.strings("cfg_blacklist"),
                validator=loader.validators.Series(),
            ),
            loader.ConfigValue(
                "always_track",
                [],
                lambda: self.strings("cfg_always_track"),
                validator=loader.validators.Series(),
            ),
            loader.ConfigValue(
                "log_edits",
                True,
                lambda: self.strings("cfg_log_edits"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "ignore_inline",
                True,
                lambda: self.strings("cfg_ignore_inline"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "fw_protect",
                3.0,
                lambda: self.strings("cfg_fw_protect"),
                validator=loader.validators.Float(minimum=0.0),
            ),
            loader.ConfigValue(
                "save_sd",
                True,
                lambda: self.strings("cfg_save_sd"),
                validator=loader.validators.Boolean(),
            ),
        )

        self._queue = []
        self._cache = {}
        self._next = 0
        self._threshold = 10
        self._flood_protect_sample = 60

    @loader.loop(interval=0.1, autostart=True)
    async def sender(self):
        if not self._queue or self._next > time.time():
            return

        item = self._queue.pop(0)
        await item
        self._next = int(time.time()) + self.config["fw_protect"]

    @staticmethod
    def _int(value: typing.Union[str, int], /) -> typing.Union[str, int]:
        return int(value) if str(value).isdigit() else value

    @property
    def blacklist(self):
        return list(
            map(
                self._int,
                self.config["blacklist"]
                + [777000, self._client.tg_id, self._tl_channel, self.inline.bot_id],
            )
        )

    @blacklist.setter
    def blacklist(self, value: list):
        self.config["blacklist"] = list(
            set(value)
            - {777000, self._client.tg_id, self._tl_channel, self.inline.bot_id}
        )

    @property
    def whitelist(self):
        return list(map(self._int, self.config["whitelist"]))

    @whitelist.setter
    def whitelist(self, value: list):
        self.config["whitelist"] = value

    @property
    def always_track(self):
        return list(map(self._int, self.config["always_track"]))

    async def client_ready(self):
        channel, _ = await utils.asset_channel(
            self._client,
            "SodaSpy",
            "Deleted and edited messages will appear there",
            silent=True,
            invite_bot=True,
            avatar="https://raw.githubusercontent.com/psleiny/SodaLEiNY/main/Images/plyusheva-anime-lyalka-ayanami-rey-ayanami-rei-20-sm_eb6634e42c46be1_500x500.webp.jpg",
            _folder="hikka",
        )

        self._channel = int(f"-100{channel.id}")
        self._tl_channel = channel.id

    @loader.command(
        ua_doc=(
             "• Хто я? • Аянамі Рей. • А хто ти? • Аянамі Рей. • Ти теж Аянамі Рей? •"
             "Так. Я та, кого знають як Аянамі Рей. • Ми всі ті, кого знають, як Аянамі"
             "Рей. • Як вони всі можуть бути мною? • Просто тому що інші звуть нас"
             " Аянамі Рей. Тільки і все. У тебе несправжня душа, і тіло твоє -"
             "Підробка. Знаєш чому? • Я не підробка і не фальшивка. Я - це я."
        ),
        tr_doc=(
            "• Kimim? • Ayanami Rei. • Kimsin? • Ayanami Rei. • Sen de Ayanami Rei"
            " misin? • Evet. Beni bilenler Ayanami Rei olarak bilir. • Hepimiz Ayanami"
            " Rei olarak bilinenleriz. • Hepimiz nasıl Ayanami Rei olabiliriz? • Sadece"
            " diğerleri bizi Ayanami Rei olarak adlandırıyor. Sadece bu. Ruhun gerçek"
            " değil ve vücudun bir kopya. Biliyor musun neden? • Ben bir kopya değilim"
            " ve sahte değilim. Ben benim."
        ),
        it_doc=(
            "• Chi sono io? • Ayanami Rei. • Chi sei tu? • Ayanami Rei. • Tu sei anche"
            " Ayanami Rei? • Sì. Io sono quella che conoscono come Ayanami Rei. • Tutti"
            " noi siamo quelli che conoscono come Ayanami Rei. • Come possono tutti"
            " essere io? • Solo perché gli altri ci chiamano Ayanami Rei. Solo questo."
            " La tua anima non è vera e il tuo corpo è una copia. Lo sai perché? • Non"
            " sono una copia e non sono una falsa. Io sono io."
        ),
        kk_doc=(
            "• Мені кім? • Аянами Рей. • Сені кім? • Аянами Рей. • Сені де Аянами Рей?"
            " • Иә. Мен Аянами Рей деп білінетін кім. • Барлығымыз Аянами Рей деп"
            " білінетін кім. • Барлар мені қайсы бола алады? • Қатарынан, біздерді"
            " Аянами Рей деп атайтын. Бірақ, бұл барлық. Сенің дуалың жарамсыз, және"
            " телегің - бұл қате. Білесін бе? • Мен жарамсыз және қате емеспін. Мен -"
            " бұл мен."
        ),
        de_doc=(
            "• Wer bin ich? • Ayanami Rei. • Und wer bist du? • Ayanami Rei. • Bist du"
            " auch Ayanami Rei? • Ja. Ich bin die, die als Ayanami Rei bekannt ist. •"
            " Wir sind alle diejenigen, die als Ayanami Rei bekannt sind. • Wie können"
            " alle mich sein? • Einfach nur, weil andere uns als Ayanami Rei nennen."
            " Das ist alles. Du hast eine falsche Seele und deinen Körper gibt es"
            " nicht. Weißt du, warum? • Ich bin nicht falsch und nicht falsch. Ich bin"
            " ich."
        ),
        es_doc=(
            "• ¿Quién soy? • Ayanami Rei. • ¿Y quién eres? • Ayanami Rei. • ¿Tú también"
            " eres Ayanami Rei? • Sí. Soy la que se conoce como Ayanami Rei. • Todos"
            " somos lo que se conoce como Ayanami Rei. • ¿Cómo pueden todos ser yo? •"
            " Simplemente porque otros nos llaman Ayanami Rei. Eso es todo. Tienes un"
            " alma falsa y tu cuerpo es una falsificación. ¿Sabes por qué? • No soy"
            " falso ni falso. Soy yo."
        ),
    )
    async def spymode(self, message: Message):
        """• Who am I? • Ayanami Rey. • Who are you? • Ayanami Rey. • Are you Ayanami Rey too? • Yes. I'm the one known as Ayanami Rey. • We're all what we know as Ayanami Rey. • How can they all be me? • Just because others call us Ayanami Rey. That's all. You have a fake soul and your body is a fake. You know why? • I'm not fake or fake. I am me."""
        await utils.answer(
            message,
            self.strings("state").format(
                self.strings("off" if self.get("state", False) else "on")
            ),
        )
        self.set("state", not self.get("state", False))

    @loader.command(
        ua_doc="Додати / видалити чат з списку ігнора",
        de_doc="Chat zur Ignorierliste hinzufügen / entfernen",
        uz_doc="Chatni qo'shish / olib tashlash",
        tr_doc="Sohbeti engelleme listesine ekle / kaldır",
        es_doc="Agregar / eliminar chat de la lista de ignorados",
        kk_doc="Чатты қосу / жою",
        it_doc="Aggiungi / rimuovi chat dalla lista di ignorati",
    )
    async def spybl(self, message: Message):
        """Add / remove chat from blacklist"""
        chat = utils.get_chat_id(message)
        if chat in self.blacklist:
            self.blacklist = list(set(self.blacklist) - {chat})
            await utils.answer(message, self.strings("spybl_removed"))
        else:
            self.blacklist = list(set(self.blacklist) | {chat})
            await utils.answer(message, self.strings("spybl"))

    @loader.command(
        ua_doc="Очистити чорний список",
        de_doc="Schwarze Liste leeren",
        uz_doc="Qora ro'yxatni tozalash",
        tr_doc="Siyah listeyi temizle",
        es_doc="Limpiar lista negra",
        kk_doc="Қара тізімді тазалау",
        it_doc="Cancella la lista nera",
    )
    async def spyblclear(self, message: Message):
        """Clear blacklist"""
        self.blacklist = []
        await utils.answer(message, self.strings("spybl_clear"))

    @loader.command(
        ua_doc="Додати / видалити чат з білого списку",
        de_doc="Chat zur Whitelist hinzufügen / entfernen",
        uz_doc="Chatni o'qish ro'yxatiga qo'shish / olib tashlash",
        tr_doc="Sohbeti beyaz listeye ekle / kaldır",
        es_doc="Agregar / eliminar chat de la lista blanca",
        kk_doc="Чатты оқыш тізіміне қосу / жою",
        it_doc="Aggiungi / rimuovi chat dalla whitelist",
    )
    async def spywl(self, message: Message):
        """Add / remove chat from whitelist"""
        chat = utils.get_chat_id(message)
        if chat in self.whitelist:
            self.whitelist = list(set(self.whitelist) - {chat})
            await utils.answer(message, self.strings("spywl_removed"))
        else:
            self.whitelist = list(set(self.whitelist) | {chat})
            await utils.answer(message, self.strings("spywl"))

    @loader.command(
        ua_doc="Очистити білий список",
        de_doc="Whitelist leeren",
        uz_doc="O'qish ro'yxatini tozalash",
        tr_doc="Beyaz listeyi temizle",
        es_doc="Limpiar lista blanca",
        kk_doc="Оқыш тізімін тазалау",
        it_doc="Cancella la whitelist",
    )
    async def spywlclear(self, message: Message):
        """Clear whitelist"""
        self.whitelist = []
        await utils.answer(message, self.strings("spywl_clear"))

    async def _get_entities_list(self, entities: list) -> str:
        return "\n".join(
            [
                "\u0020\u2800\u0020\u2800<emoji"
                ' document_id=4971987363145188045>▫️</emoji> <b><a href="{}">{}</a></b>'
                .format(
                    utils.get_entity_url(await self._client.get_entity(x, exp=0)),
                    utils.escape_html(
                        get_display_name(await self._client.get_entity(x, exp=0))
                    ),
                )
                for x in entities
            ]
        )

    @loader.command(
        ua_doc="Показати поточну конфігурацію спай-мода",
        de_doc="Aktuelle Spy-Modus-Konfiguration anzeigen",
        uz_doc="Spy rejimining hozirgi konfiguratsiyasini ko'rsatish",
        tr_doc="Spy modu geçerli yapılandırmasını göster",
        es_doc="Mostrar la configuración actual del modo espía",
        kk_doc="Спай-режимдің ағымдағы конфигурациясын көрсету",
        it_doc="Mostra la configurazione attuale della modalità spia",
    )
    async def spyinfo(self, message: Message):
        """Show current spy mode configuration"""
        if not self.get("state"):
            await utils.answer(
                message, self.strings("mode_off").format(self.get_prefix())
            )
            return

        info = ""

        if self.config["save_sd"]:
            info += self.strings("save_sd")

        if self.config["enable_groups"]:
            info += self.strings("chat")

        if self.config["enable_pm"]:
            info += self.strings("pm")

        if self.whitelist:
            info += self.strings("whitelist").format(
                await self._get_entities_list(self.whitelist)
            )

        if self.config["blacklist"]:
            info += self.strings("blacklist").format(
                await self._get_entities_list(self.config["blacklist"])
            )

        if self.always_track:
            info += self.strings("always_track").format(
                await self._get_entities_list(self.always_track)
            )

        await utils.answer(message, info)

    async def _message_deleted(self, msg_obj: Message, caption: str):
        caption = self.inline.sanitise_text(caption)

        if not msg_obj.photo and not msg_obj.video and not msg_obj.document:
            self._queue += [
                self.inline.bot.send_message(
                    self._channel,
                    caption,
                    disable_web_page_preview=True,
                )
            ]
            return

        if msg_obj.sticker:
            self._queue += [
                self.inline.bot.send_message(
                    self._channel,
                    caption + "\n\n&lt;sticker&gt;",
                    disable_web_page_preview=True,
                )
            ]
            return

        file = io.BytesIO(await self._client.download_media(msg_obj, bytes))
        args = (self._channel, file)
        kwargs = {"caption": caption}
        if msg_obj.photo:
            file.name = "photo.jpg"
            self._queue += [self.inline.bot.send_photo(*args, **kwargs)]
        elif msg_obj.video:
            file.name = "video.mp4"
            self._queue += [self.inline.bot.send_video(*args, **kwargs)]
        elif msg_obj.voice:
            file.name = "audio.ogg"
            self._queue += [self.inline.bot.send_voice(*args, **kwargs)]
        elif msg_obj.document:
            file.name = next(
                attr.file_name
                for attr in msg_obj.document.attributes
                if isinstance(attr, DocumentAttributeFilename)
            )
            self._queue += [self.inline.bot.send_document(*args, **kwargs)]

    async def _message_edited(self, caption: str, msg_obj: Message):
        args = (
            self._channel,
            await self._client.download_media(msg_obj, bytes),
        )
        kwargs = {"caption": self.inline.sanitise_text(caption)}
        if msg_obj.photo:
            self._queue += [self.inline.bot.send_photo(*args, **kwargs)]
        elif msg_obj.video:
            self._queue += [self.inline.bot.send_video(*args, **kwargs)]
        elif msg_obj.voice:
            self._queue += [self.inline.bot.send_voice(*args, **kwargs)]
        elif msg_obj.document:
            self._queue += [self.inline.bot.send_document(*args, **kwargs)]
        else:
            self._queue += [
                self.inline.bot.send_message(
                    self._channel,
                    self.inline.sanitise_text(caption),
                    disable_web_page_preview=True,
                )
            ]

    @loader.raw_handler(UpdateEditChannelMessage)
    async def channel_edit_handler(self, update: UpdateEditChannelMessage):
        if (
            not self.get("state", False)
            or update.message.out
            or (self.config["ignore_inline"] and update.message.via_bot_id)
        ):
            return

        key = f"{utils.get_chat_id(update.message)}/{update.message.id}"
        if key in self._cache and (
            utils.get_chat_id(update.message) in self.always_track
            or self._cache[key].sender_id in self.always_track
            or (
                self.config["log_edits"]
                and self.config["enable_groups"]
                and utils.get_chat_id(update.message) not in self.blacklist
                and (
                    not self.whitelist
                    or utils.get_chat_id(update.message) in self.whitelist
                )
            )
        ):
            msg_obj = self._cache[key]
            if not msg_obj.sender.bot and update.message.raw_text != msg_obj.raw_text:
                await self._message_edited(
                    self.strings("edited_chat").format(
                        utils.get_entity_url(msg_obj.chat),
                        utils.escape_html(get_display_name(msg_obj.chat)),
                        utils.get_entity_url(msg_obj.sender),
                        utils.escape_html(get_display_name(msg_obj.sender)),
                        msg_obj.text,
                        message_url=await utils.get_message_link(msg_obj),
                    ),
                    msg_obj,
                )

        self._cache[key] = update.message

    def _should_capture(self, user_id: int, chat_id: int) -> bool:
        return (
            chat_id not in self.blacklist
            and user_id not in self.blacklist
            and (
                not self.whitelist
                or chat_id in self.whitelist
                or user_id in self.whitelist
            )
        )

    @loader.raw_handler(UpdateEditMessage)
    async def pm_edit_handler(self, update: UpdateEditMessage):
        if (
            not self.get("state", False)
            or update.message.out
            or (self.config["ignore_inline"] and update.message.via_bot_id)
        ):
            return

        key = update.message.id
        msg_obj = self._cache.get(key)
        if (
            key in self._cache
            and (
                self._cache[key].sender_id in self.always_track
                or (utils.get_chat_id(self._cache[key]) in self.always_track)
                or (
                    self.config["log_edits"]
                    and self._should_capture(
                        self._cache[key].sender_id,
                        utils.get_chat_id(self._cache[key]),
                    )
                )
                and (
                    (
                        self.config["enable_pm"]
                        and not isinstance(msg_obj.peer_id, PeerChat)
                        or self.config["enable_groups"]
                        and isinstance(msg_obj.peer_id, PeerChat)
                    )
                )
            )
            and update.message.raw_text != msg_obj.raw_text
        ):
            sender = await self._client.get_entity(msg_obj.sender_id, exp=0)
            if not sender.bot:
                chat = (
                    await self._client.get_entity(
                        msg_obj.peer_id.chat_id,
                        exp=0,
                    )
                    if isinstance(msg_obj.peer_id, PeerChat)
                    else None
                )
                await self._message_edited(
                    (
                        self.strings("edited_chat").format(
                            utils.get_entity_url(chat),
                            utils.escape_html(get_display_name(chat)),
                            utils.get_entity_url(sender),
                            utils.escape_html(get_display_name(sender)),
                            msg_obj.text,
                            message_url=await utils.get_message_link(msg_obj),
                        )
                        if isinstance(msg_obj.peer_id, PeerChat)
                        else self.strings("edited_pm").format(
                            utils.get_entity_url(sender),
                            utils.escape_html(get_display_name(sender)),
                            msg_obj.text,
                            message_url=await utils.get_message_link(msg_obj),
                        )
                    ),
                    msg_obj,
                )

        self._cache[update.message.id] = update.message

    @loader.raw_handler(UpdateDeleteMessages)
    async def pm_delete_handler(self, update: UpdateDeleteMessages):
        if not self.get("state", False):
            return

        for message in update.messages:
            if message not in self._cache:
                continue

            msg_obj = self._cache.pop(message)

            if (
                msg_obj.sender_id not in self.always_track
                and utils.get_chat_id(msg_obj) not in self.always_track
                and (
                    not self._should_capture(
                        msg_obj.sender_id, utils.get_chat_id(msg_obj)
                    )
                    or (self.config["ignore_inline"] and msg_obj.via_bot_id)
                    or (
                        not self.config["enable_groups"]
                        and isinstance(msg_obj.peer_id, PeerChat)
                    )
                    or (
                        not self.config["enable_pm"]
                        and not isinstance(msg_obj.peer_id, PeerChat)
                    )
                )
            ):
                continue

            sender = await self._client.get_entity(msg_obj.sender_id, exp=0)

            if sender.bot:
                continue

            chat = (
                await self._client.get_entity(msg_obj.peer_id.chat_id, exp=0)
                if isinstance(msg_obj.peer_id, PeerChat)
                else None
            )

            await self._message_deleted(
                msg_obj,
                (
                    self.strings("deleted_chat").format(
                        utils.get_entity_url(chat),
                        utils.escape_html(get_display_name(chat)),
                        utils.get_entity_url(sender),
                        utils.escape_html(get_display_name(sender)),
                        msg_obj.text,
                        message_url=await utils.get_message_link(msg_obj),
                    )
                    if isinstance(msg_obj.peer_id, PeerChat)
                    else self.strings("deleted_pm").format(
                        utils.get_entity_url(sender),
                        utils.escape_html(get_display_name(sender)),
                        msg_obj.text,
                        message_url=await utils.get_message_link(msg_obj),
                    )
                ),
            )

    @loader.raw_handler(UpdateDeleteChannelMessages)
    async def channel_delete_handler(self, update: UpdateDeleteChannelMessages):
        if not self.get("state", False):
            return

        for message in update.messages:
            key = f"{update.channel_id}/{message}"
            if key not in self._cache:
                continue

            msg_obj = self._cache.pop(key)

            if (
                msg_obj.sender_id in self.always_track
                or utils.get_chat_id(msg_obj) in self.always_track
                or self.config["enable_groups"]
                and (
                    self._should_capture(
                        msg_obj.sender_id,
                        utils.get_chat_id(msg_obj),
                    )
                    and (not self.config["ignore_inline"] or not msg_obj.via_bot_id)
                    and not msg_obj.sender.bot
                )
            ):
                await self._message_deleted(
                    msg_obj,
                    self.strings("deleted_chat").format(
                        utils.get_entity_url(msg_obj.chat),
                        utils.escape_html(get_display_name(msg_obj.chat)),
                        utils.get_entity_url(msg_obj.sender),
                        utils.escape_html(get_display_name(msg_obj.sender)),
                        msg_obj.text,
                        message_url=await utils.get_message_link(msg_obj),
                    ),
                )

    @loader.watcher("in")
    async def watcher(self, message: Message):
        if (
            self.config["save_sd"]
            and getattr(message, "media", False)
            and getattr(message.media, "ttl_seconds", False)
        ):
            media = io.BytesIO(await self.client.download_media(message.media, bytes))
            media.name = "sd.jpg" if message.photo else "sd.mp4"
            sender = await self.client.get_entity(message.sender_id, exp=0)
            await (
                self.inline.bot.send_photo
                if message.photo
                else self.inline.bot.send_video
            )(
                self._channel,
                media,
                caption=self.strings("sd_media").format(
                    utils.get_entity_url(sender),
                    utils.escape_html(get_display_name(sender)),
                ),
            )

        with contextlib.suppress(AttributeError):
            self._cache[
                (
                    message.id
                    if message.is_private or isinstance(message.peer_id, PeerChat)
                    else f"{utils.get_chat_id(message)}/{message.id}"
                )
            ] = message
