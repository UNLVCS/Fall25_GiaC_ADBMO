import pandas as pd 
import time 
import re 
import os
import json 
import requests
from selenium import webdriver  
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By 
from urllib.parse import urljoin  
from selenium.webdriver.support.ui import WebDriverWait 
from selenium.webdriver.support import expected_conditions as EC  
from bs4 import BeautifulSoup  
from dateutil import parser as dateparser

# Makes Chrome run without showing visible browser window
options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)

titles = []

# ----- IGC PHARMA -----
def scrape_igcpharma():
    base_url = "https://igcpharma.com/category/news/"
    folder = "igcpharma_articles"
    os.makedirs(folder, exist_ok=True)

    driver.get(base_url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    for article in soup.select("article"):
        heading = article.find(["h2", "h3"])
        link_tag = article.find("a", href=True)

        title = heading.get_text(strip=True) if heading else None
        href = urljoin(base_url, link_tag["href"]) if link_tag else None

        if not title or not href or "alzheimer" not in title.lower():
            continue

        driver.get(href)
        time.sleep(2)

        # Save HTML to folder
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', "_", title[:60])
        html_path = os.path.join(folder, f"{safe_title}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        print("Saved HTML:", title)


def extract_igcpharma_content(path):
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Title
    title_tag = soup.select_one("h1, h2, h3, .elementor-post-title, .entry-title")
    title = title_tag.get_text(strip=True) if title_tag else os.path.basename(path).replace(".html", "")

    # Date
    date_tag = soup.select_one(".elementor-post-date, time, .post-date")
    date = date_tag.get_text(strip=True) if date_tag else None

    # Author
    author = None
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = meta_author["content"]
    elif soup.select_one(".author, .byline, .post-author, .entry-author"):
        author = soup.select_one(".author, .byline, .post-author, .entry-author").get_text(strip=True)
    else:
        # Fallback
        text_lower = soup.get_text(" ", strip=True).lower()
        if "rosalyn christian" in text_lower:
            author = "Rosalyn Christian"
        elif "john nesbett" in text_lower:
            author = "John Nesbett"
        else:
            author = "IGC Pharma"

    # Content 
    article_container = soup.select_one("article, .elementor-post, .entry-content, main, .post")
    content_container = article_container or soup
    paragraphs = content_container.find_all("p")
    content = "\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))

    # Clean unwanted sections
    content = re.sub(
        r"(Contact Information.*|Forward[- ]Looking Statements.*|Recent Post.*|Related Posts.*)",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE
    )
    content = re.sub(
        r"(Rosalyn Christian.*|John Nesbett.*|Investor Relations.*|VP of Clinical.*)",
        "",
        content,
        flags=re.IGNORECASE
    )
    content = re.sub(r"\n{2,}", "\n\n", content).strip()

    return {
        "filename": os.path.basename(path),
        "title": title,
        "date": date,
        "author": author,
        "content": content,
        "content_source": "html",
    }

# Parse saved HTML
def igcpharma_metadata(folder="igcpharma_articles"):
    metadata = []
    for file in os.listdir(folder):
        if not file.endswith(".html"):
            continue
        path = os.path.join(folder, file)
        data = extract_igcpharma_content(path)
        metadata.append(data)
    return metadata

# ----- ASCENEURON -----
def scrape_asceneuron():
    base_url = "https://asceneuron.com/news-events/"
    folder = "asceneuron_articles"
    os.makedirs(folder, exist_ok=True)

    driver.get(base_url)
    time.sleep(2)

    seen_links = set()
    while True:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        articles = soup.select("div.df-item-wrap.df-cpt-title-wrap a")
        current_links = {urljoin(base_url, a.get("href")) for a in articles}
        new_links = current_links - seen_links
        if not new_links:
            break
        seen_links.update(new_links)

        try:
            load_more = driver.find_element(By.CSS_SELECTOR, ".df-cptfilter-load-more")
            driver.execute_script("arguments[0].click();", load_more)
            time.sleep(3)
        except:
            break

    # Folder for PDFs
    pdf_folder = "asceneuron_pdfs"
    os.makedirs(pdf_folder, exist_ok=True)

    for href in seen_links:
        driver.get(href)
        time.sleep(2)
        detail_soup = BeautifulSoup(driver.page_source, "html.parser")

        title_tag = detail_soup.select_one("h1, .entry-title")
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"
        if "alzheimer" not in title.lower():
            continue

        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title[:60])
        html_path = os.path.join(folder, f"AsceNeuron_{safe_title}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Saved HTML:", title)

        # Downloads PDF if available
        pdf_link_tag = detail_soup.find("a", string=re.compile(r"Download", re.I))
        if not pdf_link_tag:
            pdf_link_tag = detail_soup.find("a", href=re.compile(r"\.pdf", re.I))

        if pdf_link_tag and pdf_link_tag.get("href"):
            pdf_url = urljoin(base_url, pdf_link_tag["href"])
            pdf_filename = f"AsceNeuron_{safe_title}.pdf"
            pdf_path = os.path.join(pdf_folder, pdf_filename)

            try:
                response = requests.get(pdf_url, timeout=10)
                if response.status_code == 200:
                    with open(pdf_path, "wb") as pdf_file:
                        pdf_file.write(response.content)
                else:
                    print(f"Failed to download PDF ({response.status_code}): {pdf_url}")
            except Exception as e:
                print(f"Error downloading {pdf_url}: {e}")

# ----- AsceNeuron Metadata -----
def extract_asceneuron_content(path):
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Title
    title_tag = soup.select_one("h1.df-cpt-title, h1, .entry-title")
    title = title_tag.get_text(strip=True) if title_tag else os.path.basename(path).replace(".html", "")

    # Date
    date = None
    time_tag = soup.select_one("time")
    if time_tag:
        date = time_tag.get("datetime") or time_tag.get_text(strip=True)
    if not date:
        meta_date = soup.find("meta", {"property": "article:published_time"}) or soup.find("meta", {"name": "date"})
        if meta_date and meta_date.get("content"):
            date = meta_date["content"]
    if date:
        date = date.replace("Posted :", "").strip()

    # Author
    author = "AsceNeuron"
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = meta_author["content"]
    elif soup.select_one(".author, .byline, .post-author, .entry-author"):
        author = soup.select_one(".author, .byline, .post-author, .entry-author").get_text(strip=True)

    # Content
    container = soup.select_one(".df-cpt-content, .elementor-widget-theme-post-content, .entry-content, article, .content, main")
    paragraphs = []
    if container:
        for p in container.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text and text not in paragraphs:
                paragraphs.append(text)
    content = "\n".join(paragraphs)
    summary = content[:500] if content else None

    return {
        "filename": os.path.basename(path),       
        "title": title,
        "date": date,
        "author": author,
        "content": summary,
        "content_source": "html"
    }

# Parse saved HTML
def asceneuron_metadata(folder="asceneuron_articles"):
    metadata = []
    for file in os.listdir(folder):
        if not file.endswith(".html"):
            continue
        path = os.path.join(folder, file)
        data = extract_asceneuron_content(path)
        metadata.append(data)
    return metadata

# ----- Aprinoia -----
def scrape_aprinoia():
    folder = "aprinoia_articles"
    os.makedirs(folder, exist_ok=True)

    base_url = "https://aprinoia.com/news/"
    driver.get(base_url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    article_links = soup.select("h2 a, h3 a, .elementor-post__title a")

    for a in article_links:
        title = a.get_text(strip=True)
        href = a.get("href")
        if not href or "alzheimer" not in title.lower():
            continue
        full_link = urljoin(base_url, href)

        # Visit article and save HTML
        driver.get(full_link)
        time.sleep(2)
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', "_", title)
        html_path = os.path.join(folder, f"Aprinoia_{safe_title}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        print("Saved HTML:", title)


# ----- Aprinoia Metadata -----
def extract_aprinoia_content(path):
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Title
    title_tag = soup.select_one("h1.entry-title, h1.post-title, h1")
    if not title_tag:
        title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
    else:
        title = os.path.basename(path).replace(".html", "").replace("_", " ")

    # Date
    date_text = None
    date_tag = soup.select_one("time.entry-date, .post-date, .entry-date, .elementor-post-date")
    if date_tag:
        date_text = date_tag.get("datetime") or date_tag.get_text(strip=True)

    # If not found, search <em>, <strong>, and <p> tags for month/year
    if not date_text:
        for tag in soup.find_all(["em", "strong", "p"]):
            text = tag.get_text(" ", strip=True)
            if re.search(
                r"(January|February|March|April|May|June|July|August|September|October|November|December).*\d{4}",
                text,
            ):
                date_text = text
                break

    # If still not found, search entire text for any date-like string
    if not date_text:
        full_text = soup.get_text(" ", strip=True)
        match = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
            full_text,
        )
        if match:
            date_text = match.group(0)

    # Clean and parse date text
    date = None
    if date_text:
        cleaned = (
            date_text.replace("\u2013", "-")   # normalize en dash
                     .replace("–", "-")
                     .replace("—", "-")
                     .strip()
        )
        cleaned = re.sub(r"^[^A-Za-z]*(?:[A-Za-z\s,]+[-–—]\s*)?", "", cleaned)
        match = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
            cleaned,
        )
        if match:
            cleaned = match.group(0)

        try:
            parsed_date = dateparser.parse(cleaned, fuzzy=True)
        except Exception:
            parsed_date = pd.to_datetime(cleaned, errors="coerce")

        if parsed_date is not None and not pd.isna(parsed_date):
            date = parsed_date.strftime("%Y-%m-%d")

    # Author
    author = "Aprinoia"
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = meta_author["content"]
    elif soup.select_one(".author, .byline, .post-author, .entry-author"):
        author = soup.select_one(".author, .byline, .post-author, .entry-author").get_text(strip=True)

    # Content
    content_containers = soup.select(".entry-content, article, .content, main")
    paragraphs = []
    for container in content_containers:
        for p in container.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)

    if not paragraphs:
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)

    content = "\n".join(paragraphs)
    summary = content[:500] if content else None

    return {
        "file": os.path.basename(path),
        "title": title,
        "date": date,
        "author": author,
        "content": summary,
        "content_source": "html"
    }


