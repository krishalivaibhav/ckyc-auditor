from retrieval import retrieve_documents


def generate_report(risk_event):
    """
    Generate an investigation report using retrieved evidence.
    """

    # Search relevant evidence
    results = retrieve_documents(
        risk_event.event_type
    )

    documents = results["documents"][0]

    metadatas = results["metadatas"][0]

    timeline = []

    citations = []

    summary = []

    for i in range(len(documents)):

        doc = documents[i]

        metadata = metadatas[i]

        timeline.append(
            {
                "date": risk_event.detected_at,
                "event": f"Evidence retrieved from {metadata['filename']}",
                "source_url": metadata["filename"],
                "excerpt": doc[:120]
            }
        )

        citations.append(
            {
                "claim": f"Evidence from {metadata['filename']}",
                "source_url": metadata["filename"],
                "excerpt": doc[:120]
            }
        )

        summary.append(
            f"Evidence from {metadata['filename']} indicates potential {risk_event.event_type.replace('_', ' ')}."
        )

    return {
        "summary": " ".join(summary),
        "timeline": timeline,
        "citations": citations
    }
