import praw
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import pdfplumber
import json
from datetime import datetime


def scan_for_new_record(url):
    record_page = requests.get(url)
    soup = BeautifulSoup(record_page.content, "html.parser")
    #quick and dirty way of finding correct links
    links = [link.get('href') for link in soup.findAll('a') if ("EXEC-ROD" in link.get('href') and "Accessible-Version" not in link.get('href')) ]
    with open("old_documents.txt",'r') as t:
        old = t.read().split('\n')
    for link in links:
        if link.split('/')[-1] not in old:
            return link

def download_record(link):
    response = requests.get(link)
    with open("reports/{}".format(link.split('/')[-1]), 'wb') as f:
        f.write(response.content)
    with open("old_documents.txt",'a') as t:
        t.write(link.split('/')[-1]+"\n")

def extract_content(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        all_pages_dirty = [page.extract_tables()[1] for page in pdf.pages]
    df_dirty = pd.concat([pd.DataFrame(page) for page in all_pages_dirty])
    df = df_dirty[df_dirty.iloc[:,1].notna()].iloc[:,1:3]
    df.reset_index(drop=True,inplace=True)
    df['continued'] = np.where(df.iloc[:,1].str.len()==0,df.iloc[:,0],"")
    df['final'] = df.iloc[:,0]+df['continued'].shift(-1,fill_value="")
    df=df[df['continued'].str.len()==0]
    df=df[df['final'].str.contains("\$")]
    return list(df['final'])

def check_link_is_new(link):
    #TODO update date parsing to work past year 2100. 
    new_date = datetime.strptime(link[-11:-4],"20%y-%m").date()
    with open("old_documents.txt",'r') as t:
        latest_record = t.read().split('\n')[-2]
    latest_date = datetime.strptime(latest_record[-11:-4],"20%y-%m").date()
    return new_date>latest_date
    
def post(resolutions):
    with open("credentials.json",'r') as j:
        credentials = json.load(j)
    reddit = praw.Reddit(
        client_id=credentials['client_id'],
        client_secret=credentials['client_secret'],
        user_agent=credentials['user_agent'],
        username=credentials['username'],
        password=credentials['password']
    )
    with open("script.json", "r") as j:
        script = json.load(j)

    selftext = format_body(resolutions,script)
    subreddit = reddit.subreddit('simonfraser')
    result = subreddit.submit(script['title'],selftext=selftext,flair_id="d3981424-91ab-11ea-a2c9-0ea986a7453b")
    print(result)


def format_body(resolutions,script):
    formatted_resolutions = [format_resolution(resolution) for resolution in resolutions]
    joined_resolutions="\n\n.\n\n".join(formatted_resolutions)
    return script['body'].replace("<BODY>",joined_resolutions)

def format_resolution(text):
    lines = text.split("\n")
    title='>**'
    while lines[0].isupper():
        title+=lines[0].strip()
        lines.pop(0)

    title+="**\n\n"
    footer="\n\n>**"+lines[-1]+"**"
    lines.pop(-1)
    body = ">"+"\n>".join(lines)
    formated_text = title+body+footer+"\n\n"
    return formated_text

def run():
    link = scan_for_new_record("https://sfss.ca/records-of-decisions/")

    if link and check_link_is_new(link):
        download_record(link)
        resolutions=extract_content("reports/{}".format(link.split('/')[-1]))
        if(len(resolutions)>0):
            post(resolutions)


if __name__=="__main__":
    run()