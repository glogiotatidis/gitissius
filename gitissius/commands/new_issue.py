import commands

class Command(commands.GitissiusCommand):
    """ Create new issue """
    name = "new"
    aliases = ["new", "add"]
    help="Create an issue"

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
