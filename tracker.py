import urllib.request, urllib.parse, json, re, os, datetime, time, subprocess, sys, random

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
CHECK_INTERVAL = 30  # seconds between checks
MAX_DURATION = 5 * 3600 + 50 * 60  # 5 hours 50 minutes

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8',
    'Cache-Control': 'no-cache'
}

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("  ⚠️ Telegram not configured"); return
    try:
        data = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}).encode()
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=data))
        print("  ✅ Telegram sent!")
    except Exception as e:
        print(f"  ❌ Telegram error: {e}")

def fetch(url):
    u = url + (f"?v={random.randint(1000,9999)}" if '?' not in url else f"&v={random.randint(1000,9999)}")
    return urllib.request.urlopen(urllib.request.Request(u, headers=HEADERS), timeout=30).read().decode('utf-8')

def check_stock(html):
    has_add = 'הוספה לסל' in html
    has_out = 'אזל מהמלאי' in html
    has_outclass = 'outofstock' in html.lower()
    has_inclass = 'instock' in html.lower()
    if has_out or has_outclass:
        return False
    if has_add or has_inclass:
        return True
    return False

def extract_info(html, book):
    if not book.get('name'):
        m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if not m: m = re.search(r'<title>(.*?)</title>', html)
        if m:
            name = m.group(1).replace(' - סיפור חוזר', '').replace('&#8211;', '-').strip()
            if name: book['name'] = name
    if not book.get('image'):
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if m: book['image'] = m.group(1)
    if not book.get('product_id'):
        m = re.search(r'data-product_id="(\d+)"', html)
        if not m: m = re.search(r'value="(\d+)"\s*name="add-to-cart"', html)
        if m: book['product_id'] = m.group(1)

def git_push():
    try:
        subprocess.run(['git', 'config', 'user.name', 'Bot'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'bot@local'], check=True, capture_output=True)
        subprocess.run(['git', 'add', 'books.json'], check=True, capture_output=True)
        r = subprocess.run(['git', 'diff', '--staged', '--quiet'], capture_output=True)
        if r.returncode != 0:  # there are changes
            subprocess.run(['git', 'commit', '-m', 'Update stock [skip ci]'], check=True, capture_output=True)
            subprocess.run(['git', 'push'], check=True, capture_output=True)
            print("  📤 Pushed to GitHub")
    except Exception as e:
        print(f"  ⚠️ Git push error: {e}")

def scan_once(books):
    changed = False
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for i, book in enumerate(books):
        try:
            html = fetch(book['url'])
            extract_info(html, book)
            
            in_stock = check_stock(html)
            was_in_stock = book.get('in_stock', False)
            
            status = "✅ IN STOCK" if in_stock else "❌ out"
            print(f"  [{i+1}/{len(books)}] {book.get('name', '???')}: {status}")
            
            if in_stock and not was_in_stock:
                print(f"  🎉 BACK IN STOCK! Notifying...")
                msg = f"📗 <b>ספר חזר למלאי!</b>\n\n<b>{book.get('name', 'ספר')}</b> זמין לרכישה!\n"
                msg += f"\n🔗 <a href='{book['url']}'>לעמוד הספר</a>"
                if book.get('product_id'):
                    msg += f"\n🛒 <a href='https://rebooks.org.il/?add-to-cart={book['product_id']}'>קנה בקליק אחד!</a>"
                send_telegram(msg)
                changed = True
            elif not in_stock and was_in_stock:
                print(f"  📉 Went out of stock")
                send_telegram(f"📕 <b>{book.get('name', 'ספר')}</b> אזל מהמלאי. נמשיך לעקוב!")
                changed = True
            
            if book.get('in_stock') != in_stock:
                changed = True
            book['in_stock'] = in_stock
            book['last_checked'] = now
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    return changed

def save(books):
    with open('books.json', 'w', encoding='utf-8') as f:
        json.dump(books, f, ensure_ascii=False, indent=4)

def run():
    loop = '--loop' in sys.argv
    start = time.time()
    cycle = 0
    
    while True:
        cycle += 1
        with open('books.json', 'r', encoding='utf-8') as f:
            books = json.load(f)
        
        elapsed = time.time() - start
        if loop:
            print(f"\n{'='*50}")
            print(f"🔄 Cycle {cycle} | {len(books)} books | {elapsed/60:.0f}min elapsed")
            print(f"{'='*50}")
        else:
            print(f"\n📖 Scanning {len(books)} books...")
        
        changed = scan_once(books)
        save(books)
        
        if changed:
            git_push()
        
        if not loop:
            if changed:
                git_push()
            break
        
        if elapsed >= MAX_DURATION:
            print("\n⏰ Max duration reached, exiting for restart")
            git_push()  # final push
            break
        
        print(f"  💤 Next check in {CHECK_INTERVAL}s...")
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    run()
