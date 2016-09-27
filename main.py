#!/usr/bin/python3

import praw
import OAuth2Util
import os
import logging.handlers
from lxml import html
import requests
import datetime
import time
import sys
import traceback
import json

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


teams = [{'contains': 'Chicago', 'acronym': 'CHI', 'link': 'http://www.chicago-fire.com'}
	,{'contains': 'Colorado', 'acronym': 'COL', 'link': 'http://www.coloradorapids.com'}
	,{'contains': 'Columbus', 'acronym': 'CLB', 'link': 'http://www.columbuscrewsc.com'}
	,{'contains': 'Dallas', 'acronym': 'FCD', 'link': 'http://www.fcdallas.com'}
	,{'contains': 'D.C. United', 'acronym': 'DC', 'link': 'http://www.dcunited.com'}
	,{'contains': 'Houston', 'acronym': 'HOU', 'link': 'http://www.houstondynamo.com'}
	,{'contains': 'Montreal', 'acronym': 'MTL', 'link': 'http://www.impactmontreal.com/en'}
	,{'contains': 'Galaxy', 'acronym': 'LAG', 'link': 'http://www.lagalaxy.com'}
	,{'contains': 'Portland', 'acronym': 'POR', 'link': 'http://www.portlandtimbers.com'}
	,{'contains': 'New England', 'acronym': 'NE', 'link': 'http://www.revolutionsoccer.net'}
	,{'contains': 'Salt Lake', 'acronym': 'RSL', 'link': 'http://rsl.com'}
	,{'contains': 'New York City', 'acronym': 'NYC', 'link': 'http://www.nycfc.com/'}
	,{'contains': 'NYCFC', 'acronym': 'NYC', 'link': 'http://www.nycfc.com/'}
	,{'contains': 'San Jose', 'acronym': 'SJ', 'link': 'http://www.sjearthquakes.com'}
	,{'contains': 'Red Bull', 'acronym': 'NYRB', 'link': 'http://www.newyorkredbulls.com'}
	,{'contains': 'Orlando', 'acronym': 'OCSC', 'link': 'http://www.orlandocitysc.com/'}
	,{'contains': 'Seattle', 'acronym': 'SEA', 'link': 'http://www.soundersfc.com'}
	,{'contains': 'Philadelphia', 'acronym': 'PHI', 'link': 'http://www.philadelphiaunion.com'}
	,{'contains': 'Sporting', 'acronym': 'SKC', 'link': 'http://www.sportingkc.com'}
	,{'contains': 'Toronto', 'acronym': 'TFC', 'link': 'http://torontofc.ca'}
	,{'contains': 'Vancouver', 'acronym': 'VAN', 'link': 'http://www.whitecapsfc.com'}
]


def getTeamLink(name):
	for item in teams:
		if item['contains'] in name:
			return "["+item['acronym']+"]("+item['link']+")"

	return "[UNK](http://www.mlssoccer.com/)"


channels = [{'contains': 'ESPN2', 'link': 'http://espn.go.com/watchespn/index/_/sport/soccer-futbol/channel/espn2'}
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

	elements = [{'title': 'Club', 'name': 'name'}
		,{'title': 'Points', 'name': 'points'}
		,{'title': 'Games Played', 'name': 'played'}
		,{'title': 'Goals For', 'name': 'goalsFor'}
		,{'title': 'Goal Difference', 'name': 'goalDiff'}
		,{'title': 'Wins', 'name': 'wins'}
	]

	for element in elements:
		for i, item in enumerate(tree.xpath("//td[@data-title='"+element['title']+"']/text()")):
			standings[i][element['name']] = item

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
def parseWeek(date):
	page = requests.get("http://matchcenter.mlssoccer.com/matches/"+date.strftime("%Y-%m-%d"))
	tree = html.fromstring(page.content)

	schedule = []
	for i, item in enumerate(tree.xpath("//span[@class='sb-club-name-full']/text()")):
		if i % 2 == 0:
			schedule.append({'home': item})
		else:
			schedule[int((i - 1) / 2)]['away'] = item

	elements = [{'title': 'sb-match-date', 'type': 'div', 'name': 'date', 'child': None}
		,{'title': 'sb-match-time', 'type': 'div', 'name': 'time', 'child': None}
		,{'title': 'sb-match-comp', 'type': 'div', 'name': 'comp', 'child': None}
		,{'title': 'sb-tv-listing', 'type': 'div', 'name': 'tv', 'child': 0}
	]

	for element in elements:
		for i, item in enumerate(tree.xpath("//" + element['type'] + "[@class='" + element['title'] + "']"+
				("/text()" if element['child'] is None else ""))):
			if element['child'] is None:
				schedule[i][element['name']] = item
			else:
				schedule[i][element['name']] = item[element['child']].text

	for match in schedule:
		try:
			match['datetime'] = datetime.datetime.strptime(match['date']+" "+str(datetime.datetime.now().year)+" "+match['time'], "%a, %b %d %Y %I:%M %p ET")
		except Exception as err:
			match['datetime'] = None

	return schedule



log.debug("Connecting to reddit")

once = False
if len(sys.argv) > 1 and sys.argv[1] == 'once':
	once = True

r = praw.Reddit(user_agent=USER_AGENT, log_request=0)
o = OAuth2Util.OAuth2Util(r)
o.refresh(force=True)

while True:
	startTime = time.perf_counter()
	log.debug("Starting run")

	strList = []
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
			strList.append(getTeamLink(team['name']))
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
		continue

	try:
		today = datetime.date.today()
		lastMonday = today - datetime.timedelta(days=today.weekday())

		schedule = parseWeek(lastMonday)
		schedule += parseWeek(lastMonday + datetime.timedelta(weeks=1))

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

			if game['comp'] != "MLS":
				continue

			if lastDate != game['datetime'].date():
				lastDate = game['datetime'].date()
				strList.append("**")
				strList.append(game['datetime'].strftime("%m/%d"))
				strList.append("**|\n")

			strList.append(game['datetime'].strftime("%I:%M"))
			strList.append(" | ")
			strList.append(getTeamLink(game['home']))
			strList.append(" | ")
			strList.append(getTeamLink(game['away']))
			strList.append(" | ")
			strList.append(getChannelLink(game['tv']))
			strList.append("|\n")

			i += 1
			if i >= 8:
				break
	except Exception as err:
		log.warning("Exception parsing schedule")
		log.warning(traceback.format_exc())
		continue

	baseSidebar = ""
	try:
		resp = requests.get(url="https://www.reddit.com/r/"+SUBREDDIT+"/wiki/sidebar-template.json", headers={'User-Agent': USER_AGENT})
		jsonData = json.loads(resp.text)
		baseSidebar = jsonData['data']['content_md'] + "\n"
	except Exception as err:
		log.warning("Exception parsing schedule")
		log.warning(traceback.format_exc())
		continue

	subreddit = r.get_subreddit(SUBREDDIT)
	subreddit.update_settings(description=baseSidebar+''.join(strList))

	log.debug("Run complete after: %d", int(time.perf_counter() - startTime))
	if once:
		break
	time.sleep(15 * 60)
