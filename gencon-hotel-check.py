#!/usr/bin/env python2
from __future__ import print_function
from argparse import Action, ArgumentParser, ArgumentError, ArgumentTypeError, SUPPRESS
from datetime import datetime, timedelta
from json import loads as fromJS, dumps as toJS
from os.path import abspath, dirname, join as pathjoin
from re import compile as reCompile, IGNORECASE as RE_IGNORECASE
from ssl import create_default_context as create_ssl_context, CERT_NONE, SSLError
from sys import stdout, version_info
from threading import Thread
from time import sleep

if version_info < (2, 7, 9):
	print("Requires Python 2.7.9+")
	exit(1)
elif version_info.major == 2:
	from cookielib import CookieJar
	from HTMLParser import HTMLParser
	from urllib import urlencode
	from urllib2 import HTTPCookieProcessor, HTTPError, Request, URLError, urlopen, build_opener
	from urlparse import urlparse
else:
	from html.parser import HTMLParser
	from http.cookiejar import CookieJar
	from urllib.error import HTTPError, URLError
	from urllib.parse import urlencode, urlparse
	from urllib.request import HTTPCookieProcessor, Request, urlopen, build_opener

firstDay, lastDay, startDay = datetime(2023, 7, 28), datetime(2023, 8, 8), datetime(2023, 8, 3)
eventId = 50430831
ownerId = 10909638

distanceUnits = {
	1: 'blocks',
	2: 'yards',
	3: 'miles',
	4: 'meters',
	5: 'kilometers',
}

class PasskeyParser(HTMLParser):
	def __init__(self, resp):
		HTMLParser.__init__(self)
		self.json = None
		self.feed(resp.read().decode('utf8'))
		self.close()

	def handle_starttag(self, tag, attrs):
		if tag.lower() == 'script':
			attrs = dict(attrs)
			if attrs.get('id', '').lower() == 'last-search-results':
				self.json = True

	def handle_data(self, data):
		if self.json is True:
			self.json = data

try:
	from html import unescape
	PasskeyParser.unescape = lambda self, text: unescape(text)
except ImportError as e:
	pass

def type_day(arg):
	try:
		d = datetime.strptime(arg, '%Y-%m-%d')
	except ValueError:
		raise ArgumentTypeError("%s is not a date in the form YYYY-MM-DD" % arg)
	if not firstDay <= d <= lastDay:
		raise ArgumentTypeError("%s is outside the Gencon housing block window" % arg)
	return arg

def type_distance(arg):
	if arg == 'connected':
		return arg
	try:
		return float(arg)
	except ValueError:
		raise ArgumentTypeError("invalid float value: '%s'" % arg)

def type_regex(arg):
	try:
		return reCompile(arg, RE_IGNORECASE)
	except Exception as e:
		raise ArgumentTypeError("invalid regex '%s': %s" % (arg, e))

class KeyAction(Action):
	def __call__(self, parser, namespace, values, option_string = None):
		key, auth = values
		if reCompile('[0-9A-Z]{8}-[0-9A-Z]{4}').match(key):
			# New reservation
			if not reCompile('[0-9a-f]{1,64}').match(auth):
				raise ValueError("invalid (new) key auth")
		elif reCompile('[0-9A-Z]{8}').match(key):
			# Existing reservation
			if not reCompile("[0-9a-f]{32}").match(auth):
				raise ValueError("invalid (existing) key auth")
		else:
			raise ValueError("invalid key")
		setattr(namespace, self.dest, values)

class PasskeyUrlAction(Action):
	def __call__(self, parser, namespace, values, option_string = None):
		url = urlparse(values)
		if url.netloc == 'book.passkey.com' and url.path == '/entry' and 'token=' in url.query:
			setattr(namespace, self.dest, values)
		else:
			raise ArgumentError(self, "invalid passkey url: '%s'" % values)

class SurnameAction(Action):
	def __call__(self, parser, namespace, values, option_string = None):
		raise ArgumentError(self, "option no longer exists. Existing reservation lookups are now done with your hash instead of your surname")

class EmailAction(Action):
	def __call__(self, parser, namespace, values, option_string = None):
		dest = getattr(namespace, self.dest)
		if dest is None:
			dest = []
			setattr(namespace, self.dest, dest)
		dest.append(tuple(['email'] + values))

