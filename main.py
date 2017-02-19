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


def getCompLink(compName):
	for comp in comps:
		if comp['name'] in compName:
			return "["+comp['acronym']+"]("+comp['link']+")"

	return ""

teams = []

def matchesTable(table, str):
	for item in table:
		if str in item:
			return True
	return False


def getTeamLink(name):
	for item in teams:
		if item['contains'] in name:
			return ("["+item['acronym']+"]("+item['link']+")", item['include'])

	return ("", False)


channels = [{'contains': 'ESPN2', 'link': 'http://espn.go.com/watchespn/index/_/sport/soccer-futbol/channel/espn2'}
    ,{'contains': 'ESPN ', 'link': 'http://www.espn.com/watchespn/index/_/sport/soccer-futbol/channel/espn'}
	,{'contains': 'FS1', 'link': 'http://msn.foxsports.com/foxsports1'}
	,{'contains': 'UniMás', 'link': 'http://tv.univision.com/unimas'}
	,{'contains': 'MLS LIVE', 'link': 'http://live.mlssoccer.com/mlsmdl'}
]


def getChannelLink(name):
	for item in channels:
		if item['contains'] in name:
			return "[]("+item['link']+")"

	return ""


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

	firstConf = {'name': "E", 'size': 10}
	secondConf = {'name': "W", 'size': 10}
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


### Parse schedule ###
def parseSchedule():
	page = requests.get("http://www.mlssoccer.com/schedule")
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
			match['tbd'] = True
		else:
			try:
				match['datetime'] = datetime.datetime.strptime(date+" "+time[0], "%A, %B %d, %Y %I:%M%p ET")
				match['tbd'] = False
			except Exception as err:
				continue

		home = element.xpath(".//*[contains(@class,'home_club')]/*[contains(@class,'club_name')]/*/text()")
		if not len(home):
			log.warning("Couldn't pull home team, skipping")
			log.warning(match)
			continue
		match['home'] = home[0]

		away = element.xpath(".//*[contains(@class,'vs_club')]/*[contains(@class,'club_name')]/*/text()")
		if not len(away):
			log.warning("Couldn't pull away team, skipping")
			log.warning(match)
			continue
		match['away'] = away[0]

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

	strList = []
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
	except Exception as err:
		log.warning("Exception parsing schedule")
		log.warning(traceback.format_exc())
		skip = True


	try:
		standings = parseTable()

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
	except Exception as err:
		log.warning("Exception parsing table")
		log.warning(traceback.format_exc())
		skip = True

	try:
		today = datetime.date.today()

		schedule = parseSchedule()

		strList.append("-----\n")
		strList.append("#Schedule\n")
		strList.append("*All times ET*\n\n")
		strList.append("Time | Home | Away | TV\n")
		strList.append(":--:|:--:|:--:|:--:|\n")

		i = 0
		lastDate = None
		for game in schedule:
			if game['datetime'] < datetime.datetime.now():
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
				strList.append("**")
				strList.append(game['datetime'].strftime("%m/%d"))
				strList.append("**|\n")

			if game['tbd']:
				strList.append("TBD")
			else:
				strList.append(game['datetime'].strftime("%I:%M"))
			strList.append(" | ")
			strList.append(homeLink)
			strList.append(" | ")
			strList.append(awayLink)
			strList.append(" | ")
			strList.append(getChannelLink(game['tv']))
			strList.append("|\n")

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
		if debug:
			log.info(''.join(strList))
		else:
			subreddit = r.get_subreddit(SUBREDDIT)
			subreddit.update_settings(description=baseSidebar+''.join(strList))

	log.debug("Run complete after: %d", int(time.perf_counter() - startTime))
	if once:
		break
	time.sleep(15 * 60)
