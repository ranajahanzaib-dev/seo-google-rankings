from flask import Flask, jsonify
from flask_cors import CORS
import requests
import random
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import time
import json

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow requests from all origins

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
    return url[start:end] if end != -1 else url[start:]

def rank_check(sitename, serp_df, keyword, type):
    d = []
    for index, row in serp_df.iterrows():
        url = row['URLs']
        if sitename in url:
            rank = index + 1
            now = datetime.date.today().strftime("%d-%m-%Y")
            d.append([keyword, rank, url, now, type])
    
    return pd.DataFrame(d, columns=['Keyword', 'Rank', 'URLs', 'Date', 'Type']) if d else pd.DataFrame(columns=['Keyword', 'Rank', 'URLs', 'Date', 'Type'])

def get_data(keywords_urls, device):
    google_uk_url = 'https://www.google.co.uk/search?num=100&q='

    headers = {'User-Agent': random.choice(mobile_agent if device.lower() == 'mobile' else desktop_agent)}

    results = pd.DataFrame()

    for keyword_url in keywords_urls:
        keyword = keyword_url['keyword']
        sitename = keyword_url['url']
        
        time.sleep(random.uniform(10, 20))
        response = requests.get(google_uk_url + keyword, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Inspect and adjust these class names as per the latest Google HTML structure
            urls = soup.find_all('div', class_="P8ujBc" if device.lower() == 'mobile' else "yuRUbf")

            data = []
            for div in urls:
                url_anchor = div.find('a')
                if url_anchor:
                    url = clean_url(url_anchor.get('href'))
                    if url:
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
    url = 'https://area.zeetach.com/data/request/save_data.php'
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        print('Data sent to PHP script successfully.')
    else:
        print(f'Failed to send data to PHP script. Status code: {response.status_code}')

@app.route('/rankings', methods=['GET'])
def get_rankings():
    keywords_url = 'https://area.zeetach.com/data/request/get_keywords.php'
    keywords_data = requests.get(keywords_url).json()

    keywords_urls = [{'keyword': keywords_data['keywords'][i], 'url': keywords_data['urls'][i]['url']} for i in range(len(keywords_data['keywords']))] if 'keywords' in keywords_data and 'urls' in keywords_data else [
        {'keyword': 'uk-writings', 'url': 'https://proukwritings.co.uk/'}
    ]

    mobile_results = get_data(keywords_urls, 'mobile')
    time.sleep(5)
    desktop_results = get_data(keywords_urls, 'desktop')

    response_data = {
        'mobile_results': mobile_results.to_dict(orient='records'),
        'desktop_results': desktop_results.to_dict(orient='records')
    }

    send_data_to_php(response_data)

    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)
