#
# Git-issues-ng
#
# Giorgos Logiotatidis <seadog@sealabs.net>
# http://www.github.com/glogiotatidis/gitissius
# http://www.gitissius.org
#
# Distributed bug tracking using git

import optparse
import os
import os.path
import shutil
import sys
import json
import readline
import hashlib
from datetime import datetime

import gitshelve

VERSION = "0.1"
readline.parse_and_bind('tab: complete')

git_repo = None
issue_manager = None

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

class PropertyValidationError(Exception):
    """
    Raised on IssuesProperty validation errors
    """
    pass

class IssueIDNotFound(Exception):
    pass

class IssueIDConflict(Exception):
    pass

class DbProperty(object):
    """
    Issue Property Generic Object
    """

    def __init__(self, name, repr_name, value=None):
        """
        Generic Initialize
        """
        self.name = name
        self.repr_name = repr_name
        self.value = value
        self.editable = True

    def __str__(self):
        return self.value or ''

    def printme(self):
        print "%s: %s" % (self.repr_name, self.value)

    def interactive_edit(self, default=None, completer=[]):
        """
        Generic Interactive Edit.

        Prompt user for input. Use default values. Validate Input
        """
        if not self.editable:
            return

        if not default:
            default = self.value

        readline.set_completer(SimpleCompleter(completer).complete)
        while True:
            value = raw_input("%s (%s): " % \
                              (self.repr_name, default)
                              )

            if not value:
                value = default

            self.value = value

            self.validate_value()

            return self.value

    def set_value(self, value):
        """
        Generic Set Value.

        Directly set a value. Validate Input
        """
        self.value = value
        self.validate_value()

        return self.value

    def validate_value(self):
        """
        Generic Validate Value.

        Always returns True. It should be overriden by properties that
        need real validation. When value does not validate, raise
        PropertyValidationError.
        """
        return True

    def serialize(self):
        """
        Generic Serialize.

        Return a python dictionary ready to be jsonized
        """
        return {'name': self.name,
                'value': unicode(self.value)
                }

class TypeProperty(DbProperty):
    """
    Type Property defines the type of issue (bug, feature)
    """
    TYPE_STATES = ['bug', 'feature']
    TYPE_STATES_SHORTCUTS = {
        'b':'bug',
        'f':'feature'
        }

    def __init__(self):
        """
        TypeProperty Initializer
        """
        super(TypeProperty, self).__init__(name="type",
                                           repr_name="Type",
                                           value="bug")

    def interactive_edit(self, default="bug"):
        """
        Interactive edit.

        Prompt user for input. Provide shortcuts for states. If
        shortcut gets used, convert it to a proper value. Validate
        provided input.
        """
        readline.set_completer(SimpleCompleter(['bug', 'feature', 'help']).complete)
        while True:
            status = raw_input('%s (%s) [b/f/h]: ' % \
                               (self.repr_name.capitalize(), default)
                               )

            if not status:
                status = default

            status = status.lower()

            if status == 'h' or status == 'help':
                # provide help
                self.help()
                continue

            self.value = status

            try:
                self.validate_value()

            except PropertyValidationError, error:
                print " >", error

            else:
                break

        return self.value

    def validate_value(self):
        """
        Validate status value based on TYPE_STATES
        """
        if self.value in self.TYPE_STATES_SHORTCUTS:
            self.value = self.TYPE_STATES_SHORTCUTS[self.value]

        if self.value not in self.TYPE_STATES:
            raise PropertyValidationError("Invalid type. Type 'help' for help.")

        return True

    def help(self):
        """ Type Help """
        print " > Type can have the following values: " + \
              ', '.join(self.TYPE_STATES)

