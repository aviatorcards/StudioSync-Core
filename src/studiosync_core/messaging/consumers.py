from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.thread_id = self.scope["url_route"]["kwargs"]["thread_id"]
        self.room_group_name = f"chat_{self.thread_id}"

        # Check if user is authenticated
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        # Check if user is a participant in this thread
        if not await self.is_participant():
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    @database_sync_to_async
    def is_participant(self):
        from .models import MessageThread

        return MessageThread.objects.filter(
            id=self.thread_id, participants=self.scope["user"]
        ).exists()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from room group
    async def chat_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send_json({"type": "message", "data": message})
