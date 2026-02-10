import requests
import json
import re
import time
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from app.rag import add_property
from app.config import OLLAMA_URL, LLM_MODEL

llm = ChatOllama(
    base_url=OLLAMA_URL,
    model=LLM_MODEL, 
    temperature=0,
    format="json"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

EXTRACTION_PROMPT = """
You are a Data Extraction Agent. 
Extract real estate listings from the following text and return them as a JSON array.
Each object must have: "title", "price" (number only), "location", "description", "features".

TEXT TO ANALYZE:
{text_data}

OUTPUT FORMAT:
{{
    "listings": [
        {{
            "title": "...",
            "price": 100000,
            "location": "...",
            "description": "...",
            "features": "..."
        }}
    ]
}}
"""

CITY_SLUGS = {
    "софия": "sofiya", "софія": "sofiya",
    "пловдив": "plovdiv",
    "варна": "varna",
    "бургас": "burgas",
    "русе": "ruse",
    "стара загора": "stara-zagora",
    "плевен": "pleven",
    "велико търново": "veliko-tarnovo",
    "благоевград": "blagoevgrad",
    "шумен": "shumen",
    "добрич": "dobrich",
    "сливен": "sliven",
    "перник": "pernik",
    "хасково": "haskovo",
    "ямбол": "yambol",
    "пазарджик": "pazardzhik",
    "враца": "vratsa",
    "габрово": "gabrovo",
    "кюстендил": "kyustendil",
    "видин": "vidin",
    "монтана": "montana",
    "ловеч": "lovech",
    "търговище": "targovishte",
    "разград": "razgrad",
    "силистра": "silistra",
    "кърджали": "kardzhali",
    "смолян": "smolyan",
    "несебър": "nesebar",
    "созопол": "sozopol",
    "банско": "bansko",
    "сандански": "sandanski",
    "поморие": "pomorie",
    "самоков": "samokov",
}

SOFIA_NEIGHBORHOODS = {
    "малинова долина": "malinova-dolina",
    "манастирски ливади": "manastirski-livadi",
    "красно село": "krasno-selo",
    "овча купел": "ovcha-kupel",
    "княжево": "knyazhevo",
    "бояна": "boyana",
    "горна баня": "gorna-banya",
    "банкя": "bankya",
    "бистрица": "bistritsa",
    "драгалевци": "dragalevtsi",
    "симеоново": "simeonovo",
    "кръстова вада": "krastova-vada",
    "витоша": "vitosha",
    "борово": "borovo",
    "гоце делчев": "gotse-delchev",
    "хиподрума": "hipodroma",
    "белите брези": "belite-brezi",
    "иван вазов": "ivan-vazov",
    "стрелбище": "strelbishte",
    "лозенец": "lozenets",
    "център": "centar",
    "оборище": "oborishte",
    "докторски паметник": "doktorski-pametnik",
    "яворов": "yavorov",
    "гео милев": "geo-milev",
    "подуяне": "poduyane",
    "хаджи димитър": "hadji-dimitar",
    "левски": "levski",
    "редута": "reduta",
    "слатина": "slatina",
    "разсадника": "razsadnika",
    "дианабад": "dianabad",
    "мусагеница": "musagenitsa",
    "дървеница": "darvenitsa",
    "младост": "mladost",
    "младост 1": "mladost-1",
    "младост 1а": "mladost-1a",
    "младост 2": "mladost-2",
    "младост 3": "mladost-3",
    "младост 4": "mladost-4",
    "полигона": "poligona",
    "дружба": "druzhba",
    "дружба 1": "druzhba-1",
    "дружба 2": "druzhba-2",
    "люлин": "lyulin",
    "люлин 1": "lyulin-1",
    "люлин 2": "lyulin-2",
    "люлин 3": "lyulin-3",
    "люлин 4": "lyulin-4",
    "люлин 5": "lyulin-5",
    "люлин 6": "lyulin-6",
    "люлин 7": "lyulin-7",
    "люлин 8": "lyulin-8",
    "люлин 9": "lyulin-9",
    "люлин 10": "lyulin-10",
    "люлин център": "lyulin-centar",
    "надежда": "nadezhda",
    "надежда 1": "nadezhda-1",
    "надежда 2": "nadezhda-2",
    "надежда 4": "nadezhda-4",
    "толстой": "tolstoy",
    "триъгълника": "triagalnika",
    "западен парк": "zapaden-park",
    "лагера": "lagera",
    "красна поляна": "krasna-polyana",
    "красна поляна 1": "krasna-polyana-1",
    "красна поляна 2": "krasna-polyana-2",
    "красна поляна 3": "krasna-polyana-3",
    "фондови жилища": "fondovi-zhilishta",
    "бели брези": "beli-brezi",
    "сердика": "serdika",
    "банишора": "banishora",
    "света троица": "sveta-troitsa",
    "илинден": "ilinden",
    "захарна фабрика": "zaharna-fabrika",
    "военна рампа": "voenna-rampa",
    "централна гара": "tsentralna-gara",
    "зона б-5": "zona-b-5",
    "зона б-18": "zona-b-18",
    "зона б-19": "zona-b-19",
    "хладилника": "hladilnika",
    "изток": "iztok",
    "изгрев": "izgrev",
    "студентски град": "studentski-grad",
    "студентски": "studentski",
    "мотописта": "motopista",
    "горубляне": "gorublyane",
    "суха река": "suha-reka",
    "обеля": "obelya",
    "обеля 1": "obelya-1",
    "обеля 2": "obelya-2",
    "връбница": "vrabnitsa",
    "връбница 1": "vrabnitsa-1",
    "връбница 2": "vrabnitsa-2",
    "модерно предградие": "moderno-predgradie",
    "света петка": "sveta-petka",
    "бъкстон": "bakston",
    "павлово": "pavlovo",
    "бели брод": "beli-brod",
    "карпузица": "karpuzitsa",
    "белия кръст": "beliya-krast",
    "славия": "slaviya",
    "факултета": "fakulteta",
    "филиповци": "filipovtsi",
    "требич": "trebich",
    "илиянци": "iliyantsi",
    "орландовци": "orlandovtsi",
    "малашевци": "malashevtsi",
    "христо ботев": "hristo-botev",
    "бенковски": "benkovski",
    "свобода": "svoboda",
    "света тройца": "sveta-troitsa",
    "хайредин": "hairedin",
    "република": "republika",
    "медицинска академия": "meditsinska-akademiya",
    "докторски": "doktorski-pametnik",
    "кючук париж": "kyuchuk-parizh",
    "лозенец": "lozenets",
    "мотописта": "motopista",
    "бъкстон": "bakston",
    "кариана": "kariana",
    "дървеница": "darvenitsa",
    "мало бучино": "malo-buchino",
    "обеля": "obelya",
}

PLOVDIV_NEIGHBORHOODS = {
    "център": "centar",
    "каменица": "kamenitsa",
    "кючук париж": "kyuchuk-parizh",
    "тракия": "trakiya",
    "смирненски": "smirnenski",
    "южен": "yuzhen",
    "северен": "severen",
    "източен": "iztоchen",
    "западен": "zapaden",
    "кършияка": "karshiyaka",
    "гагарин": "gagarin",
    "марица": "maritsa",
    "столипиново": "stolipinovo",
    "христо ботев": "hristo-botev",
    "прослав": "proslav",
    "беломорски": "belomorski",
}

VARNA_NEIGHBORHOODS = {
    "център": "centar",
    "чайка": "chaika",
    "левски": "levski",
    "бриз": "briz",
    "трошево": "troshevo",
    "владиславово": "vladislavovo",
    "младост": "mladost",
    "аспарухово": "asparuhovo",
    "виница": "vinitsa",
    "галата": "galata",
    "изгрев": "izgrev",
}

CITY_NEIGHBORHOOD_MAP = {
    "sofiya": SOFIA_NEIGHBORHOODS,
    "plovdiv": PLOVDIV_NEIGHBORHOODS,
    "varna": VARNA_NEIGHBORHOODS,
}


def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower().strip())


