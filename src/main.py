import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# The URL of the website to scrape follows a pattern:
# https://www.in.gov.br/consulta/-/buscar/dou?q=concurso&s=do3&exactDate=personalizado&sortType=0&publishFrom=14-02-2026&publishTo=18-02-2026
# What changes is the date range in the URL, which is defined by the 'publishFrom' and 'publishTo' parameters.
# The "concurso" parameter is the search query, which can be changed to other keywords related to public tenders and competitions.
# Also, do3 is the code for the Diário Oficial da União (DOU), which is the official journal of the Brazilian government,
# which can be changed to other codes for different official journals (1,2,3).
# We're particularly interested in the DO3, which is the Diário Oficial da União (DOU), 
# as it contains the most relevant information about public tenders and competitions.
# On that page, each link corresponds to a match for the search query, 
# and we can extract the relevant information from those links.

def scrape_concursos(start_date, end_date):
    url = f"https://www.in.gov.br/consulta/-/buscar/dou?q=concurso&s=do3&exactDate=personalizado&sortType=0&publishFrom={start_date}&publishTo={end_date}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all links that match the search query
    links = soup.find_all('a', href=True)

    concursos = []
    for link in links:
        if 'concurso' in link.text.lower():
            concursos.append(link['href'])

    return concursos

if __name__ == "__main__":

    # Make it so that the end_date is today's date, and the start_date is 7 days before today's date.
    
    end_date = datetime.today().strftime('%d-%m-%Y')
    start_date = (datetime.today() - timedelta(days=7)).strftime('%d-%m-%Y')

    concursos = scrape_concursos(start_date, end_date)
    for concurso in concursos:
        print(concurso)
