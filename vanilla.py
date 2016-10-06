#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" 
Simple web app engine, developed by Hao Feng (whisperaven@gmail.com).

    1, Provide basic request dispatching.
    2, Provide basic http context access (e.g.: request/response/cookie).
    3, Provide basic http tools (e.g.: static file sender).

"""

import os
import re
import sys
import time
import json
import socket
import mimetypes

from copy import deepcopy
from threading import local
from traceback import format_exc

try:                # Py2
    import httplib
    import __builtin__ as builtins
    from inspect import getargspec as getfullargspec
    from urlparse import parse_qs
except ImportError: # Py3
    import http.client as httplib
    import builtins
    from inspect import getfullargspec
    from urllib.parse import parse_qs


## Compatible issues ##
if "unicode" not in dir(builtins):
    unicode = str
else:
    bytes   = str
       

## Http ##
_HTTP_PORT   = socket.getservbyname("http")
_HTTP_METHOD = ["GET", "POST", "PUT", "DELETE", "TRACE",
                    "CONNECT", "OPTION", "ANY"]
_HTTP_STATUS = deepcopy(httplib.responses)
_HTTP_ERROR_PAGE_CONTENT = "<html><title>oops</title>" \
                            "<body>Http Error occurred</body></html>"


## Helper ##
def _errno():
    """ Compatible with old versions which doesn't have the `as` keyword. """
    return sys.exc_info()[1]


def u2b(string, encoding="utf8", errors="strict"):
    """ Covert unicode/str to str/bytes, 
            if string already encoded, do nothing. """
    if isinstance(string, unicode):
        return string.encode(encoding, errors)
    else:
        return string


def b2u(string, encoding="utf8", errors="strict"):
    """ Covert str/bytes to unicode/str, 
            if string already decoded, do nothing. """
    if isinstance(string, bytes):
        return string.decode(encoding, errors)
    else:
        return string


## Exception ##
class VanillaError(Exception):
    """ Base Exception for everything. """
    pass


class EngineError(VanillaError):
    """ Base Exception for Engine errors. """


class HttpAbort(EngineError):
    """ Abort the current http process. 
        
        See doc str of `Engine.abort` for more detail. """

    def __init__(self, buf=""):
        """ Abort context. """
        self.buf = buf


class RouterError(VanillaError):
    """ Base Exception for Router errors. """


## TemplateEngineAdapter ##
class TemplateAdapter(object):
    """ Template Engine. """

    def __init__(self, dirs, **options):
        """ Prepare template adapter. """
        self.prepare(dirs, **options)

    def prepare(self, dirs, **opt):
        """ Userdefine template adapter prepare method. """
        raise NotImplementedError

    def render(self, tpl, **tpl_args):
        """ Userdefine template render method. """
        raise NotImplementedError


