# coding=utf-8
import re
import os
import numpy as np
import pandas as pd
import sys
import json
import argparse
import regex as reg

parser = argparse.ArgumentParser()

parser.add_argument('--input', type=str, dest='path', default='data/papers/',  help='specifies the path to input dir')
parser.add_argument('-o', type=str, dest='output', default='data/',  help='specifies the path to output dir')

rootdir = parser.parse_args().path
output = parser.parse_args().output

def author_title(x):
    """Gets author and tite part of reference string"""
    ref = str(x['ref'])
    authors = str(x['ref_parsed'])
    search = len(authors)+1
    end = re.search('\.|\?', ref[search:])
    if end:
        end = end.start()
    else:
        end = 0
    return ref[: (search+end)]

def ref_extraction(text, extract=False):
    """extracts refrerence section: on well formated documents"""
    mention = text.rfind("\nReferences")
    if mention == -1:
        mention = text.rfind("\nReference")
    if mention == -1 and reg.search('\n[\p{L}]*( |)[\p{L}]*( |)(R|r)eferences\n', text):
        #to keep everything consistent substract
            mention =  reg.search('\n[\p{L}]*( |)[\p{L}]*( |)(R|r)eferences\n', text).span()[1] - len("references")
    if mention == -1:
        return None
    #get reference section, account for different spelling
    acknowledgements = max(text.find("Acknowledgement"), text.find('Acknowledgment'), text.find('Appendix'))

    #handle case that acknowlege ments are before references
    if acknowledgements < mention:
        acknowledgements = -1
    ref = text[mention+len("references"):acknowledgements]

    references = re.split(r'\n', ref)

    #extract references while not extracting bottom text
    ref = [r for r in references if r and len(r) > 3 and not re.match(r'(CSCL|ICLS) \d{4} Proceedings|© ISLS', r)]
    if extract:
        print(text[mention+len("references"):acknowledgements])
        print(references)
    return ref

def contains_citation_beginning(sentence):

    ##Check for mention of publication date,
    #do it this way to not allow for ICLS 2015 string to be counted
    months = '(january|february|march|april|may|june|july|august|september|october|november|december)?'
    publication_year = r'(?<!\d)\('+months+'[\-\ ]*'+months+'[\ \,]*(18|19|20)\d{2}( |)[a-z]?[\,\ ]*'+months+'[\-\ \d]*'+months+'\)'

    #sometimes two years are mentioned, we use this regex to parse them
    match_bad_year = r'\((18|19|20)\d{2}\/(18|19|20)\d{2}\)'


    alternative_release = '|'.join(['in press', 'forthcoming', 'accepted', 'submitted', 'under review'])
    authors = '^[\p{L}\ \. \,\&\(\)\-\'\’\…]*'
    #these regex account for special strings used in the references
    match_press = authors + '('+alternative_release+')'
    sentence = sentence.lower()

    year = reg.match(authors + publication_year, sentence) or  reg.match(authors+match_bad_year, sentence)

    return  year or reg.match(match_press, sentence)

#moving sentences starting with lowercase letter or number strings "one up"
def moving_up(issues, condition=lambda x: reg.match('^[^\p{L}\*]|'+ #don't start with number or ., &
                                                    '(?!((d)[\p{Ll}])|(van))(^\p{Ll}{2,3} )|'+#no overly short non name start
                                                    '^\p{Ll}{6}[\p{Ll}]*|'+
                                                    '^([a-z]+[\.] )|'+ #no point
                                                    '^[\p{L}]*$', #no only word citations
                                                    x)):
    issues = [i for i in issues if len(i) > 0]
    patchwork = []
    j = 0

    for i, sentence in enumerate(issues):
        if i != 0 and condition(sentence):
            patchwork[j-1] += ' ' + sentence
            #print(sentence)
        else:
            j +=1
            patchwork.append(sentence)
    patchwork = [p for p in patchwork if len(p) > 0]

    return patchwork

def moving_down(issues, condition=lambda x: re.match('^[\d\(\.]', x)):
    """Moving sentences starting with lowercase letter or number strings "one up" """

    issues = [i for i in issues if len(i) > 0]
    patchwork = issues.copy()
    j = 0

    for i, sentence in enumerate(issues):
        if condition(sentence) and i+1 < len(issues):
            patchwork[i] = sentence + ' ' + patchwork[i+1]
            patchwork[i+1] = ''

    patchwork = [p for p in patchwork if len(p) > 0]

    return patchwork

def match_author(authors):
    """Identifies string starting with authors (APA) format"""

    regex = r'(([\p{L}\-]*[\,\&] [\p{Lu}\.\ ]+[\&\,]?)*$)'
    USA = r'([A-Z]{2,})'
    return not reg.search(USA, authors) and reg.match(regex, authors)

def contains_author(sentence):
    regex = r'(^[\p{L}\-\’\'\*]*[\,\&] [A-Z\.\ ]+[\&\,]?)'
    if reg.search(regex, sentence):
        return len(reg.search(regex, sentence).group(0)) > 0
    else:
        return False


