import os
import supabase
import pandas as pd
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from multiprocessing import Manager

def qdrant_context_processing(doc, course_name, result_contexts):
    """
    Re-factor QDRANT objects into Supabase objects and append to result_docs
    """
    context_dict = {
        'text': doc.page_content,
        'embedding': '',
        'pagenumber': doc.metadata['pagenumber'],
        'readable_filename': doc.metadata['readable_filename'],
        'course_name': course_name,
        's3_path': doc.metadata['s3_path'],
        'base_url': doc.metadata['base_url']
    }
    if 'url' in doc.metadata.keys():
      context_dict['url'] = doc.metadata['url']
        
    result_contexts.append(context_dict)
    return result_contexts    


def context_padding(found_docs, search_query, course_name):
    """
    Takes top N contexts acquired from QRANT similarity search and pads them
    """
    print("inside main context padding")
    start_time = time.monotonic()

    with Manager() as manager:
        result_contexts = manager.list()
        partial_func = partial(qdrant_context_processing, course_name=course_name, result_contexts=result_contexts)

        with ProcessPoolExecutor() as executor:
            executor.map(partial_func, found_docs[5:])

        print(f"⏰ QDRANT processing runtime: {(time.monotonic() - start_time):.2f} seconds")
        return list(result_contexts)
    