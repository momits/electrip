#!/usr/bin/env python3
# -*- coding: UTF 8 -*-
import subprocess
import os
import argparse

from electrip.constants import APP_ID

PATH = os.path.dirname(os.path.realpath(__file__))

LOCALE_PATH = os.path.join(PATH, "locale")

translation_domains = {
    APP_ID + '-main': '{__main__,electrip}.py',
    APP_ID + '-configuration': '{configuration_ui,config/{loco,json_model,vocab}}.py',
    APP_ID + '-control': 'control_ui.py'
}

po_paths = [os.path.join(LOCALE_PATH, l, 'LC_MESSAGES')
            for l in next(os.walk(LOCALE_PATH))[1]]


def _compile():
    for po_path in po_paths:
        for domain in translation_domains.keys():
            msgfmt_cmd = 'msgfmt {} -o {}'.format(os.path.join(po_path, domain + '.po'),
                                                  os.path.join(po_path, domain + '.mo'))
            subprocess.call(msgfmt_cmd, shell=True)


def _extract():
    for (domain, src_files) in translation_domains.items():
        xgettext_cmd = 'xgettext -L Python -d {} -o {} {}'\
            .format(domain,
                    os.path.join(LOCALE_PATH, domain + '.pot'),
                    os.path.join(PATH, src_files))
        subprocess.call(xgettext_cmd, shell=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['compile', 'extract'])
    args = parser.parse_args()
    if args.action == 'compile':
        _compile()
    elif args.action == 'extract':
        _extract()
    else:
        raise RuntimeError("Argument must either be 'compile' or 'extract'.")


if __name__ == '__main__':
    main()
