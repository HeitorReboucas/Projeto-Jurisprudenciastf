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

    with patch("app.stf.httpx.Client") as client_factory, patch("app.stf.time.sleep") as sleep:
        client_factory.return_value.__enter__.return_value.post.return_value = response
        documents = STFClient().search_page(
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
    sleep.assert_called_once_with(1.0)


def test_normalize_document_rejects_missing_identifier() -> None:
    try:
        STFClient._normalize_document({}, "acordaos")
    except ValueError as error:
        assert "identificador estável" in str(error)
    else:
        raise AssertionError("Documento sem identificador deveria ser rejeitado")


def test_search_reports_empty_accepted_response_as_temporary_portal_failure() -> None:
    response = MagicMock()
    response.status_code = 202
    response.content = b""
    response.headers = {"content-type": "text/html; charset=UTF-8"}
    response.json.side_effect = ValueError("Expecting value: line 1 column 1")

    with patch("app.stf.httpx.Client") as client_factory, patch("app.stf.time.sleep") as sleep:
        client_factory.return_value.__enter__.return_value.post.return_value = response
        try:
            STFClient(max_attempts=1)._post_search(
                {"query": {"match_all": {}}}
            )
        except RuntimeError as error:
            assert "202" in str(error)
            assert "vazia" in str(error).lower()
            assert client_factory.return_value.__enter__.return_value.post.call_count == 1
            sleep.assert_called_once_with(1.0)
        else:
            raise AssertionError("Resposta temporária vazia deveria falhar explicitamente")


def test_default_request_delay_respects_portal_rate_limit() -> None:
    assert STFClient().request_delay_seconds >= 1.0


def test_client_rejects_request_delay_below_portal_rate_limit() -> None:
    try:
        STFClient(request_delay_seconds=0.5)
    except ValueError as error:
        assert "1 segundo" in str(error)
    else:
        raise AssertionError("O cliente aceitou um intervalo abaixo do limite")


def test_search_without_dates_sends_only_keyword_and_content_filters() -> None:
    response = MagicMock()
    response.json.return_value = {"result": {"hits": {"hits": []}}}

    with patch("app.stf.httpx.Client") as client_factory, patch("app.stf.time.sleep"):
        client_factory.return_value.__enter__.return_value.post.return_value = response
        STFClient().search_page(
            query="mulheres e direito fundamental",
            content_type="acordaos",
            date_from=None,
            date_to=None,
            process_class=None,
            page=0,
        )

    sent_body = client_factory.return_value.__enter__.return_value.post.call_args.kwargs[
        "json"
    ]
    filters = sent_body["query"]["bool"]["filter"]
    assert filters == [{"term": {"base": "acordaos"}}]
    assert sent_body["query"]["bool"]["must"][0]["query_string"]["query"] == (
        "mulheres e direito fundamental"
    )


def test_search_accepts_single_open_date_boundary() -> None:
    response = MagicMock()
    response.json.return_value = {"result": {"hits": {"hits": []}}}

    with patch("app.stf.httpx.Client") as client_factory, patch("app.stf.time.sleep"):
        client_factory.return_value.__enter__.return_value.post.return_value = response
        STFClient().search_page(
            query=None,
            content_type="acordaos",
            date_from=date(2024, 1, 1),
            date_to=None,
            process_class=None,
            page=0,
        )

    filters = client_factory.return_value.__enter__.return_value.post.call_args.kwargs[
        "json"
    ]["query"]["bool"]["filter"]
    assert filters == [
        {"term": {"base": "acordaos"}},
        {"range": {"publicacao_data": {"gte": "2024-01-01"}}},
    ]