## AppEngine ##
class Engine(object):
    """ The engine object for create app instance. """

    def __init__(self, appName="vanilla.latte", 
                        appDebug=False,
                        appCatchExc=True,
                        appPrefix=os.getcwd(), 
                        appStatic="static", 
                        appTemplate="templates",
                        appTemplateAdapter=None,
                        appTemplateAdapterOptions=dict()):
        """ Init new App instance. """

        self.name        = appName
        self.prefix      = appPrefix
        self.static      = appStatic
        self.template    = list()

        self.debug       = appDebug
        self.catch       = appCatchExc
        self.content     = HttpContext()
        self.router      = RequestRouter()
        self.err_handler = dict()

        self.request_preprocessor = list()
        self.request_postprocessor = list()

        if not os.path.isabs(self.static):
            self.static   = os.path.join(self.prefix, self.static)

        appTemplate = appTemplate if isinstance(appTemplate, (list, tuple)) \
                                        else (appTemplate,)
        for template in appTemplate:
            if not os.path.isabs(template):
                template = os.path.join(self.prefix, template)
            self.template.append(template)

        if appTemplateAdapter:
            self.tpl     = appTemplateAdapter(dirs=self.template, 
                                                **appTemplateAdapterOptions)

    def __call__(self, environ, start_response):
        """ WSGI compatible callable object. """
        return self.wsgi(environ, start_response)

    def get_tpl(self):
        """ Return the Template Reader Object of this instance. """
        return self.tpl

    def get_ctx(self):
        """ Return the Http Content Object of this instance. """
        return self.content

    def ssfile(self, filepath, mime_type=None, prefix=None):
        """ Static file sender. """
        
        if prefix is None:
            prefix = self.static

        filepath = os.path.join(prefix, filepath)
        if os.path.isdir(filepath) or not os.access(filepath, os.R_OK):
            raise HttpError(403)
        elif not os.path.exists(filepath):
            raise HttpError(404)

        response = self.content.response
        filestat = os.stat(filepath)

        if mime_type is None:
            mime_type, encoding = mimetypes.guess_type(filepath)
            if encoding:
                response.set_header("Content-Encoding", encoding)

        response.set_header("Content-Type", mime_type)
        response.set_header("Content-Length", filestat.st_size)
        response.set_header("Last-Modified", 
                                time.strftime("%a, %d %b %Y %H:%M:%S GMT", 
                                                time.gmtime(filestat.st_mtime)))

        return open(filepath, 'rb')

    def route(self, regex, methods=["GET"], callback=None):
        """ Insert new rule to Router. """

        if callback is not None:
            self.router.insert(methods, regex, callback)
            return 0

        def _add_rule(callback):
            self.router.insert(methods, regex, callback)

        return _add_rule

    def error_page(self, http_error_code, callback=None):
        """ Register error handler for http error such as 404/500. """
        
        if callback is not None:
            self.err_handler[int(http_error_code)] = callback
            return 0

        def _register_error_handler(callback):
            self.err_handler[int(http_error_code)] = callback

        return _register_error_handler

    def pre_request(self, callback):
        """ Register handler as each http request preprocessor. 
        
            While the handler invoked, you can access the http 
            request  via `engine.http.request` and the http 
            response via `engine.http.response` and also the 
            request rule which going to invoked by the engine.
            
            But when something goes wrong, the engine will create
            a new HttpResponse instance as error response, at this
            point, everything you done to the `engine.http.response` 
            will all gone. """
        self.request_preprocessor.append(callback)

    def post_request(self, callback):
        """ Register handler as each http request postprocessor.
        
            Like the `pre_request`, you can access the http context,
            and you can access the response buf (which returned by the
            request handler callback) via the `engine.http.response.body`.
            
            But this/these hook(s) will not invoked when something wrong
            (for example, if some exception raised by user callback, or some
            http error occurred.), if you need handle errors, you should 
            do that in `engine.error_page`.

            Remember, if the `buf` is a static file returned by the 
            callback, it is a standard python File-like Object and you 
            should't change that. """
        self.request_postprocessor.append(callback)

    def abort(self, buf):
        """ Abort the current http request process.

            Before you do that, you should set the response status 
            code via `engine.http.response.set_status` if you want a
            specify http status code.
            
            If what you want is an error response, you should raise 
            the `HttpError` exception instead of use this method. """
        raise HttpAbort(buf)

    def wsgi(self, environ, start_response):
        """ WSGI Handler. """

        buf      = self._request_handler(environ)
        response = self._make_output(buf)
        
        start_response(response.status_line, response.header_fields)
        return response.body
        
    def _request_handler(self, environ):
        """ Handle request, init request/response instance and return 
                response buffer. """

        self.content.request = HttpRequest(environ)
        self.content.response = HttpResponse()

        try:

            rule = self.router.match(self.content.request.method, 
                                            self.content.request.path)
            # Pre-processor.
            self.content.rule = rule
            if self.request_preprocessor:
                for processor in self.request_preprocessor:
                    processor()

            _buf = self.content.rule.make_call(self.content.request.path)

            # Post-processor.
            self.content.response.body = _buf
            if self.request_postprocessor:
                for processor in self.request_postprocessor:
                    processor()

            return self.content.response.body

        except HttpAbort:
            context = _errno()
            return context.buf
        # Not Found or Forbidden or http error which raised by ourself.
        except HttpError:
            self.content.response = _errno()
        # Other unexpected error, treat as http error 500.
        #   TODO: Here needs some trackback object.
        except:
            if not self.catch:
                raise
            self.content.response = HttpError(500)
            if self.debug:
                _buf_exc = format_exc()

        # something wrong, which means we got http error response:
        status_code = self.content.response.status_code
        err_handler = self.err_handler.get(int(status_code), None)

        if err_handler:
            try:        
                # We have error handler for this error.
                _buf = self.err_handler[int(status_code)]()
            except:     
                # Error handler raise unexpected error, return default content.
                self.content.response = HttpError(500)
                _buf = _HTTP_ERROR_PAGE_CONTENT
                if self.debug:
                    _buf_exc = format_exc()
        else:           
            # We don't have error handler defined.
            _buf = _HTTP_ERROR_PAGE_CONTENT

        try:
            # when debug is enabled, unexcept error traceback
            #   will override the error handler for http 500.
            return _buf_exc
        except NameError:
            return _buf

    def _make_output(self, buf):
        """ Parse response buf, 
                make sure response instance WSGI compatible. """
        
        request  = self.content.request
        response = self.content.response

        # This is a `HEAD` request.
        if request.method == "HEAD":
            buf = ""

        # Empty (e.g.: If-Modified-Since/HEAD/etc.).
        if buf == "":
            response.body = [u2b(buf)]
            return response

        # This is a static file.
        if hasattr(buf, 'read'):
            if request.file_wrapper:
                response.body = request.file_wrapper(buf)
            else:
                response.body = buf
            return response

        # Normal content.
        response.body = [u2b(buf)]

        return response

        
