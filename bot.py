import classes,socket,time,re,threading,json,time,math,datetime,os,gspread,loginInfo,data
from oauth2client.service_account import ServiceAccountCredentials
from utilityFunctions import utilityFunctions
from urllib2 import urlopen

#--------------------
#    constants
#--------------------
uf = utilityFunctions()
info = classes.info()
ralle = classes.info()
timer = classes.timer()
joke = classes.randomMessages()
quote = classes.randomMessages()

CHAT_MSG=re.compile(r"^:\w+!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :")
streamtime = 0
mvd = 0
md = 0
lastChat = ""
status = False

channel = data.channel
ops = data.ops
info.info = data.info
ralle.info = data.ralle
joke.load(data.joke)
quote.load(data.quote)
commands = data.commands

#--------------------
# configuring socket
#--------------------
s = socket.socket()
s.connect(("irc.twitch.tv", 6667))
s.send(("PASS %s\r\n"%loginInfo.twitchPass).encode("utf-8"))
s.send(("NICK %s\r\n"%loginInfo.twitchUsername).encode("utf-8"))
s.send(("JOIN #%s\r\n"%channel).encode("utf-8"))

#--------------------
#     functions
#--------------------
def save():
    global channel,info,ops,records
    try:
        f = open("data.py","w")
        f.write("channel = \""+channel+"\"\n")
        f.write("info = \""+info.info+"\"\n")
        f.write("ops = "+str(ops)+"\n")
        f.write("ralle = \""+ralle.info+"\"\n")
        f.write("quote = "+str(quote.array)+"\n")
        f.write("joke = "+str(joke.array)+"\n")
        f.write("commands = "+str(commands).replace("], [","],\n[").replace("[[","[\n[")+"\n")
        f.close()
    except:
        print("saving failed. recovering backup...")
        os.system("sudo cp dataBackup.py data.py")
    os.system("sudo cp data.py dataBackup.py")

def chat(msg):
    global s,channel,lastChat
    if msg == lastChat:
        msg = str(msg)+" ."
    s.send(("PRIVMSG #%s :%s\r\n"%(channel,msg)).encode("utf-8"))
    #print(str(msg)+"\r\n")
    lastChat = msg
    
#--------------------
#     threads
#--------------------
def spreadsheetUpdater(): #handles all spreadsheet vars and updating
    global ss,ss2,ss3,ssval,ss2val,ss3val,gs,sss,er
    ecount = 0
    er = False
    while True:
        try:
            def reloadSpreadsheets():
                global ss,ss2,ss3,ssval,ss2val,ss3val,sss,er
                try:
                    ss3 = sss.worksheet("TimerSplits")
                    ss2 = sss.worksheet("Charts")
                    ss = sss.worksheet("Data")
                    ssval = ss.get_all_values()
                    ss2val = ss2.get_all_values()
                    ss3val = ss3.get_all_values()
                except:
                    er = True

            spReload = threading.Thread(target=reloadSpreadsheets)
            spReload.start()
            spReload.join(30)
            if spReload.isAlive():
                raise Exception("reload timed out")

            if er:
                er = False
                raise Exception("error when reloading")
                
        except Exception as error:
            print("spreadsheet updating failed: "+str(error))
            try:
                def reauth():
                    try:
                        global sss,gs,er
                        scope = ['https://spreadsheets.google.com/feeds']
                        credentials = ServiceAccountCredentials.from_json_keyfile_name(loginInfo.gspread, scope)
                        gs = gspread.authorize(credentials)
                        sss = gs.open("brians stream spreadsheet")
                    except:
                        er = True

                auth = threading.Thread(target=reauth)
                auth.start()
                auth.join(15)
                if auth.isAlive():
                    raise Exception("reauth timed out")
                else:
                    ss = sss.worksheet("Data")
                    ssval = ss.get_all_values()

                if er:
                    er = False
                    raise Exception("error while reauthing")

                print("reauthed")
            except Exception as error:
                print("reauth failed: " + str(error))

