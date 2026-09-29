from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Xabar YUBORISH hamon HTTP POST orqali boradi (/chat/api/... - CSRF,
    autentifikatsiya va validatsiya Django view darajasida, ishonchliroq).
    Bu WebSocket faqat: 1) serverdan brauzerga jonli push (yangi xabar,
    tahrirlash, o'chirish, o'qildi belgisi), 2) "onlayn" holatini
    yangilab turish uchun ping qabul qilish uchun ishlatiladi."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        employee = await self._get_employee(user)
        if not employee:
            await self.close()
            return

        self.employee_id = employee.id
        self.group_name = f"chat_user_{employee.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._touch_online()

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self._touch_online()

    # ---- guruhdan kelgan hodisalarni brauzerga uzatish ----
    async def chat_message(self, event):
        await self.send_json({"type": "message", "message": event["message"]})

    async def chat_edit(self, event):
        await self.send_json({"type": "edit", "message": event["message"]})

    async def chat_delete(self, event):
        await self.send_json({"type": "delete", "message": event["message"]})

    async def chat_read(self, event):
        await self.send_json({
            "type": "read",
            "conversation_id": event["conversation_id"],
            "reader_id": event["reader_id"],
            "message_ids": event["message_ids"],
        })

    @staticmethod
    async def _get_employee(user):
        from asgiref.sync import sync_to_async
        return await sync_to_async(lambda: getattr(user, "employee", None))()

    async def _touch_online(self):
        from asgiref.sync import sync_to_async
        from .services import touch_online

        employee_id = getattr(self, "employee_id", None)
        if not employee_id:
            return

        def _do():
            from main.models import Employee
            emp = Employee.objects.filter(pk=employee_id).first()
            if emp:
                touch_online(emp)

        await sync_to_async(_do)()