parser = ArgumentParser()
parser.add_argument('--surname', '--lastname', action = SurnameAction, help = SUPPRESS)
parser.add_argument('--guests', type = int, default = 1, help = 'number of guests')
parser.add_argument('--children', type = int, default = 0, help = 'number of children')
parser.add_argument('--rooms', type = int, default = 1, help = 'number of rooms')
group = parser.add_mutually_exclusive_group()
group.add_argument('--checkin', type = type_day, metavar = 'YYYY-MM-DD', default = startDay.strftime('%Y-%m-%d'), help = 'check in')
group.add_argument('--wednesday', dest = 'checkin', action = 'store_const', const = (startDay - timedelta(1)).strftime('%Y-%m-%d'), help = 'check in on Wednesday')
parser.add_argument('--checkout', type = type_day, metavar = 'YYYY-MM-DD', default = (startDay + timedelta(3)).strftime('%Y-%m-%d'), help = 'check out')
group = parser.add_mutually_exclusive_group()
group.add_argument('--max-distance', type = type_distance, metavar = 'BLOCKS', help = "max hotel distance that triggers an alert (or 'connected' to require skywalk hotels)")
group.add_argument('--connected', dest = 'max_distance', action = 'store_const', const = 'connected', help = 'shorthand for --max-distance connected')
parser.add_argument('--budget', type = float, metavar = 'PRICE', default = '99999', help = 'max total rate (not counting taxes/fees) that triggers an alert')
parser.add_argument('--hotel-regex', type = type_regex, metavar = 'PATTERN', default = reCompile('.*'), help = 'regular expression to match hotel name against')
parser.add_argument('--room-regex', type = type_regex, metavar = 'PATTERN', default = reCompile('.*'), help = 'regular expression to match room against')
parser.add_argument('--show-all', action = 'store_true', help = 'show all rooms, even if miles away (these rooms never trigger alerts)')
group = parser.add_mutually_exclusive_group()
group.add_argument('--delay', type = int, default = 1, metavar = 'MINS', help = 'search every MINS minute(s)')
group.add_argument('--once', action = 'store_true', help = 'search once and exit')
parser.add_argument('--test', action = 'store_true', dest = 'test', help = 'trigger every specified alert and exit')

group = parser.add_argument_group('required arguments')
# Both of these set 'key'; only one of them is required
group.add_argument('--url', action = PasskeyUrlAction, help = 'passkey URL containing your token')

group = parser.add_argument_group('alerts')
group.add_argument('--popup', dest = 'alerts', action = 'append_const', const = ('popup',), help = 'show a dialog box')
group.add_argument('--cmd', dest = 'alerts', action = 'append', type = lambda arg: ('cmd', arg), metavar = 'CMD', help = 'run the specified command, passing each hotel name as an argument')
group.add_argument('--browser', dest = 'alerts', action = 'append_const', const = ('browser',), help = 'open the Passkey website in the default browser')
group.add_argument('--email', dest = 'alerts', action = EmailAction, nargs = 3, metavar = ('HOST', 'FROM', 'TO'), help = 'send an e-mail')
group.add_argument('--pushbullet', dest = 'alerts', action = 'append', type = lambda arg: ('pushbullet', arg), metavar = 'ACCESS_TOKEN', help = 'send a Pushbullet notification')

args = parser.parse_args()

if args.url is None and not args.test:
	parser.print_usage()
	exit(1)

# Attempt to check the version against Github, but ignore it if it fails
# Only updating the version when a breaking bug is fixed (a crash or a failure to search correctly)
try:
	version = open(pathjoin(dirname(abspath(__file__)), 'version')).read()
	resp = urlopen('https://raw.githubusercontent.com/mrozekma/gencon-hotel-check/master/version')
	if resp.getcode() == 200:
		head = resp.read().decode('utf8')
		if version != head:
			print("Warning: This script is out-of-date. If you downloaded it via git, use 'git pull' to fetch the latest version. Otherwise, visit https://github.com/mrozekma/gencon-hotel-check")
			print()
except (HTTPError, IOError):
	pass

baseUrl = "https://book.passkey.com/event/%d/owner/%d" % (eventId, ownerId)

