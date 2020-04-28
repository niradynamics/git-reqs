# Gitreqs requirement specification

*Gitreqs is a simple requirement tool based on git (or some other version management system) and python*

## General requirements

Gitreqs shall store each requirment in a .json file *[ROOT_SRS_4]*

A gitreqs module shall be able to contain requirements and other gitreqs modules *[ROOT_SRS_5]*

Each gitreqs module shall have a prefix *[ROOT_SRS_30]*

The module prefix shall be added to the parent modules prefix recursively *[ROOT_SRS_31]*

It shall be possible to link requirements to other requrements *[ROOT_SRS_6]*

  - Links shall be parsed, separating link type from link id using a colon *[ROOT_SRS_7]*

  - Links shall be parsed, separating multiple links with comma *[ROOT_SRS_8]*

  - Links shall have a direction, upward or downward *[ROOT_SRS_9]*

It should be possible to link requirements, relatively to other modules *[ROOT_SRS_11]*

It should be possible to link requirements, to external items *[ROOT_SRS_12]*

It should be possible to explicitly set a link as external using the extern_ prefix in the link name *[ROOT_SRS_13]*

## Formatting requirements

It should be possible to use markdown syntax in requirement descriptions  *[ROOT_SRS_10]*

|Table example | Col1 | Col2 | Req-Id |
|--------------|------|------|-------- |
|Tables from markdown shall be possible to use | with columns | and more columns  | *ROOT_SRS_15* |
|Tables from markdown shall be preserved when importing and exporting | with columns | and more columns  | *ROOT_SRS_16* |
|It should be possible to have one requirement per table row  | with columns | and more columns  | *ROOT_SRS_17* |
## Import and Export

It should be possible to export a module to xls *[ROOT_SRS_20]*

It should be possible to export a module to markdown *[ROOT_SRS_21]*

It should be possible to create a report showing the a part of the requirement tree containing each requirement *[ROOT_SRS_22]*

It should be possible to import a module from xls *[ROOT_SRS_23]*

It should be possible to import descriptions and links of a module from markdown *[ROOT_SRS_24]*

When importing requirements, if no requirement id was specified a new new number shall be assigned *[ROOT_SRS_25]*

Requirement ids shall not be reused *[ROOT_SRS_26]*

When importing requirements, links must be checked so they are not be specified both ways. They should only be stored in one side of the requirement pair. *[ROOT_SRS_27]*

## User interface

Gitreqs shall use a command line interface to import, export, verify and init a new module *[ROOT_SRS_29]*