def socketUpdater(): #necessary as socket sometimes randomly stop listening
    global s
    socketTimer = time.time()
    while True:
        if socketTimer + 3600 < time.time():
            while True:
                try:
                    socketTimer = time.time()
                    s2 = socket.socket()
                    s2.connect(("irc.twitch.tv", 6667))
                    s2.send(("PASS %s\r\n"%loginInfo.twitchPass).encode("utf-8"))
                    s2.send(("NICK %s\r\n"%loginInfo.twitchUsername).encode("utf-8"))
                    s2.send(("JOIN #%s\r\n"%channel).encode("utf-8"))
                    break
                except:
                    pass
            s = s2
        time.sleep(0.1)

def streamCheck(): #handles most stream info like live status and uptime
    global status,streamInfo,seconds,streamtime,uptime
    while True:
        streamInfo = json.loads(uf.url("https://api.twitch.tv/kraken/astystreams/%s?client_id=%s"%(channel, loginInfo.twitchApiId)).read().decode('utf-8'))
        if streamInfo.get("stream") == None:
            if status == True:
                status = False
                #to execute when stream stops, usualy about 5 minutes late
                print("stream Stop\r\n")
                chat("stream stop detected, stream was up %s. Thanks for the stream brian!"%uptime)
                streamtime += seconds
                time.sleep(120) #to prevent buggy twitch api being buggy
            status = False
        else:
            if status == False:
                status = True
                #to execute when stream starts, usualy a minute late
                print("stream Start\r\n")
                time.sleep(60) #to prevent buggy twitch api being buggy
            status = True
        
        #timezone converting madness for uptime
        if status:
            weirdTime = streamInfo.get("stream").get("created_at")
            date, times = weirdTime.split("T")
            times = times.split("Z")
            h, m, se = times[0].split(":")
            y, mo, d = date.split("-")
            dt = datetime.datetime(int(y),int(mo),int(d),int(h),int(m),int(se))
            start = time.mktime(dt.timetuple())
            seconds = time.mktime(datetime.datetime.utcfromtimestamp(time.time()).timetuple())-start
            m, sec = divmod(seconds, 60)
            h, m = divmod(m, 60)
            uptime = "%sh%sm%ss"%(h, m, sec)

def spreadsheetHandler(): #handles all the spreadsheet updating for data
    global spreadsheetTimer,streamtime,ss,ssval,mvd,md,ss2
    spreadsheetTimer = uf.nyctime().date()
    time.sleep(10)
    while True:
        try:
            if uf.nyctime().date() != spreadsheetTimer: #if its time to update spreadsheet
                print("new day")
                strlen = str(uf.length(ssval,0)+1)
                nostrlen = str(uf.length(ssval,8)+1)

                ss.update_acell("M"+nostrlen,"0")
                
                if mvd: #if there was a stream today
                    ss.update_acell("A"+strlen,str(spreadsheetTimer))
                    ss.update_acell("B"+strlen,str(streamtime))
                    ss.update_acell("C"+strlen,uf.readableTime(streamtime))
                    ss.update_acell("D"+strlen,str(spreadsheetTimer))
                    ss.update_acell("E"+strlen,mvd)
                    ss.update_acell("F"+strlen,str(spreadsheetTimer))
                    ss.update_acell("G"+strlen,md)
                    ss.update_acell("M"+nostrlen,"1")

                ss.update_acell("H"+nostrlen,str(spreadsheetTimer))
                ss.update_acell("I"+nostrlen,int(json.loads(uf.url("https://api.twitch.tv/kraken/channels/lorgon?client_id=%s"%loginInfo.twitchApiId).read()).get("views"))-int(ss.acell("K"+str(int(nostrlen)-1)).value))#dont question the readability, it works
                ss.update_acell("J"+nostrlen,str(spreadsheetTimer))
                ss.update_acell("K"+nostrlen,str(int(json.loads(uf.url("https://api.twitch.tv/kraken/channels/lorgon?client_id=%s"%loginInfo.twitchApiId).read()).get("views"))))
                ss.update_acell("L"+nostrlen,str(spreadsheetTimer))

                
                spreadsheetTimer = uf.nyctime().date()
                mvd = 0
                md = 0

            ss2.update_acell("B3",uf.readableTime(uf.largest(uf.getColumn(ssval,2))))
            ss2.update_acell("C3",uf.largest(uf.getColumn(ssval,5)))
            ss2.update_acell("D3",uf.streak(uf.getColumn(ssval,13)))
            num = 0
            for i in range(0,len(uf.getColumn(ssval,2))):
                num += int(uf.getColumn(ssval,2)[i])
            num = num / len(uf.getColumn(ssval,2))
            ss2.update_acell("E3",uf.readableTime(num))
            ss2.update_acell("B6",uf.largest(uf.getColumn(ssval,7)))
            ss2.update_acell("C6",uf.largest(uf.getColumn(ssval,9)))
        except Exception as error:
            pass

