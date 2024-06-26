import http.server
import socketserver
import urllib.parse
import io
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Definir a senha necessária para acessar o download
PASSWORD = 'password123'


def obter_numero_paginas(url_base):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url_base, headers=headers)
    if response.status_code != 200:
        print(f'Falha ao carregar a página: {response.status_code}')
        return 0

    soup = BeautifulSoup(response.content, 'html.parser')

    paginacao = soup.find('ul', {'data-cy': 'frontend.search.base-pagination.nexus-pagination'})
    if not paginacao:
        return 1

    paginas = paginacao.find_all('li')
    total_paginas = int(paginas[-2].text.strip()) if paginas else 1
    return total_paginas


def scrape_imoveis(url_base):
    dados_imoveis = []
    total_paginas = obter_numero_paginas(url_base)

    for pagina in range(1, total_paginas + 1):
        url = f'{url_base}&page={pagina}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f'Falha ao carregar a página {pagina}: {response.status_code}')
            continue

        soup = BeautifulSoup(response.content, 'html.parser')

        articles = soup.find_all('article', {'data-cy': 'listing-item'})

        for article in articles:
            try:
                localizacao = article.find('p', class_='css-1dvtw4c eejmx80').text.strip() if article.find('p',
                                                                                                           class_='css-1dvtw4c eejmx80') else 'N/A'
                preco = article.find('span', class_='css-1uwck7i evk7nst0').text.strip() if article.find('span',
                                                                                                         class_='css-1uwck7i evk7nst0') else 'N/A'
                tipologia = article.find('dt', string='Tipologia').find_next_sibling('dd').text.strip() if article.find(
                    'dt', string='Tipologia') else 'N/A'
                metros_quadrados = article.find('dt', string='Zona').find_next_sibling('dd').text.strip() if article.find(
                    'dt', string='Zona') else 'N/A'
                preco_por_metro_quadrado = article.find('dt', string='Preço por metro quadrado').find_next_sibling(
                    'dd').text.strip() if article.find('dt', string='Preço por metro quadrado') else 'N/A'

                link = article.find('a', {'data-cy': 'listing-item-link'})['href'] if article.find('a', {
                    'data-cy': 'listing-item-link'}) else 'N/A'
                link_completo = f'https://www.imovirtual.com{link}' if link != 'N/A' else 'N/A'

                dados_imovel = {
                    'preço': preco,
                    'localização': localizacao,
                    'tipologia': tipologia,
                    'm2': metros_quadrados,
                    'preço por m2': preco_por_metro_quadrado,
                    'link': link_completo
                }

                dados_imoveis.append(dados_imovel)
            except Exception as e:
                print(f'Erro ao processar um artigo na página {pagina}: {e}')

    return dados_imoveis


def salvar_excel(dados):
    df = pd.DataFrame(dados)

    # Criar um buffer de bytes para salvar o arquivo Excel
    output = io.BytesIO()

    # Salvar o DataFrame para o Excel
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')

    output.seek(0)
    return output


class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)

        if parsed_path.path == "/":  # Servir index.html para o caminho raiz
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('index.html', 'rb') as f:
                self.wfile.write(f.read())
            return

        if parsed_path.path == "/download":
            url_base = query_params.get('url', [None])[0]
            password = query_params.get('password', [None])[0]

            # Verificar se a senha está correta
            if password != PASSWORD:
                self.send_response(401)
                self.end_headers()
                self.wfile.write('Unauthorized: senha incorreta'.encode('utf-8'))
                return

            if not url_base:
                self.send_response(400)
                self.end_headers()
                self.wfile.write('Bad Request: parâmetro url_base faltando'.encode('utf-8'))
                return

            dados_imoveis = scrape_imoveis(url_base)
            excel_data = salvar_excel(dados_imoveis)

            self.send_response(200)
            self.send_header('Content-Disposition', 'attachment; filename="dados_imoveis.xlsx"')
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.end_headers()
            self.wfile.write(excel_data.getvalue())


# Criar um servidor HTTP com o manipulador personalizado
with socketserver.TCPServer(("", 8000), CustomHandler) as httpd:
    print("Servindo na porta", 8000)
    httpd.serve_forever()

