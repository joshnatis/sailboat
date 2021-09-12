#---------------------------------------------------------------------------
# Author        : Josh Natis
# Description   : A command-line web browser!
# License       : MIT
#
# Setup         : pip3 install beautifulsoup4
#
# Usage         : python3 sailboat.py
#                 python3 sailboat.py [url]
#
# Dependencies  : python3, ncurses, BeautifulSoup4
#---------------------------------------------------------------------------

import os
import sys
import curses
import curses.ascii
import curses.textpad
import textwrap
import urllib.request
import http
from bs4 import BeautifulSoup
import bs4.element

class WebsiteContent():
	def __init__(self, html, success=True, errmsg=""):
		self.html = html
		self.success = success
		self.errmsg = errmsg

"""
API:
- search(query)     : returns the HTML content of a URL or file path
- parse(WebContent) : parses HTML string into intermediary format to be drawn
                      on the display.
"""
class Browser():
	_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"

	class HTMLMarkupLink():
		name = "link"
		def __init__(self, href, text, nestedObjects=None):
			self.href = href
			self.text = text
			self.nestedObjects = nestedObjects

	class HTMLMarkupImage():
		name = "image"
		def __init__(self, src, alt):
			self.src = src
			self.alt = alt

	class HTMLMarkupText():
		name = "text"
		def __init__(self, text, emphasized=False, underlined=False):
			self.text = text
			self.emphasized = emphasized
			self.underlined = underlined

	class HTMLMarkupError():
		name = "error"
		def __init__(self, errmsg):
			self.errmsg = errmsg

	class HTMLMarkupTitle():
		name = "title"
		def __init__(self, title):
			self.title = title

	def search(self, query):
		if self._is_path(query):
			return self._file_search(query)
		else:
			if "://" not in query:
				query = "http://" + query
			return self._web_search(query)

	def parse(self, content):
		if not content.success:
			return [self.HTMLMarkupError(content.errmsg)]

		soup = BeautifulSoup(content.html, "html.parser")

		if soup.body is None:
			text = soup.get_text()
			# no body but has content
			if len(text) != 0:
				if soup.html is not None:
					# parse html instead of body
					soup.body = soup.html
				else:
					# no html, no body, but has content??? do you my friend
					return self._parse_as_plaintext(text)
			else:
				return [self.HTMLMarkupError("Empty Page")]

		parsedContent = self._parse(soup.body)

		if soup.head.title is not None:
			title = self.HTMLMarkupTitle(soup.head.title.string)
			parsedContent.insert(0, title)

		if len(parsedContent) == 0:
			return [self.HTMLMarkupError("Empty Page")]

		return parsedContent

	def _parse_as_plaintext(self, text):
		text = filter(None, text.split("\n"))
		lines = []
		for line in text:
			lines.append(self.HTMLMarkupText(line.strip()))
		return lines

	def _parse(self, element):
		if isinstance(element, bs4.element.Comment):
			return []

		elif element.name in ['style', 'script', 'head', 'title', 'meta', '[document]']:
			return []

		elif isinstance(element, bs4.element.NavigableString):
			if element.isspace(): return []
			else: return [self.HTMLMarkupText(element)]

		elif element.name == "img":
			src = element.get("src")
			alt = element.get("alt")
			return [self.HTMLMarkupImage(src, alt)]

		elif element.name == "br":
			return [self.HTMLMarkupText("\n")]

		elif element.name == "a":
			href = element.get("href")
			text = element.string

			# nested elements in <a>
			if hasattr(element, "children"):
				try: child = next(element.children)
				except StopIteration: return []

				if type(child) == bs4.element.NavigableString:
					text = child
				else:
					content = []
					for child in element.children:
						content += self._parse(child)
					return [self.HTMLMarkupLink(href, None, content)]

			if text is None or text.isspace(): return []

			return [self.HTMLMarkupLink(href, text)]

		else:
			content = []
			for child in element.children:
				content += self._parse(child)
			return content

	def _web_search(self, url):
		req = urllib.request.Request(url, data = None,
 			headers = {"User-Agent" : self._USER_AGENT})

		try: html = urllib.request.urlopen(req).read().decode("utf-8")
		except (urllib.error.URLError, http.client.HTTPException, UnicodeDecodeError) as err:
			return WebsiteContent("", False, str(err))
		return WebsiteContent(html)

	def _file_search(self, path):
		if not os.path.exists(path) or \
		   not os.path.isfile(path) or \
		   not path.lower().endswith(".html"):
		   	return WebsiteContent("", False, \
		   	"'" + path + "' is not a valid path to an HTML file.")

		with open(path, "r") as f:
			html = f.read()
			return WebsiteContent(html)

	def _is_path(self, string):
		return string[0] == '~' or string[0] == '/' or string[0] == '.' or os.path.exists(string)

