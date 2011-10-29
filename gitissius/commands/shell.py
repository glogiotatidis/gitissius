import gitissius.commands as commands

class Command(commands.GitissiusCommand):
    """
    Interactive shell
    """
    name="shell"
    help="Open a gitissius shell"

    def _execute(self, options, args):
        print "Not implemented yet."
