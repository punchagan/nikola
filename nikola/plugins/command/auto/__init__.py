# -*- coding: utf-8 -*-

# Copyright © 2012-2017 Roberto Alsina and others.

# Permission is hereby granted, free of charge, to any
# person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice
# shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
# OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Automatic rebuilds for Nikola."""

from __future__ import print_function

import os
import subprocess
try:
    from urlparse import urlparse
    from urllib2 import unquote
except ImportError:
    from urllib.parse import urlparse, unquote  # NOQA
import pkg_resources

try:
    from livereload import Server, shell
except ImportError:
    Server = shell = None

from nikola.plugin_categories import Command
from nikola.utils import dns_sd, req_missing, get_logger, get_theme_path, STDERR_HANDLER


class CommandAuto(Command):
    """Automatic rebuilds for Nikola."""

    name = "auto"
    logger = None
    has_server = True
    doc_purpose = "builds and serves a site; automatically detects site changes, rebuilds, and optionally refreshes a browser"
    dns_sd = None

    cmd_options = [
        {
            'name': 'port',
            'short': 'p',
            'long': 'port',
            'default': 8000,
            'type': int,
            'help': 'Port number (default: 8000)',
        },
        {
            'name': 'address',
            'short': 'a',
            'long': 'address',
            'type': str,
            'default': '127.0.0.1',
            'help': 'Address to bind (default: 127.0.0.1 -- localhost)',
        },
        {
            'name': 'browser',
            'short': 'b',
            'long': 'browser',
            'type': bool,
            'help': 'Start a web browser',
            'default': False,
        },
        {
            'name': 'ipv6',
            'short': '6',
            'long': 'ipv6',
            'default': False,
            'type': bool,
            'help': 'Use IPv6',
        },
        {
            'name': 'no-server',
            'long': 'no-server',
            'default': False,
            'type': bool,
            'help': 'Disable the server, automate rebuilds only'
        },
    ]

    def _execute(self, options, args):
        """Start the watcher."""

        self.logger = get_logger('auto', STDERR_HANDLER)

        if Server is None:
            req_missing(['livereload'], 'use the "auto" command')

        self.cmd_arguments = ['nikola', 'build']
        if self.site.configuration_filename != 'conf.py':
            self.cmd_arguments.append('--conf=' + self.site.configuration_filename)

        # Run an initial build so we are up-to-date
        subprocess.call(self.cmd_arguments)

        # Do not duplicate entries -- otherwise, multiple rebuilds are triggered
        watched = set([
            'templates/'
        ] + [get_theme_path(name) for name in self.site.THEMES])
        for item in self.site.config['post_pages']:
            watched.add(os.path.dirname(item[0]))
        for item in self.site.config['FILES_FOLDERS']:
            watched.add(item)
        for item in self.site.config['GALLERY_FOLDERS']:
            watched.add(item)
        for item in self.site.config['LISTINGS_FOLDERS']:
            watched.add(item)
        for item in self.site._plugin_places:
            watched.add(item)

        # Nikola itself (useful for developers)
        watched.add(pkg_resources.resource_filename('nikola', ''))

        # Nikola config file
        config_file = os.path.abspath(self.site.configuration_filename or 'conf.py')
        watched.add(config_file)

        server = Server()

        # Watch input folders and trigger rebuilds
        for path in watched:
            if os.path.exists(path):
                self.logger.debug("Watching {}...".format(path))
                server.watch(path, self.shell())

        # Seems like this was was added because livereload didn't work very
        # well? (Issue #1883) Do we still need this?
        has_server = not options['no-server']
        dhost = '::' if options['ipv6'] else None
        host = options['address'].strip('[').strip(']') or dhost
        # FIXME: Using None for port is a hack
        port = options.get('port') if has_server else None
        open_url = has_server and options['browser']

        if port is not None:
            self.dns_sd = dns_sd(port, (options['ipv6'] or '::' in host))

        server.serve(host=host, port=port, open_url=open_url, root='output')

        if self.dns_sd is not None:
            self.dns_sd.Reset()

    def shell(self):
        run_shell = shell(self.cmd_arguments)

        def run_shell_logged(*args, **kwargs):
            self.logger.info('REBUILDING ...')
            self.logger.info(str(args) + str(kwargs))
            return run_shell()

        return run_shell_logged
