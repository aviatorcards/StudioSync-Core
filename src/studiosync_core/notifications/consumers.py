from channels.generic.websocket import AsyncJsonWebsocketConsumer


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Check if user is authenticated - deny the connection outright, not after accept
        if self.scope["user"].is_anonymous:
            await self.close(code=4003)
            return

        self.user_id = self.scope["user"].id
        self.group_name = f"user_notifications_{self.user_id}"

        # Join the user's personal notification group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group if it was set
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Handler called by channel layer group_send
    async def send_notification(self, event):
        notification = event["notification"]
        await self.send_json({"type": "notification", "data": notification})