class StatusProperty(DbProperty):
    """
    Status Property holds the status of an Issue
    """
    ISSUE_STATES = [ 'new', 'assigned', 'invalid', 'closed' ]
    ISSUE_STATES_SHORTCUTS = {
        'n':'new',
        'a':'assigned',
        'i':'invalid',
        'c':'closed'
        }

    def __init__(self):
        """
        StatusProperty Initializer
        """
        super(StatusProperty, self).__init__(name="status",
                                             repr_name="Status",
                                             value="New")

    def interactive_edit(self, default="new"):
        """
        Interactive edit.

        Prompt user for input. Provide shortcuts for states. If
        shortcut gets used, convert it to a proper value. Validate
        provided input.
        """
        readline.set_completer(
            SimpleCompleter(
                self.ISSUE_STATES + ["help"]
                ).complete
            )
        while True:
            status = raw_input('%s (%s) [n/a/i/c/h]: ' % \
                               (self.repr_name.capitalize(), default)
                               )

            if not status:
                status = default

            status = status.lower()

            if status == 'h' or status == 'help':
                # provide help
                self.help()
                continue

            self.value = status

            try:
                self.validate_value()

            except PropertyValidationError, error:
                print " >", error

            else:
                return self.value

    def validate_value(self):
        """
        Validate status value based on ISSUE_STATES_SHORTCUTS and
        ISSUE_STATES.
        """
        if self.value in self.ISSUE_STATES_SHORTCUTS.keys():
            self.value = self.ISSUE_STATES_SHORTCUTS[self.value]

        if self.value not in self.ISSUE_STATES:
            raise PropertyValidationError("Invalid Status. Type 'help' for help")

        return True

    def help(self):
        """ Status Help """
        print " > Status can have the following values: " + \
              ', '.join(self.ISSUE_STATES)

class DescriptionProperty(DbProperty):
    """
    DescriptionProperty to hold
    """
    def __init__(self, allow_empty=False):
        """
        DescriptionProperty Initializer
        """
        self.allow_empty = allow_empty
        super(DescriptionProperty, self).__init__(name="description",
                                                  repr_name="Description"
                                                  )

    def printme(self):
        print "%s:\n  %s" % (self.repr_name, self.value.replace('\n', '\n  '))

    def interactive_edit(self, default=''):
        while True:
            description = ''
            print "Description (End with a line containing only '.'): "

            self.old_description = self.value
            if self.value:
                print "Current: "
                print " " + self.value.replace('\n', '\n ')
                print '-' * 5

            while True:
                line = raw_input(" ")

                if line == '.':
                    break

                description += line + '\n'

            self.value = description.strip()
            if not self.value and self.old_description:
                self.value = self.old_description

            try:
                self.validate_value()

            except PropertyValidationError, error:
                print " >", error
                continue

            else:
                return self.value

    def validate_value(self):
        if self.value == '' and not self.allow_empty:
            raise PropertyValidationError("Sorry description cannot be empty")

        return True

class IdProperty(DbProperty):
    """
    IdProperty to hold issue id
    """
    def __init__(self, name="id", repr_name="ID"):
        """
        IdProperty Initializer
        """
        super(IdProperty, self).__init__(name=name,
                                         repr_name=repr_name
                                         )
        self.editable = False

class AssignedToProperty(DbProperty):
    """
    AssignedToProperty stores details for the person assigned to the
    issue
    """
    def __init__(self):
        """
        AssignedToProperty Initializer
        """
        super(AssignedToProperty, self).__init__(name="assigned_to",
                                                 repr_name="Assigned To"
                                                 )

    def interactive_edit(self, default=None):
        super(AssignedToProperty, self).\
                                  interactive_edit(default,
                                                   completer=_get_commiters()
                                                   )

class ReportedFromProperty(DbProperty):
    """
    ReportedFromProperty stores details for the person who reported
    the issue
    """
    def __init__(self):
        """
        ReportedFromProperty Initializer
        """
        super(ReportedFromProperty, self).__init__(name="reported_from",
                                                   repr_name="Reported From",
                                                   value=_current_user()
                                                   )

    def interactive_edit(self, default=None):
        super(ReportedFromProperty, self).\
                                    interactive_edit(default=default,
                                                     completer=_get_commiters())
        readline.set_completer(None)


class TitleProperty(DbProperty):
    """
    TitleProperty stores the issue title
    """
    def __init__(self):
        """
        TitleProperty Initializer
        """
        super(TitleProperty, self).__init__(name="title",
                                            repr_name="Title"
                                            )

    def interactive_edit(self, default=None):
        if not default:
            default = self.value

        while True:
            try:
                super(TitleProperty, self).interactive_edit(default)

            except PropertyValidationError, error:
                print " >", error
                continue

            else:
                return self.value

    def validate_value(self):
        if self.value == None or len(self.value) == 0:
            raise PropertyValidationError("Title cannot be empty")

class CreatedOnProperty(DbProperty):
    """
    Stores the date and time the issue was first created
    """
    def __init__(self):
        """
        CreatedOnProperty Initializer
        """
        super(CreatedOnProperty, self).__init__(name="created_on",
                                                repr_name="Created On",
                                                )

    def interactive_edit(self, default=None):
        """
        Interactive edit.

        Call interactive_edit from DbProperty by providing default
        the currect datetime.
        """
        if self.value:
            default = self.value

        else:
            default = _now()

        return super(CreatedOnProperty, self).interactive_edit(default)


