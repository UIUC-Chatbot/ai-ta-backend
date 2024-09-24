    import os
    from dotenv import load_dotenv
    import pytest
    from unittest.mock import Mock, patch
    from ai_ta_backend.database.vector import VectorDatabase
    from qdrant_client import models

    load_dotenv()

    @pytest.fixture
    def mock_qdrant_client():
        return Mock()

    @pytest.fixture
    def mock_vectorstore():
        return Mock()

    @pytest.fixture
    def vector_db(mock_qdrant_client, mock_vectorstore):
        with patch('ai_ta_backend.database.vector.QdrantClient', return_value=mock_qdrant_client), \
            patch('ai_ta_backend.database.vector.Qdrant', return_value=mock_vectorstore), \
            patch('ai_ta_backend.database.vector.OpenAIEmbeddings'), \
            patch.dict('os.environ', {
                'QDRANT_URL': 'http://mock-qdrant-url',
                'QDRANT_API_KEY': 'mock-api-key',
                'QDRANT_COLLECTION_NAME': 'uiuc-chatbot-quantized',
                'VLADS_OPENAI_KEY': 'mock-openai-key'
            }):
            return VectorDatabase()

    # @pytest.mark.skip(reason="This test is not ready yet")
    def test_vector_search(vector_db, mock_qdrant_client):
        # Arrange
        # print("key: ", os.environ['QDRANT_COLLECTION_NAME'])
        search_query = "test query"
        course_name = "Test Course"
        doc_groups = ["Group1", "Group2"]
        user_query_embedding = [0.1, 0.2, 0.3]
        top_n = 5
        disabled_doc_groups = ["DisabledGroup"]
        
        mock_qdrant_client.search.return_value = [{"id": 1, "score": 0.9}]

        # Act
        result = vector_db.vector_search(search_query, course_name, doc_groups, user_query_embedding, top_n, disabled_doc_groups)

        # Assert
        mock_qdrant_client.search.assert_called_once_with(
            collection_name='uiuc-chatbot-quantized',
            query_vector=user_query_embedding,
            query_filter=vector_db._create_search_filter(course_name, doc_groups, disabled_doc_groups),
            limit=top_n
        )    
        assert result == [{"id": 1, "score": 0.9}]

    def test_create_search_filter(vector_db):
        # Test case 1: With doc_groups and disabled_doc_groups
        filter1 = vector_db._create_search_filter("Course1", ["Group1", "Group2"], ["DisabledGroup"])
        assert isinstance(filter1, models.Filter)
        assert len(filter1.must) == 2
        assert len(filter1.must_not) == 1

        # Test case 2: With "All Documents" in doc_groups
        filter2 = vector_db._create_search_filter("Course2", ["All Documents"], [])
        assert isinstance(filter2, models.Filter)
        assert len(filter2.must) == 1
        assert not filter2.must_not

        # Test case 3: Without doc_groups and disabled_doc_groups
        filter3 = vector_db._create_search_filter("Course3", [], [])
        assert isinstance(filter3, models.Filter)
        assert len(filter3.must) == 1
        assert not filter3.must_not

    def test_delete_data(vector_db, mock_qdrant_client):
        # Arrange
        collection_name = "test_collection"
        key = "test_key"
        value = "test_value"

        # Act
        vector_db.delete_data(collection_name, key, value)

        # Assert
        mock_qdrant_client.delete.assert_called_once_with(
            collection_name=collection_name,
            points_selector=models.Filter(must=[
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(value=value),
                ),
            ]),
        )