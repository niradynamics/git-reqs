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

## User api
gitreqs has a commandline interface.

To create a root project called my_reqs with project prefix ABC:
  .src/gitreqs init --module my_reqs --module_prefix ABC 

Enter your new root specification:
cd my_reqs

To create a new module:
  ../src/gitreqs init --module SystemRequirementsSpecification --module_prefix SRS 

To export a module to xls:
  ../src/gitreqs export --module SystemRequirementsSpecification --format xls

Modify the exported test.xls file, req-ids shall not be added manually. 

To import the updated reqs from xls:
  ../src/gitreqs import --module SystemRequirementsSpecification --format xls --file test.xls

To export a module to markdown:
  ../src/gitreqs export --module SystemRequirementsSpecification --format md

To create a requirement traceability report of the whole project:
  ../src/gitreqs report --project_root . --type relations