# Setup the alert handlers
alertFns = []
success = True
for alert in args.alerts or []:
	if alert[0] == 'popup':
		try:
			import win32api
			alertFns.append(lambda preamble, hotels: win32api.MessageBox(0, 'Gencon Hotel Search', "%s\n\n%s" % (preamble, '\n'.join("%s: %s: %s" % (hotel['distance'], hotel['name'], hotel['room']) for hotel in hotels))))
		except ImportError:
			try:
				import tkinter, tkinter.messagebox
				def handle(preamble, hotels):
					window = tkinter.Tk()
					window.wm_withdraw()
					tkinter.messagebox.showinfo(title = 'Gencon Hotel Search', message = "%s\n\n%s" % (preamble, '\n'.join("%s: %s: %s" % (hotel['distance'], hotel['name'], hotel['room']) for hotel in hotels)))
					window.destroy()
				alertFns.append(handle)
			except ImportError:
				print("Unable to show a popup. Install either win32api (if on Windows) or Tkinter")
				success = False
	elif alert[0] == 'cmd':
		import subprocess
		alertFns.append(lambda preamble, hotels, cmd = alert[1]: subprocess.Popen([cmd] + ["%s: %s" % (hotel['name'], hotel['room']) for hotel in hotels]))
	elif alert[0] == 'browser':
		import webbrowser
		alertFns.append(lambda preamble, hotels: webbrowser.open(baseUrl + '/home'))
	elif alert[0] == 'email':
		from email.mime.text import MIMEText
		import getpass, smtplib, socket
		_, host, fromEmail, toEmail = alert
		password = getpass.getpass("Enter password for %s (or blank if %s requires no authentication): " % (fromEmail, host))
		def closure(host, fromEmail, toEmail):
			def smtpConnect():
				try:
					smtp = smtplib.SMTP_SSL(host)
				except socket.error:
					smtp = smtplib.SMTP(host)
				if password:
					smtp.login(fromEmail, password)
				return smtp
			try:
				smtpConnect()
				def handle(preamble, hotels):
					msg = MIMEText("%s\n\n%s\n\n%s" % (preamble, '\n'.join("  * %s: %s: %s" % (hotel['distance'], hotel['name'].encode('utf-8'), hotel['room'].encode('utf-8')) for hotel in hotels), baseUrl + '/home'), 'plain', 'utf-8')
					msg['Subject'] = 'Gencon Hotel Search'
					msg['From'] = fromEmail
					msg['To'] = toEmail
					smtpConnect().sendmail(fromEmail, toEmail.split(','), msg.as_string())
				alertFns.append(handle)
				return True
			except Exception as e:
				print(e)
				return False
		if not closure(host, fromEmail, toEmail):
			success = False
	elif alert[0] == 'pushbullet':
		_, accessToken = alert
		def handle(preamble, hotels):
			data = {
				'type': 'link',
				'title': 'Gencon Hotel Search',
				'body': '\n'.join("%s: %s" % (hotel['name'], hotel['room']) for hotel in hotels),
				'url': baseUrl + '/home',
			}
			headers = {
				'Content-Type': 'application/json',
				'Access-Token': accessToken,
			}
			resp = urlopen(Request('https://api.pushbullet.com/v2/pushes', toJS(data).encode('utf-8'), headers))
			if resp.getcode() != 200:
				print("Response %d trying to send Pushbullet alert" % resp.getcode())
				return False
			return True
		alertFns.append(handle)

if not success:
	exit(1)
if not alertFns:
	print("Warning: You have no alert methods selected, so you're not going to know about a match unless you're staring at this window when it happens. See the README for more information")
	print()

if args.test:
	print("Testing alerts one at a time...")
	preamble = 'This is a test'
	hotels = [{'name': 'Test hotel 1', 'distance': '2 blocks', 'rooms': 1, 'room': 'Queen/Queen suite'}, {'name': 'Test hotel 2', 'distance': '5 blocks', 'rooms': 5, 'room': 'Standard King'}]
	for fn in alertFns:
		fn(preamble, hotels)
	print("Done")
	exit(0)

lastAlerts = set()
cookieJar = CookieJar()
opener = build_opener(HTTPCookieProcessor(cookieJar))

def send(name, *args):
	try:
		resp = opener.open(*args)
		if resp.getcode() != 200:
			raise RuntimeError("%s failed: %d" % (name, resp.getcode()))
		return resp
	except URLError as e:
		raise RuntimeError("%s failed: %s" % (name, e))