_CYR_TO_LAT = {
    'а': 'a',  'б': 'b',  'в': 'v',  'г': 'g',  'д': 'd',
    'е': 'e',  'ж': 'zh', 'з': 'z',  'и': 'i',  'й': 'y',
    'к': 'k',  'л': 'l',  'м': 'm',  'н': 'n',  'о': 'o',
    'п': 'p',  'р': 'r',  'с': 's',  'т': 't',  'у': 'u',
    'ф': 'f',  'х': 'h',  'ц': 'ts', 'ч': 'ch', 'ш': 'sh',
    'щ': 'sht','ъ': 'a',  'ь': '',   'ю': 'yu', 'я': 'ya',
}


def _transliterate(text: str) -> str:
    text = text.lower().strip()
    result = []
    for ch in text:
        if ch in _CYR_TO_LAT:
            result.append(_CYR_TO_LAT[ch])
        elif ch == ' ':
            result.append('-')
        elif ch.isascii() and (ch.isalnum() or ch == '-'):
            result.append(ch)
    slug = ''.join(result)
    slug = re.sub(r'-{2,}', '-', slug).strip('-')
    return slug


def _find_in_dict(query_norm: str, mapping: dict) -> str | None:
    for key in sorted(mapping, key=len, reverse=True):
        if key in query_norm:
            return mapping[key]
    return None


