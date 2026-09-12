"""Descriptive execution metrics; answer quality is unknown without references."""


def response_metrics():
    def score(result, reference):
        completed = result.get("status") == "completed"
        references = reference if isinstance(reference, list) else [reference]
        match = (
            None
            if reference is None
            else float(
                completed
                and any(
                    str(result.get("answer", "")).strip() == str(r).strip()
                    for r in references
                )
            )
        )
        return {
            "completed": float(completed),
            "exact_match": match,
            **{
                key: result.get(key)
                for key in (
                    "steps",
                    "simulations",
                    "tokens",
                    "llm_calls",
                    "elapsed_seconds",
                    "tree_nodes",
                    "tree_depth",
                    "facts",
                    "pruned_nodes",
                    "cost",
                )
            },
        }

    return score
