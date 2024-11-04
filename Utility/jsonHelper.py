import json
import os

class jsonHelper():
    def __init__(self, appInfo):
        self.appFolder = "Data/" + appInfo.getAppName() + "/"
        self.users = self.getUserList(self.appFolder)
        self.currentUser = None


    ### Initializes array of [user_id, user_folder_path, list(activities_id_relatedToUser)]
    @staticmethod
    def getUserList(appFolder):
        users = []
        for user in os.listdir(appFolder):
            userFolder = os.path.join(appFolder, user)
            users.append([user, userFolder, os.listdir(userFolder)])
        return users



    def setCurrentUser(self, userID):
        self.currentUser = userID
        return
    
    def getActivityIdListByUserID(self, userID=None):
        if userID is not None:
            self.setCurrentUser(userID)
        activityIdList = []
        for activity in os.listdir(os.path.join(self.appFolder, self.currentUser)):
            activityIdList.append(self.appFolder + self.currentUser + "/activities/" + activity)
        return activityIdList
    
    @staticmethod
    def getActivityIdListByPath(path):
        activityIdList = []
        for activityId in os.listdir(path):
            activityIdList.append(activityId)
        return activityIdList
        
    ### Returns the Value for the Attribute "Key" in the json file in "jsonPath"
    #### Nested Attributes can be returned with sintax "outerAttribute.innerAttribute"
    @staticmethod
    def getJsonValue(jsonPath, key):
        keys=key.split('.')
        jsonData = json.loads(open(jsonPath, encoding="utf-8").read())
        for k in keys:
            if k not in jsonData:
                print(f"Invalid key {k} in {jsonPath}")
                return None
            jsonData = jsonData[k]
        return jsonData
    

    @staticmethod
    def getJsonValues(jsonPath, keys):
        jsonData = json.loads(open(jsonPath, encoding="utf-8").read())
        jsonValueList = {}
        for key in keys:
            found = True
            dividedKey = key.split('.')
            jsonSubData = jsonData
            for subKey in dividedKey:
                if subKey not in jsonSubData:
                    jsonValueList[subKey] = None
                    found = False
                    break
                jsonSubData = jsonSubData[subKey]
            if found:
                jsonValueList[key]=jsonSubData
        return jsonValueList

        