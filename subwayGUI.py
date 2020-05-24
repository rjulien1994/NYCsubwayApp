from flask import Flask, render_template, request, url_for, redirect
import mysql.connector
import numpy as np

#Connection with private raspberry pi server
myHost = "85.201.144.18"     #These parameters are set when you build your database
myUser = "julien"          #This is where you have to put your info
myPassword = "Ejordan1994-"
myDatabase = "NYCsubwayDB"
myPort = 2500

myHost = "85.201.144.18"     #These parameters are set when you build your database
myUser = "julien"          #This is where you have to put your info
myPassword = "Ejordan1994-"
myDatabase = "NYCsubwayDB"
myPort = 2500

app = Flask(__name__)

def fetchFromPI(tableName, variableNames='*', condition='none'):
    mydb = mysql.connector.connect(
    host=myHost,   
    user=myUser,       
    passwd=myPassword,
    database=myDatabase,
    port=myPort
    )
    if(condition != 'none'):
        condition = 'WHERE ' + condition

    SQLCommand = "SELECT {} FROM {} {};".format(variableNames, tableName, condition)  

    mycursor = mydb.cursor()    
    mycursor.execute(SQLCommand)    #we sent the command to the server
    data = mycursor.fetchall()  #we read the response and translate it to have array per variable
    mydb.close()    #We close the connection with the db

    return np.array(data)

def addUser(user, psd, email):
    mydb = mysql.connector.connect(
    host=myHost,   
    user=myUser,       
    passwd=myPassword,
    database=myDatabase,
    port=myPort
    )
    
    SQLCommand = "INSERT INTO UsersTable(userName, userPassword, userEmail) VALUES ('{}', '{}', '{}');".format(user, psd, email)
    
    mycursor = mydb.cursor()    
    mycursor.execute(SQLCommand)
    mydb.commit()                   #we sent and execute the insert command to the db
    
    mydb.close()
    
def addRequest(stopID, userID):
    mydb = mysql.connector.connect(
    host=myHost,   
    user=myUser,       
    passwd=myPassword,
    database=myDatabase,
    port=myPort
    )
    
    SQLCommand = "INSERT INTO requestTable(userID, stopID) VALUES ('{}', '{}');".format(userID, stopID)
    
    mycursor = mydb.cursor()    
    mycursor.execute(SQLCommand)
    mydb.commit()                   #we sent and execute the insert command to the db
    
    mydb.close()
    
def deleteRequest(requestID):
    mydb = mysql.connector.connect(
    host=myHost,   
    user=myUser,       
    passwd=myPassword,
    database=myDatabase,
    port=myPort
    )
    
    SQLCommand = "DELETE FROM requestTable WHERE requestID={};".format(requestID)
    
    mycursor = mydb.cursor()    
    mycursor.execute(SQLCommand)
    mydb.commit()                   #we sent and execute the insert command to the db
    
    mydb.close()
    

@app.route("/login", methods=['POST', 'GET'])
def login():
    
    if request.form.get('userName') != None: #if user is already trying to log in
        userTable = fetchFromPI('UsersTable')
        
        user = request.form.get('userName')
        password = request.form.get('password')
        
        for u in userTable:
            if u[1] == user and u[2] == password:
                #Here we would go to homepage of user with id u[0]
                return redirect(url_for('homePage', userID=u[0]))
        
        return render_template('logInPage.html', Msg='No account found for username and/or password')
    
    elif request.form.get('newUserName') != None: #if user created an account
        userTable = fetchFromPI('UsersTable')
        
        userName = request.form.get('newUserName')
        password = request.form.get('newPassword')
        confpassword = request.form.get('newPassword2')
        emailAdress = request.form.get('newEmail')
        
        if password != confpassword:
            return render_template('logInPage.html', Msg="The passwords didn't match")
        
        for u in userTable:
            if u[1] == userName and u[2] == password:
                return render_template('logInPage.html', Msg='Account already exist')
        
        addUser(userName, password, emailAdress)
        
        return render_template('logInPage.html', Msg='Thank you for signing up, you can now log in')
    
    return render_template('logInPage.html', Msg='')
        

    
@app.route("/signUp", methods=['POST', 'GET'])
def signUp():
    return render_template('signUpPage.html')

    
@app.route("/home/<userID>", methods=['POST', 'GET'])
def homePage(userID):
    requests = fetchFromPI('requestTable, StopsTable, Stations', variableNames='Stations.stationID, StopsTable.stopID, StopsTable.lineID, direction, stationName, northBound, southBound, requestID', condition='requestTable.stopID = StopsTable.stopID AND Stations.stationID =StopsTable.stationID AND requestTable.userID = {}'.format(userID))
    
    trainSchedule = []
    
    for r in requests:
        route = {'station': r[4], 'train': r[2], 'terminal': r[5], 'requestID': r[7]}
        if r[3] == 'South':
            route['terminal'] = r[6]
        
        route['times'] = fetchFromPI('scheduleTable', variableNames='arrivalTime', condition="scheduleTable.stopID = '{}'".format(r[1]))
        trainSchedule.append(route)
        
    return render_template('homePage.html', schedule=trainSchedule, user=userID)

@app.route("/addARoute/<userID>", methods=['POST', 'GET'])
def addRoute(userID):
    if request.form.get('newStop') != None:
        newStop = request.form.get('newStop')
        addRequest(newStop, userID)
        return redirect(url_for('homePage', userID=userID))
    
    if request.form.get('newDirection') != None:
        newDir = request.form.get('newDirection')
        newstationID = request.form.get('newStation')
        stopList = fetchFromPI('StopsTable', variableNames='stopID, lineID', condition="direction='{}' and stationID='{}'".format(newDir, newstationID))
        
        return render_template('addRoute.html', stopData=stopList, check=2)
    
    if request.form.get('newStation') != None:
        newStationID = request.form.get('newStation')

        directionList = fetchFromPI('Stations', variableNames='stationID, northBound, southBound', condition="stationID='{}'".format(newStationID))

        return render_template('addRoute.html', directionData=directionList, check=1)
    
    stationList = fetchFromPI('Stations', variableNames='stationID, stationName')
    
    
    return render_template('addRoute.html', stationData=stationList, check=0)

@app.route("/removeRequest/<requestID>/<userID>", methods=['POST', 'GET'])
def removeRequest(requestID, userID):
    deleteRequest(requestID)
    return redirect(url_for('homePage', userID=userID))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    
    
    
    
