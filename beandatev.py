#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Beancount importer for DATEV files
# Author: Frank Stollmeier
# License: GNU GPLv3
#

import os
import datetime
import argparse
import csv
from collections import Counter, defaultdict
from beancount.core.number import D
from beancount.core import data
from beancount.core import amount
from beancount.parser import printer
from beancount import loader
import pydatev as datev




def beancount2datev(filename_beancount, filename_datev, account_converter_beancount2datev, year, date_start = None, date_stop = None):
    '''Convert data from beancount to DATEV.
    
    Parameters
    ----------
    filename_beancount:     str, the existing beancount file
    filename_datev:         str, the file to create
    account_converter_beancount2datev: callable or dict
    year:                   int
    date_start:             datetime.date, optional. If not specified, start from the first entry of the specified year.
    date_stop:              datetime.date, optional. If not specified, stop at the last entry of the specified year.
    
    Return
    ------
    buchungsstapel:     instance of pydatev.Buchungsstapel
    '''
    #load transactions from beancount file
    entries,errors,options = loader.load_file(filename_beancount)
    transactions = [e for e in entries if isinstance(e, data.Transaction)]
    
    #set start and stop date
    if date_start is None:
        date_start = datetime.date(year,1,1)
    else:
        if date_start.year != year:
            raise ValueError("Start and stop date need to be within the year.")
    if date_stop is None:
        date_stop = datetime.date(year,12,31)
    else:
        if date_stop.year != year:
            raise ValueError("Start and stop date need to be within the year.")
    
    #filter and sort transactions
    transactions = [t for t in transactions if date_start <= t.date <= date_stop]
    transactions = sorted(transactions, key = lambda e: e.date)
    
    #find currency
    currencies = Counter([t.postings[0].units.currency for t in transactions])
    default_currency = currencies.most_common()[0][0]
    
    #Create a DATEV buchungsstapel
    buchungsstapel = datev.Buchungsstapel(berater = 1001, mandant = 1, wirtschaftsjahr_beginn = datetime.date(year,1,1), sachkontennummernlänge = 4, datum_von = date_start, datum_bis = date_stop, waehrungskennzeichen = default_currency)
    
    # Add transactions to the DATEV buchungsstapel
    for t in transactions:
        if len(t.postings) > 2:
            print("Warning: Skip transaction. Dealing with transactions which have more the two postings is not yet implemented.")
            continue
        p1,p2 = t.postings
        if float(p1.units.number) < 0:
            p2,p1 = p1,p2
        
        if isinstance(account_converter_beancount2datev, dict):
            k = account_converter_beancount2datev[p1.account]
            gk = account_converter_beancount2datev[p2.account]
        else:
            k = account_converter_beancount2datev(p1.account)
            gk = account_converter_beancount2datev(p2.account)
        
        buchung = buchungsstapel.add_buchung(umsatz = float(p1.units.number),
                    soll_haben = 'S',
                    konto = k,
                    gegenkonto = gk,
                    belegdatum = t.date)
        buchung['Buchungstext'] = t.narration[:60]
        if p1.units.currency != default_currency:
            buchung['WKZ Umsatz'] = p1.units.currency
    
    # Save to DATEV file
    buchungsstapel.save(filename_datev)
    return buchungsstapel
    


