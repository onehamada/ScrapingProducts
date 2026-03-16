import requests
from bs4 import BeautifulSoup
import time
import json
from typing import Dict, Any

class OLXScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def search_olx(self, query: str, location: str = "brasil") -> Dict[str, Any]:
        """
        Realiza uma busca na OLX usando apenas requests (mais confiável)
        
        Args:
            query: Termo de busca
            location: Localização para filtrar resultados
            
        Returns:
            Dicionário com HTML e conteúdo estruturado
        """
        try:
            # Construir URL da busca - usando URL principal
            formatted_query = query.replace(' ', '+')
            url = f"https://www.olx.com.br/brasil?q={formatted_query}&sf=1"
            
            print(f"Buscando em: {url}")
            
            # Fazer requisição
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # Parsear HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extrair informações estruturadas
            listings = []
            
            # Procurar por anúncios usando diferentes seletores
            selectors = [
                '[data-testid="ad-card"]',
                '[data-lurker-detail="ad_id"]',
                '.ad-card',
                '.sc-1fpybdo-0',
                '[role="article"]',
                'a[href*="/anuncio/"]'
            ]
            
            for selector in selectors:
                try:
                    elements = soup.select(selector)
                    if elements:
                        print(f"Encontrados {len(elements)} elementos com seletor: {selector}")
                        
                        for element in elements[:20]:
                            try:
                                # Extrair título
                                title_elem = element.find(['h2', 'h3', 'span', 'a'], string=True)
                                title = title_elem.get_text(strip=True) if title_elem else ''
                                
                                # Extrair preço
                                price_elem = element.find(text=lambda text: text and ('R$' in text or '$' in text))
                                price = price_elem.strip() if price_elem else ''
                                
                                # Extrair link
                                link_elem = element.find('a', href=True)
                                link = link_elem.get('href') if link_elem else ''
                                if link and not link.startswith('http'):
                                    link = 'https://www.olx.com.br' + link
                                
                                # Extrair localização
                                location_elem = element.find(text=lambda text: text and any(estado in text.lower() for estado in ['sp', 'rj', 'mg', 'rs', 'pr', 'sc', 'ba', 'pe', 'ce', 'df']))
                                location_text = location_elem.strip() if location_elem else ''
                                
                                listing_data = {
                                    'title': title,
                                    'price': price,
                                    'link': link,
                                    'location': location_text,
                                    'html_section': str(element)[:500]  # Primeiros 500 caracteres
                                }
                                
                                # Adicionar apenas se tiver informação útil
                                if listing_data['title'] or listing_data['price']:
                                    listings.append(listing_data)
                                    
                            except Exception as e:
                                continue
                        
                        if listings:  # Se encontrou algo, para de procurar
                            break
                            
                except Exception as e:
                    continue
            
            # Se não encontrou com seletores específicos, tenta abordagem genérica
            if not listings:
                print("Tentando abordagem genérica...")
                all_links = soup.find_all('a', href=True)
                for link in all_links[:30]:
                    href = link.get('href', '')
                    if '/anuncio/' in href or 'ad_id' in href:
                        title = link.get_text(strip=True)
                        if len(title) > 10:  # Título razoável
                            listings.append({
                                'title': title,
                                'price': '',
                                'link': 'https://www.olx.com.br' + href if href.startswith('/') else href,
                                'location': '',
                                'html_section': str(link)[:300]
                            })
            
            return {
                'success': True,
                'url': url,
                'query': query,
                'location': location,
                'html_content': response.text,
                'css_links': [],
                'js_links': [],
                'structured_data': {
                    'listings': listings,
                    'total_found': len(listings),
                    'page_title': soup.title.get_text() if soup.title else '',
                    'note': f'Busca usando requests method'
                },
                'metadata': {
                    'status_code': response.status_code,
                    'content_length': len(response.text),
                    'method': 'requests_only'
                }
            }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'location': location,
                'note': 'Erro ao acessar OLX'
            }

class FacebookScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def search_facebook_marketplace(self, query: str, location: str = "") -> Dict[str, Any]:
        """
        Tenta buscar no Facebook Marketplace (limitado sem autenticação)
        
        Args:
            query: Termo de busca
            location: Localização para filtrar resultados
            
        Returns:
            Dicionário com resultado da tentativa
        """
        try:
            # URL do Facebook Marketplace
            url = f"https://www.facebook.com/marketplace/{location.lower()}/search/?query={query}"
            
            print(f"Tentando acessar Facebook: {url}")
            
            # Fazer requisição
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Procurar por conteúdo de marketplace
                listings = []
                
                # Procurar por elementos que possam ser anúncios
                potential_elements = soup.find_all(['div', 'span', 'a'], string=True)
                
                for element in potential_elements[:50]:
                    text = element.get_text(strip=True)
                    if len(text) > 20 and len(text) < 200:
                        listings.append({
                            'content': text,
                            'html_section': str(element)[:300]
                        })
                
                return {
                    'success': True,
                    'url': url,
                    'query': query,
                    'location': location,
                    'html_content': response.text,
                    'css_links': [],
                    'js_links': [],
                    'structured_data': {
                        'listings': listings[:10],  # Limitar resultados
                        'total_found': len(listings),
                        'page_title': soup.title.get_text() if soup.title else '',
                        'note': 'Facebook pode requerer login para resultados completos'
                    },
                    'metadata': {
                        'status_code': response.status_code,
                        'content_length': len(response.text),
                        'method': 'requests_only'
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f'Status code: {response.status_code}',
                    'query': query,
                    'location': location,
                    'note': 'Facebook bloqueou acesso (provavelmente requer login)'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'location': location,
                'note': 'Facebook Marketplace geralmente requer autenticação'
            }
