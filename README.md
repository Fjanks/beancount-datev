# Beancount DATEV converter

This is a tool to convert accounting data from [beancount](https://github.com/beancount/beancount) to DATEV and vice versa. 

Warning: The tool is in an early state of development and not well tested.

## State of implementation

The basic conversion in both directions is implemented. Not yet implemented:

* Support for documents attached to transactions.
* Dealing with multiple currencies.
* Converting beancount transactions with more than two postings to datev. 


## Requirements

  * beancount
  * [pydatev](https://github.com/Fjanks/pydatev)
  * some common python modules


## Install

1. Install the requirements (all requirements can be installed via pip).
2. Clone the repository, e.g. `git clone --depth 0 <url>`


## Usage

### Preparation

The converter can not guess how to translate the account names in your beancount files to the account numbers in the datev file. You need to create a csv file in which the first column is the account number in datev and the second column is the corresponding account name in beancount. You can create this file manually, but since there is a huge number of account numbers in datev, I recommend to choose an account naming scheme that allows to create this csv file automatically. If you use the account naming scheme described below (section "Suggestion on account naming scheme"), the tool can create the csv file for you. Open all necessary accounts in your beancount file (with the naming scheme described below) and then run

    ./beandatev.py source.beancount --create_account_dictionary --out account_dictionary.csv

If you are only interested in converting from datev to beancount and you are satisfied with a simple account structure in beancount, you can also write the csv file manually and use wildcards `*` to assign a large group of account numbers to one account name in beancount, for example `5***` to `Aufwand:5-Materialaufwand`. 

### Convert data from a beancount file source.beancount to a datev file EXTF_target.csv
    ./beandatev.py source.beancount --out EXTF_target.csv --year 2020

Note that the datev standard requires the file to begin with `EXTF_' and that the data file allows to include only data of one specific year, which is why you need to add the parameter --year.

### Convert data from a datev file EXTF_source.csv to a beancount file target.beancount

    ./beandatev.py EXTF_source.csv --out target.beancount


## Suggestion on account naming scheme

As mentioned above, you can use any account names you like if you create the csv file. For example, you can use the four digit account number WXYZ from DATEV and name the corresponding account in beancount `Aktiva:WXYZ`. However, one of the nice things of plain text accounting is human readability, but with account names like `Aktiva:WXYZ` the resulting beancount file would be full of cryptic account numbers. However, removing the number and just using descriptive names has the disadvantages that we would loose the order and hierarchy of the datev accounts and that the software can not automatically extract the datev account number from the beancount account name. 
A good compromise is to name the datev account `WXYZ` in beancount `Aktiva:W-groupname:WXYZ-description`, for example `0440` becomes `Aktiva:0-Anlagevermögen:0440-Maschinen`. Such names are human readable, have a meaningful hierarchy, and can be automatically converted to the datev account number. 
