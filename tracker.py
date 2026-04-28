import urllib.request
import urllib.parse
import json
import re
import os
import datetime
import sys

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Telegram credentials missing, skipping notification.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req)
        print("✅ Sent Telegram notification.")
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")

def fetch_page(url):
    """Fetch a page with browser-like headers to bypass bot protection."""
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
    return urllib.request.urlopen(req, timeout=30).read().decode('utf-8')

def check_stock(html):
    """
    Check stock status using multiple methods for reliability.
    Returns (is_in_stock: bool, reason: str)
    """
    # Method 1: Check for the Hebrew "Add to Cart" button text
    has_add_to_cart = 'הוספה לסל' in html
    
    # Method 2: Check for out-of-stock indicators
    has_out_of_stock_text = 'אזל מהמלאי' in html
    
    # Method 3: Check for WooCommerce stock CSS classes
    has_outofstock_class = 'outofstock' in html.lower()
    has_instock_class = 'instock' in html.lower()
    
    # Method 4: Check for the actual add-to-cart button element
    has_cart_button = bool(re.search(r'<button[^>]*add.to.cart[^>]*>', html, re.IGNORECASE))
    
    # Method 5: Check for WooCommerce stock status meta
    stock_meta = re.search(r'"availability"\s*:\s*"([^"]*)"', html)
    
    print(f"   🔍 Detection results:")
    print(f"      - 'הוספה לסל' found: {has_add_to_cart}")
    print(f"      - 'אזל מהמלאי' found: {has_out_of_stock_text}")
    print(f"      - CSS class 'instock': {has_instock_class}")
    print(f"      - CSS class 'outofstock': {has_outofstock_class}")
    print(f"      - Add-to-cart button element: {has_cart_button}")
    if stock_meta:
        print(f"      - Schema.org availability: {stock_meta.group(1)}")
    
    # Decision logic: multiple signals
    if has_out_of_stock_text or has_outofstock_class:
        return False, "Out of stock (explicit out-of-stock indicator found)"
    
    if has_add_to_cart or has_cart_button or has_instock_class:
        return True, "In stock (add-to-cart button or instock class found)"
    
    # Default: assume out of stock if no positive signal
    return False, "Unknown - assuming out of stock (no positive stock signals)"

def extract_name(html):
    """Extract book name from the page."""
    # Try og:title first (most reliable)
    match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if match:
        name = match.group(1).replace(' - סיפור חוזר', '').strip()
        if name:
            return name
    
    # Try <title> tag
    match = re.search(r'<title>(.*?)</title>', html)
    if match:
        name = match.group(1).replace(' - סיפור חוזר', '').replace('&#8211;', '-').strip()
        if name:
            return name
    
    # Try h1 product title (various class formats)
    match = re.search(r'<h1[^>]*product_title[^>]*>(.*?)</h1>', html, re.DOTALL)
    if match:
        name = re.sub(r'<[^>]+>', '', match.group(1)).strip()
        if name:
            return name
    
    return None

def extract_image(html):
    """Extract book image from the page."""
    match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if match:
        return match.group(1)
    return None

def extract_product_id(html):
    """Extract WooCommerce product ID."""
    match = re.search(r'data-product_id="(\d+)"', html)
    if not match:
        match = re.search(r'value="(\d+)"\s*name="add-to-cart"', html)
    if not match:
        match = re.search(r'"product_id"\s*:\s*(\d+)', html)
    if match:
        return match.group(1)
    return None

def add_new_book(books, new_url):
    """Add a new book URL to the tracking list."""
    # Normalize URL
    new_url = new_url.strip().rstrip('/')
    
    # Check if already tracked
    for book in books:
        existing = book['url'].strip().rstrip('/')
        if existing == new_url:
            print(f"⚠️  Book URL already tracked: {new_url}")
            return False
    
    books.append({
        "url": new_url if new_url.endswith('/') else new_url + '/',
        "name": "",
        "image": "",
        "in_stock": False,
        "last_checked": "",
        "product_id": ""
    })
    print(f"✅ Added new book URL: {new_url}")
    return True