def datev2beancount(datev_file, account_converter_datev2beancount, filename_beancount = None, flag = 'txn', metadata = None, payee = '', print_result = False):
    '''Convert data from DATEV to beancount.
    
    Parameters
    ----------
    datev_file:         str (the filename) or instance of datev.Buchungsstapel
    filename_beancount:     str, optional. The beancount file to write to (create if not existing, otherwise append. If not specified, just print the output.
    account_converter_datev2beancount: callable or dict
    flag:                   str, optional
    metadata:               dict, optional. Convert datev fieldnames to beancount metadata. Example: If metadata = {'Belegfeld 1': 'belegnummer'}, then the content of the datev field 'Belegfeld 1' will appear as metadata 'belegnummer' in the beancount transaction.
    payee:              str. In datev, there is nothing like the payee in beancount. This option can be used to set it to a default value.
    
    Return
    ------
    beancount_entries:  list of beancount.core.data.Transaction instances (sorted by date).
    
    '''
    #Load DATEV data
    if isinstance(datev_file, str):
        buchungsstapel = datev.Buchungsstapel(filename = datev_file)
    elif isinstance(datev_file, datev.Buchungsstapel):
        buchungsstapel = datev_file
    else:
        raise IOError
    beancount_entries = []
    for entry in buchungsstapel.data:
        sign1 = '' if entry['Soll/Haben-Kennzeichen'] == 'S' else '-'
        sign2 = '-' if entry['Soll/Haben-Kennzeichen'] == 'S' else ''
        if isinstance(account_converter_datev2beancount, dict):
            k = account_converter_datev2beancount[entry['Kontonummer']]
            gk = account_converter_datev2beancount[entry['Gegenkonto (ohne BU-Schlüssel)']]
        else:
            k = account_converter_datev2beancount(entry['Kontonummer'])
            gk = account_converter_datev2beancount(entry['Gegenkonto (ohne BU-Schlüssel)'])
        currency = entry['WKZ Umsatz'] if not (entry['WKZ Umsatz'] is None) else buchungsstapel.metadata['Währungskennzeichen'] 
        p1 = data.Posting(k, amount.Amount(D(sign1+str(entry['Umsatz (ohne Soll/Haben-Kz)'])), currency), None, None, None, None)
        p2 = data.Posting(gk, amount.Amount(D(sign2+str(entry['Umsatz (ohne Soll/Haben-Kz)'])), currency), None, None, None, None)

        kvl = dict()
        for key,value in metadata.items():
            if not (entry[key] is None):
                kvl[value] = entry[key]
        meta = data.new_metadata(datev_file, None, kvlist = kvl)
        txn = data.Transaction(meta, entry['Belegdatum'], flag, payee, entry['Buchungstext'], data.EMPTY_SET, data.EMPTY_SET, [p1,p2])
        beancount_entries.append(txn)
    beancount_entries = sorted(beancount_entries, key=lambda e: e.date) 
    if isinstance(filename_beancount, str):
        with open(filename_beancount, "a") as f:
            printer.print_entries(beancount_entries, file = f)
    if print_result:
        printer.print_entries(beancount_entries)
    return beancount_entries
    



def create_account_dictionary(filename_beancount, convert_function, dict_filename = None):
    '''Read all open accounts from a beancount file and create a csv file where the first column is the account number and the second column is the account name.
    
    Parameters
    ----------
    beancount_file:     str, filename
    convert_function:   callable, which takes a string as an argument (account name) and returns a string (account number)
    dict_filename:      optional, str. Filename to save the csv. If none, just print the result instead of saving to file.
    '''
    header = "#account number (datev), account name (beancount)"
    entries,errors,options = loader.load_file(filename_beancount)
    accounts = [e.account for e in entries if isinstance(e, data.Open)]
    account_numbers = [convert_function(a) for a in accounts]
    lines = [header] + ["{},{}".format(an,a) for an,a in zip(account_numbers, accounts)]
    if dict_filename is None:
        for line in lines:
            print(line)
    else:
        if os.path.isfile(dict_filename):
            print("Error: File exists")
        else:
            with open(dict_filename, "w") as f:
                for line in lines:
                    f.write(line + '\n')
                

convert_function = lambda account_name: account_name.split(':')[2].split('-')[0]

def expand_asterisk_wildcard(account_number):
    '''
    If the account number contains wildchard charakter *, return a list of all account numbers matching the specified string.
    
    Parameters
    ----------
    account_number: str
    
    Return
    ------
    collection:     list of strings (account numbers)
    '''
    collection = [list(account_number)]
    for i in range(len(account_number)):
        collection_new = []
        for c in collection:
            if c[i].isdigit():
                collection_new.append(c)
            elif c[i] == '*':
                for digit in range(10):
                    c2 = c[:]
                    c2[i] = str(digit)
                    collection_new.append(c2)
            else:
                raise IOError("Not a valid account number: ", account_number)
        collection = collection_new
    collection = [''.join(c) for c in collection]
    return collection

