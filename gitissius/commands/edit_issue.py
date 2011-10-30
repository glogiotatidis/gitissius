import gitissius.commands as commands
import gitissius.common as common
import gitissius.common as common

class Command(commands.GitissiusCommand):
    """ Edit an issue """

    name="edit"
    aliases = ['e']
    help="Edit an issue"

    def _help(self):
        """
        Edit issue help
        """
        print "Edit issue help"

    def _execute(self, options, args):
        # find issue
        try:
            issue_id = args[0]

        except IndexError:
            self._help()

        issue = common.issue_manager.get(issue_id)

        # edit
        issue.interactive_edit()

        if not common.verify("Edit issue (y)? ", default='y'):
            print " >", "Issue discarded"
            return

        # add to repo
        common.git_repo[issue.path] = issue.serialize(indent=4)

        # commit
        common.git_repo.commit("Edited issue %s" % issue.get_property('id'))

        print "Edited issue: %s" % issue.get_property('id')
