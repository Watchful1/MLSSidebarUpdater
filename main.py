#!/usr/bin/python3

import praw
import os
import logging.handlers
from lxml import html
import requests
import datetime
import time
import sys
import traceback
import json
import configparser

### Config ###
LOG_FOLDER_NAME = "logs"
SUBREDDIT = "mls"
USER_AGENT = "MLSSideBarUpdater (by /u/Watchful1)"

SUBREDDIT2 = "rbny"
TEAM_NAME2 = "New York Red Bulls"

### Logging setup ###
LOG_LEVEL = logging.DEBUG
if not os.path.exists(LOG_FOLDER_NAME):
    os.makedirs(LOG_FOLDER_NAME)
LOG_FILENAME = LOG_FOLDER_NAME+"/"+"bot.log"
LOG_FILE_BACKUPCOUNT = 5
LOG_FILE_MAXSIZE = 1024 * 256

log = logging.getLogger("bot")
log.setLevel(LOG_LEVEL)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
log_stderrHandler = logging.StreamHandler()
log_stderrHandler.setFormatter(log_formatter)
log.addHandler(log_stderrHandler)
if LOG_FILENAME is not None:
	log_fileHandler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=LOG_FILE_MAXSIZE, backupCount=LOG_FILE_BACKUPCOUNT)
	log_formatter_file = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
	log_fileHandler.setFormatter(log_formatter_file)
	log.addHandler(log_fileHandler)

comps = [{'name': 'MLS', 'link': 'http://www.mlssoccer.com/', 'acronym': 'MLS'}
	,{'name': 'Preseason', 'link': 'http://www.mlssoccer.com/', 'acronym': 'UNK'}
	,{'name': 'CONCACAF', 'link': 'https://www.facebook.com/concacafcom', 'acronym': 'CCL'}
]

RBNYcomps = [{'name': 'MLS', 'link': '/MLS', 'acronym': 'MLS'}
	,{'name': 'Preseason', 'link': '/MLS', 'acronym': 'UNK'}
	,{'name': 'CONCACAF', 'link': 'http://category/champions-league/schedule-results', 'acronym': 'CCL'}
]


def getCompLink(compName):
	for comp in comps:
		if comp['name'] in compName:
			return "["+comp['acronym']+"]("+comp['link']+")"

	return ""


def getRBNYCompLink(compName):
	for comp in RBNYcomps:
		if comp['name'] in compName:
			return comp['link']

	return ""


teams = []


def matchesTable(table, str):
	for item in table:
		if str in item:
			return True
	return False


def getTeamLink(name, useFullname=False, nameOnly=False):
	for item in teams:
		if item['contains'] in name:
			if nameOnly:
				return (item['contains'] if useFullname else item['acronym'])
			else:
				return ("["+(item['contains'] if useFullname else item['acronym'])+"]("+item['link']+")", item['include'])

	return ("", False)


channels = [{'contains': 'ESPN2', 'link': 'http://espn.go.com/watchespn/index/_/sport/soccer-futbol/channel/espn2', 'exact': True, 'allowMLS': False}
    ,{'contains': 'ESPN', 'link': 'http://www.espn.com/watchespn/index/_/sport/soccer-futbol/channel/espn', 'exact': True, 'allowMLS': False}
	,{'contains': 'FS1', 'link': 'http://msn.foxsports.com/foxsports1', 'exact': False, 'allowMLS': False}
	,{'contains': 'FS2', 'link': 'https://en.wikipedia.org/wiki/Fox_Sports_2', 'exact': False, 'allowMLS': False}
	,{'contains': 'UDN', 'link': 'http://www.univision.com/deportes/futbol/mls', 'exact': False, 'allowMLS': False}
	,{'contains': 'Univision', 'link': 'http://www.univision.com/deportes/futbol/mls', 'exact': True, 'allowMLS': False}
	,{'contains': 'UniMás', 'link': 'http://tv.univision.com/unimas', 'exact': False, 'allowMLS': False}
	,{'contains': 'facebook.com', 'link': 'http://www.live.fb.com/', 'exact': False, 'allowMLS': True}
	,{'contains': 'FOX', 'link': 'http://www.fox.com/', 'exact': True, 'allowMLS': False}
	,{'contains': 'beIN', 'link': 'http://www.beinsport.tv/', 'exact': False, 'allowMLS': True}
	,{'contains': 'TSN', 'link': '#tsn', 'exact': False, 'allowMLS': True}
	,{'contains': 'MLS LIVE', 'link': 'http://live.mlssoccer.com/mlsmdl', 'exact': False, 'allowMLS': True}
]
msgLink = 'http://www.msgnetworks.com/teams/red-bulls/'