def main():
    with open('books.json', 'r', encoding='utf-8') as f:
        books = json.load(f)

    # Check if a new book URL was provided via environment variable
    new_book_url = os.environ.get('NEW_BOOK_URL', '').strip()
    if new_book_url:
        print(f"\n📚 Adding new book: {new_book_url}")
        if add_new_book(books, new_book_url):
            send_telegram_message(f"📚 <b>ספר חדש נוסף למעקב!</b>\n\n🔗 <a href='{new_book_url}'>לעמוד הספר</a>\n\nהמערכת תתחיל לעקוב אחר המלאי שלו אוטומטית.")

    print(f"\n{'='*60}")
    print(f"📖 ReBooks Tracker - Scanning {len(books)} books")
    print(f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    for i, book in enumerate(books, 1):
        url = book['url']
        print(f"\n📗 [{i}/{len(books)}] Checking: {book.get('name') or url}")
        
        try:
            html = fetch_page(url)
            print(f"   ✅ Page fetched successfully ({len(html)} chars)")
            
            # Extract name if missing
            if not book.get('name'):
                name = extract_name(html)
                if name:
                    book['name'] = name
                    print(f"   📝 Name extracted: {name}")
                else:
                    print(f"   ⚠️  Could not extract name")
            
            # Extract image if missing
            if not book.get('image'):
                image = extract_image(html)
                if image:
                    book['image'] = image
                    print(f"   🖼️  Image extracted: {image[:60]}...")
                else:
                    print(f"   ⚠️  No image found on page")

            # Extract product ID if missing
            if not book.get('product_id'):
                pid = extract_product_id(html)
                if pid:
                    book['product_id'] = pid
                    print(f"   🆔 Product ID extracted: {pid}")

            # Check stock status
            currently_in_stock, reason = check_stock(html)
            previous_status = book.get('in_stock', False)
            
            print(f"   📊 Stock status: {'✅ IN STOCK' if currently_in_stock else '❌ OUT OF STOCK'}")
            print(f"      Reason: {reason}")
            print(f"      Previous status: {'IN STOCK' if previous_status else 'OUT OF STOCK'}")
            
            # Notify on stock change (out -> in)
            if currently_in_stock and not previous_status:
                print(f"   🎉 STATUS CHANGED! Sending notification...")
                msg = f"📗 <b>ספר חזר למלאי!</b>\n\nהספר: <b>{book.get('name', 'ספר ללא שם')}</b> זמין כעת לרכישה!\n"
                msg += f"\n🔗 <a href='{url}'>לעמוד הספר</a>"
                if book.get('product_id'):
                    buy_link = f"https://rebooks.org.il/?add-to-cart={book['product_id']}"
                    msg += f"\n🛒 <a href='{buy_link}'>קליק אחד להוספה לעגלה וקנייה!</a>"
                
                send_telegram_message(msg)
            
            # Notify on stock change (in -> out)
            elif not currently_in_stock and previous_status:
                print(f"   📉 Book went OUT OF STOCK. Sending notification...")
                msg = f"📕 <b>ספר אזל מהמלאי</b>\n\nהספר: <b>{book.get('name', 'ספר ללא שם')}</b> כבר לא זמין.\n\nהמערכת תמשיך לעקוב ותודיע כשיחזור!"
                send_telegram_message(msg)
                
            book['in_stock'] = currently_in_stock
            book['last_checked'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        except Exception as e:
            print(f"   ❌ Error checking: {e}")

    # Write updated data back
    with open('books.json', 'w', encoding='utf-8') as f:
        json.dump(books, f, ensure_ascii=False, indent=4)
    
    print(f"\n{'='*60}")
    print(f"✅ Scan complete! Updated books.json")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
