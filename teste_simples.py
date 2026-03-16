#!/usr/bin/env python3
"""
Teste simples para obter HTML legível da pesquisa GTX 1060
"""

import requests

def buscar_gtx1060():
    """Busca GTX 1060 com headers simples para evitar compressão"""
    
    # Headers sem compressão
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        'Accept-Encoding': 'identity',  # Sem compressão
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        # URL do Mercado Livre (fallback da OLX)
        url = "https://lista.mercadolivre.com.br/gtx-1060"
        
        print(f"🔍 Buscando em: {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Salvar HTML bruto
        with open("gtx1060_mercadolivre.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        
        print(f"✅ HTML salvo como 'gtx1060_mercadolivre.html'")
        print(f"📊 Tamanho: {len(response.text)} caracteres")
        print(f"📋 Status: {response.status_code}")
        print(f"🌐 Content-Type: {response.headers.get('content-type', 'N/A')}")
        
        # Mostrar primeiras linhas do HTML
        linhas = response.text.split('\n')[:10]
        print(f"\n📝 Primeiras linhas do HTML:")
        for i, linha in enumerate(linhas, 1):
            print(f"{i:2d}: {linha[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Buscando GTX 1060 de forma legível...")
    print("=" * 50)
    
    sucesso = buscar_gtx1060()
    
    if sucesso:
        print("\n✅ Sucesso! Abra 'gtx1060_mercadolivre.html' no navegador")
    else:
        print("\n❌ Falha na busca")
