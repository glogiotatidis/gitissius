import sys
import os
import optparse

class GitissiusCommand(object):
    """
    Gitissius Generic Command Object
    """
    aliases = []
    help = ''

    def __init__(self):
        self.parser = optparse.OptionParser()

    def __call__(self, args):
        (options, args) = self.parser.parse_args(args)
        return self._execute(options, args)

    def _execute(self, options, args):
        assert False

# import commands
available_commands = []
command = {}
here = lambda path: os.path.join(os.path.realpath(os.path.dirname(__file__)), path)

for key in ['commands', 'common', 'gitshelve', 'database']:
    if key in sys.modules:
        sys.modules['gitissius.%s' % key] = sys.modules[key]

def import_commands():
    for filename in os.listdir(here('.')):
        (filename, ext) = (filename[:-3], filename[-3:])
        if ext == '.py' and not filename == '__init__':
            try:

                cmd = __import__(filename,
                                 globals(), locals(),
                                 ['Command'], -1
                                 )
                available_commands.append(cmd.Command.name)

                command[cmd.Command.name] = cmd.Command()
                for alias in cmd.Command.aliases:
                    command[alias] = cmd.Command()

            except ImportError, e:
                print "Error importing command:", filename
                print e
