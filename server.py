from flask import Flask, jsonify, request
from flask_cors import CORS  # Add this import
import requests
import random
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import time
import json
from termcolor import colored

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Define user agents and other necessary variables
mobile_agent = [
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/114.0.5735.99 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/114.1 Mobile/15E148 Safari/605.1.15',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 EdgiOS/114.0.5735.99',
]

desktop_agent = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:105.0) Gecko/20100101 Firefox/105.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:15.0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
]

def clean_url(url):
    start = url.find('https://')
    if start == -1:
        return None

    end = url.find('&ved', start)
    if end == -1:
        return url[start:]
    else:
        return url[start:end]

def rank_check(sitename, serp_df, keyword, type):
    counter = 0
    d = []
    for i in serp_df['URLs']:
        counter += 1
        if sitename in str(i):
            rank = counter
            url = i 
            now = datetime.date.today().strftime("%d-%m-%Y")
            d.append([keyword, rank, url, now, type])
    
    if d:
        df = pd.DataFrame(d, columns=['Keyword', 'Rank', 'URLs', 'Date', 'Type'])
    else:
        df = pd.DataFrame(columns=['Keyword', 'Rank', 'URLs', 'Date', 'Type'])
    
    return df

def get_data(keywords, sitename, device):
    # Google Search URL
    google_url = 'https://www.google.com/search?num=100&q='

    if device.lower() == 'mobile':
        print(colored("- Checking Mobile Rankings" ,'black',attrs=['bold']))
        useragent = random.choice(mobile_agent)      
        headers = {'User-Agent': useragent}
        print(headers)
    elif device.lower() == 'desktop':
        print(colored("- Checking  Desktop Rankings" ,'black',attrs=['bold']))
        useragent = random.choice(desktop_agent)      
        headers = {'User-Agent': useragent}
        print(headers)

    results = pd.DataFrame()
    
    for keyword in keywords:
        time.sleep(random.uniform(10, 20))
        response = requests.get(google_url + keyword, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            if device.lower() == 'mobile':
                urls = soup.find_all('div', class_="P8ujBc")
            elif device.lower() == 'desktop':
                urls = soup.find_all('div', class_="yuRUbf")

            data = []
            for div in urls:
                soup = BeautifulSoup(str(div), 'html.parser')
                url_anchor = soup.find('a')
                if url_anchor:
                    url = url_anchor.get('href', "No URL")
                else:
                    url = "No URL"
                url = clean_url(url)
                data.append(url)

            serp_df = pd.DataFrame(data, columns=['URLs']).dropna(subset=['URLs'])
            keyword_results = rank_check(sitename, serp_df, keyword, "My Site")
            results = pd.concat([results, keyword_results])

        elif response.status_code == 429:
            error_message = 'Rate limit hit, status code 429. You are Blocked From Google'
            results = pd.concat([results, pd.DataFrame({'Keyword': [keyword], 'Rank': [None], 'URLs': [None], 'Date': [datetime.date.today().strftime("%d-%m-%Y")], 'Type': ["My Site"], 'Status': [error_message]})])
        else:
            error_message = f'Failed to retrieve data, status code: {response.status_code}'
            results = pd.concat([results, pd.DataFrame({'Keyword': [keyword], 'Rank': [None], 'URLs': [None], 'Date': [datetime.date.today().strftime("%d-%m-%Y")], 'Type': ["My Site"], 'Status': [error_message]})])

    return results

def send_data_to_php(data):
    url = 'http://localhost/keywordranking/client/save_data.php'
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        print('Data sent to PHP script successfully.')
    else:
        print(f'Failed to send data to PHP script. Status code: {response.status_code}')

@app.route('/rankings', methods=['GET'])
def get_rankings():
    keywords = ['proukwritings', 'proukwritings.co.uk', 'uk-writings']
    sitename = "https://proukwritings.co.uk/"

    mobile_results = get_data(keywords, sitename, 'mobile')
    time.sleep(5)
    desktop_results = get_data(keywords, sitename, 'desktop')

    response_data = {
        'mobile_results': mobile_results.to_dict(orient='records'),
        'desktop_results': desktop_results.to_dict(orient='records')
    }

    send_data_to_php(response_data)

    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)
