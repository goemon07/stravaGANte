from DataCollector import SessionFactory
import webbrowser

class AuthController():
    def __init__(self, appInfo, scope = ['activity:read_all']):
        self.appInfo = appInfo
        self.scope = scope

    def retriveSession(self):
        sessionFactory = SessionFactory.SessionFactory(self.appInfo, self.scope)
        session = sessionFactory.createSession()      
        auth_link = session.authorization_url(self.appInfo.auth_base_url)

        print(f'Opening authorization link: {auth_link}')
        webbrowser.open(auth_link[0])

        redirect_response = input("Please paste redirecter URL here: ")

        session.fetch_token(
            token_url=self.appInfo.token_url,
            client_id=self.appInfo.client_id,
            client_secret=self.appInfo.client_secret,
            authorization_response=redirect_response,
            include_client_id=True
        )
        print(f"Access Token: {session.access_token}, Refresh Token: {session.refresh_token}")
        return session