def getChannelLink(name, replaceMLSLive=False):
	stations = name.split(',')
	strList = []
	included = set()
	allowMLS = True
	for item in channels:
		for station in stations:
			if item['contains'] not in included:
				if len(strList) < 3 or (len(strList) < 6 and (item['contains'] != "MLS LIVE" or allowMLS)):
					if (item['exact'] and item['contains'] == station.strip()) or (not item['exact'] and item['contains'] in station):
						included.add(item['contains'])
						strList.append("[](")
						strList.append(msgLink if replaceMLSLive and item['contains'] == "MLS LIVE" else item['link'])
						strList.append(")")
						if not item['allowMLS']:
							allowMLS = False

	return ''.join(strList)


### Parse table ###
def compareTeams(team1, team2):
	if int(team1['points']) > int(team2['points']):
		return True
	elif int(team1['points']) < int(team2['points']):
		return False
	else:
		if int(team1['wins']) > int(team2['wins']):
			return True
		elif int(team1['wins']) < int(team2['wins']):
			return False
		else:
			if int(team1['goalDiff']) > int(team2['goalDiff']):
				return True
			elif int(team1['goalDiff']) < int(team2['goalDiff']):
				return False
			else:
				if int(team1['goalsFor']) > int(team2['goalsFor']):
					return True
				elif int(team1['goalsFor']) < int(team2['goalsFor']):
					return False
				else:
					log.error("Ran out of tiebreakers")
					return True

def parseTable():
	page = requests.get("http://www.mlssoccer.com/standings")
	tree = html.fromstring(page.content)

	firstConf = {'name': "E", 'size': 11}
	secondConf = {'name': "W", 'size': 11}
	standings = []
	for i in range(0, firstConf['size']+secondConf['size']):
		standings.append({'conf': (firstConf['name'] if i < firstConf['size'] else secondConf['name'])})

	elements = [{'title': 'Points', 'name': 'points'}
		,{'title': 'Games Played', 'name': 'played'}
		,{'title': 'Goals For', 'name': 'goalsFor'}
		,{'title': 'Goal Difference', 'name': 'goalDiff'}
		,{'title': 'Wins', 'name': 'wins'}
	]

	for element in elements:
		for i, item in enumerate(tree.xpath("//td[@data-title='"+element['title']+"']/text()")):
			standings[i][element['name']] = item

	for i, item in enumerate(tree.xpath("//td[@data-title='Club']")):
		names = item.xpath(".//a/text()")
		if not len(names):
			log.warning("Couldn't find team name")
			continue
		teamName = ""
		for name in names:
			if len(name) > len(teamName):
				teamName = name

		standings[i]['name'] = name


	sortedStandings = []
	firstCount = 0
	secondCount = firstConf['size']
	while True:
		if compareTeams(standings[firstCount], standings[secondCount]):
			standings[firstCount]['ranking'] = firstConf['name'] + str(firstCount + 1)
			sortedStandings.append(standings[firstCount])
			firstCount += 1
		else:
			standings[secondCount]['ranking'] = secondConf['name'] + str(secondCount - firstConf['size'] + 1)
			sortedStandings.append(standings[secondCount])
			secondCount += 1

		if firstCount == firstConf['size']:
			while True:
				standings[secondCount]['ranking'] = secondConf['name'] + str(secondCount - firstConf['size'] + 1)
				sortedStandings.append(standings[secondCount])
				secondCount += 1

				if secondCount == firstConf['size'] + secondConf['size']:
					break

			break

		if secondCount == firstConf['size'] + secondConf['size']:
			while True:
				standings[firstCount]['ranking'] = firstConf['name'] + str(firstCount + 1)
				sortedStandings.append(standings[firstCount])
				firstCount += 1

				if firstCount == firstConf['size']:
					break

			break

	return sortedStandings


def printTable(standings):
	strList = []
	strList.append("**[Standings](http://www.mlssoccer.com/standings)**\n\n")
	strList.append("*")
	strList.append(datetime.datetime.now().strftime("%m/%d/%y"))
	strList.append("*\n\n")
	strList.append("Pos | Team | Pts | GP | GF | GD\n")
	strList.append(":--:|:--:|:--:|:--:|:--:|:--:\n")

	for team in standings:
		strList.append(team['ranking'])
		strList.append(" | ")
		strList.append(getTeamLink(team['name'])[0])
		strList.append(" | **")
		strList.append(team['points'])
		strList.append("** | ")
		strList.append(team['played'])
		strList.append(" | ")
		strList.append(team['goalsFor'])
		strList.append(" | ")
		strList.append(team['goalDiff'])
		strList.append(" |\n")

	strList.append("\n\n\n")
	return strList


