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

VERSION = "0.1"
readline.parse_and_bind('tab: complete')

git_repo = None
issue_manager = None

def _disable_colorama(fn):
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
                value = color + value + colorama.Fore.RESET

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

        readline.set_completer(SimpleCompleter(completer).complete)
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
        readline.set_completer(SimpleCompleter(['bug', 'feature', 'help']).complete)

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
            SimpleCompleter(
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
                                                   value=_current_user()
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

        self.editable = False

    @_disable_colorama
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

class GitissiusCommand(object):
    """
    Gitissius Generic Command Object
    """
    def __init__(self, name, repr_name, help):
        self.name = name
        self.repr_name = repr_name
        self.help = help
        self.parser = optparse.OptionParser()

    def __call__(self, args):
        (options, args) = self.parser.parse_args(args)
        return self._execute(options, args)

    def _execute(self, options, args):
        assert False

class NewIssueCommand(GitissiusCommand):
    """ Create new issue """
    def __init__(self):
        super(NewIssueCommand, self).__init__(name="new",
                                              repr_name="New Issue",
                                              help="Create an issue"
                                              )
    def _execute(self, options, args):
        try:
            title = args[0]
            issue = Issue(title=title)

        except IndexError:
            issue = Issue()

        # edit
        issue.interactive_edit()

        if not _verify("Create issue (y)? ", default='y'):
            print " >", "Issue discarded"
            return

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
        self.parser.add_option("--all",
                               action="store_true",
                               default=False,
                               help="Show all details, including comments"
                               )

    def help():
        print "Usage:"
        print "\t%s show [issue_id]" % sys.argv[0]

    def _execute(self, options, args):
        # find issue
        try:
            issue_id = args[0]

        except IndexError:
            self.help()
            return

        issue = issue_manager.get(issue_id)

        # show
        issue.printme()

        if options.all:
            print '-' * 5
            for comment in issue.comments:
                comment.printme()

                print '-' * 5

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

    def _execute(self, options, args):
        # find issue
        try:
            issue_id = args[0]
        except IndexError:
            self.help()

        issue = issue_manager.get(issue_id)

        # edit
        comment = Comment(issue_id=issue.get_property('id').value)
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

    def _execute(self, options, args):
        print "Not implemented yet"

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

    def _execute(self, options, args):
        # find issue
        try:
            issue_id = args[0]

        except IndexError:
            self.help()

        issue = issue_manager.get(issue_id)

        # edit
        issue.interactive_edit()

        if not _verify("Edit issue (y)? ", default='y'):
            print " >", "Issue discarded"
            return

        # add to repo
        git_repo[issue.path] = issue.serialize(indent=4)

        # commit
        git_repo.commit("Edited issue %s" % issue.get_property('id'))

        print "Edited issue: %s" % issue.get_property('id')

class PushCommand(GitissiusCommand):
    """
    Push issues to repo
    """
    def __init__(self):
        super(PushCommand, self).__init__(name="push",
                                          repr_name="Push",
                                          help="Push issues to origin master"
                                          )

    def _execute(self, options, args):
        gitshelve.git('push', 'origin', 'gitissius')

class PullCommand(GitissiusCommand):
    """
    Pull issues to repo
    """
    def __init__(self):
        super(PullCommand, self).__init__(name="pull",
                                          repr_name="Pull",
                                          help="Pull issues to origin master"
                                          )

    def _execute(self, options, args):
        # save current branch name
        branch = gitshelve.git('name-rev', '--name-only', 'HEAD') or 'master'

        # stash changes
        try:
            gitshelve.git('stash')

        except gitshelve.GitError, error:
            if 'You do not have the initial commit yet' in error.stderr:
                # don't worry, we just created 'gitissius' branch
                pass

            else:
                raise

        else:
            # switch branches
            gitshelve.git('checkout', 'gitissius')

        # pull updates
        gitshelve.git('pull', 'origin', 'gitissius')

        # switch back to previous branch
        gitshelve.git('checkout', branch)

        # pop stashed changes
        try:
            gitshelve.git('stash', 'pop')

        except gitshelve.GitError, error:
            # no worries, no stash to apply
            pass

class ShellCommand(GitissiusCommand):
    """
    Interactive shell
    """
    def __init__(self):
        super(ShellCommand, self).__init__(name="shell",
                                           repr_name="Shell",
                                           help="Open a gitissius shell"
                                           )

    def _execute(self, options, args):
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
        self.parser = optparse.OptionParser()
        self.parser.add_option("--sort",
                               help="Sort results using key")
        self.parser.add_option("--filter",
                               default=None,
                               help="Filter result using key")
        self.parser.add_option("--all",
                               default=False,
                               action="store_true",
                               help="List all issues, " \
                               "including closed and invalid"
                               )

    def _execute(self, options, args):
        if options.all:
            filters = []

        else:
            # default filters, to filter out invalid and closed issues
            filters = [{'status__not':'closed'}, {'status__not':'invalid'}]

        if options.filter:
            for fltr in options.filter.split(","):
                key, value = fltr.split(':')
                filters.append({key:value})

        _print_issues(issue_manager.filter(sort_key=options.sort, rules=filters))

class ListMyIssuesCommand(GitissiusCommand):
    """
    List MyIssues
    """
    def __init__(self):
        super(ListMyIssuesCommand, self).__init__(name="myissues",
                                                  repr_name="My Issues",
                                                  help="Show issues assigned to you"
                                                  )

        self.parser = optparse.OptionParser()
        self.parser.add_option("--sort",
                               help="Sort results using key")
        self.parser.add_option("--all",
                               action="store_true",
                               default=False,
                               help="Show all my issues, " \
                               "including closed and invalid"
                               )

    def _execute(self, options, args):
        user_email = gitshelve.git('config', 'user.email')

        if options.all:
            rules = [{'assigned_to': user_email}]

        else:
            rules = [{'assigned_to': user_email},
                     {'status__not': 'closed'},
                     {'status__not': 'invalid'}
                     ]

        issues = issue_manager.filter(rules=rules,
                                      operator="and",
                                      sort_key=options.sort
                                      )
        _print_issues(issues)

class CloseIssueCommand(GitissiusCommand):
    """
    Close Issue
    """
    def __init__(self):
        super(CloseIssueCommand, self).__init__(name="close",
                                                repr_name="Close",
                                                help="Close an issue"
                                                )

    def _execute(self, options, args):
        # find issue
        try:
            issue_id = args[0]

        except IndexError:
            self.help()

        issue = issue_manager.get(issue_id)

        # close issue
        if issue.get_property('status').value == 'closed':
            print " >", "Issue already closed"
            return

        issue.get_property('status').value = 'closed'
        issue.get_property('updated_on').value = _now()

        # add to repo
        git_repo[issue.path] = issue.serialize(indent=4)

        # commit
        git_repo.commit("Closed issue %s" % issue.get_property('id'))

        print "Closed issue: %s" % issue.get_property('id')

class InstallCommand(GitissiusCommand):
    """ Initiailize repo to use git-issues """

    def __init__(self):
        super(InstallCommand, self).__init__(name="install",
                                             repr_name="Install",
                                             help="Install Gitissius "\
                                             "in current repositoy"
                                             )

    def _execute(self, options, args):
        cwd = _find_repo_root()
        mydir = os.path.join(cwd, ".gitissius")

        if os.path.exists(mydir):
            print "git-issius helper directory %s already exists." % mydir
            print "Doing nothing."
            return 1

        os.makedirs(mydir)

        for fle in map(lambda x: os.path.join(os.path.dirname(__file__), x),
                       ['gitissius.py', 'gitshelve.py', 'README', 'LICENSE']
                       ):
            shutil.copy(fle, mydir)

        return 0

def _print_issues(issues):
    """ List issues """

    twidth = _terminal_width()

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

    print '-' * _terminal_width()
    for issue in issues:
        print fmt.format(**issue.printmedict())

    print '-' * _terminal_width()
    print "Total Issues: %d" % len(issues)

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

def _verify(text, default=None):
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

def _find_repo_root():
    cwd = os.getcwd()

    while not os.path.exists(os.path.join(cwd, ".git")):
        cwd, extra = os.path.split(cwd)

        if not extra:
            raise Exception("Unable to find a git repository. ")

    return cwd


def usage(available_commands):
    USAGE = "Gitissius v%s\n\n" % VERSION
    USAGE += "Available commands: \n"

    for cmd in available_commands.values():
        USAGE += "\t{0:12}: {1}\n".format(cmd.name, cmd.help)

    return USAGE

def main():
    global git_repo, issue_manager

    available_commands = {
        'new': NewIssueCommand(),
        'list': ListIssuesCommand(),
        'install': InstallCommand(),
        'show': ShowIssueCommand(),
        'myissues': ListMyIssuesCommand(),
        'mylist': ListMyIssuesCommand(),
        'search_issues': SearchCommand(),
        'edit': EditIssueCommand(),
        'shell': ShellCommand(),
        'comment': CommentIssueCommand(),
        'push': PushCommand(),
        'pull': PullCommand(),
        'close': CloseIssueCommand(),
        }

    try:
        command = sys.argv[1]

    except IndexError:
        # no command given
        print usage(available_commands)
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
            cwd = _find_repo_root()
            os.unlink(os.path.join(cwd, '.git', 'index'))
            gitshelve.git('clean', '-fdx')

    # initialize gitshelve
    git_repo = gitshelve.open(branch='gitissius')

    # initialize issue manager
    issue_manager = IssueManager()

    try:
        available_commands[command](sys.argv[2:])

    except KeyError:
        print " >", "Invalid command"
        print usage(available_commands)

    except IssueIDConflict, error:
        print " >", "Error: Conflicting IDS"
        print error

    except IssueIDNotFound, error:
        print " >", "Error: ID not found", error

    git_repo.close()

if __name__ == '__main__':
    main()