class UpdatedOnProperty(DbProperty):
    """
    Stores the last update date and time of the issue
    """
    def __init__(self):
        """
        UpdatedOnProperty Initializer
        """
        super(UpdatedOnProperty, self).__init__(name="updated_on",
                                                repr_name="Updated On",
                                                )

    def interactive_edit(self, default=None):
        """
        Interactive edit.

        Call interactive_edit from DbProperty and always provide
        current date and time as default value.
        """
        return super(UpdatedOnProperty, self).\
               interactive_edit(default=_now())

class DbObject(object):
    """
    Issue Object. The Mother of All
    """
    def __init__(self, *args, **kwargs):
        """
        Issue Initializer
        """
        self._properties += [IdProperty()]

        for item in self._properties:
            if item.name in kwargs.keys():
                item.set_value(kwargs[item.name])

        if not self.get_property('id').value:
            self._gen_id()

        # random print order. override in children
        self._print_order = []
        for item in self._properties:
            self._print_order.append(item.name)

    def _gen_id(self):
        # generate id
        self.get_property('id').value = ''
        while True:
            self.get_property('id').value = hashlib.sha256(
                self.get_property('id').value + str(_now())
                ).hexdigest()

            try:
                git_repo[self.path]

            except KeyError:
                break

    def printme(self):
        for name in self._print_order:
            prop = self.get_property(name)
            prop.printme()

    @property
    def path(self):
        assert False

    def get_property(self, name):
        for prop in self._properties:
            if prop.name == name:
                return prop

        raise Exception("Property not found")

    def interactive_edit(self):
        """
        Interactive edit of issue properties.
        """
        for item in self._properties:
            item.interactive_edit()

    def serialize(self, indent=0):
        """
        Return a json string containing all issue information
        """
        data = {}
        for item in self._properties:
            item_data = item.serialize()
            data[item_data['name']] = item_data['value']

        return json.dumps(data, indent=indent)

    @property
    def properties(self):
        data = {}
        for item in self._properties:
            data[item.name] = item

        return data

    def __str__(self):
        return self.get_property('title')

class Issue(DbObject):
    def __init__(self, *args, **kwargs):
        self._properties =  [TitleProperty(), StatusProperty(), TypeProperty(),
                             AssignedToProperty(), UpdatedOnProperty(),
                             ReportedFromProperty(), CreatedOnProperty(),
                             DescriptionProperty(),
                             ]

        self._comments = []
        super(Issue, self).__init__(*args, **kwargs)

        self._print_order = ['id', 'title', 'type', 'reported_from', 'assigned_to',
                             'created_on', 'updated_on', 'status', 'description'
                             ]

    @property
    def path(self):
        id = self.get_property('id')
        return "{id!s}/issue".format(**{'id':id})


    @property
    def comments(self):
        if not self._comments:
            self._build_commentsdb()

        return self._comments

    def _build_commentsdb(self):
        id = self.get_property('id')
        comment_path = "{id}/comments/".format(**{'id':id})
        for item in git_repo.keys():
            if item.startswith(comment_path):
                obj = Comment.load(json.loads(git_repo[item]))
                self._comments.append(obj)

        self._comments.sort(key=lambda x: x.get_property('created_on').value)

        return self._comments

    @classmethod
    def load(cls, data):
        return Issue(**data)

class Comment(DbObject):
    def __init__(self, *args, **kwargs):
        self._properties = [ReportedFromProperty(),
                            IdProperty(name="issue_id", repr_name="Issue ID"),
                            CreatedOnProperty(), DescriptionProperty(),
                            ]

        super(Comment, self).__init__(*args, **kwargs)

        self._print_order = ['reported_from', 'created_on', 'description']

    @property
    def path(self):
        issue_id = self.get_property('issue_id')
        return "{issueid!s}/comments/{commentid!s}".\
               format(**{'issueid': issue_id,
                         'commentid': self.get_property('id')
                         })

    @classmethod
    def load(cls, data):
        return Comment(**data)

