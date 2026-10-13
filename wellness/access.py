"""SR10: authorization check on every request for a wearer's data.

Allowed requesters:
  1. the wearer;
  2. an accepted trusted contact reading a data category the wearer selected
     (PR3, PR4, PR10);
  3. a user linked to the wearer by a pending or accepted invitation,
     reading the wearer's display name only.
The check reads the database on every request, so removing a contact or
deselecting a category takes effect from the next request (PR7).
"""

from . import audit
from .db import query_one

CATEGORIES = ("heart_rate", "steps", "sleep", "alerts")   # FR22


def can_read(requester_id, wearer_id, category):
    if requester_id == wearer_id:
        return True

    if category == "display_name":
        link = query_one(
            "SELECT 1 FROM invitations WHERE (wearer_id = ? AND contact_user_id = ?) "
            "OR (wearer_id = ? AND contact_user_id = ?)",
            (wearer_id, requester_id, requester_id, wearer_id),
        )
        return link is not None

    if category not in CATEGORIES:
        return False
    link = query_one(
        "SELECT * FROM invitations WHERE wearer_id = ? AND contact_user_id = ? AND status = 'accepted'",
        (wearer_id, requester_id),
    )
    return link is not None and link["share_" + category] == 1


def check(requester_id, wearer_id, category):
    """Returns None if allowed, or an HTTP 403 response (SR12). Logs the result (SR21)."""
    if can_read(requester_id, wearer_id, category):
        audit.log("sensitive_data_access", "success", requester_id)
        return None
    audit.log("authorization_failure", "denied", requester_id)
    return {"error": "Forbidden"}, 403
