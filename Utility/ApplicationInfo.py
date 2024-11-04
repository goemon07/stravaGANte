from dotenv import load_dotenv
import os

class ApplicationInfo():
    def __init__(self, applicationName):
        load_dotenv()
        self.applicationName = applicationName
        self.client_id = os.getenv(applicationName+"client_id")
        self.client_secret = os.getenv(applicationName+"client_secret")
        self.auth_base_url = os.getenv(applicationName+"auth_base_url")
        self.redirect_uri = os.getenv(applicationName+"redirect_uri")
        self.token_url = os.getenv(applicationName+"token_url")
        self.AthleteActivitiesUrl = os.getenv(applicationName+"AthleteActivitiesUrl")
        self.ActivitiesUrl = os.getenv(applicationName+"ActivitiesUrl")
        self.EPZRadiusesList = []
        EPZRadiusesList = os.getenv(applicationName+"EPZRadiuses")
        if EPZRadiusesList is not None:
            for radius in EPZRadiusesList.split(","):
                self.EPZRadiusesList.append(int(radius))                
        self.IntersectionThreshold = float(os.getenv(applicationName+"IntersectionThreshold"))
        self.DistanceThreshold = float(os.getenv(applicationName+"DistanceThreshold"))
        self.ConfidenceThreshold = float(os.getenv(applicationName+"ConfidenceThreshold"))
        self.MinDistanceThreshold = float(os.getenv(applicationName+"MinDistanceThreshold"))

    def getAthleteActivityUrl(self):
        return self.AthleteActivitiesUrl
    
    def getActivityUrl(self):
        return self.ActivitiesUrl
    
    def getAppName(self):
        return self.applicationName
    
    def getEPZRadiusesList(self):
        return self.EPZRadiusesList
    
    def getIntersectionThreshold(self):
        return self.IntersectionThreshold
    
    def getDistanceThreshold(self):
        return self.DistanceThreshold
    
    def getMinDistanceThreshold(self):
        return self.MinDistanceThreshold

    def getConfidenceThreshold(self):
        return self.ConfidenceThreshold