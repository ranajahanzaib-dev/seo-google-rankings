from flask import Flask, jsonify
from flask_cors import CORS
import requests
import random
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import time
import json
import logging
from concurrent.futures import ThreadPoolExecutor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Define desktop user agents
desktop_agent = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:105.0) Gecko/20100101 Firefox/105.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:15.0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
]

google_uk_url = 'https://www.google.co.uk/search?num=100&q='  # UK-specific Google search URL

def clean_url(url):
    """Simplify URL extraction and handle unexpected URL formats."""
    start = url.find('https://')
    if start == -1:
        return None
    end = url.find('&ved', start)
    return url[start:end] if end != -1 else url[start:]

def rank_check(sitename, serp_df, keyword, type):
    """Check the rank of a site in the SERP."""
    df = pd.DataFrame(columns=['Keyword', 'Rank', 'URLs', 'Date', 'Type'])
    for idx, url in enumerate(serp_df['URLs']):
        if sitename in str(url):
            df = df.append({
                'Keyword': keyword,
                'Rank': idx + 1,
                'URLs': url,
                'Date': datetime.date.today().strftime("%d-%m-%Y"),
                'Type': type
            }, ignore_index=True)
    return df

def fetch_rank_data(keyword_url):
    """Fetch ranking data for a given keyword."""
    keyword = keyword_url['keyword']
    sitename = keyword_url['url']
    useragent = random.choice(desktop_agent)
    headers = {'User-Agent': useragent}

    try:
        response = requests.get(google_uk_url + keyword, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        urls = [clean_url(a['href']) for a in soup.find_all('a', href=True) if 'url' in a['href']]

        serp_df = pd.DataFrame(urls, columns=['URLs']).dropna(subset=['URLs'])
        return rank_check(sitename, serp_df, keyword, "My Site")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for keyword '{keyword}': {e}")
        return pd.DataFrame({'Keyword': [keyword], 'Rank': [None], 'URLs': [None], 'Date': [datetime.date.today().strftime('%d-%m-%Y')], 'Type': ['My Site'], 'Status': [str(e)]})

def get_data(keywords_urls):
    """Fetch data for all keywords and aggregate results."""
    logger.info("- Checking Desktop Rankings")

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(fetch_rank_data, keywords_urls))

    return pd.concat(results, ignore_index=True)

def send_data_to_php(data):
    """Send the data to a remote PHP endpoint."""
    url = 'https://area.zeetach.com/data/request/save_data.php'
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        logger.info('Data sent to PHP script successfully.')
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send data to PHP script: {e}")

@app.route('/rankings', methods=['GET'])
def get_rankings():
    """Handle the '/rankings' endpoint."""
    try:
        with open('request_counter.txt', 'r') as f:
            request_count = int(f.read().strip())
    except FileNotFoundError:
        request_count = 0
    
    # Calculate the start and end based on the request count (increments of 10)
    start = (request_count * 10) % 120
    end = start + 10
    keywords_url = f'https://area.zeetach.com/data/request/get_keywords.php?start={start}&end={end}'

    try:
        response = requests.get(keywords_url)
        response.raise_for_status()
        keywords_data = response.json()
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to retrieve data from the PHP endpoint: {str(e)}'}), 500
    except json.decoder.JSONDecodeError:
        return jsonify({'error': 'Failed to retrieve valid data from the PHP endpoint.'}), 500

    if 'keywords' in keywords_data and 'urls' in keywords_data:
        keywords_urls = [{'keyword': keywords_data['keywords'][i], 'url': keywords_data['urls'][i]['url']} for i in range(len(keywords_data['keywords']))]
    else:
        return jsonify({'error': 'No keywords or URLs found in the PHP response.'}), 500

    desktop_results = get_data(keywords_urls)

    response_data = {
        'desktop_results': desktop_results.to_dict(orient='records')
    }

    send_data_to_php(response_data)

    # Update the request counter
    with open('request_counter.txt', 'w') as f:
        f.write(str(request_count + 1))

    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)
