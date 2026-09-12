"""Offline evaluators. Factories return functions taking (result, reference)."""


def exact_match():
    def score(result, reference):
        completed = result.get("status") == "completed"
        success = (
            completed
            and str(result.get("answer", "")).strip() == str(reference).strip()
        )
        return {
            "success": float(success),
            "steps": result.get("steps"),
            "tokens": result.get("tokens"),
            "tool_calls": result.get("tool_calls"),
            "cost": result.get("cost"),
            "elapsed_seconds": result.get("elapsed_seconds"),
        }

    return score


def retrieval():
    def score(result, reference):
        relevant = set(reference.get("document_ids", []))
        found = {hit["document_id"] for hit in result.get("hits", [])}
        return {"recall": len(found & relevant) / len(relevant) if relevant else None}

    return score


def answer_with_retrieval():
    retrieval_score = retrieval()

    def score(result, reference):
        values = retrieval_score(result, reference)
        values["exact_match"] = float(
            str(result.get("answer", "")).strip() == str(reference["answer"]).strip()
        )
        return values

    return score


answer_with_retrieval.__paper_dependencies__ = (retrieval,)
