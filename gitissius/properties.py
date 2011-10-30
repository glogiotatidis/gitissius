import common
import hashlib
import readline

readline.parse_and_bind('tab: complete')

class DbProperty(object):
    """
    Property Generic Object
    """

    def __init__(self, name, completion=[], editable=True, allow_empty=True, default=None):
        """
        Generic Initialize
        """
        self.name = name
        self.editable = editable
        self.allow_empty = allow_empty
        self.completion = completion
        self.value = default

        # if colorama is presend set colors
        if common.colorama:
            self._color = {
                'repr_name': common.colorama.Fore.WHITE + common.colorama.Style.BRIGHT,
                'value': '',
                }

    def __str__(self):
        return self.value or ''

    @property
    def repr_name(self):
        return ' '.join(map(lambda x: x.capitalize(), self.name.split('_')))

    def repr(self, attr):
        value = getattr(self, attr)

        if common.colorama:
            color = self._color.get(attr, None)
            if color:
                value = color + value + common.colorama.Style.RESET_ALL

        return value

    def printme(self):
        print "%s: %s" % (self.repr('repr_name'), self.repr('value'))

    @common.disable_colorama
    def interactive_edit(self):
        """
        Generic Interactive Edit.

        Prompt user for input. Use default values. Validate Input
        """
        if not self.editable:
            return

        readline.set_completer(common.SimpleCompleter(self.completion).complete)
        while True:
            value = raw_input("%s (%s): " % \
                              (self.repr_name, self.value)
                              )

            if not value:
                value = self.value

            self.value = value

            try:
                self.validate_value()

            except common.PropertyValidationError, error:
                print " >", error
                continue

            else:
                break

        return self.value

    def set_value(self, value):
        """
        Generic Set Value.

        Directly set a value. Validate Input
        """
        self.value = value
        self.validate_value()

        return self.value

    def validate_value(self):
        """
        Generic Validate Value.

        Always returns True. It should be overriden by properties that
        need real validation. When value does not validate, raise
        PropertyValidationError.
        """
        if not self.allow_empty and not self.value:
            raise common.PropertyValidationError("%s cannot be empty." %\
                                                 self.name.capitalize()
                                                 )

    def serialize(self):
        """
        Generic Serialize.

        Return a python dictionary ready to be jsonized
        """
        return {'name': self.name,
                'value': unicode(self.value)
                }

class Option(DbProperty):
    def __init__(self, name, options, default=None):
        super(Option, self).__init__(name=name,
                                     completion=options.keys(),
                                     default=default)
        self.options = options

    def repr(self, attr):
        value = getattr(self, attr)

        if attr == 'value':
            if common.colorama:
                value = self.options[value].get('color', '') + value.capitalize()
                value += common.colorama.Style.RESET_ALL

            else:
                value = value.capitalize()

        else:
            return super(Option, self).repr(attr)

        return value

    @common.disable_colorama
    def interactive_edit(self, default=None):
        """
        Interactive edit.

        Prompt user for input. Provide shortcuts for states. If
        shortcut gets used, convert it to a proper value. Validate
        provided input.
        """
        readline.set_completer(common.SimpleCompleter(self.completion).complete)

        if not default:
            default = self.value

        while True:
            status = raw_input('%s (%s) [%s/h]: ' % \
                               (self.repr_name.capitalize(),
                                default,
                                '/'.join(map(
                                    lambda x: self.options[x].get('shortcut',''),
                                    self.options.keys()
                                    )
                                         )
                                )
                               )

            if not status:
                status = default

            status = status.lower()

            self.value = status.lower()

            try:
                self.validate_value()

            except common.PropertyValidationError, error:
                print " >", error

            else:
                break

        return self.value

    def validate_value(self):
        """
        Validate status value based on TYPE_STATES
        """
        shortcut_reverse = {}
        for key in self.options.keys():
            shortcut_reverse[self.options[key].get('shortcut')] = key

        if self.value.lower() in shortcut_reverse.keys():
            self.value = shortcut_reverse[self.value.lower()]

        if self.value.lower() not in self.options.keys():
            raise common.PropertyValidationError("Invalid type.")

        return True

class Description(DbProperty):
    """
    DescriptionProperty
    """
    def printme(self):
        print "%s:\n  %s" % (self.repr('repr_name'),
                             self.repr('value').replace('\n', '\n  ')
                             )

    @common.disable_colorama
    def interactive_edit(self, default=None):
        if not default:
            default = self.value

        while True:
            description = ''
            print "Description (End with a line containing only '.'): "

            self.old_description = self.value
            if self.value:
                print "Current: "
                print " " + self.value.replace('\n', '\n ')
                print '-' * 5

            while True:
                line = raw_input(" ")

                if line == '.':
                    break

                description += line + '\n'

            self.value = description.strip()
            if not self.value and self.old_description:
                self.value = self.old_description

            try:
                self.validate_value()

            except common.PropertyValidationError, error:
                print " >", error
                continue

            else:
                return self.value

class Id(DbProperty):
    """
    IdProperty to hold issue id
    """
    def __init__(self, name, editable=False, auto=True):
        """
        IdProperty Initializer
        """
        super(Id, self).__init__(name=name, editable=editable)
        self.auto = auto

        if self.auto:
            self.value = self._gen_id()

    def _gen_id(self):
        # generate id
        value = ''

        while True:
            value = hashlib.sha256(
                value + str(common.now())
                ).hexdigest()

            # check if in collection
            if len(common.git_repo.keys()) == 0:
                break

            elif not reduce(lambda x, y: x or y,
                            map(lambda x: value in x, common.git_repo.keys())
                            ):
                break

        return value

class Text(DbProperty):
    pass

class Date(DbProperty):
    """
    Stores the date and time the issue was first created
    """
    def __init__(self, name, editable=True, allow_empty=False,
                 auto_add_now=False, auto_now=False,
                 completion=[]):
        """
        DateProperty Initializer
        """
        super(Date, self).__init__(name=name,
                                   editable=editable,
                                   allow_empty=allow_empty
                                   )

        self.auto_add_now = auto_add_now
        self.auto_now = auto_now

    @common.disable_colorama
    def interactive_edit(self):
        """
        Interactive edit.

        Call interactive_edit from DbProperty by providing default
        the currect datetime.
        """
        if not self.value and self.auto_add_now:
            self.value = common.now()

        elif self.auto_now:
            self.value = common.now()

        elif self.editable:
            super(CreatedOnProperty, self).interactive_edit(default=default)

        return self.value