# Parse saved HTML
def aprinoia_metadata(folder="aprinoia_articles"):
    metadata = []
    seen_titles = set()

    for file in os.listdir(folder):
        if not file.endswith(".html"):
            continue

        path = os.path.join(folder, file)
        data = extract_aprinoia_content(path)

        normalized_title = re.sub(r'\s+', ' ', data["title"].strip().lower())
        if normalized_title in seen_titles:
            print(f"🔁 Skipping duplicate: {data['title']}")
            continue

        seen_titles.add(normalized_title)
        metadata.append(data)
    return metadata

# ----- UC Davis -----
def scrape_ucdavis():
    folder = "ucdavis_articles"
    os.makedirs(folder, exist_ok=True)

    base_url = "https://health.ucdavis.edu/alzheimers-research/news/topic/neurological-health"
    driver.get(base_url) 
    time.sleep(2)

    seen_links = set()

    # Scroll to load all articles
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    soup = BeautifulSoup(driver.page_source, "html.parser")
    article_links = soup.select("h2 a, h3 a, h4 a")

    for a in article_links:
        title = a.get_text(strip=True)
        href = a.get("href")
        if not href or "alzheimer" not in title.lower():
            continue

        full_link = urljoin(base_url, href)
        if full_link in seen_links:
            continue
        seen_links.add(full_link)

        driver.get(full_link)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".article-body, .news-body, div.text-body, div.parsys")
                )
            )
        except:
            print("Timeout waiting for article body on:", full_link)

        time.sleep(1.5)
        page_html = driver.page_source

        # Save article HTML
        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title[:60])
        html_path = os.path.join(folder, f"UCDavis_{safe_title}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page_html)

        print("Saved HTML:", title)

# ----- UC Davis Metadata -----
def extract_ucdavis_content(path):
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    jsonld_tag = soup.find("script", type="application/ld+json")
    if jsonld_tag:
        try:
            data = json.loads(jsonld_tag.string)
            if isinstance(data, dict):
                headline = data.get("headline")
                date = data.get("datePublished")
                author = None
                author_data = data.get("author")
                if isinstance(author_data, dict):
                    author = author_data.get("name")
                elif isinstance(author_data, list) and len(author_data) > 0:
                    author = author_data[0].get("name")
                description = data.get("description")
                return {
                    "filename": os.path.basename(path),
                    "title": headline,
                    "date": date,
                    "author": author,
                    "content": description,
                    "content_source": "jsonld",
                }
        except Exception:
            pass

    # Fallback
    title_tag = soup.select_one("h1, .article-title, .news-title")
    title = title_tag.get_text(strip=True) if title_tag else os.path.basename(path).replace(".html", "")

    date_tag = soup.select_one("time, .news-date, .article-date")
    date = date_tag.get_text(strip=True) if date_tag else None

    author_tag = soup.select_one(".author, .byline, .article-author")
    author = author_tag.get_text(strip=True) if author_tag else "UC Davis Health"

    content_container = soup.select_one(".article-body, .news-body, main, div.text-body, div.parsys") or soup
    paragraphs = content_container.find_all(["p", "li"])
    content = "\n".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))

    summary = content[:500] if content else None

    return {
        "filename": os.path.basename(path),
        "title": title,
        "date": date,
        "author": author,
        "content": summary,
        "content_source": "html",
    }

