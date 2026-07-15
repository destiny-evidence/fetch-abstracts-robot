import json

from far.local.models import LocalAbstractRetrievalOutput


def test_local_abstract_retrieval_output_model():

    original_dois = ["10.1000/xyz123", "10.1000/xyz456", "10.1000/xyz789"]
    original_abstracts = [
        {"doi": original_dois[0], "abstract": "This is a test abstract 1."},
        {"doi": original_dois[1], "abstract": "This is a test abstract 2."},
        {"doi": original_dois[2], "abstract": "This is a test abstract 3."},
    ]

    dois_with_abstracts = original_dois[:2]
    dois_without_abstracts = original_dois[2:]

    output_model = LocalAbstractRetrievalOutput(
        abstracts=original_abstracts,
        dois_with_abstracts=dois_with_abstracts,
        dois_without_abstracts=dois_without_abstracts,
    )

    json_output = output_model.model_dump_json(indent=2)
    dict_from_json = json.loads(json_output)

    assert isinstance(output_model, LocalAbstractRetrievalOutput)
    assert output_model.abstracts is not None
    assert output_model.abstracts == original_abstracts
    assert output_model.dois_with_abstracts == dois_with_abstracts
    assert output_model.dois_without_abstracts == dois_without_abstracts

    assert dict_from_json.get("abstracts") == original_abstracts
    assert dict_from_json.get("dois_with_abstracts") == dois_with_abstracts
    assert dict_from_json.get("dois_without_abstracts") == dois_without_abstracts
