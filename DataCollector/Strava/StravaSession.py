from typing import Any
from oauthlib.oauth2 import Client
from requests_oauthlib import OAuth2Session
import time

class StravaSession(OAuth2Session):
    def __init__(self, client_id: Any | None = None, client: Client | None = None, auto_refresh_url: str | None = None, auto_refresh_kwargs: dict[str, Any] | None = None, scope: Any | None = None, redirect_uri: Any | None = None, token: Any | None = None, state: Any | None = None, token_updater: Any | None = None, **kwargs) -> None:
        super().__init__(client_id, client, auto_refresh_url, auto_refresh_kwargs, scope, redirect_uri, token, state, token_updater, **kwargs)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        rateLimit = response.headers['X-ReadRateLimit-Limit'].split(',')
        rateUsage = response.headers['X-ReadRateLimit-Usage'].split(',')
        
        if rateUsage[0] == rateLimit[0]:
            time.sleep(15*60)
        
        if rateUsage[1] == rateLimit[1]:
            return response, "Reached Daily Rate Limit"
        else:
            return response

