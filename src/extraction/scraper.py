from bs4 import BeautifulSoup

import json
import re
import requests
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}


def scrape_concursos(start_date, end_date, do_type='do3') -> list[dict]:
    """
    Scrapes the DOU website for public tenders and competitions (concursos) published between start_date and end_date.
    Parameters:
        - start_date: The start date for the search in the format 'dd-mm-yyyy'
        - end_date: The end date for the search in the format 'dd-mm-yyyy'
        - do_type: The type of DOU to search (default is 'do3' for the main section)
    Returns:
        - A list of dictionaries containing information about each concurso found, including title, date, edition, section, and URL.
    """

    url = (
        "https://www.in.gov.br/consulta/-/buscar/dou"
        f"?q=title_pt_BR-concurso&s={do_type}"
        f"&exactDate=personalizado&sortType=0&publishFrom={start_date}&publishTo={end_date}"
    )

    # Add retry logic with timeout
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            break
        except requests.exceptions.HTTPError as e:
            # Retry on 5xx server errors, don't retry on 4xx client errors
            if 500 <= response.status_code < 600:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                    print(f"Server error ({response.status_code}). Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"Server error ({response.status_code}) persisted after {max_retries} attempts")
                    return []
            else:
                # Don't retry on client errors (4xx)
                print(f"Client error ({response.status_code}): {e}")
                return []
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                print(f"Connection failed: {type(e).__name__}. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Failed after {max_retries} attempts: {e}")
                return []

    soup = BeautifulSoup(response.text, 'html.parser')

    # The search results are embedded as JSON in a script tag, not as HTML links
    # Find the script tag containing the JSON data
    params_script = soup.find('script', {'id': '_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params'})

    if not params_script:
        print("Error: Could not find results JSON in page")
        return []

    # Parse the JSON data
    try:
        data = json.loads(params_script.string)
        results = data.get('jsonArray', [])

        # Return a list of dicts with the title, date, edition, section, and URL of each concurso found in the search results.
        concursos = []
        for result in results:
            url_title = result.get('urlTitle', '')
            title = result.get('title', '')
            # Extract content from HTML span tags and remove the tags
            title = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', title)
            # Remove consecutive duplicate words (case-insensitive)
            title = re.sub(r'(\w+)(?:\s*\1)+', r'\1', title, flags=re.IGNORECASE)
            pub_date = result.get('pubDate', '')
            edition = result.get('editionNumber', '')
            pub_name = result.get('pubName', '')

            # Construct the full URL
            full_url = f"https://www.in.gov.br/web/dou/-/{url_title}"

            concursos.append({
                'url': full_url,
                'title': title,
                'date': pub_date,
                'edition': edition,
                'section': pub_name,
                'url_title': url_title
            })

        return concursos

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return []