def build_imot_search_url(user_query: str) -> str | None:
    query_norm = _normalize(user_query)

    city_slug = _find_in_dict(query_norm, CITY_SLUGS)

    neighborhood_slug = None
    if city_slug:
        nb_map = CITY_NEIGHBORHOOD_MAP.get(city_slug, {})
        if nb_map:
            neighborhood_slug = _find_in_dict(query_norm, nb_map)
    else:
        neighborhood_slug = _find_in_dict(query_norm, SOFIA_NEIGHBORHOODS)
        if neighborhood_slug:
            city_slug = "sofiya"

    if city_slug:
        url = f"https://www.imot.bg/obiavi/prodazhbi/grad-{city_slug}"
        if neighborhood_slug:
            url += f"/{neighborhood_slug}"
        print(f"  🔗 Built imot.bg URL (dict): {url}")
        return url

    translit_city = None
    translit_nb = None
    for bg_city, slug in sorted(CITY_SLUGS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if bg_city in query_norm:
            translit_city = slug
            remainder = query_norm.replace(bg_city, '').strip()
            cyrillic_words = re.findall(r'[а-яА-ЯёЁ][а-яА-ЯёЁ0-9\-]+(?:\s+[а-яА-ЯёЁ][а-яА-ЯёЁ0-9\-]+)*', remainder)
            _STOP_WORDS = {'искам', 'търся', 'апартамент', 'стая', 'стаен', 'двустаен', 'тристаен',
                           'четиристаен', 'многостаен', 'едностаен', 'къща', 'имот', 'жилище',
                           'продава', 'наем', 'покупка', 'евтин', 'скъп', 'нов', 'стар',
                           'квартал', 'район', 'град', 'село', 'махала'}
            filtered = [w for w in cyrillic_words if w not in _STOP_WORDS and len(w) > 2]
            if filtered:
                translit_nb = _transliterate(' '.join(filtered))
            break

    if not translit_city:
        pass

    if translit_city:
        url = f"https://www.imot.bg/obiavi/prodazhbi/grad-{translit_city}"
        if translit_nb:
            url += f"/{translit_nb}"
        print(f"  🔗 Built imot.bg URL (transliterate): {url}")
        return url

    return _build_url_via_llm(user_query)


URL_BUILDER_PROMPT = """You are a URL slug builder for imot.bg, a Bulgarian real estate website.
From the user's query, extract the city and neighborhood (if mentioned) and
return their URL-safe Latin slugs exactly as imot.bg uses them.

URL pattern: /obiavi/prodazhbi/grad-{{city_slug}}/{{neighborhood_slug}}

SLUG RULES:
- Transliterate Bulgarian Cyrillic to Latin letter-by-letter.
- Replace spaces with hyphens (-).
- All lowercase, no special characters.
- щ→sht, ж→zh, ч→ch, ш→sh, ц→ts, ю→yu, я→ya, ь→, ъ→a, й→y
- Examples: Малинова долина → malinova-dolina, Овча купел → ovcha-kupel,
  Красно село → krasno-selo, Манастирски ливади → manastirski-livadi,
  Студентски град → studentski-grad, Хладилника → hladilnika

City examples: София→sofiya, Пловдив→plovdiv, Варна→varna, Бургас→burgas

Respond with ONLY valid JSON:
{{"city_slug": "sofiya", "neighborhood_slug": "malinova-dolina"}}
If no neighborhood: {{"city_slug": "sofiya", "neighborhood_slug": null}}
If no Bulgarian city at all: {{"city_slug": null, "neighborhood_slug": null}}
Default to sofiya if the user mentions a neighbourhood without a city.
"""


def _build_url_via_llm(user_query: str) -> str | None:
    try:
        result = llm.invoke([
            {"role": "system", "content": URL_BUILDER_PROMPT},
            {"role": "user", "content": user_query},
        ])
        data = json.loads(result.content)

        city_slug = data.get("city_slug")
        neighborhood_slug = data.get("neighborhood_slug")

        if not city_slug:
            print("  ℹ️ No city extracted from query, skipping auto-scrape.")
            return None

        city_slug = re.sub(r'[\s]+', '-', city_slug.strip().lower())
        if neighborhood_slug:
            neighborhood_slug = re.sub(r'[\s]+', '-', neighborhood_slug.strip().lower())

        url = f"https://www.imot.bg/obiavi/prodazhbi/grad-{city_slug}"
        if neighborhood_slug:
            url += f"/{neighborhood_slug}"

        print(f"  🔗 Built imot.bg URL (LLM): {url}")
        return url

    except Exception as e:
        print(f"  ❌ URL builder error: {e}")
        return None


# =============================================================================
# imot.bg — целенасочено парсиране
# =============================================================================

def _is_imot_bg(url: str) -> bool:
    return "imot.bg" in urlparse(url).netloc

def _is_imot_listing_page(url: str) -> bool:
    return "/obiavi/" in url and "/obiava-" not in url

def _is_imot_detail_page(url: str) -> bool:
    return "/obiava-" in url

def _parse_price(text: str) -> float:
    if not text:
        return 0.0

    eur_match = re.search(r'([\d\s,.]+)\s*(?:€|EUR|евро)', text)
    if eur_match:
        price_str = eur_match.group(1).replace(' ', '').replace(',', '')
        try:
            return float(price_str)
        except ValueError:
            pass

    bgn_match = re.search(r'([\d\s,.]+)\s*(?:лв|BGN)', text)
    if bgn_match:
        price_str = bgn_match.group(1).replace(' ', '').replace(',', '')
        try:
            return float(price_str) / 1.956
        except ValueError:
            pass
    
    return 0.0

def _scrape_imot_detail(url: str) -> dict | None:
    try:
        clean_url = url.split('#')[0]
        print(f"  📄 Fetching detail: {clean_url}")
        resp = requests.get(clean_url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.content, 'html.parser')

        h1 = soup.find('h1')
        title = h1.get_text(separator=' ', strip=True) if h1 else "N/A"
        title = re.sub(r'\s*Обява:\s*\S+', '', title).strip()

        price = 0.0
        price_el = soup.find(string=re.compile(r'[\d\s,.]+\s*€'))
        if price_el:
            price = _parse_price(price_el.strip())
        else:
            full_text = soup.get_text()
            price = _parse_price(full_text[:2000])

        location = ""
        loc_header = soup.find(string=re.compile(r'Местоположение'))
        if loc_header:
            parent = loc_header.find_parent()
            if parent:
                location = parent.get_text(separator=' ', strip=True)
                location = re.sub(r'^Местоположение:\s*', '', location).strip()
        
        if not location:
            parts = title.split(',')
            location = ', '.join(parts[1:]).strip() if len(parts) > 1 else ""

        description = ""
        desc_div = soup.find('div', class_='text')
        if desc_div:
            description = desc_div.get_text(separator=' ', strip=True)[:1000]
        if not description:
            desc_header = soup.find(string=re.compile(r'Описание на имота'))
            if desc_header:
                parent = desc_header.find_parent()
                if parent:
                    container = parent.find_parent()
                    if container:
                        for sib in container.find_next_siblings():
                            txt = sib.get_text(strip=True)
                            if len(txt) > 20:
                                description = txt[:1000]
                                break

        ad_params = ""
        params_div = soup.find('div', class_='adParams')
        if params_div:
            ad_params = params_div.get_text(separator=', ', strip=True)

        features = ""
        features_container = soup.find('div', class_='carExtri')
        if features_container:
            items_div = features_container.find('div', class_='items')
            if items_div:
                feat_list = [d.get_text(strip=True) for d in items_div.find_all('div')]
                features = ', '.join(feat_list)
        if not features:
            features_el = soup.find(string=re.compile(r'Особености'))
            if features_el:
                parent = features_el.find_parent()
                if parent:
                    pp = parent.find_parent()
                    if pp:
                        items = pp.find('div', class_='items')
                        if items:
                            feat_list = [d.get_text(strip=True) for d in items.find_all('div')]
                            features = ', '.join(feat_list)
                            
        if ad_params:
            description = f"{description} | {ad_params}".strip(' |')

        if not title or title == "N/A":
            return None

        return {
            "title": title,
            "price": price,
            "location": location,
            "description": description,
            "features": features,
            "source_url": clean_url,
        }

    except Exception as e:
        print(f"  ❌ Error parsing detail {url}: {e}")
        return None

def _scrape_imot_listing_page(url: str, max_pages: int = 3) -> list[dict]:
    all_listings = []
    
    for page_num in range(1, max_pages + 1):
        if page_num == 1:
            page_url = url
        else:
            page_url = url.rstrip('/') + f'/p-{page_num}'
        
        print(f"🕷️ Scraping list page {page_num}: {page_url}")

        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=15)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.content, 'html.parser')

            detail_links = set()
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/obiava-' in href:
                    full_url = urljoin('https://www.imot.bg', href)
                    full_url = full_url.split('#')[0]
                    detail_links.add(full_url)

            if not detail_links:
                print(f"  ℹ️ No listing links found on page {page_num}, stopping pagination.")
                break

            print(f"  📋 Found {len(detail_links)} listing links on page {page_num}")

            for link in list(detail_links)[:15]:
                listing = _scrape_imot_detail(link)
                if listing:
                    all_listings.append(listing)
                time.sleep(0.5)

        except Exception as e:
            print(f"  ❌ Error on page {page_num}: {e}")
            break
    
    return all_listings

