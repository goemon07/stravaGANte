import os

class ActivityRetriever():
    def __init__(self, session, appInfo):
        self.session = session
        self.appInfo = appInfo
    
    def retriveActivityIDList(self):
        response = self.session.get(self.appInfo.getAthleteActivityUrl()+"?per_page=200")
        page=1
        responseData = response.json()
        activityIDList = []
        for item in responseData:
            activityIDList.append(item['id'])

        ##  Multiple Requests for all activities.   ##
        """
        while len(activityIDList)==200*page:
            page+=1
            response = self.session.get(self.appInfo.AthleteActivitiesUrl()+f"?page={page}&per_page=200")
            responseData = response.json()
            for item in responseData:
                activityIDList.append(item['id'])
        """

        return activityIDList
    
    def retriveActivity(self, id):
        response = self.session.get(self.appInfo.getActivityUrl()+str(id))
        responseData = response.json()
        athleteID = str(responseData['athlete']['id'])

        ## Create Folder if not exists
        appFolder = "Data/" + self.appInfo.getAppName() + "/" + athleteID
        folderPath = os.path.join(appFolder, athleteID)
        filename = f'./Data/{self.appInfo.getAppName()}/{athleteID}/{id}.json'
        if not os.path.exists(os.path.dirname(folderPath)):
            os.makedirs(os.path.dirname(folderPath))
        with open(filename, 'w', encoding="utf-8") as outfile:
            outfile.write(response.text)
            outfile.close()
        

    def fetchActivity(self):
        activityList = self.retriveActivityIDList()
        for id in activityList:
            self.retriveActivity(id)