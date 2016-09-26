#!/usr/bin/python3

import praw
import OAuth2Util
import os
import logging.handlers
from lxml import html
import requests
import datetime

### Config ###
LOG_FOLDER_NAME = "logs"
SUBREDDIT = "MLS"
BOT_NAME = "UNKNOWN"

### Logging setup ###
LOG_LEVEL = logging.DEBUG
if not os.path.exists(LOG_FOLDER_NAME):
    os.makedirs(LOG_FOLDER_NAME)
LOG_FILENAME = LOG_FOLDER_NAME+"/"+"bot.log"
LOG_FILE_BACKUPCOUNT = 5
LOG_FILE_MAXSIZE = 1024 * 256

log = logging.getLogger("bot")
log.setLevel(LOG_LEVEL)
log_formatter = logging.Formatter('%(levelname)s: %(message)s')
log_stderrHandler = logging.StreamHandler()
log_stderrHandler.setFormatter(log_formatter)
log.addHandler(log_stderrHandler)
if LOG_FILENAME is not None:
	log_fileHandler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=LOG_FILE_MAXSIZE, backupCount=LOG_FILE_BACKUPCOUNT)
	log_formatter_file = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
	log_fileHandler.setFormatter(log_formatter_file)
	log.addHandler(log_fileHandler)


### Parse table ###
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
]

teams = [{'contains': 'Chicago', 'acronym': 'CHI', 'link': 'http://www.chicago-fire.com'}
	,{'contains': 'Colorado', 'acronym': 'COL', 'link': 'http://www.coloradorapids.com'}
	,{'contains': 'Columbus', 'acronym': 'CLB', 'link': 'http://www.thecrew.com'}
	,{'contains': 'Dallas', 'acronym': 'FCD', 'link': 'http://www.fcdallas.com'}
	,{'contains': 'D.C. United', 'acronym': 'DC', 'link': 'http://www.dcunited.com'}
	,{'contains': 'Houston', 'acronym': 'HOU', 'link': 'http://www.houstondynamo.com'}
	,{'contains': 'Montreal', 'acronym': 'MTL', 'link': 'http://www.impactmontreal.com/en'}
	,{'contains': 'Galaxy', 'acronym': 'LAG', 'link': 'http://www.lagalaxy.com'}
	,{'contains': 'Portland', 'acronym': 'POR', 'link': 'http://www.portlandtimbers.com'}
	,{'contains': 'New England', 'acronym': 'NE', 'link': 'http://www.revolutionsoccer.net'}
	,{'contains': 'Salt Lake', 'acronym': 'RSL', 'link': 'http://www.realsaltlake.com'}
	,{'contains': 'New York City', 'acronym': 'NYC', 'link': 'http://www.nycfc.com/'}
	,{'contains': 'San Jose', 'acronym': 'SJ', 'link': 'http://www.sjearthquakes.com'}
	,{'contains': 'Red Bull', 'acronym': 'NYRB', 'link': 'http://www.newyorkredbulls.com'}
	,{'contains': 'Orlando', 'acronym': 'OCSC', 'link': 'http://www.orlandocitysc.com/'}
	,{'contains': 'Seattle', 'acronym': 'SEA', 'link': 'http://www.soundersfc.com'}
	,{'contains': 'Philadelphia', 'acronym': 'PHI', 'link': 'http://www.philadelphiaunion.com'}
	,{'contains': 'Sporting', 'acronym': 'SKC', 'link': 'http://www.sportingkc.com'}
	,{'contains': 'Toronto', 'acronym': 'TFC', 'link': 'http://torontofc.ca'}
	,{'contains': 'Vancouver', 'acronym': 'VAN', 'link': 'http://www.whitecapsfc.com'}
]

for element in elements:
	for i, item in enumerate(tree.xpath("//td[@data-title='"+element['title']+"']/text()")):
		standings[i][element['name']] = item

for team in standings:
	for item in teams:
		if item['contains'] in team['name']:
			team['acronym'] = item['acronym']
			team['link'] = item['link']

	if 'acronym' not in team:
		team['acronym'] = "UNK"
		team['link'] = "http://www.mlssoccer.com/"


sortedStandings = []
firstCount = 0
secondCount = firstConf['size']
while True:
	if int(standings[firstCount]['points']) > int(standings[secondCount]['points']):
		standings[firstCount]['ranking'] = firstConf['name'] + str(firstCount + 1)
		sortedStandings.append(standings[firstCount])
		firstCount += 1
	else:
		standings[secondCount]['ranking'] = secondConf['name'] + str(secondCount - firstConf['size'] + 1)
		sortedStandings.append(standings[secondCount])
		secondCount += 1

	if firstCount == firstConf['size'] - 1:
		while True:
			standings[secondCount]['ranking'] = secondConf['name'] + str(secondCount - firstConf['size'] + 1)
			sortedStandings.append(standings[secondCount])
			secondCount += 1

			if secondCount == firstConf['size'] + secondConf['size']:
				break

		break

	if secondCount == firstConf['size'] + secondConf['size'] - 1:
		while True:
			standings[firstCount]['ranking'] = firstConf['name'] + str(firstCount + 1)
			sortedStandings.append(standings[firstCount])
			firstCount += 1

			if firstCount == firstConf['size']:
				break

		break


### Parse schedule ###
def parseWeek(date):
	page = requests.get("http://matchcenter.mlssoccer.com/matches/"+lastMonday.strftime("%Y-%m-%d"))
	tree = html.fromstring(page.content)

	schedule = []
	for i, item in enumerate(tree.xpath("//span[@class='sb-club-name-short']/text()")):
		if i % 2 == 0:
			schedule.append({'home': item})
		else:
			schedule[int((i - 1) / 2)]['away'] = item

	elements = [{'title': 'sb-match-date', 'type': 'div', 'name': 'date'}
		,{'title': 'sb-match-time', 'type': 'div', 'name': 'time'}
		,{'title': 'sb-match-comp', 'type': 'div', 'name': 'comp'}
	]

	for element in elements:
		for i, item in enumerate(tree.xpath("//" + element['type'] + "[@class='" + element['title'] + "']/text()")):
			schedule[i][element['name']] = item

	for match in schedule:
		match['datetime'] = datetime.datetime.strptime(match['date']+" "+str(datetime.datetime.now().year)+" "+match['time'], "%a, %b %d %Y %I:%M %p ET")

	return schedule

today = datetime.date.today()
lastMonday = today - datetime.timedelta(days=today.weekday())

schedule = parseWeek(lastMonday)
schedule += parseWeek(lastMonday + datetime.timedelta(weeks=1))


