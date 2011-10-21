import commands

#from common import print_issues
#from gitissius import issue_manager, colorama
import common
import gitissius

class Command(commands.GitissiusCommand):
    """
    List Issues
    """
    name="list"
    aliases = ['l']
    help="List issues"

    def __init__(self):
        super(Command, self).__init__()

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

        common.print_issues(gitissius.issue_manager.filter(sort_key=options.sort,
                                                           rules=filters)
                            )
