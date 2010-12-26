import logging
import copy
import j2shim
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponse
from django.shortcuts import redirect

class BaseView(object):
    methods = ("GET", "POST")

    template = "notemplate.html"
    basetemplate = ""

    response = None
    context = {}

    login_required = False
    staff_required = False
    permissions = []

    forms_valid = True
    forms = []
    formdata = {}

    def __init__(self, is_instance=False):
        self.is_instance = is_instance

    def __call__(self, request, *args, **kwargs):

        if not self.is_instance:
            newcopy = copy.copy(self)
            newcopy.is_instance=True
            if self.login_required or self.permissions or self.staff_required:
                newcopy = login_required(newcopy)
            return newcopy(request, *args, **kwargs)

        self.log = logging.getLogger("BaseView")

        self.method = method = request.method

        self.log.debug(u"Request method is : %s" % self.method)

        if not method in self.methods or not hasattr(self, self.method):
            return self.method_not_allowed()

        self.request = request
        self.session = request.session

        return self.run_requests(*args, **kwargs)

    def run_requests(self, *args, **kwargs):
        """
        Run the request gauntlet
        """

        if not self.check_permissions():
            return self.deny_permission()

        self.handle_forms()

        self.pre_view()
        getattr(self, self.method)(*args, **kwargs)
        self.post_view()

        self.context.update(self.set_context())
        return self.render()

    def check_permissions(self):
        if self.staff_required and not self.request.user.is_staff:
            return False
        for perm in self.permissions:
            if not self.request.user.has_perm(perm):
                return False
        return True

    def deny_permission(self):
        return HttpResponse("Permission denied")

    def pre_view(self):
        pass

    def GET(self):
        self.log.debug("Default GET was called")
        pass

    def handle_forms(self):
        for (form, formname) in self.forms:
            if self.method == "POST":
                form_instance = form(self.request.POST)
                if not form_instance.is_valid():
                    self.forms_valid = False
                else:
                    self.formdata[formname] = form_instance.cleaned_data
            else:
                form_instance = form()
            self.context[formname] = form_instance

    def post_view(self):
        pass

    def set_context(self):
        return {}

    def redirect(self, target):
        self.log.debug(u"Setting redirect to target %s" % target)
        self.response = redirect(target)

    def render(self):
        self.request.session = self.session
        if self.response:
            self.log.debug("Returning predefined response")
            return self.response
        self.log.debug("Returning default template")
        self.log.debug(u"Context is : %s" % self.context)
        return j2shim.r2r(self.basetemplate + self.template, self.context, self.request)

    def method_not_allowed(self, method):
        self.log.info("Method is not allowed")
        response = HttpResponse('Method not allowed: %s' % method)
        response.status_code = 405
        return response
