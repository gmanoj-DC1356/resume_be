from rest_framework.permissions import BasePermission, IsAuthenticated


class CanViewResume(BasePermission):
    """Who may open a given resume.

    Current policy: any authenticated recruiter may open any resume. The object-level hook is the
    single place to tighten this later (for example by role or ownership) without touching the view.
    """

    message = "You do not have access to this resume."

    def has_permission(self, request, view) -> bool:
        return IsAuthenticated().has_permission(request, view)

    def has_object_permission(self, request, view, obj) -> bool:
        return bool(request.user and request.user.is_authenticated)