def search():
	'''Search using a reservation key (for users who don't have a booking yet)'''
	resp = send('Session request', args.url)
	# For some reason getting a cookie out of the CookieJar is overly complicated, so this uses the internal _cookies field
	xsrfToken = cookieJar._cookies['book.passkey.com']['/']['XSRF-TOKEN'].value

	data = {
		'_csrf': xsrfToken,
		'hotelId': '0',
		'blockMap.blocks[0].blockId': '0',
		'blockMap.blocks[0].checkIn': args.checkin,
		'blockMap.blocks[0].checkOut': args.checkout,
		'blockMap.blocks[0].numberOfGuests': str(args.guests),
		'blockMap.blocks[0].numberOfRooms': str(args.rooms),
		'blockMap.blocks[0].numberOfChildren': str(args.children),
	}
	return send('Search', baseUrl + '/rooms/select', urlencode(data).encode('utf8'))

def parseResults():
	resp = send('List', baseUrl + '/list/hotels')
	parser = PasskeyParser(resp)
	if not parser.json:
		raise RuntimeError("Failed to find search results")

	hotels = fromJS(parser.json)

	print("Results:   (%s)" % datetime.now())
	alerts = []

	print("   %-15s %-10s %-80s %s" % ('Distance', 'Price', 'Hotel', 'Room'))
	for hotel in hotels:
		for block in hotel['blocks']:
			# Don't show hotels miles away unless requested
			if hotel['distanceUnit'] == 3 and not args.show_all:
				continue

			connected = ('Skywalk to ICC' in (hotel['messageMap'] or ''))
			simpleHotel = {
				'name': parser.unescape(hotel['name']),
				'distance': 'Skywalk' if connected else "%4.1f %s" % (hotel['distanceFromEvent'], distanceUnits.get(hotel['distanceUnit'], '???')),
				'price': int(sum(inv['rate'] for inv in block['inventory'])),
				'rooms': min(inv['available'] for inv in block['inventory']),
				'room': parser.unescape(block['name']),
			}
			if simpleHotel['rooms'] == 0:
				continue
			result = "%-15s $%-9s %-80s (%d) %s" % (simpleHotel['distance'], simpleHotel['price'], simpleHotel['name'], simpleHotel['rooms'], simpleHotel['room'])
			# I don't think these distances (yards, meters, kilometers) actually appear in the results, but if they do assume it must be close enough regardless of --max-distance
			closeEnough = hotel['distanceUnit'] in (2, 4, 5) or \
			              (hotel['distanceUnit'] == 1 and (args.max_distance is None or (isinstance(args.max_distance, float) and hotel['distanceFromEvent'] <= args.max_distance))) or \
			              (args.max_distance == 'connected' and connected)
			cheapEnough = simpleHotel['price'] <= args.budget
			regexMatch = args.hotel_regex.search(simpleHotel['name']) and args.room_regex.search(simpleHotel['room'])
			if closeEnough and cheapEnough and regexMatch:
				alerts.append(simpleHotel)
				stdout.write(' ! ')
			else:
				stdout.write('   ')
			print(result)

	global lastAlerts
	if alerts:
		alertHash = {(alert['name'], alert['room']) for alert in alerts}
		if alertHash <= lastAlerts:
			print("Skipped alerts (no new rooms in nearby hotel list)")
		else:
			numHotels = len(set(alert['name'] for alert in alerts))
			preamble = "%d %s near the ICC:" % (numHotels, 'hotel' if numHotels == 1 else 'hotels')
			for fn in alertFns:
				# Run each alert on its own thread since some (e.g. popups) are blocking and some (e.g. e-mail) can throw
				Thread(target = fn, args = (preamble, alerts)).start()
			print("Triggered alerts")
	else:
		alertHash = set()

	print()
	lastAlerts = alertHash
	return True

while True:
	print("Searching... (%d %s, %d %s, %s - %s, %s)" % (args.guests, 'guest' if args.guests == 1 else 'guests', args.rooms, 'room' if args.rooms == 1 else 'rooms', args.checkin, args.checkout, 'connected' if args.max_distance == 'connected' else 'downtown' if args.max_distance is None else "within %.1f blocks" % args.max_distance))
	try:
		search()
		parseResults()
	except Exception as e:
		print(str(e))
	if args.once:
		exit(0)
	sleep(60 * args.delay)
