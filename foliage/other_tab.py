'''
other_tab.py: implementation of the "Other" tab

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait
from   decouple import config
from   pywebio.input import input, select, checkbox, radio
from   pywebio.input import NUMBER, TEXT, input_update, input_group
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import toast, popup, close_popup, put_buttons, put_button, put_error
from   pywebio.output import use_scope, set_scope, clear, remove, put_warning
from   pywebio.output import put_success, put_info, put_table, put_grid, span
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code, put_link
from   pywebio.output import put_processbar, set_processbar, put_loading
from   pywebio.output import put_column
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   sidetrack import set_debug, log
import threading
import webbrowser

from   .base_tab import FoliageTab
from   .credentials import credentials_from_user, current_credentials
from   .credentials import use_credentials
from   .folio import Folio, RecordKind, RecordIdKind, TypeKind, NAME_KEYS
from   .ui import quit_app, reload_page, confirm, notify
from   .ui import image_data, user_file, JS_CODE, CSS_CODE
from   .ui import note_info, note_warn, note_error, tell_success, tell_failure


# Tab definition class.
# .............................................................................

class OtherTab(FoliageTab):
    def contents(self):
        return {'title': 'Other', 'content': tab_contents()}

    def pin_watchers(self):
        return {}


# Tab creation function.
# .............................................................................

def tab_contents():
    log(f'generating other tab contents')
    return [
        put_grid([[
            put_markdown('Foliage stores the FOLIO credentials you provide the'
                         + ' first time it runs, so that you don\'t have to'
                         + ' enter them again. Click this button to update the'
                         + ' stored credentials.'),
            put_button('Edit credentials', onclick = lambda: edit_credentials(),
                       ).style('margin-left: 20px; text-align: left'),
        ], [
            put_markdown('Before performing destructive operations, Foliage'
                         + ' saves copies of the records as they exist before'
                         + ' modification. Click this button to open the folder'
                         + ' containing the files. (Note: a given record may'
                         + ' have multiple backups with different time stamps.)'),
            put_button('Show backups', onclick = lambda: show_backup_dir(),
                       ).style('margin-left: 20px; margin-top: 0.8em'),
        ], [
            put_markdown('The debug log file contains a detailed trace of'
                         + ' every action that Foliage takes. This can be'
                         + ' useful when trying to resolve bugs and other'
                         + ' problems.'),
            put_button('Show log file', onclick = lambda: show_log_file(),
                       ).style('margin-left: 20px; text-align: left'),
        ]], cell_widths = 'auto 170px', cell_heights = '29% 42% 29%'),
    ]


# Miscellaneous helper functions.
# .............................................................................

def edit_credentials():
    log(f'user invoked Edit credentials')
    current = current_credentials()
    creds = credentials_from_user(warn_empty = False, initial_creds = current)
    if creds != current:
        log(f'user has provided updated credentials')
        use_credentials(creds)
    else:
        log(f'credentials unchanged')


def show_backup_dir():
    log(f'user invoked Show backup dir')
    webbrowser.open_new("file://" + config('BACKUP_DIR'))


def show_log_file():
    log(f'user invoked Show log file')
    log_file = config('LOG_FILE')
    if log_file == '-':
        note_warn('No log file -- log output is being directed to the terminal.')
        return
    elif log_file and exists(log_file):
        if readable(log_file):
            webbrowser.open_new("file://" + log_file)
        else:
            note_error(f'Log file is unreadable -- please report this error.')