def recordsHandler():
    global streamInfo,seconds,mvd
    while True:
        try:
            if int(streamInfo.get("stream").get("viewers")) > mvd:
                    mvd = int(streamInfo.get("stream").get("viewers"))
            if seconds > records[1]:
                    records[1] = seconds
                    save()
        except:
            time.sleep(10)
        time.sleep(0.1)

def responseHandler(): #handles socket responses
    global s,commands,md
    pingTimer = time.time()
    while True:
        response = s.recv(1024).decode("utf-8")
        if response != None:
            if response == "PING :tmi.twitch.tv\r\n":
                s.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
                #print(time.time()-pingTimer)
                pingTimer = time.time()
            else:
                username = re.search(r"\w+", response).group(0)
                message = CHAT_MSG.sub("", response)
                message = message.replace("\r\n","")
                messageSplit = message.split(" ")
                if status:
                    md += 1

                for i in range(0,len(commands)): #checks if command is a command added by !addcommand, if so chats the coresponding message
                    if commands[i][0] == message and commands[i][3] == True:
                        chat(commands[i][4])

                #the if statement for checking for commands
                #add an elif to add another command
                #"message" is the chat message
                #"username" is the username that sent the message
                #"messageSplit" is an array of the message split at every space
                #bot does not register messages it sends itself.
                if messageSplit[0] == "!addcommand":
                    try:
                        if uf.isOp(ops, username):
                            messageSplit[1] = messageSplit[1].replace("!","")
                            for i in range(0,len(commands)):
                                if commands[i][0] == "!"+messageSplit[1]:
                                    chat("command %s alredy exists."%commands[i][0])
                                    break
                            else:
                                commands.append(["!"+messageSplit[1],"This command returns simple text.",True,True,message.split(" ",2)[2]])
                                save()
                                chat("Command !%s has been added with message \"%s\""%(messageSplit[1],message.split(" ",2)[2]))
                        else:
                            chat("You do not have permission to do that!")
                    except:
                        chat("An error occurred. You are probably missing something.")
                        
                elif messageSplit[0] == "!removecommand":
                    try:
                        if uf.isOp(ops, username):
                            for i in range(0,len(commands)):
                                if messageSplit[1].replace("!","") == commands[i][0].replace("!",""):
                                    if commands[i][2] == True:
                                        commands.remove(commands[i])
                                        chat("Command !%s has been removed"%messageSplit[1].replace("!",""))
                                        break
                                    else:
                                        chat("!%s is not a removeable command"%messageSplit[1].replace("!",""))
                            else:
                                chat("!%s is not a command and thus cannot be removed"%messageSplit[1].replace("!",""))
                        else:
                            chat("You do not have permission to do that!")
                    except Exception as error:
                        chat(str(error)+" An error occurred. You are probably missing something.")

                elif message == "!commands":
                    string = ""
                    for item in commands:
                        string += item[0] + " "
                    chat(string)

                elif messageSplit[0] == "!help":
                    for item in commands:
                        if "!%s"%messageSplit[1].replace("!","") == item[0]:
                            chat(item[1])
#--------------------
#initializing threads
#--------------------
thread1 = threading.Thread(target=spreadsheetUpdater)
thread1.start()
thread2 = threading.Thread(target=socketUpdater)
thread2.start()
thread3 = threading.Thread(target=streamCheck)
thread3.start()
thread4 = threading.Thread(target=spreadsheetHandler)
thread4.start()
thread5 = threading.Thread(target=recordsHandler)
thread5.start()
thread6 = threading.Thread(target=responseHandler)
thread6.start()
