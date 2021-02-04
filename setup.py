from distutils.core import setup
setup(
  name = 'git_reqs',
  packages = ['git_reqs'],
  version = '0.2.6',
  description = 'Simple requirement management system for developers based yaml, networkx and git',
  author = 'Jonas Josefsson',
  author_email = 'Jonas.josefsson@niradynamics.se',
  url = 'https://github.com/niradynamics/git-reqs',
  download_url = 'https://github.com/niradynamics/git-reqs/archive/0.1.tar.gz',
  keywords = ['Requirements', 'gitreqs'],
   install_requires=[
           'junitparser',
           'networkx',
           'numpy',
           'PyYAML',
           'xlrd',
           'xlwt',
           'GitPython',
           'bokeh'
      ],
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'Topic :: Software Development',
    'Programming Language :: Python :: 3.6',
  ],
  scripts = ['git-reqs'],
)
