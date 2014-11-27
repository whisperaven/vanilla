#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from mako.template import Template
from mako.lookup import TemplateLookup

from vanilla import Engine, TemplateAdapter

# Mako Template Adapter:
class MakoTemplateAdapter(TemplateAdapter):
    """ Mako Template Wrapper """

    def prepare(self, tpl_dir, **opt):
        self.lookup = TemplateLookup(tpl_dir, **opt)

    def render(self, tpl, **tpl_args):
        tpl = self.lookup.get_template(tpl)
        return tpl.render(**tpl_args)

MakoTemplateAdapterOptions = {'module_directory': "/tmp/mako_modules",
                            'collection_size': 350}
        
# App:
app = Engine("whisperaven", 
                appStatic="static",
                appTemplate="templates",
                appTemplateAdapter=MakoTemplateAdapter,
                appTemplateAdapterOptions=MakoTemplateAdapterOptions)

# StaticFiles:
@app.route("/static/(.*)$")
def static_files(filename):
    return app.ssfile(filename)

# Index:
#@app.route("/index$", method = "GET")
def index():
    return app.tpl.render("index.tpl")
app.route("/index$", method = "GET", callback = index)

# UrlArgs:
@app.route("/urlarg/(.*)$")
def urlarg(arg):
    return app.tpl.render("urlarg.tpl", argstr = arg)

# PostData:
@app.route("/postdata$")
def upload():
    data = app.http.request.request_data
    return app.tpl.render("postdata.tpl", userdata = data)

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
        server = make_server("localhost", 8080, app)
        server.serve_forever()
    except KeyboardInterrupt:
        print("exit...")
        sys.exit(1)

