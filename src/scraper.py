from bs4 import BeautifulSoup

import json
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
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Progressive backoff: 2s, 4s, 6s
                print(f"Connection failed. Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
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


def get_concurso_preview_lines(concurso, max_lines=10) -> list[str]:
    response = requests.get(concurso['url'], headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = 'utf-8'

    page_text = BeautifulSoup(response.text, 'html.parser').get_text('\n')
    raw_lines = [line.strip() for line in page_text.split('\n') if line.strip()]

    # Filter out common navigation/boilerplate lines that appear on the DOU site
    BOILERPLATE = [
        'Você precisa habilitar o JavaScript',
        'Ir para o conteúdo',
        'Ir para o rodapé',
        'Acesso rápido',
        'Órgãos do Governo',
        'Acesso à Informação',
        'Legislação',
        'Acessibilidade',
        'Voltar',
        'Compartilhe:',
        'Publicador de Conteúdos e Mídias',
        'Versão certificada',
        'Diário Completo',
        'Impressão',
        'Imagem não disponível',
        'Brasão do Brasil',
        'Destaques do Diário Oficial da União',
        'Base de Dados de Publicações do DOU',
        'Verificação de autenticidade',
        'Acesso GOV.BR',
        'Mudar para o modo de alto contraste',
        'Você precisa habilitar o JavaScript para o funcionamento correto.',
    ]

    def _is_boiler(line: str) -> bool:
        ll = line.lower()
        for phrase in BOILERPLATE:
            if phrase.lower() in ll:
                return True
        # skip very short lines which are usually navigation labels
        if len(ll) <= 2:
            return True
        return False

    filtered = [l for l in raw_lines if not _is_boiler(l)]

    # preserve order but remove exact duplicates
    seen = set()
    unique = []
    for l in filtered:
        if l not in seen:
            seen.add(l)
            unique.append(l)

    return unique[:max_lines]
