# **UNMAINTAINED**

This repository is an excerpt of my work as System Administrator for the Faculty of
Technology, Bielefeld University. Specific details have been removed and therefore this
software is not functional as is.

# Account Antrag Applikation

Eine Ablösung für alte Python 2-Skripte, welche ein kleines Chaos waren und
bedingt durch Python 2 ab 2020 keine Sicherheitsupdates mehr bekommen.

Die Idee ist soviel wie möglich statisch zu bauen und so wenig Javascript/CGI wie
möglich zu verwenden. Weitere Vorteile:

- Nur noch eine einzelne Seite, welche bei Bedarf Formulare für weitere Informationen
  einblendet
- HTML-Templates welche mit den verschiedenen Übersetzungen gefüllt werden und nicht
  mehr einzeln gewartet werden müssen
- Leichtere Übersetzung
- Leichtere Erweiterbarkeit, wenn zB ein neues Feld oder eine neue AG dazu kommen sollte

## Konfigurations-Dateien

Alle Skripte versuchen zuerst eine Development-Config `etc/develop_config.toml` relativ
zu ihrem Pfad innerhalb des Projektes zu laden und anschließend eine Produktions-Config
von einem absoluten Pfad.

## Templates

Die HTML-Templates sind Jinja2-Templates und bauen aktuell 3 Seiten:

- Die Accountantrag-Seite, auf welcher neue Benutzer einen Account beantragen können
- Eine Success-Seite, auf welche der Nutzer weitergeleitet wird
- Eine Error-Seite, welche im Fall von Fehlern gezeigt wird

## Internalization (I18N)

Die Datei `i18n.toml` enthält alle Übersetzungen, welche in den Templates referenziert
werden, wobei der Name innerhalb der eckigen Klammern den Schlüssel für die Templates
darstellt.

## Bauen der Templates

 Erfolgt durch das `build-accountApplication`-Skript

```
usage: build-accountApplication-index.py [-h] [-t TEMPLATE_DIR] [-i I18N]
                                         [-l LANGUAGE [LANGUAGE ...]]
                                         [-o OUTPUT]

Builds all templates of the accountAntrag application as specified in the
config file. A template file called ``$file.*`` will be rendered and written
to ``$file.$lang.html``.

optional arguments:
  -h, --help            show this help message and exit
  -t TEMPLATE_DIR, --template-dir TEMPLATE_DIR
                        Directory to contain template files which will be
                        rendered with the given translations (default:
                        share/templates)
  -i I18N, --i18n I18N  TOML file containing internationalization strings.
                        (default: share/i18n.toml)
  -l LANGUAGE [LANGUAGE ...], --language LANGUAGE [LANGUAGE ...]
                        A subset of the supported languages of the i18n file.
                        Per default all supported languages are rendered.
                        (default: all)
  -o OUTPUT, --output OUTPUT
                        Output directory (default: srv)

AGPL v3 @ tl
```

Alle wichtigen Einstellungen finden sich innerhalb der o.g. Konfigurationseinstellungen,
zB alle existierenden Arbeitsgruppen oder verschiedene Typen von Studenten (Techfak,
Nicht-Techfak, etc.)

## CGI

Das CGI-Skript unter `srv/cgi-bin/accountApplication.py` muss via entsprechender Apache
oder nginx-Config zur Verfügung gestellt werden, die URL kann in der Konfigurationsdatei
eingestellt werden.

Die Konfigurationsdateien enthalten ein Ausgabetemplate, welches mit den Werten des
übermittelten HTML-Formulars befüllt wird und, abhängig von der Konfiguration, entweder
in eine neue Datei geschrieben oder an eine existierende angehangen wird. Damit im
letzteren Fall die Datei von parallelen Threads nicht korrumpiert gibt es für jede
einzelne Datei einen Locking-Mechanismus, welcher mit Hilfe von OS-Mitteln realisiert
ist, also keine Eigenentwicklung innerhalb von Python.

Der Pfad zu einer automatisch rotierenden Logdatei kann ebenfalls via Konfiguration
angegeben werden, das Standard-Level ist INFO. Dieses kann auf DEBUG gesetzt werden,
indem *neben* dem CGI-Skript eine Datei mit dem Name `DEBUG` erstellt wird, z.B. `touch
srv/cgi-bin/DEBUG`

# Lokale Entwicklung

`etc/lighttpd.conf.in` stellt ein Template für eine `lighttpd`-Konfigurationsdatei
bereit, welches mit folgendem Kommando an die lokale Umgebung angepasst werden kann:
```bash
sed -e "s&%PROJECT_ROOT%&$(pwd)&g" -e "s&%USER%&${USER}&g" etc/lighttpd.conf.in > etc/lighttpd.conf
```
Die absoluten Pfade hierbei **sind notwendig**.
Die gebauten HTML-Seiten sind **nicht** innerhalb von `git`, weshalb diese vor der
ersten Verwendung gebaut werden müssen via `bin/build-accountApplication-index.py`.
Anschließend kann in dem Projekt-Verzeichnis ein `lighttpd` daemon im Vordergrund
gestartet werden: `lighttpd -f etc/lighttpd.conf -D` und die Seite unter
`http://localhost:8080` betrachtet werden.

# Deployment

Falls die Ordnerstruktur in der Produktion abgeändert werden sollte bitte die lokale
Entwicklungsumgebung intakt lassen und ggf die Ordner auf dem Produktiv-System
umbenennen, sodass die Pfade aus `etc/config.toml` korrekt sind
