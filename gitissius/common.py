from datetime import datetime
import sys
import readline

readline.parse_and_bind('tab: complete')

# needed for enabling / disabling colorama
ORIGINAL_STDOUT = sys.stdout
ORIGINAL_STDERR = sys.stderr

try:
    import colorama
    colorama.init(autoreset=True)
except ImportError:
    colorama = False


def disable_colorama(fn):
    # if colorama is present, pause it

    def _foo(*args, **kwargs):
        if colorama:
            sys.stdout = ORIGINAL_STDOUT

        fn(*args, **kwargs)

        if colorama:
            colorama.init(autoreset=True)

    return _foo

class SimpleCompleter(object):
    """
    Completer to be used with readline to complete field values.

    from http://blog.doughellmann.com/2008/11/pymotw-readline.html
    """
    def __init__(self, options):
        self.options = sorted(options)

    def complete(self, text, state):
        response = None
        text = text.lower()
        if state == 0:
            # This is the first time for this text, so build a match list.
            if text:
                print "f"
                self.matches = [s
                                for s in self.options
                                if s and text in s.lower()]

            else:
                self.matches = self.options[:]

        # Return the state'th item from the match list,
        # if we have that many.
        try:
            response = self.matches[state]

        except IndexError:
            response = None

        return response

def now():
    n = datetime.utcnow()
    return datetime(year=n.year, month=n.month, day=n.day,
                    hour=n.hour, minute=n.minute, second=n.second)

def find_repo_root():
    cwd = os.getcwd()

    while not os.path.exists(os.path.join(cwd, ".git")):
        cwd, extra = os.path.split(cwd)

        if not extra:
            raise Exception("Unable to find a git repository. ")

    return cwd

def terminal_width():
    """Return terminal width."""
    width = 0
    try:
        import struct, fcntl, termios
        s = struct.pack('HHHH', 0, 0, 0, 0)
        x = fcntl.ioctl(1, termios.TIOCGWINSZ, s)
        width = struct.unpack('HHHH', x)[1]

    except:
        pass

    if width <= 0:
        if os.environ.has_key("COLUMNS"):
            width = int(os.getenv("COLUMNS"))

        if width <= 0:
            width = 80

    return width

def verify(text, default=None):
    while True:
        reply = raw_input(text)
        reply = reply.strip().lower()

        if default and reply == '':
            reply = 'y'

        if reply in ['y', 'n', 'yes', 'no']:
            break

        print "Please answer '(y)es' no '(n)o'"

    if reply in ['y', 'yes']:
        return True

    else:
        return False

def current_user():
    return "%s <%s>" % (gitshelve.git('config', 'user.name'),
                        gitshelve.git('config', 'user.email')
                        )

def get_commiters():
    """
    Return a set() of strings containing commiters of the repo
    """
    commiters = gitshelve.git('log', '--pretty=format:"%an <%ae>"')
    commiters = set(commiters.split('"'))
    try:
        commiters.remove('')

    except KeyError:
        # no '', it's ok
        pass
    try:
        commiters.remove('\n')

    except KeyError:
        # no '\n', it's ok
        pass

    return commiters

def print_issues(issues):
    """ List issues """

    twidth = terminal_width()

    # 40% for title
    title_size = int(twidth * .4)
    status_size = 8 if not colorama else 17
    id_size = 5
    type_size = 7 if not colorama else 16
    assigned_to_size = twidth - title_size - id_size - status_size - type_size
    assigned_to_size -= 13 if not colorama else -5

    fmt = "{id:%s.%ss} | {title:%s.%ss} | {assigned_to:%s.%ss} | {type:%s.%ss} | {status:%s.%ss} " % \
          (id_size, id_size,
           title_size, title_size,
           assigned_to_size, assigned_to_size,
           type_size, type_size,
           status_size, status_size)


    # fields to be printed
    table_fields = {'id': 'ID',
                    'title':'Title',
                    'status':'Status',
                    'type':'Type',
                    'assigned_to':'Assigned To'
                    }

    if colorama:
        for key in ['type', 'status']:
            table_fields[key] = colorama.Fore.RESET + table_fields[key] +\
                                colorama.Style.RESET_ALL

    print fmt.format(**table_fields)

    print '-' * terminal_width()
    for issue in issues:
        print fmt.format(**issue.printmedict())

    print '-' * terminal_width()
    print "Total Issues: %d" % len(issues)


class InvalidCommand(Exception):
    def __init__(self, command):
        self.command = command
        return super(UnknownCommand, self).__init__()

class PropertyValidationError(Exception):
    """
    Raised on IssuesProperty validation errors
    """
    pass

class IssueIDNotFound(Exception):
    pass

class IssueIDConflict(Exception):
    def __init__(self, issues):
        self.issues = issues
        self._threshold = self._calculate_threshold()

        return super(IssueIDConflict, self).__init__()

    def _calculate_threshold(self):
        first = self.issues[0].get_property('id').value
        second = self.issues[1].get_property('id').value

        for i in range(len(first)):
            if first[i] != second[i]:
                break

        return i

    def __str__(self):
        msg = ''
        for issue in self.issues:
            msg += "[%s]%s: %s\n" %\
                   (issue.get_property('id').value[:self._threshold],
                    issue.get_property('id').value[self._threshold:],
                    issue.get_property('title')
                    )

        return msg.strip()

import gitshelve
import database

# initialize gitshelve
git_repo = gitshelve.open(branch='gitissius')

# initialize issue manager
issue_manager = database.IssueManager()

