#!/usr/bin/env python3
"""
Scraping preciso para GTX 1060 - Filtra apenas produtos relevantes
"""

import requests
from bs4 import BeautifulSoup
import re
import json

class ScraperPreciso:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive'
        })
    
    def buscar_gtx1060_preciso(self):
        """Busca GTX 1060 com filtro preciso"""
        
        try:
            # URL específica para GTX 1060
            url = "https://lista.mercadolivre.com.br/gtx-1060#D[A:gtx%201060]"
            
            print(f"🔍 Buscando GTX 1060 em: {url}")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Lista para produtos relevantes
            produtos_relevantes = []
            
            # Palavras-chave para GTX 1060
            keywords_gtx1060 = [
                'gtx 1060', 'gtx1060', 'geforce gtx 1060',
                'gtx 1060 ti', 'gtx1060ti', 'geforce gtx 1060 ti',
                'nvidia gtx 1060', 'nvidia gtx1060'
            ]
            
            # Procurar por cards de produtos
            produtos = soup.find_all(['li', 'div'], class_=lambda x: x and (
                'ui-search-layout' in str(x).lower() or
                'search-result' in str(x).lower() or
                'item' in str(x).lower() or
                'card' in str(x).lower() or
                'poly-card' in str(x).lower()
            ))
            
            print(f"📊 Encontrados {len(produtos)} cards de produtos")
            
            for produto in produtos:
                try:
                    # Extrair título
                    titulo_elem = produto.find(['h2', 'h3', 'span', 'a'], string=True)
                    if not titulo_elem:
                        titulo_elem = produto.find('a')
                    
                    titulo = titulo_elem.get_text(strip=True).lower() if titulo_elem else ''
                    
                    # Verificar se o título contém GTX 1060
                    if not any(keyword in titulo for keyword in keywords_gtx1060):
                        continue
                    
                    # Extrair preço
                    preco_elem = produto.find(['span', 'div'], class_=lambda x: x and (
                        'price' in str(x).lower() or
                        'price-tag' in str(x).lower() or
                        'money' in str(x).lower()
                    ))
                    
                    preco = preco_elem.get_text(strip=True) if preco_elem else ''
                    
                    # Extrair link
                    link_elem = produto.find('a', href=True)
                    link = link_elem.get('href') if link_elem else ''
                    
                    # Extrair imagem
                    img_elem = produto.find('img', src=True)
                    imagem = img_elem.get('src') if img_elem else ''
                    
                    # Extrair localização/vendedor
                    local_elem = produto.find(['span', 'div'], class_=lambda x: x and (
                        'location' in str(x).lower() or
                        'seller' in str(x).lower() or
                        'poly' in str(x).lower()
                    ))
                    local = local_elem.get_text(strip=True) if local_elem else ''
                    
                    # Extrair avaliações
                    avaliacao_elem = produto.find(['span', 'div'], class_=lambda x: x and (
                        'review' in str(x).lower() or
                        'rating' in str(x).lower() or
                        'stars' in str(x).lower()
                    ))
                    avaliacao = avaliacao_elem.get_text(strip=True) if avaliacao_elem else ''
                    
                    # Verificar se é realmente GTX 1060
                    if titulo and ('gtx' in titulo and '1060' in titulo):
                        produto_info = {
                            'titulo': titulo.title(),
                            'preco': preco,
                            'link': link,
                            'imagem': imagem,
                            'localizacao': local,
                            'avaliacao': avaliacao,
                            'relevancia': self.calcular_relevancia(titulo),
                            'html_bruto': str(produto)[:500]
                        }
                        
                        produtos_relevantes.append(produto_info)
                        print(f"✅ Produto encontrado: {titulo[:50]}...")
                
                except Exception as e:
                    continue
            
            # Ordenar por relevância
            produtos_relevantes.sort(key=lambda x: x['relevancia'], reverse=True)
            
            # Salvar resultados
            resultados = {
                'query': 'GTX 1060',
                'total_encontrados': len(produtos_relevantes),
                'data_busca': '2026-03-09',
                'produtos': produtos_relevantes[:20],  # Top 20 mais relevantes
                'resumo': {
                    'faixa_preco': self.analisar_precos(produtos_relevantes),
                    'lojas_mencionadas': self.contar_lojas(produtos_relevantes),
                    'tipos_gtx': self.classificar_tipos_gtx(produtos_relevantes)
                }
            }
            
            # Salvar JSON
            with open("gtx1060_preciso.json", "w", encoding="utf-8") as f:
                json.dump(resultados, f, indent=2, ensure_ascii=False)
            
            # Salvar HTML filtrado
            html_filtrado = self.gerar_html_filtrado(resultados)
            with open("gtx1060_preciso.html", "w", encoding="utf-8") as f:
                f.write(html_filtrado)
            
            print(f"\n📊 Resultado da busca precisa:")
            print(f"✅ {len(produtos_relevantes)} produtos GTX 1060 encontrados")
            print(f"📁 Arquivos salvos: gtx1060_preciso.json e gtx1060_preciso.html")
            
            return resultados
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            return None
    
    def calcular_relevancia(self, titulo):
        """Calcula pontuação de relevância do produto"""
        score = 0
        
        # Pontos por termos exatos
        if 'gtx 1060' in titulo:
            score += 10
        elif 'gtx1060' in titulo:
            score += 9
        
        # Bônus por termos específicos
        if 'ti' in titulo:
            score += 2
        if '6gb' in titulo or '8gb' in titulo:
            score += 1
        if 'nvidia' in titulo:
            score += 1
        if 'geforce' in titulo:
            score += 1
        
        # Penalidade por termos irrelevantes
        if 'rx' in titulo or 'radeon' in titulo:
            score -= 5
        if 'rtx' in titulo:
            score -= 5
        
        return max(0, score)
    
    def analisar_precos(self, produtos):
        """Analisa faixa de preços"""
        precos = []
        for produto in produtos:
            preco = produto['preco']
            # Extrair números do preço
            numeros = re.findall(r'R\$\s*([\d\.]+)', preco)
            if numeros:
                precos.append(float(numeros[0].replace('.', '')))
        
        if precos:
            return {
                'menor_preco': min(precos),
                'maior_preco': max(precos),
                'preco_medio': sum(precos) / len(precos),
                'quantidade_precos': len(precos)
            }
        return None
    
    def contar_lojas(self, produtos):
        """Conta menções de lojas"""
        lojas = {}
        for produto in produtos:
            titulo = produto['titulo'].lower()
            if 'magazine' in titulo:
                lojas['Magazine Luiza'] = lojas.get('Magazine Luiza', 0) + 1
            elif 'americanas' in titulo:
                lojas['Americanas'] = lojas.get('Americanas', 0) + 1
            elif 'kabum' in titulo:
                lojas['Kabum'] = lojas.get('Kabum', 0) + 1
            elif 'terabyte' in titulo:
                lojas['Terabyte'] = lojas.get('Terabyte', 0) + 1
        
        return lojas
    
    def classificar_tipos_gtx(self, produtos):
        """Classifica os tipos de GTX 1060"""
        tipos = {'GTX 1060': 0, 'GTX 1060 Ti': 0, 'Outros': 0}
        
        for produto in produtos:
            titulo = produto['titulo'].lower()
            if 'ti' in titulo:
                tipos['GTX 1060 Ti'] += 1
            elif 'gtx 1060' in titulo or 'gtx1060' in titulo:
                tipos['GTX 1060'] += 1
            else:
                tipos['Outros'] += 1
        
        return tipos
    
    def gerar_html_filtrado(self, resultados):
        """Gera HTML com apenas os produtos relevantes"""
        html = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resultados GTX 1060 - Scraping Preciso</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .produto { background: white; margin: 15px 0; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .titulo { font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 10px; }
        .preco { font-size: 24px; color: #27ae60; font-weight: bold; margin: 10px 0; }
        .info { color: #7f8c8d; margin: 5px 0; }
        .relevancia { background: #3498db; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; }
        .resumo { background: #ecf0f1; padding: 15px; border-radius: 8px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Resultados Precisos para GTX 1060</h1>
        <p>Total encontrados: {} produtos</p>
        <p>Data da busca: {}</p>
    </div>
    
    <div class="resumo">
        <h2>📊 Resumo da Busca</h2>
        {}
    </div>
    
    <h2>🎮 Produtos GTX 1060 Encontrados</h2>
""".format(resultados['total_encontrados'], resultados['data_busca'], self.gerar_resumo_html(resultados['resumo']))
        
        for produto in resultados['produtos']:
            html += f"""
    <div class="produto">
        <div class="titulo">{produto['titulo']}</div>
        <div class="preco">{produto['preco']}</div>
        <div class="info">📍 {produto['localizacao'] or 'Local não informado'}</div>
        <div class="info">⭐ {produto['avaliacao'] or 'Sem avaliação'}</div>
        <div class="info">🔗 <a href="{produto['link']}" target="_blank">Ver produto</a></div>
        <div class="relevancia">Relevância: {produto['relevancia']}/10</div>
    </div>"""
        
        html += """
</body>
</html>"""
        return html
    
    def gerar_resumo_html(self, resumo):
        """Gera HTML do resumo"""
        html = ""
        
        if resumo.get('faixa_preco'):
            fp = resumo['faixa_preco']
            html += f"<p>💰 Faixa de preço: R${fp['menor_preco']:.2f} - R${fp['maior_preco']:.2f}</p>"
            html += f"<p>📈 Preço médio: R${fp['preco_medio']:.2f}</p>"
        
        if resumo.get('tipos_gtx'):
            tipos = resumo['tipos_gtx']
            html += f"<p>🎮 Tipos encontrados: {tipos['GTX 1060']} normais, {tipos['GTX 1060 Ti']} Ti</p>"
        
        if resumo.get('lojas_mencionadas'):
            lojas = resumo['lojas_mencionadas']
            html += f"<p>🏪 Lojas mencionadas: {', '.join(lojas.keys())}</p>"
        
        return html

if __name__ == "__main__":
    print("🎯 Iniciando scraping preciso para GTX 1060...")
    print("=" * 60)
    
    scraper = ScraperPreciso()
    resultados = scraper.buscar_gtx1060_preciso()
    
    if resultados:
        print("\n✅ Scraping preciso concluído com sucesso!")
        print("📁 Arquivos criados:")
        print("   - gtx1060_preciso.json (dados estruturados)")
        print("   - gtx1060_preciso.html (visualização)")
    else:
        print("\n❌ Falha no scraping preciso")
