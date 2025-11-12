def validate(doc, method):
    """Auto-generate full name (hb_name) from salutation and name parts."""
    name_parts = []

    if doc.salutation:
        name_parts.append(doc.salutation.strip())
    if doc.first_name:
        name_parts.append(doc.first_name.strip())
    if doc.middle_name:
        name_parts.append(doc.middle_name.strip())
    if doc.last_name:
        name_parts.append(doc.last_name.strip())

    full_name = " ".join(name_parts)

    if full_name:
        doc.custom_hb_name = full_name
    else:
        return
