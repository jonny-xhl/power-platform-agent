"""Solution — HKL CCRM Page 21 (Figma "2.3 View Tenant Contact").

A single brand-new unmanaged solution that holds every component this feature creates:
- the ``contact`` entity's custom fields (Contact Code / Tenant Code / HKL PIC / Last
  Engagement Date) — added via ``deploy contact --solution``;
- the custom web resources (HTML contact-list page + JS + CSS) — added via
  ``webresource sync --solution``;
- the Account "Contact View" form (Contact tab embeds the HTML page) — added via
  ``form deploy --solution``;
- the Contact "Summary and Engagements" form — added via ``form deploy --solution``.

This file is the SHELL only (publisher + solution object); the components themselves are
deployed by their own phase commands with ``--solution new_HklccrmPage21``, which adds each
to this solution (idempotent). Keeping the shell empty avoids ``solution_deployer``'s
standard-entity skip on the authored forms.
"""

from framework_power import Publisher, Solution

SOLUTION = Solution(
    unique_name="new_HklccrmPage21",
    friendly_name="HKL CCRM Page 21",
    version="1.0.0.0",
    publisher=Publisher(
        name="DefaultPublishercrmdev",
        display_name="CrmDev 的默认发布者",
        prefix="new",
    ),
)
