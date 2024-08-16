from flask import Flask, jsonify
from flask_cors import CORS
import requests
import random
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from termcolor import colored

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
    ranks = [(i+1, url) for i, url in enumerate(serp_df['URLs']) if sitename in str(url)]
    now = datetime.date.today().strftime("%d-%m-%Y")
    return pd.DataFrame(
        [[keyword, rank, url, now, type] for rank, url in ranks], 
        columns=['Keyword', 'Rank', 'URLs', 'Date', 'Type']
    )

def fetch_search_results(keyword_url, device, headers):
    keyword, sitename = keyword_url['keyword'], keyword_url['url']
    google_uk_url = f'https://www.google.co.uk/search?num=100&q={keyword}'

    response = requests.get(google_uk_url, headers=headers)
    if response.status_code != 200:
        status = 'Blocked' if response.status_code == 429 else 'Failed'
        return pd.DataFrame({'Keyword': [keyword], 'Rank': [None], 'URLs': [None], 'Date': [datetime.date.today().strftime("%d-%m-%Y")], 'Type': ["My Site"], 'Status': [status]})

    soup = BeautifulSoup(response.text, 'html.parser')
    class_name = "P8ujBc" if device == 'mobile' else "yuRUbf"
    urls = [clean_url(a['href']) for a in soup.find_all('a', href=True, class_=class_name)]
    
    serp_df = pd.DataFrame(urls, columns=['URLs']).dropna()
    return rank_check(sitename, serp_df, keyword, "My Site")

def get_data(keywords_urls, device):
    user_agent = random.choice(mobile_agent if device.lower() == 'mobile' else desktop_agent)
    headers = {'User-Agent': user_agent}
    print(colored(f"- Checking {device.capitalize()} Rankings", 'black', attrs=['bold']))
    print(headers)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_search_results, keyword_url, device, headers) for keyword_url in keywords_urls]
        results = pd.concat([future.result() for future in as_completed(futures)])

    return results

def send_data_to_php(data):
    url = 'https://area.zeetach.com/data/request/save_data.php'
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    print('Data sent successfully.' if response.status_code == 200 else f'Failed to send data. Status code: {response.status_code}')

@app.route('/rankings', methods=['GET'])
def get_rankings():
    keywords_url = 'https://area.zeetach.com/data/request/get_keywords.php'
    keywords_data = requests.get(keywords_url).json()

    keywords_urls = [{'keyword': keywords_data['keywords'][i], 'url': keywords_data['urls'][i]['url']} for i in range(len(keywords_data['keywords']))] if 'keywords' in keywords_data and 'urls' in keywords_data else [{'keyword': 'uk-writings', 'url': 'https://proukwritings.co.uk/'}]

    mobile_results = get_data(keywords_urls, 'mobile')
    desktop_results = get_data(keywords_urls, 'desktop')

    response_data = {
        'mobile_results': mobile_results.to_dict(orient='records'),
        'desktop_results': desktop_results.to_dict(orient='records')
    }

    send_data_to_php(response_data)
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)
