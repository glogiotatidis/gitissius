import commands

class Command(commands.GitissiusCommand):
    """ Search issues """

    name="search"
    help="Search issues"

    def _execute(self, options, args):
        print "Not implemented yet"
