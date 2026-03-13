import logging

from django.contrib.auth.models import AnonymousUser

from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken

from studiosync_core.core.models import User

from urllib.parse import unquote

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user(token_key):
    try:
        # Decode token if it was URL encoded
        token_key = unquote(token_key)
        # Validate token
        access_token = AccessToken(token_key)
        user_id = access_token.payload.get("user_id")
        return User.objects.get(id=user_id)
    except Exception as e:
        logger.error(f"WebSocket JWT Auth Error: {e}")
        return AnonymousUser()


class TokenAuthMiddleware:
    """
    Custom middleware that takes a token from the query string and authenticates the user.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        query_params = dict(qp.split("=") for qp in query_string.split("&") if "=" in qp)
        token_key = query_params.get("token")

        if token_key:
            scope["user"] = await get_user(token_key)
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)
