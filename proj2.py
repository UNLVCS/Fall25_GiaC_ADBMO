
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

# Empty list to store extracted Alzheimer-related titles + links
titles = []

# Function to parse page
def parse_page(url, classname):
    driver.get(url)
    time.sleep(2)

    # Keeps clicking until no more pages
    while True:
        try:
            # Parse page
            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Extract Alzheimer-related titles 
            for heading in soup.find_all(["h1", "h2", "h3", "h4"]): # Different header tags depending on website
                # Extracts the heading text, looks for a hyperlink inside, and pulls out its href (if it exists)
                text = heading.get_text(strip=True)
                link = heading.find("a")
                href = link.get("href") if link else None

                # Saves both title and link when alzheimer (case-sensitive) is present
                if "alzheimer" in text.lower():
                    # Gets title and will also get link if exist
                    titles.append({"title": text, "link": href if href else url})
                    # Prints text and link saved
                    print("Saved:", text)
                    if href:
                        print("Link:", href)

            # If a classname was given, it looks for the button by class name, if no class was provided, breaks out of the loop after the first page
            if classname != "":
                load_more = driver.find_element(By.CLASS_NAME, classname)
                driver.execute_script("arguments[0].click();", load_more)
                time.sleep(3)

            else:        
                break
            
        # If anything fails, break the loop.
        except:
            break 

def contains_alzheimer(text):
    return "alzheimer" in text.lower()

# Function specific for IGCPharma
def scrape_igcpharma():
    base_url = "https://igcpharma.com/category/news/"
    driver.get(base_url)
    time.sleep(2)

    # Looks for folder IGCPharma
    folder = "igcpharma_pdfs"
    os.makedirs(folder, exist_ok=True)

 # Saves the landing page HTML of IGCPharma
    landing_html = os.path.join(folder, "IGCPharma_landing.html")
    with open(landing_html, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"Saved landing page HTML: {landing_html}")

    soup = BeautifulSoup(driver.page_source, "html.parser")

    for article in soup.select("article"):
        heading = article.find(["h2", "h3"])
        link_tag = article.find("a", href=True)
        date_tag = article.select_one(".elementor-post-date")

        title = heading.get_text(strip=True) if heading else None
        href = urljoin(base_url, link_tag["href"]) if link_tag else None
        date = date_tag.get_text(strip=True) if date_tag else None

        # Processes only Alzheimer-related articles
        if title and href and contains_alzheimer(title):
            titles.append({
                "title": title,
                "link": href,
                "date": date,
                "author": "IGC Pharma"
            })
            print("Saved:", title)
            print("Link:", href)

            driver.get(href)
            time.sleep(2)

            # Saves HTML of article
            safe_title = re.sub(r'[^a-zA-Z0-9_-]', "_", title[:60]) 
            html_filename = os.path.join(folder, f"IGCPharma_{safe_title}.html")
            with open(html_filename, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
           
            # Saves PDF or article
            pdf = driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})
            pdf_filename = os.path.join(folder, f"IGCPharma_{safe_title}.pdf")
            with open(pdf_filename, "wb") as f:
                f.write(base64.b64decode(pdf['data']))

# Function specific for AsceNeuron
def scrape_asceneuron():
    base_url = "https://asceneuron.com/news-events/"
    driver.get(base_url)
    time.sleep(2)

    # Looks for folder AsceNeuron
    folder = "asceneuron_pdfs"
    os.makedirs(folder, exist_ok=True)

    # Saves landing page HTML of AsceNeuron
    landing_html = os.path.join(folder, "AsceNeuron_landing.html")
    with open(landing_html, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"Saved landing page HTML: {landing_html}")

    seen_links = set()

    # Clicks 'Load More' until all articles are loaded, before parsing
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

    # Processes all loaded articles
    for article in soup.select("div.df-item-wrap.df-cpt-title-wrap a"):
        title = article.get_text(strip=True)
        href = urljoin(base_url, article.get("href"))

        if "alzheimer" not in title.lower():
            continue

        # Avoid duplicates
        if any(d.get("link") == href for d in titles):
            continue

       # Visit article to get date
        driver.get(href)
        time.sleep(2)
        detail_soup = BeautifulSoup(driver.page_source, "html.parser")

        # Extract date
        date_tag = detail_soup.select_one("span.df-cpt-date-wrap")
        date = date_tag.get_text(strip=True) if date_tag else None

        # Save metadata
        titles.append({
            "title": title,
            "link": href,
            "date": date,
            "author": "AsceNeuron"
        })
        print("Saved:", title)
        print("Link:", href)
        if date:
            print("Date:", date)

        # Saves HTML or article
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', "_", title[:60])
        html_filename = os.path.join(folder, f"AscenNeuron_{safe_title}.html")
        with open(html_filename, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        # Saves PDF of article
        pdf = driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})
        pdf_filename = os.path.join(folder, f"AscenNeuron_{safe_title}.pdf")
        with open(pdf_filename, "wb") as f:
            f.write(base64.b64decode(pdf['data']))

# Runs for 4 different sites
def main():
    parse_page("https://www.alzinova.com/investors/press-releases/", "mfn-pagination-link.mfn-next")
    parse_page("https://aprinoia.com/news/","")
    scrape_igcpharma()
    scrape_asceneuron()
main() 


# Saves to CSV
df = pd.DataFrame(titles)
df.to_csv("alzheimer_titles.csv", index=False)

print(f"Saved {len(titles)} alzheimer_titles.csv")