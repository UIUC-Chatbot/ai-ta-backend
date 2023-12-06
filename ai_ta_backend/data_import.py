import os
import arxiv
import pandas as pd

def get_arxiv_data(query: str) -> str:
    """
    Fetch papers through query or id and store them in local directory.
    Eventually needs to be ingested into database.
    """

    search = arxiv.Search(query=query, 
                          max_results=10, 
                          sort_by = arxiv.SortCriterion.SubmittedDate)
    
    directory = os.path.join(os.getcwd(), 'arxiv_papers')
    if not os.path.exists(directory):
        os.makedirs(directory)

    for result in arxiv.Client().results(search):
        print("Downloading paper: ", result.title)
        result.download_pdf(dirpath=directory)
    

    return "success"
