"""

"""
import os.path
import json
import pickle

import common
import properties

class DbObject(object):
    """
    Issue Object. The Mother of All
    """
    def __init__(self, *args, **kwargs):
        """
        Issue Initializer
        """
        self._properties += [properties.Id(name='id')]

        for item in self._properties:
            if item.name in kwargs.keys():
                item.set_value(kwargs[item.name])

        # random print order. override in children
        self._print_order = []
        for item in self._properties:
            self._print_order.append(item.name)

    def printme(self):
        for name in self._print_order:
            prop = self.get_property(name)
            prop.printme()

    def printmedict(self):
        """
        Return a dictionary with all properties after self.repr
        """
        dic = {}
        for prop in self._properties:
            dic[prop.name] = prop.repr('value')

        return dic

    @property
    def path(self):
        assert False

    def get_property(self, name):
        for prop in self._properties:
            if prop.name == name:
                return prop

        raise Exception("Property not found")

    def interactive_edit(self):
        """
        Interactive edit of issue properties.
        """
        for name in self._print_order:
            prop = self.get_property(name)
            prop.interactive_edit()

    def serialize(self, indent=0):
        """
        Return a json string containing all issue information
        """
        data = {}
        for item in self._properties:
            item_data = item.serialize()
            data[item_data['name']] = item_data['value']

        return json.dumps(data, indent=indent)

    @property
    def properties(self):
        data = {}
        for item in self._properties:
            data[item.name] = item

        return data

    def __str__(self):
        return self.get_property('title')

class Issue(DbObject):
    def __init__(self, *args, **kwargs):
        self._properties =  [
            properties.Text(name='title', allow_empty=False),
            properties.Option(name='status',
                              options={'new':{'shortcut':'n', 'color':common.get_fore_color('YELLOW')},
                                       'assigned':{'shortcut':'a', 'color':common.get_fore_color('GREEN')},
                                       'invalid':{'shortcut':'i', 'color':common.get_fore_color('WHITE')},
                                       'closed':{'shortcut':'c', 'color':common.get_fore_color('WHITE')}
                                       },
                              default='new'),
            properties.Option(name='type',
                              options={'bug':{'shortcut':'b', 'color':common.get_fore_color('YELLOW')},
                                       'feature':{'shortcut':'f', 'color':common.get_fore_color('GREEN')}
                                       },
                              default='bug'),
            properties.Text(name='assigned_to', completion=common.get_commiters()),
            properties.Text(name='reported_from', completion=common.get_commiters(), default=common.current_user()),
            properties.Date(name='created_on', editable=False, auto_add_now=True),
            properties.Date(name='updated_on', editable=False, auto_now=True),
            properties.Description(name='description')
            ]

        self._comments = []
        super(Issue, self).__init__(*args, **kwargs)

        self._print_order = ['id', 'title', 'type', 'reported_from', 'assigned_to',
                             'created_on', 'updated_on', 'status', 'description'
                             ]

    @property
    def path(self):
        id = self.get_property('id')
        return "{id!s}/issue".format(**{'id':id})


    @property
    def comments(self):
        if not self._comments:
            self._build_commentsdb()

        return self._comments

    def delete(self):
        for comment in self.comments:
            comment.delete()

        del common.git_repo[self.path]

    def _build_commentsdb(self):
        id = self.get_property('id')
        comment_path = "{id}/comments/".format(**{'id':id})

        for item in common.git_repo.keys():
            if item.startswith(comment_path):
                obj = Comment.load(json.loads(common.git_repo[item]))
                self._comments.append(obj)

        self._comments.sort(key=lambda x: x.get_property('created_on').value)

        return self._comments

    @classmethod
    def load(cls, data):
        return Issue(**data)