def get_authors_month(sentence, debug = False):
    regex = r'[ééüş\xad\p{L}\,\ \.\:\;\/\&\-\'\`\(\)\’\–\¨\…\‐\*\´\＆\\]*\([\,\ \p{L}\d\-]*(18|19|20)\d{2}[\,\ \p{L}\d\-]*\)'
    match_bad_year = r'[\S\s]*\((18|19|20)\d{2}\/(18|19|20)\d{2}\)'

    match_press = r'[\S\s]*\((i|I)n (P|p)ress|manuscript under review\)'
    match_forth = r'[\S\s]*\((f|F)orthcoming\)'
    match_accepted = r'[\S\s]*\((a|A)ccepted\)'
    match_submitted = r'[\S\s]*\((s|S)ubmitted\)'
    match_underreview = r'[\S\s]*\((u|U)nder (R|r)eview\)'

    #sentence = sentence.lower()
    if reg.match(regex, sentence):
        s = reg.search(regex, sentence).group(0)
        if len(s) > 9:
            return s
    elif re.match(match_bad_year, sentence):
        return re.search(match_bad_year, sentence).group(0)
    elif re.match(match_press, sentence):
        return re.search(match_press, sentence).group(0)
    elif re.match(match_forth, sentence):
        return re.search(match_forth, sentence).group(0)
    elif re.match(match_accepted, sentence):
        return re.search(match_accepted, sentence).group(0)
    elif re.match(match_submitted, sentence):
        return re.search(match_submitted, sentence).group(0)
    elif re.match(match_underreview, sentence):
        return re.search(match_underreview, sentence).group(0)

    return np.nan


def extract_year(x, current_year):
    """Returns year of reference"""
    match_press = r'\(in press|submitted|under review|accepted|forthcoming'
    years = r'\([\w\d\,\ \.\-]*(18|19|20)\d{2}[\,\ \w\d\/\-]*\)'
    year = re.search(years, x)
    if re.search(match_press, x.lower()):
        return current_year
    if year:
        year = year.group(0)
        year = re.findall('\d{4}', year)
        return int(year[0])
    else:
        return np.nan

def extract_author(x):
    author_split = r'\.\,| & | and |;'
    list_authors = reg.split(author_split, x)
    list_authors = [name.replace('&', '').replace(',', '').strip() for name in list_authors]
    #remove end of string that isn't name
    list_authors = [re.sub(r'\([\s\S]*\)|\.\.\.|…| et al|\.', '', name).strip() for name in list_authors if len(name) > 0]
    list_authors = [name for name in list_authors if len(name) > 0]
    return list_authors

#### Main Code
contents = []
i = 0
source = []
for subdir, dirs, files in os.walk(rootdir):
    for file in files:
        if 'txt' in file:
            i += 1
            path = os.path.join(subdir, file)
            with open(path) as file:
                try:
                    text = file.read()
                    contents.append(text)
                    source.append(path[len(rootdir):-4])
                except:
                    name, message, content = sys.exc_info()
                    print(message)

references = []
for i, content in enumerate(contents):
    references.append((ref_extraction(content)))

#remove pdfs that do not have
reference_series = pd.DataFrame([references, source]).T.rename(columns={0: 'ref', 1: 'file'})
references = reference_series[reference_series.ref.notna()].ref.tolist()
source = reference_series[reference_series.ref.notna()].file.tolist()

print('\tNumber of pdf documents : ', len(contents))
print('\tNumber of documents for which we have an extracted reference section: ', len(references))


cutoff_name = r'^[A-Z]+\.\ ?'
ref_1 = [moving_up(r, lambda x: re.match(cutoff_name, x)) for r in references]
ref_1 = [moving_down(r, lambda x: reg.search('In [\p{Lu}\-\.]*\.$|\:$|\,$', x)) for r in ref_1]

ref_1 = [moving_up(r) for r in ref_1]

ref_2 = [moving_down(r, match_author) for r in ref_1]

words_at_end = r'( of| and| the| | [\p{Lu}])$'
ref_2 = [moving_down(r, lambda x: reg.search(words_at_end, x)) for r in ref_2]

ref_3 = [moving_up(r, lambda x: not (contains_author(x) or contains_citation_beginning(x))) for r in ref_2]
#pivoting up around strings containing citation
ref_4 = [moving_up(r, lambda x: not contains_citation_beginning(x)) for r in ref_3]

#build dataframe
references_df = pd.DataFrame([(f, source[i]) for i, flat in enumerate(ref_4) for f in flat], columns=['ref', 'file'])

references_df['length'] = references_df.ref.map(lambda x: len(x))
references_df = references_df[references_df.length > 30]
references_df = references_df[(references_df.length < 800)]

del references_df['length']

references_df['ref_parsed'] = references_df.apply(lambda x: get_authors_month(x['ref']), axis=1)

print('\tPercentage of unparsed references: {:0.3f}'.format(references_df.ref_parsed.isna().sum()/references_df.ref_parsed.shape[0]))
print('\tNumber of unparsed references: ', references_df[references_df.ref_parsed.isna()].ref.shape[0])
print('\tNumber of properly parsed references: ', references_df.ref_parsed.shape[0])

references_df['pub_year'] = references_df.file.map(lambda x: int(re.search('20[\d]{2}', x).group(0)))
references_df.loc[~references_df.ref_parsed.isna(),'year'] = references_df[~references_df.ref_parsed.isna()].apply(
    lambda x: extract_year(x.ref_parsed, x.pub_year), axis=1)
references_df['identifier'] = references_df.apply(author_title , axis=1)

print('\tSaved reference list to: {} as References.csv'.format(output))
os.path.join(output, 'References.csv')
references_df.to_csv(os.path.join(output, 'References.csv'))



#extract authors and clean strings a bit
references_df['authors'] =  references_df[~references_df.ref_parsed.isna()].ref_parsed.map(lambda x: extract_author(x))

tags = references_df.authors.apply(pd.Series)
tags = tags.rename(columns = lambda x : 'tag_' + str(x))

df = pd.concat([references_df, tags], axis=1)
tag_cols = [c for c in df.columns if 'tag' not in c]
df = df.melt(id_vars=tag_cols)

df['author'] = df['value']
df = df[df.value.notna()].reset_index(drop=True)
del df['variable'], df['authors'], df['value']

print('\tSaved to individual authors list: {} as Reference_authors.csv'.format(output))
df.to_csv(os.path.join(output, 'Reference_authors.csv'))
