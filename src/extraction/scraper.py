from bs4 import BeautifulSoup

import json
import re
import requests
import time

try:
    from src.config.dou_urls import get_dou_config
except ModuleNotFoundError:
    # Support running from `python src/main.py` where `src` isn't a package root in sys.path.
    from config.dou_urls import get_dou_config

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}


def resolve_url_title_by_document_id(document_id: str, do_type: str = 'do3') -> str | None:
    """
    Resolve DOU `url_title` using a legacy `document_id`.

    This is a fallback path for migrated summaries that don't have `_source.url_title`.
    Returns the matched `urlTitle` when possible, otherwise `None`.
    """
    doc_id = (document_id or "").strip()
    if not doc_id:
        return None

    dou_config = get_dou_config()
    search_base_url = dou_config.get_search_url()
    url = f"{search_base_url}?q={doc_id}&s={do_type}&sortType=0"

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        params_script = soup.find('script', {'id': '_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params'})
        if not params_script or not params_script.string:
            return None

        data = json.loads(params_script.string)
        results = data.get('jsonArray', [])
        first_url_title = None
        for result in results:
            url_title = (result.get('urlTitle') or '').strip()
            if not url_title:
                continue

            if first_url_title is None:
                first_url_title = url_title

            result_doc_id = str(
                result.get('documentId')
                or result.get('document_id')
                or result.get('id')
                or ''
            ).strip()
            if result_doc_id and result_doc_id == doc_id:
                return url_title

        return first_url_title
    except Exception:
        return None


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
    
    # Use configured DOU URL (resilient to future changes)
    dou_config = get_dou_config()
    search_base_url = dou_config.get_search_url()
    
    url = (
        f"{search_base_url}"
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
                    dou_config.record_component_failure("search")
                    return []
            else:
                # Don't retry on client errors (4xx)
                print(f"Client error ({response.status_code}): {e}")
                dou_config.record_component_failure("search")
                return []
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                print(f"Connection failed: {type(e).__name__}. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Failed after {max_retries} attempts: {e}")
                dou_config.record_component_failure("search")
                return []

    soup = BeautifulSoup(response.text, 'html.parser')

    # The search results are embedded as JSON in a script tag, not as HTML links
    # Find the script tag containing the JSON data
    params_script = soup.find('script', {'id': '_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params'})

    if not params_script:
        print("Error: Could not find results JSON in page")
        dou_config.record_component_failure("search")
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

            # Construct the full URL using configured pattern
            dou_config = get_dou_config()
            full_url = dou_config.get_document_url(url_title)

            concursos.append({
                'url': full_url,
                'title': title,
                'date': pub_date,
                'edition': edition,
                'section': pub_name,
                'url_title': url_title
            })

        dou_config.record_component_success("search")
        return concursos

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        dou_config.record_component_failure("search")
        return []