class Comment(DbObject):
    def __init__(self, *args, **kwargs):
        self._properties = [
            properties.Text(name='reported_from', default=common.current_user(), completion=common.get_commiters(),),
            properties.Id(name="issue_id", auto=False),
            properties.Date(name="created_on", editable=False, auto_add_now=True),
            properties.Description(name="description"),
            ]

        super(Comment, self).__init__(*args, **kwargs)

        self._print_order = ['reported_from', 'created_on', 'description']

    @property
    def path(self):
        issue_id = self.get_property('issue_id')
        return "{issueid!s}/comments/{commentid!s}".\
               format(**{'issueid': issue_id,
                         'commentid': self.get_property('id')
                         })

    def delete(self):
        del common.git_repo[self.path]

    @classmethod
    def load(cls, data):
        return Comment(**data)

class IssueManager(object):
    """
    Issue manager object
    """
    def __init__(self):
        self._issuedb = None

    @property
    def issuedb(self):
        if not self._issuedb:
            self._build_issuedb()

        return self._issuedb

    def _build_issuedb(self):
        self._issuedb = {}

        # get current head
        current_head = common.git_repo.current_head()

        # check if we have cache for current head
        path = os.path.join(common.find_repo_root(),
                            '.git',
                            'gitissius.%s.cache' % current_head
                            )
        loaded = False

        if os.path.exists(path):
            with open(path) as flp:
                try:
                    self._issuedb = pickle.load(flp)
                    loaded = True

                except:
                    loaded = False

        if not loaded:
            for issue in common.git_repo.keys():
                if not '/comments/' in issue:
                    # making sure that we don't treat comments as issues
                    obj = Issue.load(json.loads(common.git_repo[issue]))
                    self._issuedb[str(obj.get_property('id'))] = obj


            # delete previous caches
            for fln in os.listdir(os.path.join(common.find_repo_root(),
                                              '.git')
                                 ):
                if fln.startswith('gitissius') and fln.endswith('.cache'):
                    os.remove(os.path.join(common.find_repo_root(),
                                           '.git',
                                           fln)
                              )

            # create new
            with open(path, "wb") as flp:
                pickle.dump(self._issuedb, flp)

    def update_db(self):
        self._build_issuedb()

    def all(self, sort_key=None):
        return self.filter(sort_key=sort_key)

    def filter(self, rules=None, operator="and", sort_key=None):
        assert isinstance(rules, list)

        matching_keys = self.issuedb.keys()
        not_maching_keys = []

        if rules:
            for rule in rules:
                name, value = rule.items()[0]
                # parse operators
                cmd = name.split("__")
                name = cmd[0]

                operators = [lambda x, y: x.lower() in y.lower()]

                if "exact" in cmd[1:]:
                    operators += [lambda x, y: x == y]

                if "startswith" in cmd[1:]:
                    operators += [lambda x, y: y.startswith(x)]

                for key in matching_keys:
                    try:
                        result = reduce(lambda x, y: x==y==True,
                                        map(lambda x: x(value,
                                                        self.issuedb[key].\
                                                        properties[name].value
                                                        ),
                                            operators
                                            )
                                        )

                        if "not" in cmd[1:]:
                            if result:
                                not_maching_keys.append(key)

                        else:
                            if not result:
                                not_maching_keys.append(key)

                    except KeyError:
                        print "Error searching"
                        return []

            for key in not_maching_keys:
                try:
                    matching_keys.remove(key)
                except ValueError:
                    continue

            issues = []
            for key in matching_keys:
                issues.append(self.issuedb[key])

        else:
            issues = [issue for issue in self.issuedb.values()]

        if sort_key:
            issues = self.order(issues, sort_key)

        return issues

    def order(self, issues, key):
        """
        Short issues by key
        """
        issues.sort(key=lambda x: x.get_property(key).value)
        return issues

    def get(self, issue_id):
        matching_keys = []

        for key in self.issuedb.keys():
            if key.startswith(issue_id):
                matching_keys.append(key)

        if len(matching_keys) == 0:
            raise common.IssueIDNotFound(issue_id)

        elif len(matching_keys) > 1:
            raise common.IssueIDConflict(map(lambda x: self.issuedb[x], matching_keys))

        return self._issuedb[matching_keys[0]]
