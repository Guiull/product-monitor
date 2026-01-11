import os
import time
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from datetime import datetime
import json
import logging
from pathlib import Path

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProductMonitor:
    def __init__(self):
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 300))  # 5 minutos padrão
        self.notified_products_file = 'notified_products.json'
        self.notified_products = self.load_notified_products()
        
    def load_notified_products(self):
        """Carrega lista de produtos já notificados"""
        if Path(self.notified_products_file).exists():
            with open(self.notified_products_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_notified_products(self):
        """Salva lista de produtos notificados"""
        with open(self.notified_products_file, 'w') as f:
            json.dump(self.notified_products, f, indent=2)
    
    def fetch_page(self, url):
        """Busca o conteúdo da página"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar página: {e}")
            return None
    
    def parse_products(self, html):
        """Extrai produtos da página"""
        soup = BeautifulSoup(html, 'html.parser')
        products = []
        
        # Procura por produtos - ajuste os seletores conforme a estrutura do site
        product_items = soup.find_all('div', class_='product-miniature')
        
        if not product_items:
            # Tenta seletores alternativos
            product_items = soup.find_all('article', class_='product-miniature')
        
        if not product_items:
            product_items = soup.find_all('div', class_='js-product-miniature')
        
        for item in product_items:
            try:
                # Extrai nome do produto
                title_elem = item.find('h2', class_='product-title') or \
                            item.find('h3', class_='product-title') or \
                            item.find('a', class_='product-title')
                
                if not title_elem:
                    title_elem = item.find('a', {'itemprop': 'name'})
                
                title = title_elem.get_text(strip=True) if title_elem else "Sem título"
                
                # Extrai link
                link_elem = item.find('a', href=True)
                link = link_elem['href'] if link_elem else ""
                
                # Extrai preço
                price_elem = item.find('span', class_='price') or \
                            item.find('span', {'itemprop': 'price'})
                price = price_elem.get_text(strip=True) if price_elem else "Preço não disponível"
                
                # Verifica disponibilidade
                availability = "Disponível"
                out_of_stock = item.find('span', class_='product-availability') or \
                              item.find('div', class_='product-availability')
                
                if out_of_stock and 'agotado' in out_of_stock.get_text().lower():
                    availability = "Esgotado"
                
                products.append({
                    'title': title,
                    'link': link,
                    'price': price,
                    'availability': availability
                })
                
            except Exception as e:
                logger.warning(f"Erro ao processar produto: {e}")
                continue
        
        return products
    
    def check_keywords(self, product, keywords):
        """Verifica se o produto contém as keywords"""
        title_lower = product['title'].lower()
        return all(keyword.lower() in title_lower for keyword in keywords)
    
    def send_email(self, product, keywords_matched):
        """Envia email de alerta"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'🚨 Produto Disponível: {product["title"][:50]}...'
            msg['From'] = self.email_user
            msg['To'] = self.email_user
            
            # HTML email
            html = f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background-color: #4CAF50; color: white; padding: 20px; text-align: center;">
                        <h1>✅ Produto Disponível!</h1>
                    </div>
                    <div style="padding: 20px; background-color: #f5f5f5;">
                        <h2 style="color: #333;">{product['title']}</h2>
                        <p style="font-size: 16px;"><strong>Preço:</strong> {product['price']}</p>
                        <p style="font-size: 16px;"><strong>Status:</strong> <span style="color: green;">{product['availability']}</span></p>
                        <p style="font-size: 14px;"><strong>Keywords encontradas:</strong> {', '.join(keywords_matched)}</p>
                        <div style="margin: 30px 0;">
                            <a href="{product['link']}" 
                               style="background-color: #4CAF50; color: white; padding: 15px 30px; 
                                      text-decoration: none; border-radius: 5px; display: inline-block;">
                                Ver Produto
                            </a>
                        </div>
                        <p style="font-size: 12px; color: #666;">
                            Alerta enviado em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}
                        </p>
                    </div>
                </body>
            </html>
            """
            
            msg.attach(MIMEText(html, 'html'))
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.email_user, self.email_password)
                server.send_message(msg)
            
            logger.info(f"Email enviado para: {product['title']}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar email: {e}")
            return False
    
    def monitor_site(self, config):
        """Monitora um site específico"""
        url = config['url']
        keywords = config['keywords']
        site_name = config.get('name', 'Site')
        
        logger.info(f"Verificando {site_name}...")
        
        html = self.fetch_page(url)
        if not html:
            return
        
        products = self.parse_products(html)
        logger.info(f"Encontrados {len(products)} produtos em {site_name}")
        
        for product in products:
            if self.check_keywords(product, keywords):
                product_id = f"{site_name}_{product['title']}"
                
                # Verifica se já foi notificado
                if product_id not in self.notified_products:
                    logger.info(f"Novo produto encontrado: {product['title']}")
                    
                    if self.send_email(product, keywords):
                        self.notified_products[product_id] = {
                            'notified_at': datetime.now().isoformat(),
                            'title': product['title'],
                            'link': product['link']
                        }
                        self.save_notified_products()
                else:
                    logger.debug(f"Produto já notificado anteriormente: {product['title']}")
    
    def run(self):
        """Loop principal de monitoramento"""
        # Carrega configuração de sites
        sites_config = self.load_sites_config()
        
        logger.info("Iniciando monitoramento...")
        logger.info(f"Intervalo de verificação: {self.check_interval} segundos")
        logger.info(f"Monitorando {len(sites_config)} site(s)")
        
        while True:
            try:
                for config in sites_config:
                    self.monitor_site(config)
                
                logger.info(f"Aguardando {self.check_interval} segundos até a próxima verificação...")
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitoramento interrompido pelo usuário")
                break
            except Exception as e:
                logger.error(f"Erro no loop principal: {e}")
                time.sleep(60)  # Aguarda 1 minuto antes de tentar novamente
    
    def load_sites_config(self):
        """Carrega configuração de sites do arquivo"""
        config_file = 'sites_config.json'
        
        if Path(config_file).exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Configuração padrão
            default_config = [{
                'name': 'Gameria - One Piece Card Game',
                'url': 'https://gameria.es/4-juegos-de-cartas/s-6/juegos_de_cartas-one_piece_card_game?current_page=1&lasIdP=18477',
                'keywords': ['One Piece Card Game', 'OP-17']
            }]
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            return default_config

if __name__ == '__main__':
    monitor = ProductMonitor()
    monitor.run()
