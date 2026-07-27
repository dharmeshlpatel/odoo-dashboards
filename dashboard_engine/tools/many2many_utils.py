def compute_many2many_order(current_ids, existing_order_str):
    """
    Compute a stable ordering for a many2many field.

    The function preserves the previously stored order where possible
    and appends any newly added IDs at the end, ensuring no duplicates.

    :param current_ids: List of current many2many record IDs.
    :type current_ids: list[int]
    :param existing_order_str: Previously stored comma-separated ID order.
    :type existing_order_str: str
    :return: Updated comma-separated ID order.
    :rtype: str
    """
    if not current_ids:
        return ""

    # Normalize existing order into a unique list of integers
    existing_ids = []
    for value in (existing_order_str or "").split(","):
        try:
            record_id = int(value)
        except (ValueError, TypeError):
            continue
        if record_id not in existing_ids:
            existing_ids.append(record_id)

    # Keep only IDs that are still present
    ordered_ids = [rid for rid in existing_ids if rid in current_ids]

    # Append new IDs while preserving input order
    ordered_ids.extend(rid for rid in current_ids if rid not in ordered_ids)

    return ",".join(str(rid) for rid in ordered_ids)
