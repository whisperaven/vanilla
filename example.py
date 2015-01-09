#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from mako.template import Template
from mako.lookup import TemplateLookup

from vanilla import Engine, TemplateAdapter

# Mako Template Adapter:
class MakoTemplateAdapter(TemplateAdapter):
    """ Mako Template Wrapper """

    def prepare(self, dirs, **opt):
        self.lookup = TemplateLookup(dirs, **opt)

    def render(self, tpl, **tpl_args):
        tpl = self.lookup.get_template(tpl)
        return tpl.render(**tpl_args)

MakoTemplateAdapterOptions = {'module_directory': "/tmp/mako_modules",
                            'collection_size': 350}
        
# App:
app = Engine("VanillaExample", 
                appDebug=False,
                appCatchExc=True,
                appStatic="static",
                appTemplate="templates",
                appTemplateAdapter=MakoTemplateAdapter,
                appTemplateAdapterOptions=MakoTemplateAdapterOptions)

# Hooks:
@app.pre_request
def pre_request_processor():
    response = app.http.response
    # If http error, you can't see this header in response.
    #   because the Engine replace the response instance with
    #   a new HttpError instance.
    response.add_header('framework-pre-set', 'vanilla')


@app.post_request
def post_request_processor():
    response = app.http.response
    # You can always see this header in response.
    response.add_header('framework-post-set', 'vanilla')


# StaticFiles:
@app.route("/static/(.*)$")
def static_files(filename):
    return app.ssfile(filename)


# Index:
#   You specify methods via `methods`, accept both `list` and `str`.
@app.route("/index$", methods="GET")
def index():
    return app.tpl.render("index.tpl")
# Also work: 
#   app.route("/index$", method = "GET", callback = index)


# UrlArgs:
@app.route("/urlarg/(.*)$")
def urlarg(arg):
    return app.tpl.render("urlarg.tpl", argstr=arg)


# PostData:
@app.route("/postdata$", methods=["POST"])
def post_data():
    data = app.http.request.data
    return app.tpl.render("postdata.tpl", userdata=data)


# QueryString:
@app.route("/qs.*$", methods=["GET"])
def qs():
    qs = app.http.request.query_string
    qd = app.http.request.qs_data
    print("qd is ", qd)
    return app.tpl.render("qs.tpl", qs=qs, qd=qd)


# AbortRequest:
@app.route("/abort$", methods="GET")
def abort():
    app.abort(app.tpl.render("abort.tpl"))


# Error Pages:
@app.error_page(400)
def error_400_page():
    return app.tpl.render("error_page.tpl", 
                            error_code = app.http.response.status_code, 
                            error_reason = "Bad Request")


@app.error_page(403)
def error_403_page():
    return app.tpl.render("error_page.tpl",
                            error_code = app.http.response.status_code, 
                            error_reason = "Forbidden")


@app.error_page(404)
def error_404_page():
    return app.tpl.render("error_page.tpl",
                            error_code = app.http.response.status_code, 
                            error_reason = "Not Found")


@app.error_page(500)
def error_500_page():
    return app.tpl.render("error_page.tpl", error_code = 500, 
                            error_reason = app.http.response.body)


## WSGI ##
if __name__ == '__main__':

    from wsgiref.simple_server import make_server

    try:
        print("Try to listening on port 8080...")
        server = make_server("localhost", 8080, app)
        server.serve_forever()
    except KeyboardInterrupt:
        print("exit...")
        sys.exit(1)

