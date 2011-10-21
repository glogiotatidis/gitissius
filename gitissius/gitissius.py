#!/usr/bin/env python
#
# Git-issues-ng
#
# Giorgos Logiotatidis <seadog@sealabs.net>
# http://www.github.com/glogiotatidis/gitissius
# http://www.gitissius.org
#
# Distributed bug tracking using git
#

import optparse
import os
import os.path
import shutil
import sys
import json
import readline
import hashlib
import string
from datetime import datetime

# needed for enabling / disabling colorama
ORIGINAL_STDOUT = sys.stdout
ORIGINAL_STDERR = sys.stderr

try:
    import colorama
    colorama.init(autoreset=True)
except ImportError:
    colorama = False

import gitshelve
import common
import commands

VERSION = "0.1.2"
readline.parse_and_bind('tab: complete')

def _disable_colorama(fn):
    # if colorama is present, pause it
    def _foo(*args, **kwargs):
        if colorama:
            sys.stdout = ORIGINAL_STDOUT

        fn(*args, **kwargs)

        if colorama:
            colorama.init(autoreset=True)

    return _foo


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
        return msg

class DbProperty(object):
    """
    Property Generic Object
    """

    def __init__(self, name, repr_name, value=None):
        """
        Generic Initialize
        """
        self.name = name
        self.repr_name = repr_name
        self.value = value
        self.editable = True

        # if colorama is presend set colors
        if colorama:
            self._color = {
                'repr_name': colorama.Fore.WHITE + colorama.Style.BRIGHT,
                'value': '',
                }

    def __str__(self):
        return self.value or ''

    def repr(self, attr):
        value = getattr(self, attr)

        if colorama:
            color = self._color.get(attr, None)
            if color:
                value = color + value + colorama.Style.RESET_ALL

        return value

    def printme(self):
        print "%s: %s" % (self.repr('repr_name'), self.repr('value'))

    def interactive_edit(self, default=None, completer=[]):
        """
        Generic Interactive Edit.

        Prompt user for input. Use default values. Validate Input
        """
        if not self.editable:
            return

        if not default:
            default = self.value

        readline.set_completer(common.SimpleCompleter(completer).complete)
        while True:
            value = raw_input("%s (%s): " % \
                              (self.repr_name, default)
                              )

            if not value:
                value = default

            self.value = value

            try:
                self.validate_value()
            except PropertyValidationError, error:
                print error
                continue
            else:
                break

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

    def repr(self, attr):
        value = getattr(self, attr)

        if attr == 'value':
            value = value.capitalize()

            if colorama:
                if self.value == 'bug':
                    value = colorama.Fore.YELLOW + value

                elif self.value == 'feature':
                    value = colorama.Fore.GREEN + value

                value += colorama.Style.RESET_ALL

        else:
            return super(TypeProperty, self).repr(attr)

        return value

    @_disable_colorama
    def interactive_edit(self, default=None):
        """
        Interactive edit.

        Prompt user for input. Provide shortcuts for states. If
        shortcut gets used, convert it to a proper value. Validate
        provided input.
        """
        readline.set_completer(common.SimpleCompleter(['bug', 'feature', 'help']).complete)

        if not default:
            default = self.value

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

            self.value = status.lower()

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
        if self.value.lower() in self.TYPE_STATES_SHORTCUTS:
            self.value = self.TYPE_STATES_SHORTCUTS[self.value]

        if self.value.lower() not in self.TYPE_STATES:
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

    def repr(self, attr):
        value = getattr(self, attr)

        if attr == 'value':
            value = value.capitalize()

            if colorama:
                if self.value == 'new':
                    value = colorama.Fore.YELLOW + value

                elif self.value == 'assigned':
                    value = colorama.Fore.GREEN + value

                elif self.value == 'invalid':
                    value = colorama.Fore.WHITE + value

                elif self.value == 'closed':
                    value = colorama.Fore.WHITE + value

                value += colorama.Style.RESET_ALL

        else:
            return super(StatusProperty, self).repr(attr)

        return value

    @_disable_colorama
    def interactive_edit(self, default=None):
        """
        Interactive edit.

        Prompt user for input. Provide shortcuts for states. If
        shortcut gets used, convert it to a proper value. Validate
        provided input.
        """
        readline.set_completer(
            common.SimpleCompleter(
                self.ISSUE_STATES + ["help"]
                ).complete
            )

        if not default:
            default = self.value

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

            self.value = status.lower()

            try:
                self.validate_value()

            except PropertyValidationError, error:
                print " >", error

            else:
                break

        return self.value

    def validate_value(self):
        """
        Validate status value based on ISSUE_STATES_SHORTCUTS and
        ISSUE_STATES.
        """
        if self.value.lower() in self.ISSUE_STATES_SHORTCUTS.keys():
            self.value = self.ISSUE_STATES_SHORTCUTS[self.value]

        if self.value.lower() not in self.ISSUE_STATES:
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
        print "%s:\n  %s" % (self.repr('repr_name'),
                             self.repr('value').replace('\n', '\n  ')
                             )

    @_disable_colorama
    def interactive_edit(self, default=None):
        if not default:
            default = self.value

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

    @_disable_colorama
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
                                                   value=common.current_user()
                                                   )

    @_disable_colorama
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

    @_disable_colorama
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

        self.editable = False

    @_disable_colorama
    def interactive_edit(self, default=None):
        """
        Interactive edit.

        Call interactive_edit from DbProperty by providing default
        the currect datetime.
        """
        if self.value:
            default = self.value

        else:
            default = common.now()
            self.value = default

        return super(CreatedOnProperty, self).interactive_edit(default=default)


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

        self.editable = False

    @_disable_colorama
    def interactive_edit(self, default=None):
        """
        Interactive edit.

        Call interactive_edit from DbProperty and always provide
        current date and time as default value.
        """
        self.value = common.now()

        return super(UpdatedOnProperty, self).\
               interactive_edit(default=common.now())

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
                self.get_property('id').value + str(common.now())
                ).hexdigest()

            try:
                git_repo[self.path]

            except KeyError:
                break

    def printme(self):
        for name in self._print_order:
            prop = self.get_property(name)
            prop.printme()

    def printmedict(self):
        """
        Return a dictionary with all properties after self.repr
        """
        dic = {}
        for prop in self._properties:
            dic[prop.name] = prop.repr('value')

        return dic

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
        for name in self._print_order:
            prop = self.get_property(name)
            prop.interactive_edit()

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
            if not '/comments/' in issue:
                # making sure that we don't treat comments as issues
                obj = Issue.load(json.loads(git_repo[issue]))
                self._issuedb[str(obj.get_property('id'))] = obj

    def update_db(self):
        self._build_issuedb()

    def all(self, sort_key=None):
        return self.filter(sort_key=sort_key)

    def filter(self, rules=None, operator="and", sort_key=None):
        assert isinstance(rules, list)

        matching_keys = self.issuedb.keys()
        not_maching_keys = []

        if rules:
            for rule in rules:
                name, value = rule.items()[0]
                # parse operators
                cmd = name.split("__")
                name = cmd[0]

                operators = [lambda x, y: x.lower() in y.lower()]

                if "exact" in cmd[1:]:
                    operators += [lambda x, y: x == y]

                if "startswith" in cmd[1:]:
                    operators += [lambda x, y: y.startswith(x)]

                for key in matching_keys:
                    try:
                        result = reduce(lambda x, y: x==y==True,
                                        map(lambda x: x(value,
                                                        self.issuedb[key].\
                                                        properties[name].value
                                                        ),
                                            operators
                                            )
                                        )

                        if "not" in cmd[1:]:
                            if result:
                                not_maching_keys.append(key)

                        else:
                            if not result:
                                not_maching_keys.append(key)

                    except KeyError:
                        print "Error searching"
                        return []

            map(lambda x: matching_keys.remove(x), not_maching_keys)
            issues = []
            for key in matching_keys:
                issues.append(self.issuedb[key])

        else:
            issues = [issue for issue in self.issuedb.values()]

        if sort_key:
            issues = self.order(issues, sort_key)

        return issues

    def order(self, issues, key):
        """
        Short issues by key
        """
        issues.sort(key=lambda x: x.get_property(key).value)
        return issues

    def get(self, issue_id):
        matching_keys = []

        for key in self.issuedb.keys():
            if key.startswith(issue_id):
                matching_keys.append(key)

        if len(matching_keys) == 0:
            raise IssueIDNotFound(issue_id)

        elif len(matching_keys) > 1:
            raise IssueIDConflict(map(lambda x: self.issuedb[x], matching_keys))

        return self._issuedb[matching_keys[0]]