class IssueManager(object):
    """
    Issue manager object
    """
    def __init__(self):
        self._issuedb = None

    @property
    def issuedb(self):
        if not self._issuedb:
            self._build_issuedb()

        return self._issuedb

    def _build_issuedb(self):
        self._issuedb = {}

        for issue in git_repo.keys():
            obj = Issue.load(json.loads(git_repo[issue]))
            self._issuedb[str(obj.get_property('id'))] = obj

    def update_db(self):
        self._build_issuedb()

    def all(self):
        return self.issuedb

    def filter(self, rules, operator="and"):
        matching_keys = self.issuedb.keys()
        not_maching_keys = []

        for name, value in rules.iteritems():
            value = value.lower()

            for key in matching_keys:
                try:
                    if value not in self.issuedb[key].properties[name].value.lower():
                        not_maching_keys.append(key)
                except KeyError:
                    print "Error searching"
                    return []

        map(lambda x: matching_keys.remove(x), not_maching_keys)
        issues = {}
        for key in matching_keys:
            issues[key] = self.issuedb[key]

        return issues

    def get(self, issue_id):
        matching_keys = []

        for key in self.issuedb.keys():
            if key.startswith(issue_id):
                matching_keys.append(key)

        if len(matching_keys) == 0:
            raise IssueIDNotFound()

        elif len(matching_keys) > 1:
            raise IssueIDConflict()

        return self._issuedb[matching_keys[0]]


class GitissiusCommand(object):
    """
    Gitissius Generic Command Object
    """
    def __init__(self, name, repr_name, help):
        self.name = name
        self.repr_name = repr_name
        self.help = help

    def __call__(self):
        assert False

class NewIssueCommand(GitissiusCommand):
    """ Create new issue """
    def __init__(self):
        super(NewIssueCommand, self).__init__(name="new",
                                              repr_name="New Issue",
                                              help="Create an issue"
                                              )
    def __call__(self, args, options):
        try:
            title = args[0]
            issue = Issue(title=title)

        except IndexError:
            issue = Issue()

        # edit
        issue.interactive_edit()

        # add to repo
        git_repo[issue.path] = issue.serialize(indent=4)

        # commit
        git_repo.commit("Added issue %s" % issue.get_property('id'))

        print "Created issue: %s" % issue.get_property('id')

class ShowIssueCommand(GitissiusCommand):
    """ Show an issue """

    def __init__(self):
        super(ShowIssueCommand, self).__init__(name="show",
                                               repr_name="Show Issue",
                                               help="Show an issue"
                                               )
    def help():
        print "Usage:"
        print "\t%s show [issue_id]" % sys.argv[0]

    def __call__(self, args, options):
        # find issue
        try:
            issue_id = args[0]

        except IndexError:
            self.help()
            return

        issue = issue_manager.get(issue_id)

        # show
        issue.printme()

        # if full show comments as well
        try:
            if args[1] == "full":
                print '-' * 5
                for comment in issue.comments:
                    comment.printme()

                    print '-' * 5

        except IndexError:
            pass

class CommentIssueCommand(GitissiusCommand):
    """ Comment on an issue """

    def __init__(self):
        super(CommentIssueCommand, self).__init__(name="comment",
                                                  repr_name="Add Comment",
                                                  help="Comment an issue"
                                                  )

    def help(self):
        print "Usage:"
        print "\t%s comment [issue_id]" % sys.argv[0]

    def __call__(self, args, options):
        # find issue
        try:
            issue_id = args[0]
        except IndexError:
            self.help()

        issue = issue_manager.get(issue_id)

        # edit
        comment = Comment(issue_id=issue_id)
        comment.interactive_edit()

        # add to repo
        git_repo[comment.path] = comment.serialize(indent=4)

        # commit
        git_repo.commit("Added comment on issue %s" % issue.get_property('id'))


class SearchCommand(GitissiusCommand):
    """ Search issues """

    def __init__(self):
        super(SearchCommand, self).__init__(name="search",
                                            repr_name="Search",
                                            help="Search issues"
                                            )

    def __call__(self, args, options):
        print "Not implemented yet"

class ShowMyIssuesCommand(GitissiusCommand):
    """
    Show only my issues.
    Helper function to list_issues
    """
    def __init__(self):
        super(ShowMyIssuesCommand, self).__init__(name="myissues",
                                                  repr_name="My Issues",
                                                  help="Show issues assigned to you"
                                                  )

    def __call__(self, args, options):
        user_email = gitshelve.git('config', 'user.email')

        issues = issue_manager.filter(rules={'assigned_to': user_email},
                                      operator="and",
                                      )

        _print_issues(issues)

class EditIssueCommand(GitissiusCommand):
    """ Edit an issue """

    def __init__(self):
        super(EditIssueCommand, self).__init__(name="edit",
                                               repr_name="Edit Issue",
                                               help="Edit an issue"
                                               )
    def help(self):
        """
        Edit issue help
        """
        print "Edit issue help"

    def __call__(self, args, options):
        # find issue
        try:
            issue_id = args[0]

        except IndexError:
            self.help()

        issue = issue_manager.get(issue_id)

        # edit
        issue.interactive_edit()

        # add to repo
        git_repo[issue.path] = issue.serialize(indent=4)

        # commit
        git_repo.commit("Edited issue %s" % issue.get_property('id'))

        print "Edited issue: %s" % issue.get_property('id')

