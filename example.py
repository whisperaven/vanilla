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
        
# App:
app = Engine("whisperaven", 
                appStatic="static",
                appTemplate="templates",
                appTemplateAdapter=MakoTemplateAdapter,
                    module_directory = "/tmp/mako_modules",
                    collection_size  = 350)

# StaticFiles:
@app.route("/static/(.*)$")
def static_files(filename):
    return app.ssfile(filename)

# Index:
@app.route("/index$", method = "GET")
def index():
    return app.tpl.render("index.tpl")

# UrlArgs:
@app.route("/project/(.*)$")
def project(project_name):
    return app.tpl.render("project.tpl", name = project_name)

# PostData:
@app.route("/upload$")
def upload():
    data = app.http.request.request_data
    return app.tpl.render("upload.tpl", name = data)

# Error Pages:
@app.error_page(400)
def error_400_page():
    return app.tpl.render("error_page.tpl", error_code = 400, 
                            error_reason = "Bad Request")

@app.error_page(403)
def error_403_page():
    return app.tpl.render("error_page.tpl", error_code = 403, 
                            error_reason = "Forbidden")

@app.error_page(404)
def error_404_page():
    return app.tpl.render("error_page.tpl", error_code = 404, 
                            error_reason = "Not Found")

@app.error_page(500)
def error_500_page():
    return app.tpl.render("error_page.tpl", error_code = 500, 
                            error_reason = "Internal Server Error")

## WSGI ##
if __name__ == '__main__':

    from wsgiref.simple_server import make_server

    try:
        server = make_server("localhost", 8080, app)
        server.serve_forever()
    except KeyboardInterrupt:
        print("exit...")
        sys.exit(1)