# Parse saved HTML
def ucdavis_metadata(folder="ucdavis_articles"):
    metadata = []
    for file in os.listdir(folder):
        if not file.endswith(".html"):
            continue
        path = os.path.join(folder, file)
        data = extract_ucdavis_content(path)
        metadata.append(data)
    return metadata

# ----- AGeneBio -----
def scrape_agenebio():
    base_url = "https://agenebio.com/about-us/recent-news/"
    folder = "agenebio_articles"
    os.makedirs(folder, exist_ok=True)

    driver.get(base_url)
    time.sleep(2)

    seen_links = set()

    while True:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        article_links = soup.select("h2 a, h3 a") 

        for a in article_links:
            title = a.get_text(strip=True)
            href = a.get("href")
            if not href or "alzheimer" not in title.lower():
                continue

            full_link = urljoin(base_url, href)
            if full_link in seen_links:
                continue
            seen_links.add(full_link)

            driver.get(full_link)
            time.sleep(2)

            # Saves HTML
            safe_title = re.sub(r'[^a-zA-Z0-9_-]', "_", title[:60])
            html_path = os.path.join(folder, f"{safe_title}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)

            print("Saved HTML:", title)

            driver.back()
            time.sleep(2)

        # Clicks next page button until no more pages 
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "a.next.page-numbers")
            driver.execute_script("arguments[0].click();", next_button)
            time.sleep(2)
        except:
            break

