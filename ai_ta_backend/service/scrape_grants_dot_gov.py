import pandas as pd
from injector import inject

from ai_ta_backend.service.retrieval_service import RetrievalService
from ai_ta_backend.service.sentry_service import SentryService


class ScrapeGrantsDotGov:

  @inject
  def __init__(self, retrievalService: RetrievalService, sentryService: SentryService):
    self.retrievalService = retrievalService
    self.sentryService = sentryService

  def main_scrape(self):
    """
    ⭐️ MAIN ENTRYPOINT ⭐️
    """
    df = self.download_csv()
    if df is not None:
      only_new_grants_df = self.remove_expired_grants(df)
      self.start_ingest(only_new_grants_df)

  def remove_expired_grants(self, df: pd.DataFrame):
    """
    1. Search SQL DB for all URLs values that are NOT in the current list, delete those.
    2. Remove URLs from the DataFrame that are already in the DB.
    """

    from ai_ta_backend.database.sql import SQLDatabase
    sql = SQLDatabase()

    all_materials = sql.getAllMaterialsForCourse_fullUsingPagination('grantsdotgov')
    print(f"⏰ Total URLs in DB: {len(all_materials)}")

    # Get all URLs from the DB
    db_urls = set(material['url'] for material in all_materials if 'url' in material)

    # Get all URLs from the DataFrame
    df_urls = set(df['OPPORTUNITY NUMBER'])

    # Find URLs in DB that are not in the current DataFrame
    urls_to_delete = db_urls - df_urls

    # Delete the expired grants
    for url in urls_to_delete:
      print("URL to delete from UIUC.chat (it's no longer a valid grant): ", url)
      sql.deleteMaterialsForCourseAndKeyAndValue('grantsdotgov', 'url', url)

    print(f"🗑️ Deleted {len(urls_to_delete)} expired grants from the database.")

    # Remove URLs from the DataFrame that are already in the DB
    new_urls_only = list(df_urls - db_urls)
    df = df.loc[df['OPPORTUNITY NUMBER'].isin(new_urls_only)]
    print(f"📊 DataFrame now contains {len(df)} new grants not present in the database.")
    return df

  def start_ingest(self, df: pd.DataFrame):
    """
    Do this sequentially so we don't overwhelm our web scraper, although that should be fine.
    """
    import requests

    # for testing
    # df = pd.read_csv('/Users/kvday2/code/ai-ta/ai-ta-backend/cleaned_grants_gov_data.csv')

    num_success = 0
    for index, row in df.iterrows():
      opportunity_url = row['OPPORTUNITY NUMBER']
      print(f"Processing row {index}: {opportunity_url}")
      if isinstance(opportunity_url, str) and opportunity_url.startswith('https://'):
        post_params = {
            'url': opportunity_url,
            # 'url': 'https://www.grants.gov/search-results-detail/356973',
            'courseName': 'grantsdotgov',
            'maxPagesToCrawl': 1,
            'scrapeStrategy': 'equal-and-below',
            'match': '**',
            'maxTokens': 20_000,
        }
        requests.post('https://crawlee-production.up.railway.app/crawl', json={'params': post_params}, timeout=60)
        num_success += 1
      else:
        print(f"Skipping invalid URL at row {index}: {opportunity_url}")
    print('num_successes', num_success)

  def clean_csv(self, csv_file: str):
    import re

    # Read the CSV file
    df = pd.read_csv(csv_file)

    # Extract hyperlinks from the OPPORTUNITY NUMBER column
    df['OPPORTUNITY NUMBER'] = df['OPPORTUNITY NUMBER'].apply(
        lambda x: re.search(r'https://www\.grants\.gov/search-results-detail/\d+', x).group()  # type: ignore
        if pd.notnull(x) and re.search(r'https://www\.grants\.gov/search-results-detail/\d+', x) else x)

    # Print the head of the DataFrame
    # print("Head of the DataFrame:")
    # print(df.head())

    # Save the DataFrame to disk
    # df.to_csv("cleaned_grants_gov_data.csv", index=False)
    # print(f"Cleaned data saved to: cleaned_grants_gov_data.csv")

    return df

  def download_csv(self):
    import os
    import shutil
    import time
    from pathlib import Path

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    # from webdriver_manager.core.utils import ChromeType
    from webdriver_manager.chrome import ChromeDriverManager

    # Create an absolute path for downloads that works cross-platform
    download_dir = str(Path.cwd() / "grants-dot-gov-downloads")
    os.makedirs(download_dir, exist_ok=True)

    # Configure Chrome options
    chrome_options = Options()
    chrome_options.add_experimental_option(
        "prefs", {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        })
    chrome_options.add_argument("--headless=new")  # Use the new headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--dns-prefetch-disable")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--enable-logging")
    chrome_options.add_argument("--verbose")

    # Initialize the WebDriver with WebDriver Manager for Chromium
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver = webdriver.Chrome(options=chrome_options)

    try:
      # Navigate to the grants search page
      driver.get("https://grants.gov/search-grants")

      export_links = WebDriverWait(driver, 10).until(
          EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a.usa-link[data-v-aa588342]')))
      print("Export links: ", export_links)
      export_link = export_links[1]

      time.sleep(7)  # The export link needs time to load. It's slow, like 3 sec.

      # Click the export link
      export_link.click()

      # Wait for the download to complete (it's super fast, like 0.1 seconds)
      time.sleep(4)

      # Get the download directory
      download_dir = "grants-dot-gov-downloads"

      # Create the directory if it doesn't exist
      os.makedirs(download_dir, exist_ok=True)

      # Find the most recently downloaded file
      files = sorted([os.path.join(download_dir, f) for f in os.listdir(download_dir)],
                     key=os.path.getmtime,
                     reverse=True)

      if files:
        latest_file = files[0]
        print(f"CSV downloaded and saved as: {latest_file}")
        cleaned_csv = self.clean_csv(latest_file)
        shutil.rmtree(download_dir, ignore_errors=True)
        return cleaned_csv
      else:
        print("No files found in the download directory.")
        raise Exception("Failed to download grants CSV from website. No files found in the download directory.")
    finally:
      driver.quit()
