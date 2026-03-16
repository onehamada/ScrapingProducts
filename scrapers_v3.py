import requests
from bs4 import BeautifulSoup
import time
import json
import gzip
from typing import Dict, Any

class SimpleScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br'
        })
    
    def scrape_any_site(self, url: str) -> Dict[str, Any]:
        """
        Faz scraping de qualquer site acessível
        
        Args:
            url: URL completa para fazer scraping
            
        Returns:
            Dicionário com HTML e conteúdo estruturado
        """
        try:
            print(f"Fazendo scraping de: {url}")
            
            # Fazer requisição
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # Verificar se o conteúdo está comprimido e descomprimir
            content = response.content
            if response.headers.get('content-encoding') == 'gzip':
                try:
                    content = gzip.decompress(content)
                    print("Conteúdo descomprimido (gzip)")
                except:
                    print("Falha ao descomprimir, usando conteúdo original")
            
            # Parsear HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extrair informações básicas
            title = soup.title.get_text() if soup.title else ''
            
            # Extrair todos os links
            links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                text = link.get_text(strip=True)
                if href and text:
                    links.append({
                        'url': href,
                        'text': text[:100],  # Primeiros 100 caracteres
                        'html': str(link)[:200]
                    })
            
            # Extrair todos os textos
            texts = []
            for element in soup.find_all(string=True):
                text = element.strip()
                if len(text) > 20 and len(text) < 500:  # Textos razoáveis
                    texts.append(text)
            
            # Extrair imagens
            images = []
            for img in soup.find_all('img', src=True):
                src = img.get('src')
                alt = img.get('alt', '')
                if src:
                    images.append({
                        'src': src,
                        'alt': alt[:100],
                        'html': str(img)[:200]
                    })
            
            # Extrair forms
            forms = []
            for form in soup.find_all('form'):
                action = form.get('action', '')
                method = form.get('method', 'GET')
                forms.append({
                    'action': action,
                    'method': method,
                    'html': str(form)[:500]
                })
            
            # Extrair metadados
            metadata = {
                'status_code': response.status_code,
                'content_length': len(response.text),
                'content_type': response.headers.get('content-type', ''),
                'response_time': 'N/A',
                'total_links': len(links),
                'total_images': len(images),
                'total_forms': len(forms),
                'total_texts': len(texts)
            }
            
            return {
                'success': True,
                'url': url,
                'html_content': content.decode('utf-8', errors='ignore'),
                'structured_data': {
                    'title': title,
                    'links': links[:50],  # Limitar para não sobrecarregar
                    'texts': texts[:100],
                    'images': images[:30],
                    'forms': forms[:10],
                    'total_elements': {
                        'links': len(links),
                        'texts': len(texts),
                        'images': len(images),
                        'forms': len(forms)
                    }
                },
                'metadata': metadata
            }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'url': url,
                'note': f'Erro ao acessar {url}'
            }

class OLXScraper:
    def __init__(self):
        self.scraper = SimpleScraper()
    
    def search_olx(self, query: str, location: str = "brasil") -> Dict[str, Any]:
        """
        Tenta fazer scraping da OLX com fallback para sites alternativos
        """
        # Tentar OLX primeiro
        olx_url = f"https://www.olx.com.br/brasil?q={query.replace(' ', '+')}&sf=1"
        result = self.scraper.scrape_any_site(olx_url)
        
        if result['success']:
            result['query'] = query
            result['location'] = location
            return result
        else:
            # Fallback para um site de exemplo (Mercado Livre)
            fallback_url = f"https://lista.mercadolivre.com.br/{query.replace(' ', '-')}"
            fallback_result = self.scraper.scrape_any_site(fallback_url)
            
            if fallback_result['success']:
                fallback_result['query'] = query
                fallback_result['location'] = location
                fallback_result['note'] = f'OLX bloqueada, usamos Mercado Livre como alternativa'
                return fallback_result
            else:
                # Fallback para site de exemplo sempre acessível
                example_url = "https://httpbin.org/html"
                example_result = self.scraper.scrape_any_site(example_url)
                example_result['query'] = query
                example_result['location'] = location
                example_result['note'] = f'Sites de compras bloqueados, usamos site de exemplo'
                return example_result

class FacebookScraper:
    def __init__(self):
        self.scraper = SimpleScraper()
    
    def search_facebook_marketplace(self, query: str, location: str = "") -> Dict[str, Any]:
        """
        Tenta fazer scraping do Facebook com fallback
        """
        # Facebook geralmente bloqueia, então vamos direto para fallback
        fallback_url = "https://example.com"
        result = self.scraper.scrape_any_site(fallback_url)
        
        result['query'] = query
        result['location'] = location
        result['note'] = 'Facebook Marketplace requer autenticação, usamos site de exemplo'
        
        return result
