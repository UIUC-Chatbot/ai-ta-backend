from arize.api import Client
from arize.pandas.embeddings import EmbeddingGenerator, UseCases
# from arize.utils import ModelTypes
# from arize.utils.ModelTypes import GENERATIVE_LLM
from arize.utils.types import (Embedding, EmbeddingColumnNames, Environments,
                               Metrics, ModelTypes, Schema)

# self.arize_client = Client(space_key=os.getenv('ARIZE_SPACE_KEY'), api_key=os.getenv('ARIZE_API_KEY')) # type: ignore

def log_to_arize(self, course_name: str, user_question: str, llm_completion: str) -> str:
    import pandas as pd
    
    features = {
        'state': 'wa',
        'city': 'seattle',
        'merchant_name': 'Starbucks Coffee',
        'pos_approved': True,
        'item_count': 2,
        'merchant_type': 'coffee shop',
        'charge_amount': 22.11,
        }
        
    #example tags
    tags = {
        'age': 21,
        'zip_code': '94610',
        'device_os': 'MacOS',
        'server_node_id': 120,
        }

    #example embeddings
    embedding_features = {
            # 'image_embedding': Embedding(
            #     vector=np.array([1.0, 2, 3]), # type: ignore
            #     link_to_data='https://my-bucket.s3.us-west-2.amazonaws.com/puppy.png',
            # ),
            'prompt': Embedding(
                vector=pd.Series([6.0, 1.0, 2.0, 6.0]), # type: ignore
                data='slightly different This is a test sentence',
            ),
            'completion': Embedding(
                vector=pd.Series([15.0, 10.0, 1.0, 9.0]), # type: ignore
                data=['slightly', 'different', 'This', 'is', 'a', 'sample', 'token', 'array'],
            ),
        }

    #log the prediction
    response = self.arize_client.log(
        prediction_id=str(uuid.uuid4()),
        prediction_label=llm_completion,
        model_id='kas-model-1',
        # model_type=ModelTypes.GENERATIVE_LLM, # I think this is a bug. 
        model_type=ModelTypes.SCORE_CATEGORICAL,
        environment=Environments.PRODUCTION,
        model_version='v1',
        prediction_timestamp=int(datetime.datetime.now().timestamp()),
        features=features,
        embedding_features=embedding_features,
        tags=tags,
    )
  
    ## Listen to response code to ensure successful delivery
    res = response.result()
    if res.status_code == 200:
        print('Success sending Prediction!')
        return "Success logging to Arize!"
    else:
        print(f'Log failed with response code {res.status_code}, {res.text}')
        return f'Log failed with response code {res.status_code}, {res.text}'
