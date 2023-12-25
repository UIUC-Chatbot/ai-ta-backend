import os
import requests
import json

# Below functions hit API endpoints from sites like arXiv, Elsevier, and Sringer Nature to retrieve journal articles

def arxiv_ingest():
    """
    This function retrieves journal articles from arXiv
    """
    