### Parse schedule ###
def parseScheduleOld():
	page = requests.get("https://www.mlssoccer.com/schedule?month=all&year=2017")
	tree = html.fromstring(page.content)

	schedule = []
	date = ""
	for i, element in enumerate(tree.xpath("//ul[contains(@class,'schedule_list')]/li[contains(@class,'row')]")):
		match = {}
		newDate = element.xpath(".//div[contains(@class,'match_date')]/text()")
		if len(newDate):
			date = newDate[0]

		time = element.xpath(".//*[contains(@class,'match_status')]/text()")
		if not len(time):
			log.warning("Couldn't find time for match, skipping")
			log.warning(match)
			continue

		if time[0] == "TBD":
			match['datetime'] = datetime.datetime.strptime(date, "%A, %B %d, %Y")
			match['status'] = 'tbd'
		elif time[0] == "FINAL":
			match['datetime'] = datetime.datetime.strptime(date, "%A, %B %d, %Y")
			match['status'] = 'final'
		elif "LIVE" in time[0]:
			match['datetime'] = datetime.datetime.strptime(date, "%A, %B %d, %Y")
			match['status'] = 'live'
		else:
			try:
				match['datetime'] = datetime.datetime.strptime(date+" "+time[0], "%A, %B %d, %Y %I:%M%p ET")
				match['status'] = ''
			except Exception as err:
				continue

		home = element.xpath(".//*[contains(@class,'home_club')]/*[contains(@class,'club_name')]/*/text()")
		if not len(home):
			log.warning("Couldn't pull home team, skipping")
			log.warning(match)
			continue
		match['home'] = home[0]

		homeScore = element.xpath(".//*[contains(@class,'home_club')]/*[contains(@class,'match_score')]/text()")
		if len(homeScore):
			match['homeScore'] = homeScore[0]
		else:
			match['homeScore'] = -1

		away = element.xpath(".//*[contains(@class,'vs_club')]/*[contains(@class,'club_name')]/*/text()")
		if not len(away):
			log.warning("Couldn't pull away team, skipping")
			log.warning(match)
			continue
		match['away'] = away[0]

		awayScore = element.xpath(".//*[contains(@class,'vs_club')]/*[contains(@class,'match_score')]/text()")
		if len(awayScore):
			match['awayScore'] = awayScore[0]
		else:
			match['awayScore'] = -1

		tv = element.xpath(".//*[contains(@class,'match_category')]/*/*/*/text()")
		if len(tv):
			match['tv'] = tv[0]
		else:
			match['tv'] = ""

		comp = element.xpath(".//*[contains(@class,'match_location_competition')]/text()")
		if not len(comp):
			log.warning("Couldn't find comp for match, skipping")
			log.warning(match)
			continue
		match['comp'] = comp[0]

		schedule.append(match)

	return schedule


### Parse schedule ###
def parseSchedule():
	page = requests.get("https://www.mlssoccer.com/")
	tree = html.fromstring(page.content)

	schedule = []
	for i, element in enumerate(tree.xpath("//*[@id='scoreboard-0']/div/div/div/a")):
		match = {}
		rawDate = element.xpath(".//div[@class='scoreboard-date-status']/span[@class='scoreboard-date']/text()")
		if len(rawDate):
			date = rawDate[0]
		else:
			log.debug("Could not find date")
			log.debug(match)

		rawTime = element.xpath(".//div[@class='scoreboard-date-status']/span[contains(@class,'scoreboard-date-time')]/text()")
		if len(rawTime):
			time = rawTime[0]
		else:
			log.debug("Could not find time")
			log.debug(match)

		match['datetime'] = datetime.datetime.strptime(date + datetime.datetime.now().strftime("/%y") + " " + time, "%m/%d/%y %I:%M%p")

		rawStatus = element.xpath(".//div[@class='scoreboard-date-status']/span[@class='scoreboard-match-period']/text()")
		if len(rawStatus):
			if rawStatus[0] == 'FINAL':
				match['status'] = 'final'
			else:
				match['status'] = ""
		else:
			match['status'] = ""


		rawHome = element.xpath(".//div[@class='scoreboard-clubs']/div/div[contains(@class,'scoreboard-home')]/span[@class='scoreboard-club-full']/text()")
		if len(rawHome):
			match['home'] = rawHome[0]
		else:
			log.debug("Could not find home")
			log.debug(match)

		rawAway = element.xpath(".//div[@class='scoreboard-clubs']/div/div[contains(@class,'scoreboard-away')]/span[@class='scoreboard-club-full']/text()")
		if len(rawAway):
			match['away'] = rawAway[0]
		else:
			log.debug("Could not find away")
			log.debug(match)

		rawComp = element.xpath(".//div[@class='scoreboard-competition']/text()")
		if len(rawComp):
			match['comp'] = rawComp[0]
		else:
			log.debug("Could not find comp")
			log.debug(match)

		rawTV = element.xpath(".//div[@class='scoreboard-broadcast']/text()")
		if len(rawTV):
			match['tv'] = rawTV[0]
		else:
			match['tv'] = ""

		#log.debug(match)

		schedule.append(match)

	return schedule