def scrape_and_store(url: str = None, mock_text: str = None, max_pages: int = 3):
    if url and _is_imot_bg(url):
        print(f"🏠 Detected imot.bg URL")
        
        if _is_imot_detail_page(url):
            listings = []
            listing = _scrape_imot_detail(url)
            if listing:
                listings.append(listing)
        elif _is_imot_listing_page(url):
            listings = _scrape_imot_listing_page(url, max_pages=max_pages)
        else:
            listings = _scrape_imot_listing_page(url, max_pages=1)

        count = 0
        skipped = 0
        added_titles = []
        for item in listings:
            if item.get("title") and item.get("price", 0) > 0:
                added = add_property(
                    title=item["title"],
                    price=item["price"],
                    location=item.get("location", "Unknown"),
                    description=item.get("description", ""),
                    features=item.get("features", ""),
                )
                if added:
                    count += 1
                    added_titles.append(item["title"])
                else:
                    skipped += 1

        return {
            "status": "success",
            "source": "imot.bg",
            "added_count": count,
            "skipped_count": skipped,
            "listings": added_titles,
        }

    raw_text = ""
    
    if url:
        try:
            print(f"🕷️ Scraping URL: {url}")
            response = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            for script in soup(["script", "style"]):
                script.extract()
            raw_text = soup.get_text(separator=' ', strip=True)[:8000]
        except Exception as e:
            return {"status": "error", "message": str(e)}
    elif mock_text:
        print("📄 Processing provided text...")
        raw_text = mock_text
    
    if not raw_text:
        return {"status": "error", "message": "No text content found"}

    print("🤖 AI is analyzing text to extract listings...")
    
    try:
        prompt = PromptTemplate(
            template=EXTRACTION_PROMPT,
            input_variables=["text_data"]
        )
        chain = prompt | llm
        
        result = chain.invoke({"text_data": raw_text})
        
        data = json.loads(result.content)
        listings = data.get("listings", [])
        
        count = 0
        skipped = 0
        added_titles = []
        for item in listings:
            if item.get("title") and item.get("price"):
                added = add_property(
                    title=item.get("title", "N/A"),
                    price=float(item.get("price", 0)),
                    location=item.get("location", "Unknown"),
                    description=item.get("description", ""),
                    features=item.get("features", "")
                )
                if added:
                    count += 1
                    added_titles.append(item.get("title"))
                else:
                    skipped += 1
            
        return {
            "status": "success", 
            "source": "llm_extraction",
            "added_count": count,
            "skipped_count": skipped,
            "listings": added_titles
        }
        
    except Exception as e:
        print(f"Extraction error: {e}")
        return {"status": "error", "message": str(e)}