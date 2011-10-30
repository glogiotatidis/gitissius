import gitissius.commands as commands
import gitissius.common as common
import sys

class Command(commands.GitissiusCommand):
    """ Show an issue """
    name = "show"
    aliases = ["s"]
    help="Show an issue"

    def __init__(self):
        super(Command, self).__init__()

        self.parser.add_option("--all",
                               action="store_true",
                               default=False,
                               help="Show all details, including comments"
                               )

    def _help(self):
        print "Usage:"
        print "\t%s show [issue_id]" % sys.argv[0]

    def _execute(self, options, args):
        # find issue
        try:
            issue_id = args[0]

        except IndexError:
            self._help()
            return

        issue = common.issue_manager.get(issue_id)

        # show
        issue.printme()

        if options.all:
            print '-' * 5
            for comment in issue.comments:
                comment.printme()

                print '-' * 5