# ----- AGeneBio Metadata -----
def extract_agenebio_content(path):
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Title
    title_tag = soup.select_one("h1.entry-title, h1.post-title, h1")
    if not title_tag:
        title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
    else:
        title = os.path.basename(path).replace(".html", "").replace("_", " ")

    # Date 
    date_text = None

    # Common date tags
    date_tag = soup.select_one("time, .post-date, .entry-date, .elementor-post-date")
    if date_tag:
        date_text = date_tag.get("datetime") or date_tag.get_text(strip=True)

    # Fallback
    if not date_text:
        full_text = soup.get_text(" ", strip=True)
        match = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4}",
            full_text,
        )
        if match:
            date_text = match.group(0)

    # Try parsing the date
    date = None
    # Date cleaning
    if date_text:
        cleaned = re.sub(r"^[^A-Za-z]*(?:[A-Za-z\s,]+[-–—]\s*)?", "", date_text)
        try:
            parsed_date = dateparser.parse(cleaned, fuzzy=True)
        except Exception:
            parsed_date = pd.to_datetime(cleaned, errors="coerce")

        if parsed_date is not None and not pd.isna(parsed_date):
            date = parsed_date.strftime("%Y-%m-%d")

    # Author
    author = None
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = meta_author["content"]
    elif soup.select_one(".author, .byline, .post-author, .entry-author"):
        author = soup.select_one(".author, .byline, .post-author, .entry-author").get_text(strip=True)
    else:
        author = "AGeneBio"

    # Content
    content_containers = soup.select(".entry-content, .elementor-widget-container, article, .post-content")
    paragraphs = []
    for container in content_containers:
        for p in container.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)

    if not paragraphs:
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)

    # Clean irrelevant text
    cleaned_paragraphs = []
    for p in paragraphs:
        lower_p = p.lower()
        if any(x in lower_p for x in [
            "©", "all rights reserved", "register now", "stay up to date",
            "read more", "contact", "suite", "baltimore, md", "@agenebio",
            "p:", "phone", "inc."
        ]):
            continue
        if re.search(r"\d{3}[-.\s]\d{3}[-.\s]\d{4}", p):
            continue
        cleaned_paragraphs.append(p)

    content = "\n".join(cleaned_paragraphs)
    content = re.sub(r"^«\s*back.*?\n", "", content, flags=re.IGNORECASE)
    summary = content[:500] if content else None

    return {
        "filename": os.path.basename(path),
        "title": title,
        "date": date,
        "author": author,
        "content": summary,
        "content_source": "html"
    }

