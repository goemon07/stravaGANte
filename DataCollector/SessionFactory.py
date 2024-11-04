from DataCollector.Strava import StravaSession

class SessionFactory:
    def __init__(self, appInfo, scope):
        self.appInfo = appInfo
        self.scope = scope
        self.session = StravaSession.StravaSession(self.appInfo.client_id, redirect_uri=self.appInfo.redirect_uri, scope=self.scope)
    

    def createSession(self):
        return self.session
