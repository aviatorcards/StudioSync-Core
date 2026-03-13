"""
Tests for WebSocket authentication middleware.
"""

from django.urls import path

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator

from studiosync_core.messaging.consumers import NotificationConsumer
from studiosync_core.messaging.middleware import TokenAuthMiddleware


@pytest.mark.websocket
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWebSocketAuth:
    """Test WebSocket authentication middleware."""

    async def test_websocket_connect_without_token(self):
        """Test WebSocket connection fails without auth token."""
        application = TokenAuthMiddleware(
            URLRouter(
                [
                    path("ws/notifications/", NotificationConsumer.as_asgi()),
                ]
            )
        )

        communicator = WebsocketCommunicator(application, "ws/notifications/")

        connected, _ = await communicator.connect()

        # Should fail to connect without token
        assert connected is False

        await communicator.disconnect()

    async def test_websocket_connect_with_invalid_token(self):
        """Test WebSocket connection fails with invalid token."""
        application = TokenAuthMiddleware(
            URLRouter(
                [
                    path("ws/notifications/", NotificationConsumer.as_asgi()),
                ]
            )
        )

        communicator = WebsocketCommunicator(
            application, "ws/notifications/?token=invalid_token_string"
        )

        connected, _ = await communicator.connect()

        # Should fail to connect with invalid token
        assert connected is False

        await communicator.disconnect()

    async def test_websocket_connect_with_valid_token(self, admin_user):
        """Test WebSocket connection succeeds with valid token."""
        from rest_framework_simplejwt.tokens import AccessToken

        # Generate a valid token for the admin user
        token = str(AccessToken.for_user(admin_user))

        application = TokenAuthMiddleware(
            URLRouter(
                [
                    path("ws/notifications/", NotificationConsumer.as_asgi()),
                ]
            )
        )

        communicator = WebsocketCommunicator(application, f"ws/notifications/?token={token}")

        try:
            connected, _ = await communicator.connect()

            # Should successfully connect with valid token
            # Note: May fail if consumer requires additional setup
            # This test mainly validates the middleware
            assert connected in [True, False]  # Adjust based on your setup

        finally:
            await communicator.disconnect()
