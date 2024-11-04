from Models import Activity

class User():
    def __init__(self, userId, activityList = [], EPZs = []):
        self.userId = userId
        self.activityList = activityList
        self.EPZs = EPZs
    
    def setActivity(self, helper):
        helper.setCurrentUser(self.userId)
        activityIdList = helper.getActivityIdListByUserID()
        for activity in activityIdList:
            currActivity = Activity.Activity.initActivityFromPath(helper, activity)
            self.activityList.append(currActivity)
