from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from urllib.parse import urljoin
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
import base64

# Makes Chrome run without showing a visible browser window
options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)

titles = []

# ---------- GENERIC PARSER ----------
def parse_page(url, classname):
    driver.get(url)
    time.sleep(3)

    folder = "alzheimers_html"
    os.makedirs(folder, exist_ok=True)

    while True:
        try:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            for tag in soup(["header", "footer", "nav"]):
                tag.decompose()

            for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
                text = heading.get_text(strip=True)
                link = heading.find("a")
                href = link.get("href") if link else None

                if "alzheimer" in text.lower():
                    full_link = urljoin(url, href) if href else url
                    if any(d.get("link") == full_link for d in titles):
                        continue

                    titles.append({"title": text, "link": full_link})
                    print("Saved:", text)

                    # Save article HTML
                    try:
                        driver.get(full_link)
                        time.sleep(2)
                        safe_title = re.sub(r'[^a-zA-Z0-9_-]', "_", text[:60])
                        html_path = os.path.join(folder, f"{safe_title}.html")
                        with open(html_path, "w", encoding="utf-8") as f:
                            f.write(driver.page_source)
                    except Exception as e:
                        print("Error saving article HTML:", e)

                    driver.back()
                    time.sleep(2)

            if classname:
                load_more = driver.find_element(By.CLASS_NAME, classname)
                driver.execute_script("arguments[0].click();", load_more)
                time.sleep(3)
            else:
                break
        except:
            break


# ---------- IGC PHARMA ----------
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
        date_tag = article.select_one(".elementor-post-date")

        title = heading.get_text(strip=True) if heading else None
        href = urljoin(base_url, link_tag["href"]) if link_tag else None
        date = date_tag.get_text(strip=True) if date_tag else None

        if not title or not href or "alzheimer" not in title.lower():
            continue

        titles.append({"title": title, "link": href, "date": date, "author": "IGC Pharma"})
        print("Saved:", title)

        driver.get(href)
        time.sleep(2)
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', "_", title[:60])
        html_path = os.path.join(folder, f"{safe_title}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)


# ---------- EXTRACT METADATA ----------
def igcpharma_metadata(folder="igcpharma_articles"):
    metadata = []
    
    for file in os.listdir(folder):
        if not file.endswith(".html"):
            continue
        path = os.path.join(folder, file)
        
        with open(path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        # Try to scope to article container first
        article_container = soup.select_one("article, .elementor-post, .post")  # adjust if needed
        if article_container:
            # Title inside the article container
            title_tag = article_container.select_one("h2, h3, .elementor-post-title, .entry-title")
        else:
            title_tag = soup.select_one("h2, h3, .elementor-post-title, .entry-title")

        title = title_tag.get_text(strip=True) if title_tag else file.replace(".html", "")

        # Date inside article container
        if article_container:
            date_tag = article_container.select_one(".elementor-post-date, time, .post-date")
        else:
            date_tag = soup.select_one(".elementor-post-date, time, .post-date")
        date = date_tag.get_text(strip=True) if date_tag else None

        # Author
        author = None
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            author = meta_author["content"]
        elif article_container and article_container.select_one(".author, .byline, .post-author, .entry-author"):
            author = article_container.select_one(".author, .byline, .post-author, .entry-author").get_text(strip=True)
        else:
            author = "IGC Pharma"

        # Content
        content_container = article_container or soup
        paragraphs = content_container.find_all("p")
        content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Append metadata
        metadata.append({
            "filename": file,
            "title": title,
            "date": date,
            "author": author,
            "content": content
        })

    return metadata


# ---------- ASCENEURON ----------
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

    for href in seen_links:
        driver.get(href)
        time.sleep(2)
        detail_soup = BeautifulSoup(driver.page_source, "html.parser")

        title_tag = detail_soup.select_one("h1, .entry-title")
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"
        if "alzheimer" not in title.lower():
            continue

        date_tag = detail_soup.select_one(".df-cpt-date-wrap, time, .elementor-post-date")
        date = date_tag.get_text(strip=True) if date_tag else None

        author = None
        meta_author = detail_soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            author = meta_author["content"]
        elif detail_soup.select_one(".author, .byline, .post-author, .entry-author"):
            author = detail_soup.select_one(".author, .byline, .post-author, .entry-author").get_text(strip=True)
        else:
            author = "AsceNeuron"

        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title[:60])
        html_path = os.path.join(folder, f"AsceNeuron_{safe_title}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        titles.append({"title": title, "link": href, "date": date, "author": author})
        print("Saved:", title)


def asceneuron_metadata(folder="asceneuron_articles"):
    metadata = []
    for file in os.listdir(folder):
        if not file.endswith(".html"):
            continue
        
        path = os.path.join(folder, file)
        with open(path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        # --- Title ---
        title_tag = soup.select_one("h1.df-cpt-title, h1, .entry-title")
        title = title_tag.get_text(strip=True) if title_tag else file.replace(".html", "")

        # --- Date ---
        date_tag = soup.select_one(".df-cpt-date-wrap, time, .elementor-post-date, .post-date")
        date = date_tag.get_text(strip=True) if date_tag else None

        # --- Author ---
        author = None
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            author = meta_author["content"]
        elif soup.select_one(".author, .byline, .post-author, .entry-author"):
            author = soup.select_one(".author, .byline, .post-author, .entry-author").get_text(strip=True)
        else:
            author = "AsceNeuron"

        # --- Content / Body of the article ---
        # This targets the main article content specifically
        content_container = soup.select_one(".df-cpt-content, .elementor-widget-theme-post-content, .entry-content, article, .content")
        if content_container:
            paragraphs = content_container.find_all("p")
        else:
            paragraphs = soup.find_all("p")

        # Join paragraph texts together as the "content"
        content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # --- Save Metadata ---
        metadata.append({
            "filename": file,
            "title": title,
            "date": date,
            "author": author,
            "content": content
        })

    return metadata


# ---------- MAIN RUN ----------
def main():
    #parse_page("https://aprinoia.com/news/","")
    #parse_page("https://agenebio.com/about-us/recent-news/","next.page-numbers")
    #parse_page("https://biggsinstitute.org/category/news/", "next")
    #parse_page("https://health.ucdavis.edu/alzheimers-research/news/topic/neurological-health", "")
    #scrape_igcpharma()
    scrape_asceneuron()


    # Save all titles
    df_titles = pd.DataFrame(titles)
    df_titles.to_csv("alzheimer_titles.csv", index=False)
    print(f"Saved {len(df_titles)} Alzheimer titles")

    # Extract and save IGC Pharma metadata
    meta = igcpharma_metadata()
    df = pd.DataFrame(meta)
    df.to_csv("igcpharma_metadata.csv", index=False)
    print("Saved metadata to igcpharma_metadata.csv")

    # Extract and save AsceNeuron metadata
    meta = asceneuron_metadata()
    df_meta = pd.DataFrame(meta)
    df_meta.to_csv("asceneuron_metadata.csv", index=False)
    print("Saved asceneuron_metadata.csv")

    driver.quit()


# Run it all
main()