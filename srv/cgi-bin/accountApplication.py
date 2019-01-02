#!/usr/bin/env python3.7
"""
This is no ordinary python wsgi application but expected to be called as a cgi script,
therefore the wrapper around the main-call. It expects to receive the form-encoded data
of the account application page via POST. No other protocol is supported and will raise
an appropriate error.

Formatting has been done automatically by black ( https://github.com/ambv/black )
"""

import cgi
from wsgiref.handlers import CGIHandler
from pathlib import Path
from collections import ChainMap, defaultdict
from datetime import datetime
from string import Template
from fcntl import lockf, LOCK_EX
from typing import Dict, Callable, List, Tuple, Iterable, Any
from sys import exc_info
from http import HTTPStatus
import logging
from logging.handlers import RotatingFileHandler


# should be installed since already needed to render the templates
import toml  # type: ignore

# type alias for optional type signatures
WsgiResponseFunction = Callable[[str, List[Tuple[str, str]]], Callable[[bytes], None]]
# dictionary to access string form of needed status codes
status_dict = {
    status.value: "{status.value} {status.phrase}".format(status=status)
    for status in [
        HTTPStatus.SEE_OTHER,
        HTTPStatus.OK,
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.METHOD_NOT_ALLOWED,
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    ]
}

# relative path inside development environment
# not relative to project root but file itself since called via cgi
develop_config_file = (
    Path(__file__).absolute().parent.parent.parent / "etc" / "develop_config.toml"
)
production_config_file = Path("/etc/config.toml")

# this is really just a backup config and should never be used in production
# so in case of changes perform them inside the production config file and not here
default_output_config = {
    "mode": "append",
    "logfile": "",
    "file": "",
    "timestamp_format": "%Y-%m-%d %H:%M:%S.%f",
    "template": """\

""",
    # string to insert in case of no submitted value
    "fallback": "invalid",
}

default_cgi_config = {"blacklist_chars": ["\\", "$", "`"], "max_content_length": 500}

# a chainmap takes multiple dictionaries and on lookup iterates over them until an entry
# is found, makes it possible to put the default config at the lowest level and the
# loaded config on top of it

config = ChainMap(default_output_config)
cgi_config = ChainMap(default_cgi_config)

try:
    if develop_config_file.exists():
        develop_config = toml.loads(develop_config_file.read_text())
        config.maps.insert(0, develop_config["output"])
        cgi_config.maps.insert(0, develop_config["cgi"])
    elif production_config_file.exists():
        production_config = toml.loads(production_config.read_text())
        config.maps.insert(0, production_config["output"])
        cgi_config.maps.insert(0, production_config["cgi"])
except Exception:
    # bad style to ignore any exception but this script must not fail under any
    # circumstance and that's why we have a default config
    pass

rotating_logfile_handler = RotatingFileHandler(
    filename=config["logfile"],
    # max size 5 MiB
    maxBytes=5 * 1024 ** 3,
    backupCount=5,
)
default_log_level = (
    logging.DEBUG if (Path(__file__).parent / "DEBUG").exists() else logging.INFO
)
# see https://docs.python.org/3/library/logging.html#logrecord-attributes
_logging_format = "%(asctime)s:%(levelname)s:%(message)s"
# see https://docs.python.org/3/library/time.html?highlight=strftime#time.strftime
_date_format = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(
    handlers=[rotating_logfile_handler],
    level=default_log_level,
    format=_logging_format,
    datefmt=_date_format,
)

logging.debug("Running with following output config: %s", config)
logging.debug("Running with following cgi config: %s", cgi_config)

# most sensible default value
used_language = "de"


def account_app(
    environ: Dict[str, Any], start_response: WsgiResponseFunction
) -> Iterable[bytes]:
    """
    The actual app. Processes the passed data, populates the template and writes them to
    the correct file. In case of question concerning the logic ask cl and dl.
    :param environ: The passed environment containing all data passed by the web server.
    :param start_response: Function to call to send a response back to the client. See
    `https://www.python.org/dev/peps/pep-0333/#specification-details` for more
    information.
    """
    # we do only accept POST requests
    if environ["REQUEST_METHOD"] != "POST":
        logging.warning("Received invalid non-POST Request. Send 405 Response")
        start_response(status_dict[405], [("Allow", "POST")])
        return []
    if int(environ["CONTENT_LENGTH"]) > cgi_config["max_content_length"]:
        logging.error(
            "Received content_length larger than configured value (%s). "
            "Send 413 header.",
            cgi["max_content_length"],
        )
        start_response(status_dict[413], [])
        return []
    logging.debug("Running in following environment: %s", environ)
    form = cgi.FieldStorage(environ=environ)
    logging.debug("Received form fields: %s", form)
    ag = None
    # application is a student
    if "stud" in form.getfirst("applicationType", ""):
        ag = "stud"
    else:
        ag = form.getfirst("institute")

    # if this is empty something definitely went wrong
    if not ag:
        logging.error("Invalid request, no valid `ag` could be derived. Returning 400")
        start_response(status_dict[400], [])
        return [b"applicationType is not stud and no institute is set"]

    # needed to determine correct language for success or maybe error pages
    global used_language
    used_language = form.getfirst("applicationLanguage", "en")

    now = datetime.now()

    non_form_fields = {"timestamp": now.strftime(config["timestamp_format"]), "ag": ag}

    # in the unlikely case of multiple submitted values only take the first occurrence
    # the data could have been sent from anywhere...
    form_fields = {key: str(form.getfirst(key)) for key in form.keys()}
    # use a dictionary with a callable providing a default/fallback value in case no
    # value is available for a specific key
    fields = defaultdict(lambda: config["fallback"])  # type: Dict[str, str]
    # add content of other dictionaries
    fields.update({**form_fields, **non_form_fields})
    # remove any blacklisted chars from any fields
    for key, value in fields.items():
        if type(value) is str:
            for char in cgi_config["blacklist_chars"]:
                value = value.replace(char, "")
        fields[key] = value

    logging.debug("Using following fields to fill the template: %s", fields)

    output_template = Template(config["template"])

    # safe_substitute does not raise an error on missing substitutions, path should be
    # valid nevertheless and that's what's most important
    output_path = Template(config["file"]).safe_substitute(fields)

    # create path to a lock file from the file to write to
    lock_file = "/tmp/{}.lock".format(output_path.split("/")[-1])

    with open(lock_file, "w") as lock_file_handle:
        # try to acquire an exclusive lock which will block until it is acquired
        lockf(lock_file_handle, LOCK_EX)
        with open(output_path, "w" if config["mode"] == "write" else "a") as file:
            file.write(output_template.substitute(fields))

    # takes a status message and list of headers
    start_response(
        status_dict[303], [("Location", "/success.{}.html".format(used_language))]
    )
    # return empty body
    return []


if __name__ == "__main__":

    def wrapper(environ, start_response):
        """
        Wrapper function to be able to catch any exception which the application might
        raise.
        """
        try:
            return account_app(environ, start_response)
        except Exception:
            # log error
            logging.exception("Unexpected exception with environment %s", environ)
            start_response(
                status_dict[303], [("Location", "/error.{}.html".format(used_language))]
            )
            # return empty body
            return []

    CGIHandler().run(wrapper)