def load_account_dictionary(filename, allow_wildcards = False, default_account_name = None):
    '''Load a csv file with account numbers and account names and return two dictionaries, one where d[account number] = account name and one where d[account name] = account number.
    
    Parameters
    ----------
    filename:           str
    allow_wildcards:    bool. If True, then account numbers containing an as asterisk, like '521*', will be expanded. Should be used only when converting from datev to beancount and not in the opposite direction, because then one account name is associated with multiple account numbers.
    default_account_name:   str, optional parameter. If provided, this account name will be used for all account numbers that are not found in the csv file.
    
    Return
    ------
    d1:     dictionary, where the keys are account names and the values are account numbers
    d2:     dictionary, where the keys are account numbers and the values are account names
    '''
    with open(filename, "r") as f:
        if default_account_name is None:
            d1 = dict()
        else:
            d1 = defaultdict(lambda : default_account_name)
        reader = csv.reader(f)
        for a,b in reader:
            if a[0] == '#':
                continue
            elif '*' in a:
                if allow_wildcards:
                    for an in expand_asterisk_wildcard(a):
                        d1[an] = b
                else:
                    raise IOError('Wildcards not allowed.')
            else:
                d1[a] = b
        #d1 = dict([(a,b) for a,b in reader])
    d2 = dict()
    for key in d1.keys():
        d2[d1[key]] = key
    return d1,d2

def main():
    parser = argparse.ArgumentParser(description='Beandatev - convert between beancount and datev.')
    parser.add_argument('--out', metavar='filename', type = str, help = "Optional parameter. Filename to save the output.")
    parser.add_argument('filename', type = str, help = "Input file (beancount or datev)")
    parser.add_argument('--create_account_dictionary', action = "store_true", help = "Get all open accounts from a beancount file and create a csv file that can be used as an account dictionary.")
    parser.add_argument('--account_dictionary', type = str, help = "The csv file to tell the converter how to translate between account numbers in datev and account names in beancount.")
    parser.add_argument('--year', type = int, help = "Optional parameter. Only relevant for beancount2datev conversion, because a datev files should contain data of a specific year. If specified, filter the input data for this year and write the output to the datev file. If not specified, use the current year.")
    args = parser.parse_args()
    
    if not os.path.isfile(args.filename):
        print("Error: Input file not found.")
    ext = os.path.splitext(args.filename)[1]
    if not (args.out is None) and os.path.isfile(args.out):
        print("Error: Output file exists.")
        return 1
    if ext == '.beancount':
        if args.create_account_dictionary:
            if args.out is None:
                create_account_dictionary(args.filename, convert_function, dict_filename = None)
                return 0
            else:
                create_account_dictionary(args.filename, convert_function, dict_filename = args.out)
                return 0
        else:
            if args.out is None:
                print("Error: parameter --out missing.")
                return 1
            else:
                if args.year is None:
                    year = datetime.datetime.today().year
                else:
                    year = args.year
                if args.account_dictionary is None:
                    print("Error: account dictionary required.")
                    return 1
                d1,d2 = load_account_dictionary(args.account_dictionary, allow_wildcards = False)
                entries = beancount2datev(args.filename, args.out, d2, year, date_start = None, date_stop = None)
                return 0
    elif ext == '.csv':
        if args.account_dictionary is None:
            print("Error: account dictionary required.")
            return 1
        d1,d2 = load_account_dictionary(args.account_dictionary, allow_wildcards = True)
        entries = datev2beancount(args.filename, d1, filename_beancount = args.out, flag = 'txn', print_result = True)
        return 0

if __name__ == '__main__':
    main()
    
    