class ShellCommand(GitissiusCommand):
    """
    Interactive shell
    """
    def __init__(self):
        super(ShellCommand, self).__init__(name="shell",
                                           repr_name="Shell",
                                           help="Open a gitissius shell"
                                           )

    def __call__(self, args, options):
        print "Not implemented yet."

class ListIssuesCommand(GitissiusCommand):
    """
    List Issues
    """
    def __init__(self):
        super(ListIssuesCommand, self).__init__(name="list",
                                                repr_name="List",
                                                help="List issues"
                                                )

    def __call__(self, args, options):
        _print_issues(issue_manager.all())

class InitCommand(GitissiusCommand):
    """ Initiailize repo to use git-issues """

    def __init__(self):
        super(InitCommand, self).__init__(name="init",
                                          repr_name="Init",
                                          help="Init Gitissius"
                                          )

    def __call__(self, args, options):
        cwd = os.getcwd()

        while not os.path.exists(os.path.join(cwd, ".git")):
            cwd, extra = os.path.split(cwd)

            if not extra:
                print "Unable to find a git repository. "
                print "Make sure you ran `git init` at some point."
                return 1

        mydir = os.path.join(cwd, ".gitissius")

        if os.path.exists(mydir):
            print "git-issius helper directory %s already exists." % mydir
            print "Doing nothing."
            return 1

        os.makedirs(mydir)

        for fle in map(lambda x: os.path.join(os.path.dirname(__file__), x),
                       [__file__, 'gitshelve.py', 'README', 'LICENSE']
                       ):
            shutil.copy(fle, mydir)

        return 0

def _print_issues(issues):
    """ List issues """

    twidth = _terminal_width()

    # 40% for title
    title_size = int(twidth * .4)
    status_size = 6
    id_size = 5
    assigned_to_size = twidth - title_size - status_size - id_size - 10

    fmt = "{id:%s.%ss} | {title:%s.%ss} | {assigned_to:%s.%ss} | {status:%s.%ss} " % \
          (id_size, id_size, title_size,
           title_size, assigned_to_size, assigned_to_size,
           status_size, status_size)


    print fmt.format(**{'id':'ID',
                        'title':'Title',
                        'status':'Status',
                        'assigned_to':'Assigned To'
                        }
                     )
    print '-' * _terminal_width()

    for id, issue in issues.iteritems():
        print fmt.format(**issue.properties)

def _current_user():
    return "%s <%s>" % (gitshelve.git('config', 'user.name'),
                        gitshelve.git('config', 'user.email')
                        )

def _get_commiters():
    """
    Return a set() of strings containing commiters of the repo
    """
    commiters = gitshelve.git('log', '--pretty=format:"%an <%ae>"')
    commiters = set(commiters.split('"'))
    commiters.remove('')
    commiters.remove('\n')
    return commiters

def _terminal_width():
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

def _now():
    n = datetime.utcnow()
    return datetime(year=n.year, month=n.month, day=n.day,
                    hour=n.hour, minute=n.minute, second=n.second)

def usage(available_commands):
    USAGE = "\nGitissius v%s\n" % VERSION
    USAGE += "Available commands: \n"

    for cmd in available_commands.values():
        USAGE += "\t{0:12}: {1}\n".format(cmd.name, cmd.help)

    return USAGE

def main():
    global git_repo, issue_manager

    available_commands = {
        'new': NewIssueCommand(),
        'list': ListIssuesCommand(),
        'init': InitCommand(),
        'show': ShowIssueCommand(),
        'myissues': ShowMyIssuesCommand(),
        'search_issues': SearchCommand(),
        'edit': EditIssueCommand(),
        'shell': ShellCommand(),
        'comment': CommentIssueCommand(),
        }

    parser = optparse.OptionParser(usage=usage(available_commands))

    (options, args) = parser.parse_args()

    try:
        command = args[0]

    except IndexError:
        # no command given
        parser.print_help()
        sys.exit()

    # initialize gitshelve
    git_repo = gitshelve.open(branch='gitissius')

    # initialize issue manager
    issue_manager = IssueManager()

    try:
        available_commands[command](args[1:], options)

    except KeyError:
        print "Invalid command"
        parser.print_help()
        raise

    git_repo.close()

if __name__ == '__main__':
    main()
