import gitissius.commands as commands
import gitissius.gitshelve as gitshelve

class Command(commands.GitissiusCommand):
    """
    Pull issues from repo, then push
    """
    name="update"
    aliases = ['u']
    help="Pull issues from origin and then push"

    def _execute(self, options, args):
        from pull import Command as pull
        from push import Command as push

        # this looks funny, because we first create a Command object
        # and then we execute it
        pull()(None)
        push()(None)

