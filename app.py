from flask import Flask, jsonify
from flask_cors import CORS
import requests
import random
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import time
import json
from termcolor import colored

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow requests from all origins

# Define desktop user agents
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

def get_data(keywords_urls):
    google_uk_url = 'https://www.google.co.uk/search?num=100&q='  # UK-specific Google search URL

    print(colored("- Checking Desktop Rankings", 'black', attrs=['bold']))
    useragent = random.choice(desktop_agent)      
    headers = {'User-Agent': useragent}
    print(headers)

    results = pd.DataFrame()
    
    for keyword_url in keywords_urls:
        keyword = keyword_url['keyword']
        sitename = keyword_url['url']
        
        time.sleep(random.uniform(10, 20))
        response = requests.get(google_uk_url + keyword, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
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
    url = 'https://area.zeetach.com/data/request/save_data.php'
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        print('Data sent to PHP script successfully.')
    else:
        print(f'Failed to send data to PHP script. Status code: {response.status_code}')

@app.route('/rankings', methods=['GET'])
def get_rankings():
    # Fetch the current request count from a file (or database) to implement the pagination logic
    try:
        with open('request_counter.txt', 'r') as f:
            request_count = int(f.read().strip())
    except FileNotFoundError:
        request_count = 0
    
    # Calculate the start and end based on the request count (increments of 10)
    start = (request_count * 10) % 120  # Reset after 120
    end = start + 10

    keywords_url = f'https://area.zeetach.com/data/request/get_keywords.php?start={start}&end={end}'
    
    try:
        response = requests.get(keywords_url)
        response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)
        keywords_data = response.json()  # Attempt to parse JSON response

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to retrieve data from the PHP endpoint: {str(e)}'}), 500
    except json.decoder.JSONDecodeError:
        return jsonify({'error': 'Failed to retrieve valid data from the PHP endpoint.'}), 500

    if 'keywords' in keywords_data and 'urls' in keywords_data:
        # Create the keywords_urls list based on the response structure
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