def usage(available_commands):
    USAGE = "Gitissius v%s\n\n" % VERSION
    USAGE += "Available commands: \n"

    for cmd in commands.available_commands:
        _cmd = commands.command[cmd]
        USAGE += "\t{0:12}: {1} (Aliases: {2})\n".\
                 format(_cmd.name,
                        _cmd.help,
                        ', '.join(_cmd.aliases) or 'None')

    return USAGE

def main():
    try:
        command = sys.argv[1]

    except IndexError:
        # no command given
        print usage(commands.available_commands)
        sys.exit()

    if not 'gitissius' in gitshelve.git('branch'):
        # no local gitissius branch exists
        # check if there is a remote
        if 'remotes/origin/gitissius' in gitshelve.git('branch', '-a'):
            # remote branch exists
            # create a local copy
            gitshelve.git('branch', 'gitissius', 'origin/gitissius')

        else:
            # create an empty repo
            gitshelve.git('symbolic-ref', 'HEAD', 'refs/heads/gitissius')
            cwd = _common.find_repo_root()
            os.unlink(os.path.join(cwd, '.git', 'index'))
            gitshelve.git('clean', '-fdx')

    try:
        commands.command[command](sys.argv[2:])

    except KeyError:
        print " >", "Invalid command"
        print usage(commands.available_commands)

    except IssueIDConflict, error:
        print " >", "Error: Conflicting IDS"
        print error

    except IssueIDNotFound, error:
        print " >", "Error: ID not found", error

    git_repo.close()


# initialize gitshelve
git_repo = gitshelve.open(branch='gitissius')


# initialize issue manager
issue_manager = IssueManager()

if __name__ == '__main__':
    main()
