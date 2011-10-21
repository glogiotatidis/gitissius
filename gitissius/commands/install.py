import commands

class Command(commands.GitissiusCommand):
    """ Initiailize repo to use git-issues """

    name="install"
    help="Install Gitissius in current repositoy"

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
