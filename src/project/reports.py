"""Reports consume committed metrics and never call the model."""

from framework.runtime.reporting import comparison_table


def summary(context, title="DeepQuestionTree experiment summary"):
    comparison_table(context)
    path = context.output_dir / "comparison.md"
    content = path.read_text(encoding="utf-8")
    path.write_text(f"# {title}\n\n" + content, encoding="utf-8")


summary.__paper_dependencies__ = (comparison_table,)