## Request Router ##
class RequestRouter(object):
    """ The router object for url match/dispatching. """

    def __init__(self):
        """ Create the route table. """
        self.method_table = dict()
        for method in _HTTP_METHOD:
            self.method_table[method] = list()

    def insert(self, methods, regex, callback):
        """ Insert rule into corresponding method table. """

        if not isinstance(methods, list):
            methods = [methods]

        for method in methods:
            method = method.upper()
            if method not in _HTTP_METHOD:
                raise RouterError("Request method %s "
                                        "for callback %s not supported." % 
                                                (method, callback.__name__))
            rule = RequestRule(regex, callback)
            self.method_table[method].append(rule)

    def match(self, method, url):
        """ Match rule with url. """

        for rule in self.method_table[method]:
            if rule.regex.match(url):
                return rule

        # No match found, because `GET` table is the default table,
        #   so we search `GET` table for `HEAD` request.
        if method is 'HEAD':
            return self.match('GET', url)

        # Still not found, search the `ANY` table.
        if method is not 'ANY':
            return self.match('ANY', url)

        # We got nothing, raise 404 error.
        raise HttpError(404)


## Request Rule ##
class RequestRule(object):
    """ Rule object for warp callback function with regex and some metadata. """

    def __init__(self, regex, callback):
        """ Compile regex and prepare callback. """

        self.regex         = re.compile(regex)
        self.handler       = callback
        self.handler_args  = None

        # Gather info about our callback
        spec = getfullargspec(callback)
        if spec.args:
            self.handler_args = spec.args

    def update_args(self, url):
        """ Set the args. """

        if not self.handler_args:
            return dict()

        argv = self.regex.match(url).groups()
        args = dict(zip(self.handler_args, argv))

        return args

    def make_call(self, url):
        """ Invoke callback with args. """
        return self.handler(**self.update_args(url))


## Http Context ##
class HttpContext(object):
    """ ThreadSafe HttpContext (e.g: Request/Response) access. """

    def __init__(self):
        """ Create the thread local object. """
        object.__setattr__(self, "thread_ctx", local())

    def __getattr__(self, name):
        """ Return http context, raise AttributeError if context not exists. """
        try:
            return self.thread_ctx.__dict__[name]
        except KeyError:
            raise AttributeError("%s, no such context" % name)

    def __setattr__(self, name, value):
        """ Associate http context. """
        self.thread_ctx.__dict__[name] = value


