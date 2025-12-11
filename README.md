# Fall25_GiaC_ADBMO
This repository contains all code, files, and documents used for the ADBMO project.

proj7.py 
  proj7.py is the completed and updated webscrapper that scrapes 15 websites for titles, authors, dates, and content from saved HTML files. It also downloads pdf files where available. Within proj7, there's multiple functions that work to collectively deliver the products. These are the following:

save_json function
  This function saves a Python object into a JSON file.

scrape_(website name) function
  This functions visits the website's news page, finds articles that has the word "Alzheimer" in the title and open the article. Then, it will save the full HTML into a local forlder. 

extract_(website name)_metadata function
  This function reads the saved HTML article from the website. It extracts its title, publication date, author, and main text content. In some cases, ir also cleans content or has stricter values to be able to gather clean infomration. The information returned is structured as a dictionary. 

(website name)_metadata function
  This function goes through all of the saved HTML files, extract the metadata through the pervious function, stores it in a list, thne save that list in a JSON file. 

main function
  This function runs all of the scrappers, downloads the articles, extract metadata, saves JSON file, prints progress messages, and closes the web driver.
