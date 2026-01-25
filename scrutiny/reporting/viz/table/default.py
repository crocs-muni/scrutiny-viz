from typing import List, Any
from dominate import tags
from scrutiny.htmlutils import show_hide_div

def render_table_block(headers: List[str], rows: List[List[Any]]):
    """
    Render a generic table block (NO per-table show/hide).
    The section wrapper decides visibility.
    """
    container = tags.div(_class="table-container")

    with container:
        t = tags.table(_class="report-table")
        with t:
            with tags.thead():
                with tags.tr():
                    for h in headers:
                        tags.th(str(h))

            with tags.tbody():
                for r in rows or []:
                    cells = r if isinstance(r, (list, tuple)) else [r]
                    with tags.tr():
                        for c in cells:
                            if hasattr(c, "__html__") or hasattr(c, "render"):
                                tags.td(c)
                            else:
                                tags.td(str(c))
    return container
