from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlencode

import httpx


STF_SEARCH_URL = "https://jurisprudencia.stf.jus.br/api/search/search"
CONTENT_BASES = {
    "acordaos": "acordaos",
    "decisoes_monocraticas": "decisoes",
    "sumulas": "sumulas",
    "informativos": "informativos",
}
SEARCH_FIELDS = [
    "processo_codigo_completo.plural",
    "titulo.plural^6",
    "ementa_texto.plural^3",
    "decisao_texto.plural^2",
    "inteiro_teor_texto.plural",
    "documental_indexacao_texto.plural",
]


@dataclass(frozen=True)
class STFDocument:
    document_key: str
    title: str
    process: str | None
    process_class: str | None
    content_type: str
    document_date: str | None
    source_url: str
    pdf_url: str | None


class STFClient:
    def __init__(
        self,
        *,
        search_url: str = STF_SEARCH_URL,
        timeout_seconds: float = 30,
        request_delay_seconds: float = 0.25,
        max_attempts: int = 3,
    ) -> None:
        self.search_url = search_url
        self.timeout_seconds = timeout_seconds
        self.request_delay_seconds = request_delay_seconds
        self.max_attempts = max_attempts

    def search_page(
        self,
        *,
        query: str | None,
        content_type: str,
        date_from: date,
        date_to: date,
        process_class: str | None,
        page: int,
        page_size: int = 100,
    ) -> list[STFDocument]:
        base = CONTENT_BASES.get(content_type)
        if base is None:
            raise ValueError(f"Tipo de conteúdo não suportado: {content_type}")

        filters: list[dict[str, Any]] = [{"term": {"base": base}}]
        filters.append(
            {
                "range": {
                    "publicacao_data": {
                        "gte": date_from.isoformat(),
                        "lte": date_to.isoformat(),
                    }
                }
            }
        )
        if process_class:
            filters.append(
                {
                    "match_phrase": {
                        "processo_classe_processual_unificada_sigla": process_class
                    }
                }
            )

        search_query: dict[str, Any]
        if query:
            search_query = {
                "query_string": {
                    "query": query,
                    "default_operator": "AND",
                    "fields": SEARCH_FIELDS,
                }
            }
        else:
            search_query = {"match_all": {}}

        body = {
            "from": page * page_size,
            "size": page_size,
            "sort": [{"publicacao_data": {"order": "asc", "unmapped_type": "date"}}],
            "query": {"bool": {"must": [search_query], "filter": filters}},
        }

        response_data = self._post_search(body)
        hits = response_data.get("result", {}).get("hits", {}).get("hits", [])
        return [
            self._normalize_document(hit.get("_source", {}), content_type)
            for hit in hits
        ]

    def _post_search(self, body: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                time.sleep(self.request_delay_seconds)
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        self.search_url,
                        json=body,
                        headers={"User-Agent": "STF-Jurisprudencias-Coletor/1.0"},
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
                if attempt + 1 < self.max_attempts:
                    time.sleep(min(2**attempt, 8))

        raise RuntimeError(f"Falha na pesquisa oficial do STF: {last_error}") from last_error

    @staticmethod
    def _normalize_document(source: dict[str, Any], content_type: str) -> STFDocument:
        document_id = source.get("id") or source.get("dg_unique") or source.get("titulo")
        if not document_id:
            raise ValueError("Documento do STF sem identificador estável")

        document_number = source.get("processo_codigo_completo") or source.get("titulo")
        return STFDocument(
            document_key=f"{source.get('base', content_type)}:{document_id}",
            title=str(source.get("titulo") or document_number or document_id),
            process=document_number,
            process_class=source.get("processo_classe_processual_unificada_sigla"),
            content_type=content_type,
            document_date=source.get("publicacao_data") or source.get("julgamento_data"),
            source_url=(
                "https://jurisprudencia.stf.jus.br/pages/search?"
                + urlencode(
                    {
                        "base": CONTENT_BASES[content_type],
                        "queryString": str(document_id),
                    }
                )
            ),
            pdf_url=source.get("inteiro_teor_url"),
        )