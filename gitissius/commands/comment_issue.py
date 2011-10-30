import sys

import gitissius.common as common
import gitissius.commands as commands

class Command(commands.GitissiusCommand):
    """ Comment on an issue """
    name = "comment"
    aliases = ["c"]
    help = "Comment an issue"

    def _help(self):
        print "Usage:"
        print "\t%s comment [issue_id]" % sys.argv[0]

    def _execute(self, options, args):
        from gitissius.database import Comment

        # find issue
        try:
            issue_id = args[0]

        except IndexError:
            self._help()
            return

        issue = common.issue_manager.get(issue_id)

        print "Commenting on:", issue.get_property('title').value

        # edit
        comment = Comment(issue_id=issue.get_property('id').value)
        comment.interactive_edit()

        # add to repo
        common.git_repo[comment.path] = comment.serialize(indent=4)

        # commit
        common.git_repo.commit("Added comment on issue %s" % issue.get_property('id'))

        print "Comment issue: %s" % issue.get_property('id')

