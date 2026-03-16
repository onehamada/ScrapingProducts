#!/usr/bin/env python3
"""
Script para decodificar e salvar o HTML da pesquisa de forma legível
"""

import requests
import json

def baixar_e_salvar_html_legivel():
    """Baixa o HTML da API e salva de forma legível"""
    
    try:
        # Fazer a requisição para a API
        response = requests.get("http://localhost:8000/scrape/olx?query=gtx%201060")
        response.raise_for_status()
        
        data = response.json()
        
        if data['success']:
            html_content = data['data']['html_content']
            
            # Salvar HTML completo
            with open("gtx1060_html_legivel.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print("✓ HTML salvo como 'gtx1060_html_legivel.html'")
            
            # Salvar dados estruturados
            structured_data = data['data']['structured_data']
            with open("gtx1060_dados_estruturados.json", "w", encoding="utf-8") as f:
                json.dump(structured_data, f, indent=2, ensure_ascii=False)
            print("✓ Dados estruturados salvos como 'gtx1060_dados_estruturados.json'")
            
            # Extrair e mostrar informações principais
            print(f"\n📊 Resumo da pesquisa:")
            print(f"Query: {data['data']['query']}")
            print(f"Location: {data['data']['location']}")
            print(f"Tamanho HTML: {len(html_content)} caracteres")
            print(f"Textos encontrados: {structured_data['total_elements']['texts']}")
            print(f"Links encontrados: {structured_data['total_elements']['links']}")
            print(f"Nota: {data['data'].get('note', 'Nenhuma')}")
            
            # Mostrar primeiros textos encontrados
            if structured_data['texts']:
                print(f"\n📝 Primeiros textos encontrados:")
                for i, text in enumerate(structured_data['texts'][:5], 1):
                    print(f"{i}. {text[:100]}...")
            
            # Mostrar primeiros links se houver
            if structured_data['links']:
                print(f"\n🔗 Primeiros links encontrados:")
                for i, link in enumerate(structured_data['links'][:3], 1):
                    print(f"{i}. {link['text'][:50]}... -> {link['url']}")
            
            return True
        else:
            print(f"✗ Erro na API: {data['error']}")
            return False
            
    except Exception as e:
        print(f"✗ Erro: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Decodificando resultado da pesquisa GTX 1060...")
    print("=" * 50)
    
    sucesso = baixar_e_salvar_html_legivel()
    
    if sucesso:
        print("\n✅ Arquivos criados com sucesso!")
        print("📁 Abra 'gtx1060_html_legivel.html' no navegador para ver o conteúdo")
    else:
        print("\n❌ Falha ao decodificar o resultado")
