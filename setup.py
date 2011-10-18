import os
from setuptools import setup

from gitissius import gitissius

setup(
    name = "Gitissius",
    version = gitissius.VERSION,
    author = "Giorgos Logiotatidis",
    author_email = "seadog@sealabs.net",
    description = "Distributed bug tracking for Git.",
    license = "Mixed",
    keywords = "bug, tracking, git, distributed",
    url="http://github.com/glogiotatidis/gitissius",
    packages=['gitissius'],
    classifiers = [
        "Topic :: Software Development :: Bug Tracking",
        "Development Status :: 4 - Beta",
        "License :: Freely Distributable",
        "License :: OSI Approved :: GNU General Public License (GPL)"
        ],
    entry_points = {
        'console_scripts': ['git-issius = gitissius.gitissius:main']
        },
    data_files = [
        ('gitissius', ['README.org', 'LICENSE']),
        ]
    )
