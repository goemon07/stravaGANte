from AuthController import *
from Utility.ApplicationInfo import *
from ActivityRetriever import *

def main():
    appInfo = ApplicationInfo("Strava")
    authController = AuthController(appInfo)
    session = authController.retriveSession()
    activityRetriver = ActivityRetriever(session, appInfo)
    activityRetriver.fetchActivity()

if __name__ == "__main__":
    main()