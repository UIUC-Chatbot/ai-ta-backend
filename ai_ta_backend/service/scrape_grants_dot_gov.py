import pandas as pd
from injector import inject


class ScrapeGrantsDotGov:

  @inject
  # def __init__(self, sql: SQLDatabase, s3: AWSStorage, sentry: SentryService, executor: ProcessPoolExecutorAdapter):
  def __init__(self):
    pass
    # self.sql = sql
    # self.s3 = s3
    # self.sentry = sentry
    # self.executor = executor

  def main_scrape(self):
    """
    This function is used to test the process.
    """
    # return {"response": "Test process successful.", "results": results}
    pass

  # def start_ingest(self, df: DataFrame):
  def start_ingest(self):
    import requests
    df = pd.read_csv('/Users/kvday2/code/ai-ta/ai-ta-backend/cleaned_grants_gov_data.csv')

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
        response = requests.post('https://crawlee-production.up.railway.app/crawl', json={'params': post_params})
        # response = requests.post('http://localhost:3000/crawl', )
        num_success += 1
      else:
        print(f"Skipping invalid URL at row {index}: {opportunity_url}")
    print('num_successes', num_success)

  def clean_csv(self, csv_file: str):
    import re

    import pandas as pd

    # Read the CSV file
    df = pd.read_csv(csv_file)

    # Extract hyperlinks from the OPPORTUNITY NUMBER column
    df['OPPORTUNITY NUMBER'] = df['OPPORTUNITY NUMBER'].apply(
        lambda x: re.search(r'https://www\.grants\.gov/search-results-detail/\d+', x).group()  # type: ignore
        if pd.notnull(x) and re.search(r'https://www\.grants\.gov/search-results-detail/\d+', x) else x)

    # Print the head of the DataFrame
    print("Head of the DataFrame:")
    print(df.head())

    # Save the DataFrame to disk
    df.to_csv("cleaned_grants_gov_data.csv", index=False)
    print(f"Cleaned data saved to: cleaned_grants_gov_data.csv")

    return df

  def download_csv(self):
    import os
    import time
    from pathlib import Path

    import requests
    from bs4 import BeautifulSoup
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

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

    # Initialize driver with options
    driver = webdriver.Chrome(options=chrome_options)

    # Set up Selenium WebDriver (you may need to adjust this based on your setup)

    try:
      # Navigate to the grants search page
      driver.get("https://grants.gov/search-grants")

      export_links = WebDriverWait(driver, 10).until(
          EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a.usa-link[data-v-aa588342]')))
      print("Export links: ", export_links)
      export_link = export_links[1]

      time.sleep(5)
      # Click the export link
      export_link.click()

      # Wait for the download to complete (adjust the time as needed)
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
        return cleaned_csv
      else:
        print("No files found in the download directory.")
        return None
    except Exception as e:
      print(e)
      # self.sentry.capture_exception(e)

    finally:
      driver.quit()


if __name__ == "__main__":

  # export_service = ExportService(SQLDatabase(), AWSStorage(), SentryService(), ProcessPoolExecutorAdapter())
  scraper = ScrapeGrantsDotGov()
  # df = scraper.download_csv()
  # if df is not None:
  #   scraper.start_ingest(df)
  scraper.start_ingest()