log.debug("Connecting to reddit")

once = False
debug = False
user = None
if len(sys.argv) >= 2:
	user = sys.argv[1]
	for arg in sys.argv:
		if arg == 'once':
			once = True
		elif arg == 'debug':
			debug = True
else:
	log.error("No user specified, aborting")
	sys.exit(0)


try:
	r = praw.Reddit(
		user
		,user_agent=USER_AGENT)
except configparser.NoSectionError:
	log.error("User "+user+" not in praw.ini, aborting")
	sys.exit(0)

while True:
	startTime = time.perf_counter()
	log.debug("Starting run")

	strListMLS = []
	strListRBNY = []
	skip = False

	teams = []
	try:
		resp = requests.get(url="https://www.reddit.com/r/"+SUBREDDIT+"/wiki/sidebar-teams.json", headers={'User-Agent': USER_AGENT})
		jsonData = json.loads(resp.text)
		teamText = jsonData['data']['content_md']

		firstLine = True
		for teamLine in teamText.splitlines():
			if firstLine:
				firstLine = False
				continue
			if teamLine.strip() == "":
				continue
			teamArray = teamLine.strip().split('|')
			if len(teamArray) < 4:
				log.warning("Couldn't parse team line: " + teamLine)
				continue
			team = {'contains': teamArray[0]
				,'acronym': teamArray[1]
				,'link': teamArray[2]
				,'include': True if teamArray[3] == 'include' else False
			}
			teams.append(team)

		schedule = parseSchedule()
		standings = parseTable()
	except Exception as err:
		log.warning("Exception parsing schedule")
		log.warning(traceback.format_exc())
		skip = True

	try:
		teamGames = []
		nextGameIndex = -1
		for game in schedule:
			if game['home'] == TEAM_NAME2 or game['away'] == TEAM_NAME2:
				teamGames.append(game)
				if game['datetime'] + datetime.timedelta(hours=2) > datetime.datetime.now() and nextGameIndex == -1:
					nextGameIndex = len(teamGames) - 1

		strListRBNY.append("##Upcoming Events\n\n")
		strListRBNY.append("Description|Time (ET)|TV\n")
		strListRBNY.append("---|---:|:---:|---|\n")
		for game in teamGames[nextGameIndex:nextGameIndex+4]:
			strListRBNY.append("**")
			strListRBNY.append(game['datetime'].strftime("%m/%d"))
			strListRBNY.append("**[](")
			strListRBNY.append(getRBNYCompLink(game['comp']))
			strListRBNY.append(")||")
			if game['home'] == TEAM_NAME2:
				strListRBNY.append("**Home**|\n")
				homeLink, homeInclude = getTeamLink(game['away'], True)
				strListRBNY.append(homeLink)
			else:
				strListRBNY.append("*Away*|\n")
				awayLink, awayInclude = getTeamLink(game['home'], True)
				strListRBNY.append(awayLink)
			strListRBNY.append("|")
			if game['status'] == 'tbd':
				strListRBNY.append("TBD")
			else:
				strListRBNY.append(game['datetime'].strftime("%I:%M"))
			strListRBNY.append("|")
			strListRBNY.append(getChannelLink(game['tv'], True))
			strListRBNY.append("|\n")

		strListRBNY.append("\n\n")
		strListRBNY.append("##Previous Results\n\n")
		strListRBNY.append("Date|Home|Result|Away\n")
		strListRBNY.append(":---:|:---:|:---:|:---:|\n")

		for game in reversed(teamGames[nextGameIndex-4:nextGameIndex]):
			strListRBNY.append("[")
			strListRBNY.append(game['datetime'].strftime("%m/%d"))
			strListRBNY.append("](")
			strListRBNY.append(getRBNYCompLink(game['comp']))
			strListRBNY.append(")|")
			if game['home'] == TEAM_NAME2:
				RBNYHome = True
			else:
				RBNYHome = False
			if RBNYHome:
				strListRBNY.append("**")
			strListRBNY.append(getTeamLink(game['home'], True, True))
			if RBNYHome:
				strListRBNY.append("**")
			strListRBNY.append("|")
			strListRBNY.append(game['homeScore'])
			strListRBNY.append("-")
			strListRBNY.append(game['awayScore'])
			strListRBNY.append("|")
			if not RBNYHome:
				strListRBNY.append("**")
			strListRBNY.append(getTeamLink(game['away'], True, True))
			if not RBNYHome:
				strListRBNY.append("**")
			strListRBNY.append("\n")

		strListRBNY.append("\n\n")
		strListRBNY.append("## MLS Standings\n\n")


	except Exception as err:
		log.warning("Exception parsing table")
		log.warning(traceback.format_exc())
		skip = True

	try:
		mlsTable = printTable(standings)
		strListMLS.extend(mlsTable)
		strListRBNY.extend(mlsTable)
	except Exception as err:
		log.warning("Exception parsing table")
		log.warning(traceback.format_exc())
		skip = True

	try:
		today = datetime.date.today()

		strListMLS.append("-----\n")
		strListMLS.append("#Schedule\n")
		strListMLS.append("*All times ET*\n\n")
		strListMLS.append("Time | Home | Away | TV\n")
		strListMLS.append(":--:|:--:|:--:|:--:|\n")

		i = 0
		lastDate = None
		for game in schedule:
			if game['datetime'].date() < (datetime.datetime.now() - datetime.timedelta(hours=3)).date():
				continue

			homeLink, homeInclude = getTeamLink(game['home'])
			awayLink, awayInclude = getTeamLink(game['away'])
			if not homeInclude and not awayInclude:
				log.warning("Could not get home/away, skipping")
				log.warning(game)
				continue

			if homeLink == "":
				homeLink = getCompLink(game['comp'])

			if awayLink == "":
				awayLink = getCompLink(game['comp'])

			if lastDate != game['datetime'].date():
				lastDate = game['datetime'].date()
				strListMLS.append("**")
				strListMLS.append(game['datetime'].strftime("%m/%d"))
				strListMLS.append("**|\n")

			if game['status'] == 'tbd':
				strListMLS.append("TBD")
			elif game['status'] == 'live':
				strListMLS.append("LIVE")
			elif game['status'] == 'final':
				strListMLS.append("FINAL")
			else:
				strListMLS.append(game['datetime'].strftime("%I:%M"))
			strListMLS.append(" | ")
			strListMLS.append(homeLink)
			strListMLS.append(" | ")
			strListMLS.append(awayLink)
			strListMLS.append(" | ")
			strListMLS.append(getChannelLink(game['tv']))
			strListMLS.append("|\n")

			i += 1
			if i >= 11:
				break
	except Exception as err:
		log.warning("Exception parsing schedule")
		log.warning(traceback.format_exc())
		skip = True

	baseSidebar = ""
	try:
		resp = requests.get(url="https://www.reddit.com/r/"+SUBREDDIT+"/wiki/sidebar-template.json", headers={'User-Agent': USER_AGENT})
		jsonData = json.loads(resp.text)
		baseSidebar = jsonData['data']['content_md'] + "\n"
	except Exception as err:
		log.warning("Exception parsing schedule")
		log.warning(traceback.format_exc())
		skip = True

	if not skip:
		try:
			subreddit2 = r.subreddit(SUBREDDIT2)
			description = subreddit2.description
			begin = description[0:description.find("##Upcoming Events")]
			end = description[description.find("##NYRB II (USL)"):]
			skipNYRB = False
		except Exception as err:
			log.warning("Broken rbny sidebar")
			log.warning(traceback.format_exc())
			skipNYRB = True
		if debug:
			log.info(''.join(strListMLS))
			log.info("\n\nRBNY\n\n")
			log.info(begin+''.join(strListRBNY)+end)
		else:
			try:
				if not skipNYRB:
					subreddit2.mod.update(description=begin+''.join(strListRBNY)+end)
				subreddit = r.subreddit(SUBREDDIT)
				subreddit.mod.update(description=baseSidebar+''.join(strListMLS))
			except Exception as err:
				log.warning("Exception updating sidebar")
				log.warning(traceback.format_exc())



	log.debug("Run complete after: %d", int(time.perf_counter() - startTime))
	if once:
		break
	time.sleep(15 * 60)
