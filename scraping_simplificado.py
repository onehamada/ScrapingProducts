#!/usr/bin/env python3
"""
Scraping simplificado e preciso para GTX 1060
"""

import requests
from bs4 import BeautifulSoup
import re
import json

def buscar_gtx1060_simplificado():
    """Busca GTX 1060 de forma simplificada e precisa"""
    
    try:
        # Headers simples
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        }
        
        url = "https://lista.mercadolivre.com.br/gtx-1060"
        
        print(f"🔍 Buscando GTX 1060 em: {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        produtos_encontrados = []
        
        # Palavras-chave para filtro
        keywords = ['gtx 1060', 'gtx1060', 'geforce gtx 1060', 'nvidia gtx 1060']
        
        # Procurar por todos os elementos que podem ser produtos
        todos_links = soup.find_all('a', href=True)
        
        print(f"📊 Analisando {len(todos_links)} links...")
        
        for link in todos_links:
            try:
                href = link.get('href', '')
                texto = link.get_text(strip=True).lower()
                
                # Verificar se é um produto e contém GTX 1060
                if (('/p/' in href or 'produto' in href) and 
                    any(keyword in texto for keyword in keywords)):
                    
                    # Encontrar o elemento pai do produto
                    produto_elem = link.find_parent(['div', 'li', 'article'])
                    
                    if produto_elem:
                        # Extrair informações do produto
                        titulo = texto.title()
                        
                        # Procurar preço
                        preco = ''
                        preco_elem = produto_elem.find(['span', 'div'], string=re.compile(r'R\$\s*\d+'))
                        if preco_elem:
                            preco = preco_elem.get_text(strip=True)
                        else:
                            # Tentar encontrar preço no texto
                            preco_match = re.search(r'R\$\s*[\d\.]+', produto_elem.get_text())
                            if preco_match:
                                preco = preco_match.group()
                        
                        # Montar link completo
                        if href.startswith('/'):
                            link_completo = 'https://www.mercadolivre.com.br' + href
                        else:
                            link_completo = href
                        
                        # Calcular relevância
                        relevancia = 0
                        if 'gtx 1060' in texto:
                            relevancia += 10
                        if '6gb' in texto:
                            relevancia += 2
                        if 'ti' in texto:
                            relevancia += 2
                        if 'nvidia' in texto:
                            relevancia += 1
                        
                        produto_info = {
                            'titulo': titulo,
                            'preco': preco,
                            'link': link_completo,
                            'relevancia': relevancia,
                            'texto_original': texto
                        }
                        
                        # Evitar duplicados
                        if not any(p['link'] == link_completo for p in produtos_encontrados):
                            produtos_encontrados.append(produto_info)
                            print(f"✅ {titulo[:60]}... - {preco}")
                
            except Exception as e:
                continue
        
        # Ordenar por relevância
        produtos_encontrados.sort(key=lambda x: x['relevancia'], reverse=True)
        
        # Limitar aos melhores resultados
        produtos_finais = produtos_encontrados[:15]
        
        # Salvar resultados
        resultados = {
            'query': 'GTX 1060',
            'total_encontrados': len(produtos_finais),
            'data_busca': '2026-03-09',
            'produtos': produtos_finais
        }
        
        # Salvar JSON
        with open("gtx1060_resultados.json", "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
        
        # Gerar HTML simples
        try:
            html = gerar_html_simples(resultados)
            with open("gtx1060_resultados.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("✅ HTML gerado com sucesso")
        except Exception as e:
            print(f"⚠️ Erro ao gerar HTML: {e}")
            print("📁 Apenas JSON foi salvo")
        
        # Mostrar resumo
        print(f"\n📊 RESUMO DA BUSCA:")
        print(f"✅ {len(produtos_finais)} produtos GTX 1060 encontrados")
        print(f"📁 Arquivos salvos:")
        print(f"   - gtx1060_resultados.json (dados)")
        print(f"   - gtx1060_resultados.html (visualização)")
        
        # Análise rápida
        precos = []
        for p in produtos_finais:
            preco_match = re.search(r'[\d\.]+', p['preco'])
            if preco_match:
                precos.append(float(preco_match.group().replace('.', '')))
        
        if precos:
            print(f"\n💰 ANÁLISE DE PREÇOS:")
            print(f"   Menor preço: R${min(precos):.2f}")
            print(f"   Maior preço: R${max(precos):.2f}")
            print(f"   Média: R${sum(precos)/len(precos):.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def gerar_html_simples(resultados):
    """Gera HTML simples com os resultados"""
    html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>GTX 1060 - Resultados Precisos</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; text-align: center; }
        .produto { background: white; margin: 15px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .titulo { font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 10px; }
        .preco { font-size: 24px; color: #27ae60; font-weight: bold; margin: 10px 0; }
        .link { margin: 10px 0; }
        .link a { background: #3498db; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; }
        .link a:hover { background: #2980b9; }
        .relevancia { background: #e74c3c; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎮 GTX 1060 - Resultados Filtrados</h1>
        <p>Total encontrados: {} produtos</p>
        <p>Data: {}</p>
    </div>
""".format(resultados['total_encontrados'], resultados['data_busca'])
    
    for i, produto in enumerate(resultados['produtos'], 1):
        html += f"""
    <div class="produto">
        <div class="titulo">#{i} {produto['titulo']}</div>
        <div class="preco">{produto['preco'] or 'Preço não informado'}</div>
        <div class="relevancia">Relevância: {produto['relevancia']}/10</div>
        <div class="link">
            <a href="{produto['link']}" target="_blank">Ver Produto no Mercado Livre</a>
        </div>
    </div>"""
    
    html += """
</body>
</html>"""
    return html

if __name__ == "__main__":
    print("🎯 Iniciando scraping simplificado e preciso para GTX 1060...")
    print("=" * 60)
    
    sucesso = buscar_gtx1060_simplificado()
    
    if sucesso:
        print("\n✅ Scraping concluído com sucesso!")
        print("📁 Abra 'gtx1060_resultados.html' no navegador para visualizar")
    else:
        print("\n❌ Falha no scraping")