"""
API:
- Display()          : creates and displays windows (search bar and main window)
- get_search_query() : awaits and returns user's search query from search bar
- await_command()    : awaits and executes user's keyboard-key command
- draw(WebContent)   : draws website content onto the main window
"""
class Display():
	_current_content = None

	def __init__(self):
		self.screen = curses.initscr()

		self._check_screen_size()
		self._init_colors()

		curses.noecho()
		curses.cbreak()

		begin_x = 0; begin_y = 0
		width = curses.COLS

		# window 1 - search bar
		search_win_height = 3
		self.search_win = curses.newwin(1, width - 2, 1, 1)
		self.search_textbox = curses.textpad.Textbox(self.search_win)
		curses.textpad.rectangle(self.screen, 0, 0, 2, width - 1)

		# window 2 - website content
		begin_y += search_win_height
		content_win_height = curses.LINES - begin_y - 1
		self.content_win = curses.newwin(content_win_height, width, begin_y, begin_x)
		self.content_win.border()
		self.content_win.keypad(True)

		self.screen.addstr(curses.LINES - 1, 0, "[q]uit, [s]earch, [d]ownload")
		self._focus(self.search_win, 1)

		self._reset_page_coordinates()

		self.screen.refresh()
		self.search_win.refresh()
		self.content_win.refresh()

	def __del__(self):
		curses.echo()
		curses.nocbreak()
		self.screen.keypad(False)
		curses.endwin()

	def get_search_query(self):
		self._reset_page_coordinates()

		query = self.search_textbox.edit(validate=self._delete_is_backspace)
		return query.strip()

	def draw(self, content):
		win = self.content_win
		h, w = win.getmaxyx()

		self._current_content = content
		self._focus_content_win()

		h, w = win.getmaxyx()

		if content[0].name == "error":
			win.addstr(0, 1, "Error")
			win.addstr(1, 1, content[0].errmsg)
			return

		if content[0].name == "title":
			win.addstr(0, 1, content[0].title, curses.A_BOLD | curses.A_UNDERLINE)
			#content.pop(0)

		row = 1
		page = content[1:][self._current_line : self._current_line + self._max_lines]

		for element in page:
			try: row = self._draw(row, element)
			except curses.error: continue

	# things had to get more complicated because of nested elements in <a> tags
	def _draw(self, row, element, isLink=False):
		win = self.content_win
		h, w = win.getmaxyx()

		if element.name == "text":
			color = self._colors["link"] if isLink else self._colors["default"]

			if element.text == "\n":
				return row + 1

			lines = textwrap.wrap(element.text, w-2)
			for line in lines:
				if row >= self._max_lines:
					break
				win.addstr(row, 1, line, color)
				row += 1

			return row

		elif element.name == "image":
			color = self._colors["link"] if isLink else self._colors["image"]

			text = element.alt if element.alt is not None else element.src
			# WIP
			win.addstr(row, 1, "[IMAGE]", color | curses.A_STANDOUT)
			win.addstr(": " + text, color)

			return row + 1

		elif element.name == "link":
			color = self._colors["link"]

			text = element.text if element.text is not None else element.href
			#WIP
			win.addstr(row, 1, " " + text, color)

			row += 1

			if element.nestedObjects is not None:
				for nestedElement in element.nestedObjects:
					row = self._draw(row, nestedElement, isLink=True)
					row += 1

			return row

	def await_command(self):
		commands = [
			ord('q'),         # quit
			ord('s'),         # search
			#ord('d'),        # download current page
			curses.KEY_DOWN,  # scroll page down
			curses.KEY_UP,    # scroll page up
			#curses.KEY_LEFT, # focus previous link
			#curses.KEY_RIGHT # focus next link
		]

		finished = False

		key = ''
		while key not in commands:
			key = self.content_win.getch()

		if key == ord('q'):
			finished = True
		elif key == ord('s'):
			self._focus_search_win()
		elif key == ord('d'):
			pass
		elif key == curses.KEY_DOWN:
			DOWN = 1
			self._scroll(DOWN)
			self.await_command()
		elif key == curses.KEY_UP:
			UP = -1
			self._scroll(UP)
			self.await_command()
		elif key == curses.KEY_LEFT:
			pass
		elif key == curses.KEY_RIGHT:
			pass

		return finished

	def _focus_content_win(self):
		self.content_win.erase()
		self.content_win.attron(self._colors["focused"])
		self.content_win.border()
		self.content_win.attroff(self._colors["default"])

		self._focus(self.search_win, 0)

	def _focus_search_win(self):
		self.content_win.erase()
		self.content_win.border()
		self.content_win.refresh()

		self.search_win.erase()
		self._focus(self.search_win, 1)

	def _focus(self, win, command):
		if command == 0:
			win.bkgd(' ', self._colors["default"])
		elif command == 1:
			win.bkgd(' ', self._colors["focused"])
		win.refresh()

	# validator for curses.textpad.Textbox
	def _delete_is_backspace(self, c):
		if c == curses.ascii.DEL:
			c = curses.ascii.BS
		return c

	def _check_screen_size(self):
		# search bar: min height 3
		# content:    min height 3
		# controls:   min height 1, min width 30
		min_dims = (3 + 3 + 1, 30)
		screen_dims = self.screen.getmaxyx()
		if screen_dims[0] < min_dims[0] or screen_dims[1] < min_dims[1]:
			self.__del__()
			print("Make sure your terminal screen size is at least " \
				+ str(min_dims[1]) + "x" + str(min_dims[0]) + ".")
			exit(1)

	def _init_colors(self):
		curses.start_color()
		curses.init_pair(1, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
		curses.init_pair(2, curses.COLOR_WHITE,   curses.COLOR_BLACK)
		curses.init_pair(3, curses.COLOR_BLUE,    curses.COLOR_BLACK)
		curses.init_pair(4, curses.COLOR_RED,     curses.COLOR_BLACK)
		curses.init_pair(5, curses.COLOR_GREEN,   curses.COLOR_BLACK)
		curses.init_pair(6, curses.COLOR_CYAN,    curses.COLOR_BLACK)

		self._colors = {
			"focused":     curses.color_pair(1),
			"default":     curses.color_pair(2),
			"link":        curses.color_pair(3),
			"heading":     curses.color_pair(4),
			"image":       curses.color_pair(5),
			"active-link": curses.color_pair(6)
		}

	# WIP
	def _scroll(self, direction):
		UP = -1; DOWN = 1

		next_line = self._current_line + direction

		# normal scroll down
		if (next_line < self._bottom) and \
		   (self._top + next_line < self._bottom):
			self._current_line = next_line
		# overflow scroll down
		elif (next_line == self._bottom) and \
		     (self._top + self._max_lines < self._bottom):
			self._top += 1

		self.draw(self._current_content)

	def _reset_page_coordinates(self):
		self._top = 0
		self._bottom = self.content_win.getmaxyx()[0]
		self._max_lines = self._bottom - 2
		self._current_line = self._top

def help():
	sys.stderr.write("Usage: " + sys.argv[0] + " [url]\n")

def main():
	if len(sys.argv) > 2 or \
	   len(sys.argv) > 1 and \
	   (sys.argv[1] == "-h" or sys.argv[1] == "--help"):
		help()
		exit()

	browser = Browser()
	display = Display()

	def process(query):
		content = browser.search(query)
		parsedContent = browser.parse(content)
		display.draw(parsedContent)

		finished = display.await_command()
		return finished

	finished = False

	if len(sys.argv) == 2:
		query = sys.argv[1]
		finished = process(query)

	while not finished:
		query = display.get_search_query()
		if query == "": continue
		finished = process(query)

try: main()
except KeyboardInterrupt: pass