# Parse saved HTML
def agenebio_metadata(folder="agenebio_articles"):
    metadata = []
    for file in os.listdir(folder):
        if not file.endswith(".html"):
            continue
        path = os.path.join(folder, file)
        data = extract_agenebio_content(path)
        metadata.append(data)
    return metadata

# ----- USC -----
def scrape_usc():
    folder = "usc_articles"
    os.makedirs(folder, exist_ok=True)

    base_url = "https://keck.usc.edu/news/tag/center-for-personalized-brain-health/"
    url = base_url
    page_num = 1
    seen_links = set()

    while url:
        driver.get(url)
        time.sleep(10)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        article_links = soup.select("h2 a, h3 a, a[href*='/news/']")

        if not article_links:
            print("No articles found on this page.")
            break

        for a in article_links:
            title = a.get_text(strip=True)
            href = a.get("href")
            if not href or "alzheimer" not in title.lower():
                continue

            full_link = urljoin(base_url, href)
            if full_link in seen_links:
                continue
            seen_links.add(full_link)

            driver.get(full_link)
            time.sleep(2)

            safe_title = re.sub(r'[^a-zA-Z0-9_-]', "_", title)
            html_path = os.path.join(folder, f"Keck_{safe_title}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)

            print("Saved HTML:", title)

        # Check for next page
        next_page_tag = soup.select_one(f"a[href*='/page/{page_num+1}/']")
        if next_page_tag and next_page_tag.get("href"):
            url = urljoin(base_url, next_page_tag.get("href"))
            page_num += 1
            time.sleep(1)
        else:
            break

# ----- USC Metadata -----
def extract_usc_content(path):
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    # Title
    title_tag = soup.select_one("h1.entry-title, h1.post-title, h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Fallback
    if not title or title.startswith("http") or re.match(r'www\.', title.lower()):
        # Cleaning title
        filename = os.path.basename(path).replace(".html", "")
        filename = re.sub(r'^Keck_', '', filename)
        filename = re.sub(r'_+', ' ', filename)
        title = filename.strip()

    # Date
    date = None

    date_tag = soup.select_one("time.entry-date, .post-date, .entry-date")
    if date_tag:
        date_text = date_tag.get("datetime") or date_tag.get_text(strip=True)
        if date_text:
            try:
                parsed_date = dateparser.parse(date_text.strip(), fuzzy=True)
                if parsed_date:
                    date = parsed_date.strftime("%Y-%m-%d")
            except:
                date = None

    # Fallback
    if not date:
        span_tag = soup.select_one("span.date")
        if span_tag:
            date_text = span_tag.get_text(strip=True)
            if date_text:
                try:
                    parsed_date = dateparser.parse(date_text, fuzzy=True)
                    if parsed_date:
                        date = parsed_date.strftime("%Y-%m-%d")
                except:
                    date = None

    # Author
    author = "Keck USC"
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = meta_author.get("content")
    elif soup.select_one(".author, .byline, .post-author, .entry-author"):
        author = soup.select_one(".author, .byline, .post-author, .entry-author").get_text(strip=True)

    # Content
    content_containers = soup.select("article, .entry-content, main, .content")
    paragraphs = []
    for container in content_containers:
        for p in container.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)
    content = "\n".join(paragraphs)
    summary = content[:500] if content else None

    return {
        "file": os.path.basename(path),
        "title": title,
        "date": date,
        "author": author,
        "content": summary,
        "content_source": "html"
    }

# Parse saved HTML
def usc_metadata(folder="usc_articles"):
    metadata = []
    seen_titles = set()
    for file in os.listdir(folder):
        if not file.endswith(".html"):
            continue
        path = os.path.join(folder, file)
        data = extract_usc_content(path)
        normalized_title = re.sub(r'\s+', ' ', data["title"].strip().lower())
        if normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)
        metadata.append(data)
    return metadata

