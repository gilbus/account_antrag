#!/usr/bin/env python3
"""
Builds all templates of the accountAntrag application as specified in the config file.

A template file called ``$file.*`` will be rendered and written to ``$file.$lang.html``.
"""

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, FileType
from typing import TextIO, Dict, Any, Set
from pathlib import Path

try:
    from toml import loads, TomlDecodeError  # type: ignore
    from jinja2 import Template, Environment, FileSystemLoader, TemplateSyntaxError
except ImportError as e:
    print("{}. The package name is usually python(3?)-<module>.".format(e))
    exit(1)

__author__ = "tl"
__license__ = "AGPL v3"

# path relative to project root, simply call all scripts from that location, since
# the paths inside the config are relativ to it as well
develop_config_file = Path("etc/develop_config.toml")
production_config_file = Path("/etc/config.toml")
config = None


def toml_loads_with_warning(fp: TextIO) -> Dict[str, Any]:
    try:
        return loads(fp.read())
    except TomlDecodeError as e:
        print("Error during TOML parsing of {!r}: {!r}".format(fp.name, e))
        print("Consider using `https://www.tomllint.com/` to find the error.")
        raise


def main(config: Dict[str, Any]) -> int:
    parser = ArgumentParser(
        epilog="{} @ {}".format(__license__, __author__),
        formatter_class=ArgumentDefaultsHelpFormatter,
        description=__doc__,
    )

    parser.add_argument(
        "-t",
        "--template-dir",
        type=str,
        help="""Directory to contain template files which will be rendered with the
        given translations""",
        default=config["build"]["template_dir"],
    )
    parser.add_argument(
        "-i",
        "--i18n",
        type=FileType(),
        help="TOML file containing internationalization strings.",
        default=config["build"]["i18n_file"],
    )

    parser.add_argument(
        "-l",
        "--language",
        help="""A subset of the supported languages of the i18n file. Per default all
        supported languages are rendered.""",
        default="all",
        nargs="+",
    )

    parser.add_argument(
        "-o", "--output", help="Output directory", default=config["build"]["www_dir"]
    )

    args = parser.parse_args()

    try:
        i18n = toml_loads_with_warning(args.i18n)
    except TomlDecodeError:
        return 1

    selected_languages = set()  # type: Set[str]
    try:
        if args.language == "all":
            selected_languages = set(i18n["supported"])
        else:
            for language in args.language:
                if language not in i18n["supported"]:
                    print(
                        "Requested language {} not supported by i18n file. Ignoring".format(
                            language
                        )
                    )
                    continue
                selected_languages.add(language)
    except (KeyError, TypeError):
        print("i18n file misses array of supported languages.")
        return 1

    if not i18n.get("fallback", ""):
        print("i18n file `fallback` not set or empty.")
        return 1
    else:
        fallback_languange = i18n["fallback"]

    translations = {
        key: translations
        for key, translations in i18n.items()
        if isinstance(translations, dict)
    }

    for key, entry in translations.items():
        if not entry.get(fallback_languange, ""):
            print(
                "Key {!r} misses fallback translation ({}).".format(
                    key, fallback_languange
                )
            )
            return 1

    def translate(key: str) -> str:
        # `language` will be set by our for loop
        try:
            entry = translations[key]
        except KeyError:
            raise ValueError("Unknown translation {!r} requested. Aborting".format(key))
        if not entry.get(language, ""):
            print("Using fallback entry for translation {!r}".format(key))
            return entry[fallback_languange]
        return entry[language]

    jinja_environment = Environment(loader=FileSystemLoader(args.template_dir))

    # add translation function to render engine
    jinja_environment.globals["_"] = translate

    try:
        tf_arguments = {
            "types": config["type"],
            "institutes": config["build"]["institutes"],
        }
    except KeyError as e:
        print("Config file contains no entries for {}. Aborting".format(e.args))
        return 1

    if not config["build"].get("cgi_url", ""):
        print("Config file does not contain url to CGI script. Aborting")
        return 1
    if not config["build"].get("application_url", ""):
        print("Config file does not contain url to main application page. Aborting")
        return 1

    # create the output directory
    output_dir = Path(args.output)
    try:
        output_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    except (FileNotFoundError, PermissionError) as e:
        print(
            "Could not create output directory `{}` due to the following error: {}".format(
                output_dir, e
            )
        )
        return 1

    for template_file in jinja_environment.list_templates():
        for language in selected_languages:
            output_path = "{dir}/{file}.{lang}.html".format(
                dir=args.output, file=template_file.split(".")[0], lang=language
            )
            print(
                "Rendering {} with language {} and writing to {}".format(
                    template_file, language, output_path
                )
            )
            try:
                with open(output_path, "w") as file:
                    file.write(
                        jinja_environment.get_template(template_file).render(
                            tf_arguments,
                            language=language,
                            supported_languages=i18n["supported"],
                            cgi_url=config["build"]["cgi_url"],
                            application_url=config["build"]["application_url"],
                        )
                    )
            except (FileNotFoundError, PermissionError) as e:
                print(
                    "Could not save `{}` due to the following error: {}".format(
                        output_path, e
                    )
                )
                return 1
            except TemplateSyntaxError as e:
                print(
                    "The template contains a syntax error at line {}: {}".format(
                        e.lineno, e.message
                    ),
                    "Aborting",
                )
                return 1

    return 0


if __name__ == "__main__":
    try:
        if develop_config_file.exists():
            config = toml_loads_with_warning(develop_config_file.open())  # type:ignore
            print("Using development config")
        elif production_config_file.exists():
            config = toml_loads_with_warning(  # type: ignore
                production_config_file.open()
            )
    except TomlDecodeError:
        exit(1)
    if not config:
        print(
            "Cannot load develop ({}) nor production config ({}). Aborting".format(
                develop_config_file, production_config_file
            )
        )
        exit(1)
    try:
        exit(main(config))
    except KeyError as e:
        print("Loaded config misses option [build][{}]. Aborting".format(*e.args))
        exit(1)
