from google.transit import gtfs_realtime_pb2
from protobuf_to_dict import protobuf_to_dict
import numpy as np
import pandas as pd
import mysql.connector
import requests
import time


#Connection with private raspberry pi server
myHost = "hostIP"     #These parameters are set when you build your database
myUser = "User"          #This is where you have to put your info
myPassword = "secretPassword"
myDatabase = "NYCsubwayDB"
myPort = 2500

#Connection parameters with MTA database
api_key = 'Your developper key'                #Developper's key
MTAfeedID = ['1','26','16','21','2','11','31','36','51']    #MTA full feed id

def fetchStationDataFromMTA(): #Outputs Station ID by station and line
    StationID = pd.read_csv("http://web.mta.info/developers/data/nyct/subway/Stations.csv")[['GTFS Stop ID','Stop Name', 'Daytime Routes', 'North Direction Label', 'South Direction Label', 'GTFS Longitude', 'GTFS Latitude']]
    StationDB = []

    for row in range(len(StationID['Stop Name'])):
        lines = StationID['Daytime Routes'][row]
        ID = StationID['GTFS Stop ID'][row]
        name = str(StationID['Stop Name'][row]).replace("'", " ")
        longitude = StationID['GTFS Longitude'][row]
        latitude = StationID['GTFS Latitude'][row]
        nDir = str(StationID['North Direction Label'][row]).replace("'", " ")
        sDir = str(StationID['South Direction Label'][row]).replace("'", " ")
        StationDB.append({'stationID': ID,
                          'stationName': name, 
                          'trainLines': lines, 
                          'northBound': nDir, 
                          'southBound': sDir, 
                          'longitude': longitude,
                         'latitude': latitude})
    return StationDB

#stationMTADB = fetchStationDataFromMTA()
#print(stationMTADB)


def sendDataToStationTable(stationData):    #add an entry in database
    mydb = mysql.connector.connect(
    host=myHost,   
    user=myUser,       
    passwd=myPassword,
    database=myDatabase,
    port=myPort
    )
    
    mycursor = mydb.cursor()
    
    SQLCommand = "INSERT INTO Stations(stationName, stationID, northBound, southBound, latitude, longitude) VALUES"  
    stopInfo = []

    for record in stationData:    #this will place the variables we want into the command
        SQLCommand += "('{}','{}','{}','{}','{}','{}'), ".format(record['stationName'], record['stationID'], record['northBound'], record['southBound'], record['latitude'], record['longitude'])
        lpt = record['trainLines'].split(' ')
        for l in lpt:
            print(l)
            stopInfo.append({'stationID': record['stationID'], 'lineID': l, 'direction': 'North'})
            stopInfo.append({'stationID': record['stationID'], 'lineID': l, 'direction': 'South'})

    SQLCommand = SQLCommand[0:-2] + ";"

    mycursor.execute(SQLCommand)
    mydb.commit()                   #we sent and execute the insert command to the db
    
    SQLCommand = "INSERT INTO StopsTable(stationID, lineID, direction) VALUES"
    
    for record in stopInfo:    #this will place the variables we want into the command
        SQLCommand += "('{}','{}','{}'), ".format(record['stationID'], record['lineID'], record['direction'])
    
    SQLCommand = SQLCommand[0:-2] + ";"

    mycursor.execute(SQLCommand)
    mydb.commit()
    
    mydb.close()

#sendDataToStationTable(stationMTADB)

def fetchFullMTASchedule():

    records = []
    currentTime = int(time.time())
    connectionStatus = {'pass' : 0, 'fail': 0, 'undefined': 0}

    for feedID in MTAfeedID:
        connection = False
        
        try:
            feed = gtfs_realtime_pb2.FeedMessage()
            response = requests.get('http://datamine.mta.info/mta_esi.php?key={}&feed_id={}'.format(api_key, feedID))
            feed.ParseFromString(response.content)
            subway_feed = protobuf_to_dict(feed)
            connection = True
            connectionStatus['pass'] += 1
        except:
            connectionStatus['fail'] += 1
            pass

        if connection:
            try:
                for record in subway_feed['entity']:
                    try:
                        info = record['trip_update']
                        #print(info)
                        L = info['trip']['route_id']
                        tripID = info['trip']['trip_id']
                        #N = len(info['stop_time_update'])
                        for stop in info['stop_time_update']:
                            T = stop['departure']['time']
                            S = stop['stop_id']
                            direction = 'North'
                            if S[-1] == 'S':
                                direction = 'South'
                            if currentTime < T and currentTime + 3600 > T:
                                records.append({'Train':L, 'trip_id':tripID, 'Station': S[:-1], 'Direction': direction, 'Time': T})
                    except:
                        pass
            except:
                connectionStatus['undefined'] += 1
                pass
        time.sleep(0.3)
        print('.')

    return [records, connectionStatus] #output data in a dataframe

