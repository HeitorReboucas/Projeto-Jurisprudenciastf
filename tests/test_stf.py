from datetime import date
from unittest.mock import MagicMock, patch

from app.stf import STFClient


def test_search_page_sends_official_query_and_maps_hit() -> None:
    response = MagicMock()
    response.json.return_value = {
        "result": {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "base": "acordaos",
                            "id": "sjur123",
                            "titulo": "RE 123",
                            "processo_codigo_completo": "RE 123",
                            "processo_classe_processual_unificada_sigla": "RE",
                            "publicacao_data": "2024-01-15",
                            "inteiro_teor_url": "https://portal.stf.jus.br/documento.pdf",
                        }
                    }
                ]
            }
        }
    }

    with patch("app.stf.httpx.Client") as client_factory:
        client_factory.return_value.__enter__.return_value.post.return_value = response
        documents = STFClient(request_delay_seconds=0).search_page(
            query="liberdade de expressão",
            content_type="acordaos",
            date_from=date(2024, 1, 1),
            date_to=date(2024, 12, 31),
            process_class="RE",
            page=2,
            page_size=50,
        )

    assert len(documents) == 1
    assert documents[0].document_key == "acordaos:sjur123"
    assert documents[0].process == "RE 123"
    assert documents[0].pdf_url == "https://portal.stf.jus.br/documento.pdf"

    sent_body = client_factory.return_value.__enter__.return_value.post.call_args.kwargs[
        "json"
    ]
    assert sent_body["from"] == 100
    assert sent_body["size"] == 50
    assert sent_body["query"]["bool"]["filter"][0] == {
        "term": {"base": "acordaos"}
    }
    assert sent_body["query"]["bool"]["must"][0]["query_string"]["query"] == (
        "liberdade de expressão"
    )


def test_normalize_document_rejects_missing_identifier() -> None:
    try:
        STFClient._normalize_document({}, "acordaos")
    except ValueError as error:
        assert "identificador estável" in str(error)
    else:
        raise AssertionError("Documento sem identificador deveria ser rejeitado")