# ----- Teikoku -----
def scrape_teikoku():
    folder = "teikoku_articles"
    os.makedirs(folder, exist_ok=True)

    base_url = "https://www.teikokuusa.com/company/news-press/"
    url = base_url
    page_num = 1
    seen_links = set()

    while url:
        driver.get(url)
        time.sleep(3) 

        soup = BeautifulSoup(driver.page_source, "html.parser")
        article_links = soup.select("a[href*='/company/news-press/'][title]")

        if not article_links:
            print("No articles found on this page.")
            break

        for a in article_links:
            title = a.get_text(strip=True)
            href = a.get("href")
            if not href or "alzheimer" not in title.lower():
                continue

            full_link = urljoin(base_url, href)
            if full_link in seen_links:
                continue
            seen_links.add(full_link)

            driver.get(full_link)
            time.sleep(2)

            safe_title = re.sub(r'[^a-zA-Z0-9_-]', "_", title[:60])
            html_path = os.path.join(folder, f"Teikoku_{safe_title}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)

            print("Saved HTML:", title)

        # Clicks next page button until no more pages 
        next_page_selector = f"a.page.larger[title='Page {page_num+1}']"
        next_tag = soup.select_one(next_page_selector)
        if next_tag and next_tag.get("href"):
            url = next_tag["href"]
            page_num += 1
            time.sleep(1)
        else:
            break

# ----- Teikoku Metadata -----
def extract_teikoku_content(path):
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Title
    title_tag = soup.select_one("h1.entry-title")
    title = title_tag.get_text(strip=True) if title_tag else os.path.basename(path).replace(".html", "")

    # Date 
    date_text = None

    # Common date tags
    date_tag = soup.select_one("time, .post-date, .entry-date, .elementor-post-date")
    if date_tag:
        date_text = date_tag.get("datetime") or date_tag.get_text(strip=True)

    # Fallback
    if not date_text:
        full_text = soup.get_text(" ", strip=True)
        match = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4}",
            full_text,
        )
        if match:
            date_text = match.group(0)

    date = None
    # Date cleaning
    if date_text:
        cleaned = re.sub(r"^[^A-Za-z]*(?:[A-Za-z\s,]+[-–—]\s*)?", "", date_text)
        try:
            parsed_date = dateparser.parse(cleaned, fuzzy=True)
        except Exception:
            parsed_date = pd.to_datetime(cleaned, errors="coerce")

        if parsed_date is not None and not pd.isna(parsed_date):
            date = parsed_date.strftime("%Y-%m-%d")

    # Author
    author = "Teikoku Pharma USA"

    # Content
    paragraphs = []
    for container in soup.select("div.wp-block-post-content, div.post-content, span.wp-block-paragraph"):
        for p in container.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)

    content = "\n".join(paragraphs)
    summary = content[:500] if content else None

    return {
        "file": os.path.basename(path),
        "title": title,
        "date": date,
        "author": author,
        "content": summary,
        "content_source": "html"
    }

# Parse saved HTML
def teikoku_metadata(folder="teikoku_articles"):
    metadata = []
    seen_titles = set()
    for file in os.listdir(folder):
        if not file.endswith(".html"):
            continue
        path = os.path.join(folder, file)
        data = extract_teikoku_content(path)
        normalized = re.sub(r'\s+', ' ', data["title"].strip().lower())
        if normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        metadata.append(data)
    return metadata

