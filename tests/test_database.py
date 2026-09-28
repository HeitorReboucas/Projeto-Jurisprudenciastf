from app.database import Database


def test_job_documents_are_idempotent_and_counts_survive_reopen(tmp_path) -> None:
    database_path = tmp_path / "state.sqlite3"
    database = Database(database_path)
    database.initialize()
    database.create_job(
        "job-1",
        {
            "content_types": ["acordaos"],
            "date_from": "2024-01-01",
            "date_to": "2024-12-31",
            "query": "liberdade",
            "process_class": None,
            "drive_folder_id": None,
        },
    )
    document = database.insert_document(
        {
            "document_key": "acordaos:sjur1",
            "title": "RE 1",
            "process": "RE 1",
            "process_class": "RE",
            "content_type": "acordaos",
            "document_date": "2024-01-01",
            "source_url": "https://jurisprudencia.stf.jus.br/",
            "pdf_url": "https://portal.stf.jus.br/documento.pdf",
            "status": "pending",
        }
    )

    assert database.link_job_document("job-1", document["id"])
    assert not database.link_job_document("job-1", document["id"])
    database.update_job_document_status("job-1", document["id"], "downloaded")
    database.update_document(
        document["id"],
        status="downloaded",
        local_path=str(tmp_path / "RE_1.pdf"),
        hash_sha256="digest-1",
    )

    reopened_database = Database(database_path)
    assert reopened_database.job_counts("job-1") == {
        "found": 1,
        "downloaded": 1,
        "uploaded": 0,
        "duplicates": 0,
        "errors": 0,
    }
    assert reopened_database.find_document_by_hash("digest-1")["document_key"] == (
        "acordaos:sjur1"
    )


def test_running_jobs_are_marked_interrupted_on_startup(tmp_path) -> None:
    database = Database(tmp_path / "state.sqlite3")
    database.initialize()
    database.create_job("job-2", {"content_types": ["acordaos"]})
    database.update_job("job-2", status="running")

    assert database.interrupt_running_jobs() == ["job-2"]
    assert database.get_job("job-2")["status"] == "interrupted"