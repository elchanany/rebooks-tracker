import urllib.request
import urllib.parse
import json
import re
import os
import datetime

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing, skipping notification.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req)
        print("Sent Telegram notification.")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def main():
    with open('books.json', 'r', encoding='utf-8') as f:
        books = json.load(f)

    for book in books:
        url = book['url']
        print(f"Checking {url}")
        
        try:
            # Use random parameter to bypass cache
            import random
            bypass_url = url + (f"?v={random.randint(1000,9999)}" if '?' not in url else f"&v={random.randint(1000,9999)}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            req = urllib.request.Request(bypass_url, headers=headers)
            html = urllib.request.urlopen(req).read().decode('utf-8')
            
            # Extract name
            if not book.get('name'):
                name_match = re.search(r'<h1 class="product_title entry-title">([^<]+)</h1>', html)
                if name_match:
                    book['name'] = name_match.group(1).strip()
            
            # Extract image
            if not book.get('image'):
                img_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
                if img_match:
                    book['image'] = img_match.group(1)

            # Extract product ID
            if not book.get('product_id'):
                # Try to find the add to cart button ID
                id_match = re.search(r'data-product_id="(\d+)"', html)
                if not id_match:
                    id_match = re.search(r'value="(\d+)" name="add-to-cart"', html)
                if id_match:
                    book['product_id'] = id_match.group(1)

            out_of_stock = 'אזל מהמלאי' in html
            add_to_cart = 'הוספה לסל' in html
            
            currently_in_stock = add_to_cart and not out_of_stock
            
            # If stock status changed to True
            if currently_in_stock and not book.get('in_stock'):
                msg = f"📗 <b>ספר חזר למלאי!</b>\n\nהספר: <b>{book.get('name', 'ספר ללא שם')}</b> זמין כעת לרכישה!\n"
                msg += f"\n🔗 <a href='{url}'>לעמוד הספר</a>"
                if book.get('product_id'):
                    buy_link = f"https://rebooks.org.il/?add-to-cart={book['product_id']}"
                    msg += f"\n🛒 <a href='{buy_link}'>קליק אחד להוספה לעגלה וקנייה!</a>"
                
                send_telegram_message(msg)
                
            book['in_stock'] = currently_in_stock
            book['last_checked'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        except Exception as e:
            print(f"Error checking {url}: {e}")

    # Write updated data back
    with open('books.json', 'w', encoding='utf-8') as f:
        json.dump(books, f, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    main()