# ----- Treeway -----
def scrape_treeway():
    folder = "treeway_articles"
    os.makedirs(folder, exist_ok=True)

    base_url = "https://treeway.nl/news/"
    driver.get(base_url)
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    article_links = soup.select("div.elementor-post__text a, article a")

    if not article_links:
        print("No articles found on the page.")
        return

    seen_links = set()

    for a in article_links:
        title = a.get_text(strip=True)
        href = a.get("href")
        if not href or "alzheimer" not in title.lower():
            continue

        full_link = urljoin(base_url, href)
        if full_link in seen_links:
            continue
        seen_links.add(full_link)

        driver.get(full_link)
        time.sleep(2)

        # Save HTML
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', "_", title[:60])
        html_path = os.path.join(folder, f"Treeway_{safe_title}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        print("Saved HTML:", title)

# ----- Treeway Metadata -----
def extract_treeway_content(path):
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Title
    title_tag = soup.select_one("h1.entry-title, h1.post-title") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else os.path.basename(path).replace(".html", "")

    # Date 
    date = None

    # Common date tags
    date_tag = soup.select_one(
        "time, .post-date, .entry-date, .elementor-post-date, span.published, strong"
    )
    if date_tag:
        date_text = date_tag.get("datetime") or date_tag.get_text(strip=True)
        if date_text:
            # Date cleaning
            cleaned = re.sub(r"^[^A-Za-z]*,?\s*", "", date_text)
            try:
                parsed_date = dateparser.parse(cleaned, fuzzy=True)
                if parsed_date:
                    date = parsed_date.strftime("%Y-%m-%d")
            except:
                date = None

    # Fallback
    if not date:
        full_text = soup.get_text(" ", strip=True)
        match = re.search(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|"
            r"January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4}",
            full_text,
            re.IGNORECASE
        )
        if match:
            # Date cleaning
            try:
                cleaned = re.sub(r"^[^A-Za-z]*,?\s*", "", match.group(0))
                parsed_date = dateparser.parse(cleaned, fuzzy=True)
                if parsed_date:
                    date = parsed_date.strftime("%Y-%m-%d")
            except:
                date = None


    # Author
    author = "Treeway"
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = meta_author.get("content")


    # Content
    paragraphs = []
    for container in soup.select("div.elementor-post-content, div.entry-content"):
        for p in container.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)

    content = "\n".join(paragraphs)

    # Clean irrelevant text
    lines = content.splitlines()
    if lines:
        first_line = lines[0]
        if re.match(r"^[A-Z][a-zA-Z\s\-]+,\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}", first_line):
            lines = lines[1:]
    content = "\n".join(lines)

    summary = content[:500] if content else None

    return {
        "file": os.path.basename(path),
        "title": title,
        "date": date,
        "author": author,
        "content": summary,
        "content_source": "html"
    }

# Parse saved HTML
def treeway_metadata(folder="treeway_articles"):
    metadata = []
    seen_titles = set()
    for file in os.listdir(folder):
        if not file.endswith(".html"):
            continue
        path = os.path.join(folder, file)
        data = extract_treeway_content(path)
        normalized = re.sub(r'\s+', ' ', data["title"].strip().lower())
        if normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        metadata.append(data)
    return metadata

# ----- MAIN FUNCTION -----
def main():
    # Runs all scrapers
    scrape_igcpharma()
    scrape_asceneuron()
    scrape_aprinoia()
    scrape_ucdavis()
    scrape_agenebio()
    scrape_usc()
    scrape_teikoku()
    srcape_treeway()

    # Extract metadata and save CSVs
    meta = igcpharma_metadata()
    df = pd.DataFrame(meta)
    df.to_csv("igcpharma_metadata.csv", index=False)
    print("Saved to igcpharma_metadata.csv")

    meta = asceneuron_metadata()
    df_meta = pd.DataFrame(meta)
    df_meta.to_csv("asceneuron_metadata.csv", index=False)
    print("Saved to asceneuron_metadata.csv")

    meta = aprinoia_metadata()
    df_meta = pd.DataFrame(meta)
    df_meta.to_csv("aprinoia_metadata.csv", index=False)
    print("Saved to aprinoia_metadata.csv")    

    meta = ucdavis_metadata()
    df_meta = pd.DataFrame(meta)
    df_meta.to_csv("ucdavis_metadata.csv", index=False)
    print("Saved to ucdavis_metadata.csv")

    meta = agenebio_metadata()
    df_meta = pd.DataFrame(meta)
    df_meta.to_csv("agenebio_metadata.csv", index=False)
    print("Saved to agenebio_metadata.csv") 

    meta = usc_metadata()
    df = pd.DataFrame(meta)
    df.to_csv("usc_metadata.csv", index=False)
    print("Saved to usc_metadata.csv")

    meta = teikoku_metadata()
    df = pd.DataFrame(meta)
    df.to_csv("teikoku_metadata.csv", index=False)
    print("Saved to teikoku_metadata.csv")
    driver.quit()

    meta = treeway_metadata()
    df = pd.DataFrame(meta)
    df.to_csv("treeway_metadata.csv", index=False)
    print("Saved to treeway_metadata.csv")

main()
