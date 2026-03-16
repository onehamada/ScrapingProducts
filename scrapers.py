import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
from typing import Dict, Any

class OLXScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def search_olx(self, query: str, location: str = "brasil") -> Dict[str, Any]:
        """
        Realiza uma busca na OLX e retorna o conteúdo completo da página
        
        Args:
            query: Termo de busca
            location: Localização para filtrar resultados
            
        Returns:
            Dicionário com HTML, CSS e conteúdo estruturado
        """
        try:
            # Construir URL da busca - usando URL mais genérica
            formatted_query = query.replace(' ', '+')
            url = f"https://www.olx.com.br/brasil?q={formatted_query}&sf=1"
            
            # Tentar usar requests primeiro (mais rápido)
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                # Parsear com BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extrair informações estruturadas
                listings = []
                ad_elements = soup.find_all(['div', 'article'], class_=lambda x: x and ('ad' in x.lower() or 'listing' in x.lower() or 'card' in x.lower()))
                
                for ad in ad_elements[:20]:
                    try:
                        title_elem = ad.find(['h2', 'h3', 'span'], class_=lambda x: x and ('title' in x.lower() or 'name' in x.lower()))
                        price_elem = ad.find(['span', 'div'], class_=lambda x: x and ('price' in x.lower() or 'valor' in x.lower()))
                        link_elem = ad.find('a')
                        
                        listing_data = {
                            'title': title_elem.get_text(strip=True) if title_elem else '',
                            'price': price_elem.get_text(strip=True) if price_elem else '',
                            'link': link_elem.get('href') if link_elem else '',
                            'html_section': str(ad)
                        }
                        
                        if listing_data['title'] or listing_data['price']:
                            listings.append(listing_data)
                    except Exception:
                        continue
                
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
                        'page_title': soup.title.get_text() if soup.title else ''
                    },
                    'metadata': {
                        'status_code': response.status_code,
                        'content_length': len(response.text),
                        'method': 'requests'
                    }
                }
                
            except Exception as e:
                # Fallback para Selenium se requests falhar
                print(f"Requests falhou, tentando Selenium: {e}")
            
            # Usar Chrome instalado no sistema
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            driver = webdriver.Chrome(options=options)
            
            try:
                driver.get(url)
                
                # Esperar carregar conteúdo dinâmico
                time.sleep(3)
                
                # Tentar rolar a página para carregar mais conteúdo
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # Obter HTML completo
                html_content = driver.page_source
                
                # Obter CSS (links de stylesheets)
                css_links = []
                stylesheets = driver.find_elements(By.TAG_NAME, "link")
                for link in stylesheets:
                    if link.get_attribute("rel") and "stylesheet" in link.get_attribute("rel"):
                        css_links.append(link.get_attribute("href"))
                
                # Obter JavaScript
                js_links = []
                scripts = driver.find_elements(By.TAG_NAME, "script")
                for script in scripts:
                    src = script.get_attribute("src")
                    if src:
                        js_links.append(src)
                
                # Parsear HTML com BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Extrair informações estruturadas
                listings = []
                ad_elements = soup.find_all(['div', 'article'], class_=lambda x: x and ('ad' in x.lower() or 'listing' in x.lower()))
                
                for ad in ad_elements[:20]:  # Limitar para não sobrecarregar
                    try:
                        title_elem = ad.find(['h2', 'h3', 'span'], class_=lambda x: x and ('title' in x.lower() or 'name' in x.lower()))
                        price_elem = ad.find(['span', 'div'], class_=lambda x: x and ('price' in x.lower() or 'valor' in x.lower()))
                        link_elem = ad.find('a')
                        
                        listing_data = {
                            'title': title_elem.get_text(strip=True) if title_elem else '',
                            'price': price_elem.get_text(strip=True) if price_elem else '',
                            'link': link_elem.get('href') if link_elem else '',
                            'html_section': str(ad)
                        }
                        
                        if listing_data['title'] or listing_data['price']:
                            listings.append(listing_data)
                    except Exception as e:
                        continue
                
                return {
                    'success': True,
                    'url': url,
                    'query': query,
                    'location': location,
                    'html_content': html_content,
                    'css_links': css_links,
                    'js_links': js_links,
                    'structured_data': {
                        'listings': listings,
                        'total_found': len(listings),
                        'page_title': soup.title.get_text() if soup.title else ''
                    },
                    'metadata': {
                        'status_code': response.status_code,
                        'content_length': len(html_content),
                        'css_count': len(css_links),
                        'js_count': len(js_links)
                    }
                }
                
            finally:
                driver.quit()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'location': location
            }

class FacebookScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def search_facebook_marketplace(self, query: str, location: str = "") -> Dict[str, Any]:
        """
        Realiza uma busca no Facebook Marketplace e retorna o conteúdo
        
        Args:
            query: Termo de busca
            location: Localização para filtrar resultados
            
        Returns:
            Dicionário com HTML, CSS e conteúdo estruturado
        """
        try:
            # URL do Facebook Marketplace
            # Nota: Facebook requer autenticação, então vamos usar uma abordagem diferente
            url = f"https://www.facebook.com/marketplace/{location.lower()}/search/?query={query}"
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            
            driver = webdriver.Chrome(options=options, service=Service(executable_path="./chrome-win64/chromedriver.exe"))
            
            try:
                driver.get(url)
                
                # Esperar carregar
                time.sleep(5)
                
                # Tentar rolar a página
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                
                html_content = driver.page_source
                
                # Obter CSS e JS links
                css_links = []
                stylesheets = driver.find_elements(By.TAG_NAME, "link")
                for link in stylesheets:
                    if link.get_attribute("rel") and "stylesheet" in link.get_attribute("rel"):
                        css_links.append(link.get_attribute("href"))
                
                js_links = []
                scripts = driver.find_elements(By.TAG_NAME, "script")
                for script in scripts:
                    src = script.get_attribute("src")
                    if src:
                        js_links.append(src)
                
                # Parsear HTML
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Extrair listings (estrutura do Facebook pode variar)
                listings = []
                # Procurar por elementos que possam ser anúncios
                potential_ads = soup.find_all(['div', 'article'], attrs={'data-testid': True})
                
                for ad in potential_ads[:20]:
                    try:
                        ad_text = ad.get_text(strip=True)
                        if len(ad_text) > 20:  # Filtrar elementos muito curtos
                            listings.append({
                                'content': ad_text[:200],  # Primeiros 200 caracteres
                                'html_section': str(ad)[:500]  # Primeiros 500 caracteres do HTML
                            })
                    except Exception:
                        continue
                
                return {
                    'success': True,
                    'url': url,
                    'query': query,
                    'location': location,
                    'html_content': html_content,
                    'css_links': css_links,
                    'js_links': js_links,
                    'structured_data': {
                        'listings': listings,
                        'total_found': len(listings),
                        'page_title': soup.title.get_text() if soup.title else '',
                        'note': 'Facebook pode requerer login para resultados completos'
                    },
                    'metadata': {
                        'content_length': len(html_content),
                        'css_count': len(css_links),
                        'js_count': len(js_links)
                    }
                }
                
            finally:
                driver.quit()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'location': location,
                'note': 'Facebook Marketplace geralmente requer autenticação'
            }
