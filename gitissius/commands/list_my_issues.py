import gitissius.commands as commands
import gitissius.common as common
import gitissius.gitshelve as gitshelve

class Command(commands.GitissiusCommand):
    """
    List MyIssues
    """
    name="myissues"
    aliases = ['my', 'mylist', 'm']
    help="Show issues assigned to you"

    def __init__(self):
        super(Command, self).__init__()

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

        issues = common.issue_manager.filter(rules=rules,
                                                operator="and",
                                                sort_key=options.sort
                                                )
        common.print_issues(issues)
