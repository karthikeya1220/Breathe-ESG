"""
OrgMiddleware — injects request.org from authenticated user.
Every ViewSet that touches multi-tenant data must call get_queryset()
with .filter(org=self.request.org).
"""


class OrgMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Attach org to request after auth middleware runs
        request.org = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.org = getattr(request.user, 'org', None)
        response = self.get_response(request)
        return response