schedule = fetchFullMTASchedule()[0]

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

#listData = fetchFromPI('StopsTable', "")
#print(listData)
#print(sum(listData[1][1:] == ['R01', 'N', 'South']))
#print([schedule[0]['Train'], schedule[0]['Station'], schedule[0]['Direction']])

def sendDataToScheduleTable(scheduleData):    #add an entry in database
    
    stopList = fetchFromPI('StopsTable')
    
    orderList = []
    PKList = []
    
    transData = []
    
    for p in stopList:
        orderList.append([p[1], p[2], p[3]])
        PKList.append(p[0])
    
    for t in scheduleData:
        try:
            stopFK = PKList[orderList.index([t['Station'], t['Train'], t['Direction']])]
            transData.append({'tripPK': t['trip_id'], 'stopFK':stopFK, 'time': t['Time']})
        except:
            print("failed to find {}".format([t['Station'], t['Train'], t['Direction']]))

    mydb = mysql.connector.connect(
    host=myHost,   
    user=myUser,       
    passwd=myPassword,
    database=myDatabase,
    port=myPort
    )
    
    mycursor = mydb.cursor()
    
    SQLCommand = "REPLACE INTO scheduleTable(tripID, stopID, arrivalTime) VALUES"  

    for row in transData:    #this will place the variables we want into the command
        SQLCommand += "('{}','{}','{}'), ".format(row['tripPK'], row['stopFK'], row['time'])

    SQLCommand = SQLCommand[0:-2] + ";"

    mycursor.execute(SQLCommand)
    mydb.commit()                   #we sent and execute the insert command to the db
    
    mydb.close()

#transit = fetchFullMTASchedule()
#print("We had {} successes and {} failures when laoding data.".format(transit[1]['pass'], transit[1]['fail']))
sendDataToScheduleTable(schedule)
#print('schedule loaded to PI')

def deleteFromPI(tableName, condition):
    mydb = mysql.connector.connect(
    host=myHost,   
    user=myUser,       
    passwd=myPassword,
    database=myDatabase,
    port=2000
    )

    SQLCommand = "DELETE FROM {} WHERE {};".format(tableName, condition)  

    mycursor = mydb.cursor()    
    mycursor.execute(SQLCommand)    #we sent the command to the server
    mydb.close()    #We close the connection with the db

def getListOfStations():
    data = fetchFromPI(variableNames='stationName', tableName='Stations')
    output = []
    for stop in data:
        output.append(stop[0])
    return output

#print(getListOfStations())
#allStations = getListOfStations()

def searchStations(partial):    #return stations db search on partial name of station
    stationList = [s for s in allStations if partial in s]  #gets list of possible stations by name
    if stationList != []:   #if any station was found
        cond = ''           #pieces together the sql condition 
        for c in stationList:
            cond += "stationName='{}' OR ".format(c)
        cond = cond[0:-4]
        data = fetchFromPI(tableName='Stations', condition=cond)    #gets data from sql
    else:
        data = "No data"
    return np.array(data)

#someStations = searchStations('145')
#print(someStations)

def fetchSchedule(staID, trainLine, trainDir): #returns sorted array of departure times
    #first fetch times
    cond = "stationID='{}' AND trainLine='{}' AND direction='{}'".format(staID, trainLine, trainDir)
    data = fetchFromPI(tableName='MTAschedule', variableNames='timeInSec', condition=cond)
    depTimes = np.array([t[0] for t in data])
    #Second fetch station info
    cond = "stationID='{}'".format(staID)
    data = fetchFromPI(tableName='Stations', condition=cond)[0]
    print(data)
    outputInfo = {'StationName': data[0], 'Line':trainLine, 'Times': np.sort(depTimes)}
    outputInfo['Direction'] = data[4] if trainDir == 'N' else data[5]
    return outputInfo

#print(fetchSchedule('A12','A','N'))
#timeTable = fetchSchedule('A12','A','N')
#print("The next {} train towards {} will depart from {} at {}".format(timeTable['Line'], timeTable['Direction'], #timeTable['StationName'], timeTable['Times'][0]))

def updateScheduleTable():
    newSchedule = fetchFullMTASchedule()[0]    #get new data from server
    updatedLines = []                       #checks the lines we successfully got update
    for update in newSchedule:
        if update['Train'] not in updatedLines:
            updatedLines.append(update['Train'])
    for l in updatedLines:                  #deletes past data for lines with new ifo
        cond = "trainLine='{}'".format(l)
        deleteFromPI('MTAschedule', cond)
    sendDataToScheduleTable(newSchedule)    #sends new schedule to PI SQL