## Http Request ##
class HttpRequest(object):
    """ Http Request object, a wrapper of environ dict. """

    __slots__ = ('environ', '_data')

    def __init__(self, environ):
        """ Wrapper the environ dict. """
        self._data = None    
        self.environ = environ

    @property
    def scheme(self):
        """ environ['wsgi.url_scheme'] """
        return self.environ.get('wsgi.url_scheme', "http")

    @property
    def protocol_version(self):
        """ environ['SERVER_PROTOCOL'] """
        return self.environ.get('SERVER_PROTOCOL', "HTTP/1.1")

    @property
    def server_name(self):
        """ environ['SERVER_NAME'] """
        return self.environ.get('SERVER_NAME', "").lower()

    @property
    def server_port(self):
        """ environ['SERVER_PORT'] """
        return self.environ.get('SERVER_PORT', _HTTP_PORT)

    @property
    def method(self):
        """ environ['REQUEST_METHOD'] """
        return self.environ.get('REQUEST_METHOD', "GET").upper()

    @property
    def script_name(self):
        """ environ['SCRIPT_NAME'] """
        script_name = self.environ.get('SCRIPT_NAME', "").strip("/") 
        if not script_name:
            return None
        else:
            return "/" + script_name + "/"

    @property
    def path(self):
        """ environ['PATH_INFO'] """
        url_path = self.environ.get('PATH_INFO', "").strip("/")
        if not url_path:
            return "/"
        else:
            return "/" + url_path

    @property
    def query_string(self):
        """ environ['QUERY_STRING'] """
        return self.environ.get('QUERY_STRING', "")

    ## Http Request Headers Access ##
    def _environ_header_key(self, request_header):
        """ Make the header indexable in environ dict 
                by add `HTTP_` prefix and replace `-` with `_`. """

        request_header = request_header.upper()
        # These headers without the "HTTP_" prefix: #
        non_prefix_headers = ("CONTENT-TYPE", "CONTENT-LENGTH")

        if request_header in non_prefix_headers:
            return request_header.replace("-", "_")
        else:
            return "HTTP_" + request_header.replace("-", "_")

    def has_header(self, request_header):
        """ Header exists test. """
        return self._environ_header_key(request_header) in environ.keys()

    def get_header(self, request_header):
        """ Get value of header, raise AttributeError if header doesn't 
                exists in environ. """
        try:
            return self.environ[self._environ_header_key(request_header)]
        except KeyError:
            raise AttributeError("Request header: %s not found in request" %
                                                                request_header)

    ## Process or Thread ##
    @property
    def is_multithread(self):
        """ Return True if Server is multithreaded. """
        return self.environ.get('wsgi.multithread', False)

    @property
    def is_multiporcess(self):
        """ Return True if Server is multiprocess. """
        return self.environ.get('wsgi.multiprocess', False)

    ## Server file wrapper ##
    @property
    def file_wrapper(self):
        """ Return wsgi.file_wrapper function or return None if server not 
                support file_wrapper. """
        return self.environ.get('wsgi.file_wrapper', None)

    ## User post data ##
    @property
    def data(self):
        """ Read all request data at once. """

        if self._data:
            return self._data

        content_type = self.get_header("content-type")
        content_length = self.get_header("content-length")
        content_data_fp = self.environ.get('wsgi.input', None)
        if not content_data_fp:
            return "" 

        # TODO: Still need handle content-type here, 
        #   and Http Transfer-Encoding/Chunked support here.
        if not content_length:
            content_length = 0

        self._data = b2u(content_data_fp.read(int(content_length)))
        return self._data

    @property
    def json(self):
        """ Dump request data (which should be json here) 
                into standard python dict. """
        try:
            return json.loads(self.data)
        except:
            return {}

    ## User query data ##
    @property
    def qs(self):
        """ Parse user query string into stardand python dict. """
        return parse_qs(self.query_string)


## Http Response ##
class HttpResponse(object):
    """ Http Response object, everything about http response. """

    default_content_type = "text/html; charset=UTF-8"

    def __init__(self, status=200, body=""):
        """ Init Http Response with default attributes. """
        self.status  = status
        self.headers = dict()
        self.body    = body

    @property
    def status_code(self):
        """ Http Response status code. """
        return self.status

    @property
    def status_line(self):
        """ Build/Return a http `Status-Line`. """
        try:
            return "%d %s" % (self.status, _HTTP_STATUS[self.status])
        except KeyError:
            return "%d Unknown Status" % self.status

    @property
    def header_fields(self):
        """ WSGI compatible list contain all response header fields. """

        header_fields = []
        if "Content-Type" not in self.headers.keys():
            header_fields.append(("Context-Type", self.default_content_type))

        for name, values in self.headers.items():
            for value in values:
                header_fields.append((name, str(value)))
        return header_fields

    def set_status(self, status_code):
        """ Set current status code to status_code. """
        try:
            self.status = int(status_code)
        except ValueError:
            err = _errno()
            err.message = "Bad Status Code %s" % status_code
            raise err

    def get_header(self, name):
        """ Return a response header's value 
                or return None if no such header. """
        try:
            return self.headers[name]
        except KeyError:
            return None

    def add_header(self, name, value):
        """ Add a response header to response 
                but doesn't check for duplicates. """
        if name not in self.headers.keys():
            self.headers[name] = []
        self.headers[name].append(value)

    def set_header(self, name, value):
        """ Create or replacing an exists header's value. """
        self.headers[name] = [value]


## Http Error Rsponse ##
class HttpError(HttpResponse, VanillaError):
    """ Http error response. """

    def __init__(self, status=500, body=""):
        super(HttpError, self).__init__(status, body)

