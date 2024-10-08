import requests
import time
import asyncio
from .. import loader

class AirRaidAlertModule(loader.Module):
    """Модуль для відслідковування повітряних тривог у Києві та Миколаєві."""
    strings = {
        "name": "AirRaidAlert",
        "alert_active": "⚠️ Повітряна тривога в {}! Початок: {}",
        "alert_ended": "✅ Повітряну тривогу в {} закінчено! Закінчення: {}"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            "API_TOKEN", None, lambda: "API токен для alerts.in.ua",
            "CHECK_INTERVAL", 60, lambda: "Інтервал перевірки тривог (у секундах)"
        )
        self.kyiv_alert_active = False
        self.mykolaiv_alert_active = False

    async def client_ready(self, client, db):
        """Функція, що виконується після готовності клієнта."""
        self.client = client
        self.chat_id = -1736424935
        while True:
            await self.check_alerts()
            await asyncio.sleep(self.config["CHECK_INTERVAL"])

    async def check_alerts(self):
        """Перевіряє статус повітряних тривог для Києва та Миколаєва."""
        url = f"https://api.alerts.in.ua/v1/iot/active_air_raid_alerts_by_oblast.json?token={self.config['API_TOKEN']}"
        response = requests.get(url)

        if response.status_code == 200:
            alerts = response.json().get("alerts", "")
            kyiv_status = alerts[9]  # 10-а буква — Київ
            mykolaiv_status = alerts[14]  # 15-а буква — Миколаїв

            current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

            # Обробка тривоги для Києва
            if kyiv_status == "A" and not self.kyiv_alert_active:
                await self.client.send_message(self.chat_id, self.strings["alert_active"].format("Київ", current_time))
                self.kyiv_alert_active = True
            elif kyiv_status == "N" and self.kyiv_alert_active:
                await self.client.send_message(self.chat_id, self.strings["alert_ended"].format("Київ", current_time))
                self.kyiv_alert_active = False

            # Обробка тривоги для Миколаєва
            if mykolaiv_status == "A" and not self.mykolaiv_alert_active:
                await self.client.send_message(self.chat_id, self.strings["alert_active"].format("Миколаїв", current_time))
                self.mykolaiv_alert_active = True
            elif mykolaiv_status == "N" and self.mykolaiv_alert_active:
                await self.client.send_message(self.chat_id, self.strings["alert_ended"].format("Миколаїв", current_time))
                self.mykolaiv_alert_active = False
        else:
            print(f"Error: Unable to fetch alerts. Status code: {response.status_code}")
