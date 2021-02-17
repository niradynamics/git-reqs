# Gitreqs

Gitreqs is a requirement management tool which emphasizes the handling of requirements in the same way as source code.

The main ideas behind gitreqs are the following:
  - The requirement tool shall be as simple as possible.
  - Requirements shall be stored fully textual so they can be handled by the same requirement tool as the source code, normally in the same repo.
  - It should be possible to branch the requirements in the same way as code is branched.
  - It should be possible to merge requirements in the same way as code.
  - Requirements shall have a simple representation in python so that tools can be used for traceability, plotting, validation etc.

## How it works
Gitreqs stores requirements, project and module info as yaml files. Each requirement is one yaml file.
Version handling and history is maintained by git (or any other version handling system).

A project consists of one or many modules where a module contains other modules or requirements. A project is just a top module.
Each module has its own requirement numbering, with a module prefix which is appended to the mother-module's prefix recursively.

Traceability is handled by NetworkX, a graph-theory package for python. Hence, each requirement is a node in a graph and each relation between requirements is an edge in the graph. Requirements can be linked to requirements in other modules in the project, or even to external items. NetworkX has many possibilities to analyze the graph for example check that the requirement graph really is tree, get subgraphs of ancestors and descendants or just get all leaves origining from one node.

Requirements can be edited by any text editor, but the general idea is to use excel round-trip when editing requirements. When exporting to excel, each requirement will be a row and each field in the requirement will be a column. Requirements can be edited or added in the excel document and imported back to yaml files.

For reports and requirement documents, each module can be exported to markdown.

## Editing requirements
When editing requirements, using an xls editor such as excel or libreoffice, the sheet will look as follows:

| Req-Id | Type | Description | downward_links | upward_links | formatting |
| ------ | ---- | ----------- | -------------- | ------------ | ---------- |
| ABC-SRS-ab35c | Info | My first requirement spec | | | Heading_1 |
| ABC-SRS-56f34 | Requirement | My first requirement | | | Requirement |
|  | Requirement | My new requirement | | refines:SRS-ab35c | Bullet_1 |
|  | Requirement | My other new requirement linked to some external document | | extern:DOORS-123 | Bullet_1 |
 
- The Req-Id column is updated by git-reqs and must not be edited manually, when adding new requrements this column is
left empty. The requirement will be given a unique id when the requirements are stored.
- The type of the requirement can be any string, but the types "Requirement" and "Testcase" are special and some 
have different handling when it comes to reports and test coverage calculations.
- Description is just a string, but if the requirement is a table item, markdown syntax shall be used, 
  i.e "| text | text |" separates the columns
- Links can be created by adding [relation type]:[target item]. More info about linking can be seen in the chapter below. 
- The formatting column can be used when exporting to markdown. The following formats are available:
  Heading_X where X is the level, BulletList_X where X is the indentation level, 
  Italic, Table Heading and Table Item

## Linking requirements
The underlying graph is a directed graph, so upwards means parents in that graph, and downwards means children. 
The target item can have arbitrary depth, just the id: ab35c will just link inside the current module, 
writing with one module prefix: TEST_be234 will also match other submodules in the same project. 
and for deeper projects, more prefixes can be required. 
The root project module prefix should however not be included in the link.

Links can be fully or partly, a link item that starts with (partly_) will handled a bit differently.
For example partly_verifies(1/2) means that the link verifies the requirement but just as one of two required tests.
The verification status will be calculated for each node and propagated upwards, so if the sum of the quota 
within parantheses is less than one, the requirement is considered partly tested.
This can apply to any link type.

Links can be added using comments in the source code, git-reqs loocks for the following pattern:
*git-reqs: [downward-link] [linktype] [upward-link]*.
So for example 
```scala
 // git-reqs: KalmanFilter implements SRS_45fad
```
will link the requirement SRS_adf45 to the implementation of KalmanFilter. If any of the link items does not 
exist in the graph, a temporary node will be added. So it is possible to link requirements to classes and such 
creating a node in the graph for the class, but it will not be given a proper id nor be stored to git..

For tests, if the comment also appears in the juint testresult file, the test result will also be linked.
For exampe in a scala test:
```scala
it should "calculate the time and measurement update" +
    "as required in git-reqs: TEST_f0ea7 verifies SRS_45fad"
```
This means that the test above is named TEST_f0ea7 in git-reqs, and it verifies the requirement
SRS_45fad. The result from this test will be called TEST_f0ea7_result and will be linked to TEST_f0ea7, 
but it will just be temporary for result evaluation and not stored to git.

When linking using comments, unexisting items can either be temporary or be created.
With the following syntax, a Testcase will be created in the TestSpecification module, 
with the description "KalmanTimeUpdateTest"
```scala
it should "perform the time update" +
    "as required in git-reqs: ?TestSpecification:Testcase:KalmanTimeUpdateTest verifies SRS_a56fe"
```
The description is optional. The source file is updated and the *"?TestSpecification:Testcase:KalmanTimeUpdateTest"* 
text is replaced by the new item number and that item will be stored as a new Testcase.

The folders to scan, and which filetypes to include when using the re.comment parse option when importing is setup in 
the root module config:
```yaml
source_extensions:
  - scala
  - yaml
  - java
source_paths:
  - src
  - helmchart
```
## Installation
git-reqs can be installed via python pip:
```bash
  pip install git-reqs
```

## User api
gitreqs has a commandline interface.
```bash
Usage: git-reqs [init, edit, export, import, report] ... [OPTIONS]

Mandatory arguments
init: Create a new module, or upgrade an existing with the --upgrade flag.
edit: Open requirements in an xls for editing, stores requirements on closure.
export: Export to xls or markdown.
import: Import requirements from xls, test-results from junit or update links 
        from source code comments.
report: Create a report of test coverage or relations.

Optional arguments:
--project_root: Path to the root module of the project. Will be PWD if not set.
--module: Name of submodule to operate on, Will be project_root if not set.

Per argument options:
init:
--upgrade [optional]: Upgrade the configuration of an existing module to the current.
--module_prefix [mandatory if not upgrade]: Set the module prefix of the new module

export:
--format FORMAT [mandatory]: The wanted output format, xls or md

import:
--format FORMAT [optional]: Format of the imported file, file-extension is default.
                            xls, junit or re.comments (parse source for req links).
--file FILE [mandatory]: File to import, or path in case of re.comments

report:
--type TYPE [mandatory]: Which type of report to generate, test_coverage or relations
```
### Examples
To create a root project called my_reqs with project prefix ABC:
```bash
  git-reqs init --module my_reqs --module_prefix ABC 
```

Enter your new root specification:
```bash
  cd my_reqs
```

To create a new module:
```bash
  git-reqs init --module SystemRequirementsSpecification --module_prefix SRS 
```

To edit the requirements:
```bash
  git-reqs edit
```
Modify the exported test.xls file, req-ids shall not be added manually. 

To export a module to xls:
```bash
  git-reqs export --module SystemRequirementsSpecification --format xls
```

To import the updated reqs from xls:
```bash
  git-reqs import --module SystemRequirementsSpecification --format xls --file test.xls
```

To export a module to markdown:
```bash
  git-reqs export --module SystemRequirementsSpecification --format md
```

To create a requirement traceability report of the whole project:
```bash
  git-reqs report --type relations
```
## git-reqs as a python module
git-reqs can also be used as a python module.
To generate markdown documents for hugo git-reqs can be used in the following way:

```python
from git_reqs.requirementmodule import requirement_module
from git_reqs import exporttools

req_module = requirement_module(path_to_requirement_module)
exporttools.convert_to_markdown(req_module, hugo=True)
```